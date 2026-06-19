"""GracyBot Pipeline — 洋葱模型管道调度器

Pipeline 是消息处理的核心，4 个 Stage 顺序执行：

    1. SecurityFilter  — 频率限制、黑名单、输入验证
    2. BuiltinCommands — 内置命令（/帮助、/状态 等）
    3. CommandMatcher  — TOML + @on_command 命令匹配
    4. PluginHandler   — 权限校验、插件执行、计时、审计
    5. ResponseSender  — 消息发送

每个 Stage 可返回 None 短路后续 Stage。

用法:
    # Runtime 创建时自动构造 Pipeline，无需手动管理
    pipeline = Pipeline()
    pipeline.add_stage(...)
    await pipeline.process(event)
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import List, Optional

from core.gracy_adapter.event import GracyEvent
from core.decorators.context import PluginContext
from core.runtime import RuntimeContext as _RuntimeContext

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
        # 从 RuntimeContext 获取当前消息来源的 Runtime
        runtime = _RuntimeContext.get()
        if runtime is None:
            _logger.warning("[Pipeline] 无可用的 Runtime 上下文，跳过处理")
            return

        # 构建 PluginContext，传入 runtime
        ctx = PluginContext(
            sender_id=str(event.sender_id),
            target_id=str(event.target_id),
            chat_type=str(event.chat_type),
            nickname=str(event.nickname or "用户"),
            raw_text=str(event.raw_text),
            is_at_bot=bool(event.is_at_bot),
            raw_data=event.raw_data,
            runtime=runtime,
        )

        for stage in self._stages:
            result = await stage.process(ctx)
            if result is None:  # 短路
                _logger.debug(f"[Pipeline] {stage.__class__.__name__} 短路")
                return


__all__ = [
    "Stage",
    "Pipeline",
    # 以下 stages 保留别名方便导入
    "SecurityFilter",
    "BuiltinCommands",
    "CommandMatcher",
    "PluginHandler",
    "ResponseSender",
]
