"""GracyBot 事件总线 — 统一事件分发层

所有消息（HTTP/WS）统一 publish(GracyEvent)，
EventBus 通过 RuntimeRegistry 查找来源 Runtime，路由到对应 Pipeline。

用法:
    from core.event import event_bus, GracyEvent

    # 发布事件
    await event_bus.publish(gracy_event)

设计：
    - 单例模式，全局共享
    - 收到事件后查 RuntimeRegistry → RuntimeContext.set() → runtime.pipeline.process()
    - 可动态 subscribe / unsubscribe
"""

import asyncio
import logging
from typing import Callable, Dict, List, Optional

from core.gracy_adapter.event import GracyEvent

_logger = logging.getLogger("GracyEvent")


class EventBus:
    """异步事件总线

    支持两种派发模式：
        1. subscribe() — 灵活的订阅机制，每个 event_type 可绑定多个处理器
        2. publish() → RuntimeRegistry → RuntimeContext → runtime.pipeline
    """

    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._running = False

    # ── 订阅管理 ──

    def subscribe(self, event_type: str, handler: Callable) -> None:
        """订阅事件类型"""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
        _logger.debug(f"[EventBus] 订阅 {event_type}: {handler.__name__}")

    def unsubscribe(self, event_type: str, handler: Callable) -> None:
        """取消订阅"""
        handlers = self._subscribers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)
            _logger.debug(f"[EventBus] 取消订阅 {event_type}: {handler.__name__}")

    # ── 事件发布 ──

    async def publish(self, event: GracyEvent) -> None:
        """发布事件（异步派发，不阻塞调用方）

        1. 通知所有 subscribe 的监听器（兼容旧接口）
        2. 通过 RuntimeRegistry 查找来源 Runtime，路由到对应 Pipeline
        """
        event_type = event.chat_type  # "private" | "group"

        # 路径 A：订阅者通知
        for handler in self._subscribers.get(event_type, []):
            asyncio.create_task(self._safe_call(handler, event))
        for handler in self._subscribers.get("*", []):
            asyncio.create_task(self._safe_call(handler, event))

        # 路径 B：通过 RuntimeRegistry 路由到对应 Runtime 的 Pipeline
        from core.runtime import RuntimeRegistry, RuntimeContext

        runtime = None
        if event.source:
            runtime = RuntimeRegistry.get_by_tag(event.source)

        if runtime is None:
            # 回退：取第一个注册的 Runtime
            all_runtimes = RuntimeRegistry.get_all()
            if all_runtimes:
                runtime = all_runtimes[0]
            else:
                _logger.warning(
                    f"[EventBus] 无可用 Runtime 处理事件 "
                    f"(source={event.source}, sender={event.sender_id})"
                )
                return

        # 设置消息链路上下文，然后交给 Runtime 的 Pipeline
        token = RuntimeContext.set(runtime)
        try:
            await runtime.pipeline.process(event)
        finally:
            RuntimeContext.reset(token)

    async def _safe_call(self, handler: Callable, event: GracyEvent) -> None:
        """安全调用 handler，捕获异常防止 Task 崩溃"""
        try:
            result = handler(event)
            if result is not None and hasattr(result, "__await__"):
                await result
        except Exception as e:
            _logger.error(f"[EventBus] handler {handler.__name__} 异常: {e}", exc_info=True)


# ── 全局单例 ──
event_bus = EventBus()


__all__ = [
    "EventBus",
    "event_bus",
    "GracyEvent",
]
