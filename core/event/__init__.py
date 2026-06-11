"""GracyBot 事件总线 — 统一事件分发层

所有消息（HTTP/WS）统一 publish(GracyEvent)，
EventBus 异步分发到 Pipeline 处理。

用法:
    from core.event import event_bus, GracyEvent

    # 发布事件
    await event_bus.publish(gracy_event)

设计：
    - 单例模式，全局共享
    - asyncio.Queue 无锁设计
    - dispatch() 通过 asyncio.create_task 异步派发
    - 可动态 subscribe / unsubscribe
"""

import asyncio
import logging
from typing import Callable, Dict, List, Optional

from core.gracy_adapter.event import GracyEvent
from core.pipeline import pipeline

_logger = logging.getLogger("GracyEvent")


class EventBus:
    """异步事件总线

    支持两种派发模式：
        1. subscribe() — 灵活的订阅机制，每个 event_type 可绑定多个处理器
        2. dispatch() — 直接派发给 pipeline 处理（主要路径）
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
        2. 主路径：交给 pipeline 处理
        """
        event_type = event.chat_type  # "private" | "group"

        # 路径 A：订阅者通知
        for handler in self._subscribers.get(event_type, []):
            asyncio.create_task(self._safe_call(handler, event))

        for handler in self._subscribers.get("*", []):  # 通配符监听器
            asyncio.create_task(self._safe_call(handler, event))

        # 路径 B：主路径 → Pipeline
        asyncio.create_task(pipeline.process(event))

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
