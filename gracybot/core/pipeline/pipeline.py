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

异步上下文管理器用法（推荐）:
    async with Pipeline() as pipeline:
        pipeline.add_stage(SecurityFilter())
        ...
        await pipeline.process(event)
"""

import asyncio
import logging
import time as _time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from gracybot.core.gracy_adapter.event import GracyEvent
from gracybot.core.decorators.context import PluginContext
from gracybot.core.runtime import RuntimeContext as _RuntimeContext

_logger = logging.getLogger("Core.Pipeline")


class PipelineError(Exception):
    pass


class StageExecutionError(PipelineError):
    pass


class StageTimeoutError(PipelineError):
    pass


class StageShortCircuit(PipelineError):
    """Stage 主动短路（信号而非错误）"""
    def __init__(self, reason: str = ""):
        self.reason = reason
        super().__init__(reason)


STAGE_TIMEOUT = 60.0
PIPELINE_TIMEOUT = 120.0


class Stage(ABC):
    """管道阶段基类"""

    timeout: float = STAGE_TIMEOUT
    on_skip: str = "break"

    async def initialize(self) -> None:
        ...

    async def shutdown(self) -> None:
        ...

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
        self._initialized: bool = False
        self._skip_after_on_break: bool = False
        self._circuit_threshold: int = 3
        self._circuit_recovery: float = 30.0
        self._circuit_recovery_max: float = 300.0
        self._circuit_states: Dict[int, Dict[str, Any]] = {}
        self._pipeline_timeout: float = PIPELINE_TIMEOUT

    def add_stage(self, stage: Stage) -> "Pipeline":
        self._stages.append(stage)
        self._initialized = False
        _logger.debug(f"[Pipeline] 注册 Stage: {stage.__class__.__name__}")
        return self

    def insert_stage(self, index: int, stage: Stage) -> "Pipeline":
        self._stages.insert(index, stage)
        self._initialized = False
        _logger.debug(f"[Pipeline] 插入 Stage: {stage.__class__.__name__} @{index}")
        return self

    def remove_stage(self, stage_or_index) -> "Pipeline":
        if isinstance(stage_or_index, int):
            stage = self._stages.pop(stage_or_index)
        else:
            self._stages.remove(stage_or_index)
            stage = stage_or_index
        self._circuit_states.pop(id(stage), None)
        _logger.debug(f"[Pipeline] 移除 Stage: {stage.__class__.__name__}")
        return self

    def clear_stages(self) -> "Pipeline":
        self._stages.clear()
        self._circuit_states.clear()
        self._initialized = False
        _logger.debug("[Pipeline] 清空所有 Stage")
        return self

    async def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        for stage in self._stages:
            try:
                await stage.initialize()
            except Exception as e:
                _logger.error(
                    f"[Pipeline] Stage {stage.__class__.__name__} "
                    f"初始化失败: {e}", exc_info=True,
                )
                raise StageExecutionError(
                    f"Stage {stage.__class__.__name__} 初始化失败"
                ) from e
        self._initialized = True

    async def initialize(self) -> None:
        await self._ensure_initialized()

    async def shutdown(self) -> None:
        for stage in self._stages:
            try:
                await stage.shutdown()
            except Exception as e:
                _logger.error(
                    f"[Pipeline] Stage {stage.__class__.__name__} "
                    f"关闭异常: {e}", exc_info=True,
                )
        self._initialized = False

    async def __aenter__(self) -> "Pipeline":
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.shutdown()

    async def before_stage(self, stage: Stage, ctx: PluginContext) -> Optional[PluginContext]:
        """返回 None 则短路该 Stage"""
        return ctx

    async def after_stage(self, stage: Stage, ctx: PluginContext) -> None:
        """洋葱模型钩子：在每个 Stage 执行后调用

        子类可覆盖以实现后处理、日志、监控等。
        """
        ...

    def _is_circuit_open(self, stage: Stage) -> bool:
        key = id(stage)
        state = self._circuit_states.get(key)
        if state is None:
            return False
        if not state['open']:
            return False
        elapsed = _time.monotonic() - state['time']
        if elapsed >= state['recovery']:
            state['half_open'] = True
            return False
        return True

    def _record_failure(self, stage: Stage) -> None:
        key = id(stage)
        name = stage.__class__.__name__
        state = self._circuit_states.setdefault(key, {
            'failures': 0, 'time': 0.0, 'open': False,
            'half_open': False, 'recovery': self._circuit_recovery,
        })
        state['time'] = _time.monotonic()

        if state['half_open']:
            state['open'] = True
            state['half_open'] = False
            state['failures'] += 1
            state['recovery'] = min(state['recovery'] * 2, self._circuit_recovery_max)
            _logger.warning(
                f"[Pipeline] 熔断器半开探针失败，恢复时间提升至 "
                f"{state['recovery']:.0f}s: {name}"
            )
            return

        state['failures'] += 1
        if state['failures'] >= self._circuit_threshold:
            state['open'] = True
            state['recovery'] = self._circuit_recovery
            _logger.warning(
                f"[Pipeline] 熔断器打开: {name} "
                f"({state['failures']}次连续失败)"
            )

    def _record_success(self, stage: Stage) -> None:
        key = id(stage)
        state = self._circuit_states.get(key)
        if state is None:
            return
        if state['half_open']:
            _logger.info(
                f"[Pipeline] 熔断器半开探针成功，已关闭: "
                f"{stage.__class__.__name__}"
            )
        state['failures'] = 0
        state['open'] = False
        state['half_open'] = False
        state['recovery'] = max(self._circuit_recovery, state['recovery'] // 2)

    async def _run_onion(
        self, ctx: PluginContext, index: int,
    ) -> Optional[PluginContext]:
        current_ctx = ctx
        after_stack: List[Stage] = []

        try:
            for i in range(index, len(self._stages)):
                stage = self._stages[i]

                if self._is_circuit_open(stage):
                    _logger.debug(
                        f"[Pipeline] 熔断跳过 "
                        f"{stage.__class__.__name__}"
                    )
                    await self.after_stage(stage, current_ctx)
                    continue

                hook_ctx = await self.before_stage(stage, current_ctx)
                if hook_ctx is None:
                    _logger.debug(
                        f"[Pipeline] before_stage 短路 "
                        f"{stage.__class__.__name__}"
                    )
                    if getattr(stage, 'on_skip', 'break') == 'skip':
                        continue
                    break

                after_stack.append(stage)

                try:
                    result = await asyncio.wait_for(
                        stage.process(current_ctx), timeout=stage.timeout,
                    )
                except asyncio.TimeoutError:
                    _logger.error(
                        f"[Pipeline] Stage {stage.__class__.__name__} "
                        f"超时 ({stage.timeout}s)"
                    )
                    self._record_failure(stage)
                    if self._skip_after_on_break:
                        after_stack.pop()
                    raise StageTimeoutError(
                        f"Stage {stage.__class__.__name__} 超时"
                    ) from None
                except asyncio.CancelledError:
                    _logger.warning(
                        f"[Pipeline] Stage {stage.__class__.__name__} 被取消"
                    )
                    raise
                except StageShortCircuit as e:
                    _logger.debug(
                        f"[Pipeline] Stage {stage.__class__.__name__} "
                        f"短路: {e.reason or '无原因'}"
                    )
                    if self._skip_after_on_break:
                        after_stack.pop()
                    if getattr(stage, 'on_skip', 'break') == 'skip':
                        continue
                    break
                except PipelineError:
                    self._record_failure(stage)
                    if self._skip_after_on_break:
                        after_stack.pop()
                    raise
                except Exception as e:
                    _logger.error(
                        f"[Pipeline] Stage {stage.__class__.__name__} "
                        f"异常: {e}", exc_info=True,
                    )
                    self._record_failure(stage)
                    if self._skip_after_on_break:
                        after_stack.pop()
                    if getattr(stage, 'on_skip', 'break') == 'skip':
                        continue
                    break

                if result is None:
                    _logger.debug(
                        f"[Pipeline] Stage {stage.__class__.__name__} "
                        f"返回 None 短路"
                    )
                    if self._skip_after_on_break:
                        after_stack.pop()
                    if getattr(stage, 'on_skip', 'break') == 'skip':
                        continue
                    break

                self._record_success(stage)
                current_ctx = result
        finally:
            for stage in reversed(after_stack):
                await self.after_stage(stage, current_ctx)

        return current_ctx if after_stack else None

    async def process(self, event: GracyEvent) -> Optional[PluginContext]:
        """处理事件，遍历洋葱模型各层，返回最终上下文"""
        if not event.segments and not event.raw_text:
            _logger.debug("[Pipeline] 空消息事件，跳过 Pipeline 处理")
            return None

        await self._ensure_initialized()

        runtime = _RuntimeContext.get()
        if runtime is None:
            _logger.warning("[Pipeline] 无可用的 Runtime 上下文，跳过处理")
            return None

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

        try:
            return await asyncio.wait_for(self._run_onion(ctx, 0), timeout=self._pipeline_timeout)
        except asyncio.TimeoutError:
            _logger.error(f"[Pipeline] 全局超时 ({self._pipeline_timeout}s)")
            return None
        except StageTimeoutError:
            return None
        finally:
            ctx.extra.clear()
