"""GracyBot Pipeline — 洋葱模型管道调度器

Pipeline 是消息处理的核心，5 个 Stage 顺序执行：

    1. SecurityFilter   — 安全过滤 + 日志记录
    2. BuiltinCommands   — 内置命令（/关机、/重启、/关于 等）
    3. CommandMatcher    — TOML + @on_command 命令匹配
    4. PluginHandler     — 权限校验、插件执行、计时
    5. ResponseSender    — 自动回复 + 兜底分发（LLM 等）

每个 Stage 可返回 None 短路后续 Stage。

用法:
    pipeline = Pipeline()
    pipeline.add_stage(SecurityFilter())
    pipeline.add_stage(BuiltinCommands())
    ...
    await pipeline.process(event)
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import List, Optional

from core.gracy_adapter.event import GracyEvent
from core.decorators.context import PluginContext
from core.runtime import RuntimeContext as _RuntimeContext

_logger = logging.getLogger("Core.Pipeline")


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
        runtime = _RuntimeContext.get()
        if runtime is None:
            _logger.warning("[Pipeline] 无可用的 Runtime 上下文，跳过处理")
            return

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
            if result is None:
                _logger.debug(f"[Pipeline] {stage.__class__.__name__} 短路")
                return


# 导入所有 Stage 实现，方便外部统一导入
from core.pipeline.security_filter import SecurityFilter
from core.pipeline.builtin_commands import BuiltinCommands
from core.pipeline.command_matcher import CommandMatcher
from core.pipeline.plugin_handler import PluginHandler
from core.pipeline.response_sender import ResponseSender


__all__ = [
    "Stage",
    "Pipeline",
    "SecurityFilter",
    "BuiltinCommands",
    "CommandMatcher",
    "PluginHandler",
    "ResponseSender",
]
