"""GracyBot Pipeline — 洋葱模型管道调度器

Pipeline 是消息处理的核心，4 个 Stage 顺序执行：

    1. SecurityFilter  — 频率限制、黑名单、输入验证
    2. CommandMatcher  — TOML + @on_command 命令匹配
    3. PluginHandler   — 权限校验、插件执行、计时、审计
    4. ResponseSender  — 消息发送

每个 Stage 可返回 PluginContext.stop = True 短路后续 Stage。

用法:
    from core.pipeline import pipeline
    await pipeline.process(event)
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import List, Optional

from core.gracy_adapter.event import GracyEvent
from core.decorators.context import PluginContext

_logger = logging.getLogger("GracyPipeline")


class Stage(ABC):
    """管道阶段基类"""

    @abstractmethod
    async def process(self, ctx: PluginContext) -> Optional[PluginContext]:
        """处理上下文

        Args:
            ctx: 插件上下文（上游传入）

        Returns:
            返回 None 表示短路（停止后续 Stage），
            返回 ctx 表示继续传递给下一个 Stage
        """
        ...


class Pipeline:
    """洋葱模型管道调度器"""

    def __init__(self):
        self._stages: List[Stage] = []

    def add_stage(self, stage: Stage) -> "Pipeline":
        """注册阶段（按添加顺序执行）"""
        self._stages.append(stage)
        _logger.debug(f"[Pipeline] 注册 Stage: {stage.__class__.__name__}")
        return self

    async def process(self, event: GracyEvent) -> None:
        """处理事件（遍历所有 Stage，支持短路）"""
        # 从 GracyEvent 构建初始 PluginContext
        from core.plugin_manager import plugin_manager as _pm
        from core.gracy_adapter.pool import adapter_pool
        from core.gracy_adapter.send import current_adapter_tag, current_robot_id, current_master_id

        ctx = PluginContext(
            sender_id=str(event.sender_id),
            target_id=str(event.target_id),
            chat_type=str(event.chat_type),
            nickname=str(event.nickname or "用户"),
            raw_text=str(event.raw_text),
            is_at_bot=bool(event.is_at_bot),
            raw_data=event.raw_data,
            plugin_manager=_pm,
            adapter_tag=event.source,
            pool=adapter_pool,
        )

        # 获取当前消息来源适配器的 robot_id
        _robot_id = ""
        _master_id = ""
        if event.source:
            _adapter = adapter_pool.get(event.source)
            if _adapter:
                _robot_id = str(getattr(_adapter, '_instance_robot_id', ''))
                _master_id = str(getattr(_adapter, '_instance_master_id', ''))

        # 设置上下文变量，供 gracy_send_msg 和各插件无 tag 时自动适配当前实例
        token_tag = current_adapter_tag.set(event.source)
        token_rid = current_robot_id.set(_robot_id)
        token_mid = current_master_id.set(_master_id)

        # 顺序执行 Stage
        try:
            for stage in self._stages:
                result = await stage.process(ctx)
                if result is None:  # 短路
                    _logger.debug(f"[Pipeline] {stage.__class__.__name__} 短路")
                    return
        finally:
            current_adapter_tag.reset(token_tag)
            current_robot_id.reset(token_rid)
            current_master_id.reset(token_mid)


# ── 全局单例（注册默认 4 个 Stage） ──
pipeline = Pipeline()


def _register_default_stages():
    """注册默认的 Pipeline Stage"""
    from core.pipeline.stages import SecurityFilter, BuiltinCommands, CommandMatcher, PluginHandler, ResponseSender
    pipeline.add_stage(SecurityFilter())
    pipeline.add_stage(BuiltinCommands())
    pipeline.add_stage(CommandMatcher())
    pipeline.add_stage(PluginHandler())
    pipeline.add_stage(ResponseSender())


_register_default_stages()


__all__ = [
    "Stage",
    "Pipeline",
    "pipeline",
    "SecurityFilter",
    "BuiltinCommands",
    "CommandMatcher",
    "PluginHandler",
    "ResponseSender",
]
