"""AdapterPool — 适配器实例池

管理所有适配器实例，提供按 tag 注册/注销/查找/发送的能力。

设计原则：
    - 每个适配器实例带 IdentityTag，由调用方在 register() 时注入
    - 发送消息时可指定 tag，否则使用默认适配器
    - 支持动态增删（运行时 register / unregister）
    - 所有操作线程安全（使用 threading.Lock）
"""

import logging
import threading
from typing import Callable, Dict, List, Optional, Tuple

from gracybot.core.gracy_adapter.adapter import GracyAdapter
from gracybot.core.gracy_adapter.event import GracyEvent
from gracybot.core.gracy_adapter.identity import IdentityTag
from gracybot.core.gracy_adapter.message import GracyMsg

_logger = logging.getLogger("Adapter.Pool")


class AdapterPool:
    """适配器实例池

    用法:
        pool = AdapterPool()
        pool.register(http_adapter, IdentityTag("onebot", "主号"))
        pool.register(ws_adapter, IdentityTag("onebot", "小号"))

        # 发送消息
        pool.send("123456", [GracyText("hi")], "private")
        pool.send("123456", [GracyText("hi")], "private", tag=some_tag)

        # 广播
        pool.broadcast("123456", [GracyText("公告")], "group")
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._adapters: Dict[str, Tuple[GracyAdapter, IdentityTag]] = {}
        self._default_key: Optional[str] = None

    # ── 注册 ──

    def register(self, adapter: GracyAdapter, tag: IdentityTag, default: bool = False) -> None:
        """注册一个适配器实例

        Args:
            adapter: 适配器实例
            tag: 身份标签
            default: 是否设为默认适配器（首次注册自动为默认）
        """
        key = tag.identity_key
        with self._lock:
            self._adapters[key] = (adapter, tag)
            if self._default_key is None or default:
                self._default_key = key
            _logger.info(f"[AdapterPool] 注册适配器: {tag.log_tag} (默认={default or self._default_key == key})")

    def unregister(self, tag: IdentityTag) -> bool:
        """注销一个适配器实例"""
        key = tag.identity_key
        with self._lock:
            if key not in self._adapters:
                _logger.warning(f"[AdapterPool] 注销失败: {tag.log_tag} 未注册")
                return False
            del self._adapters[key]
            if self._default_key == key:
                self._default_key = next(iter(self._adapters)) if self._adapters else None
            _logger.info(f"[AdapterPool] 注销适配器: {tag.log_tag}")
            return True

    # ── 查询 ──

    def get(self, tag: IdentityTag) -> Optional[GracyAdapter]:
        """按 tag 获取适配器"""
        key = tag.identity_key
        with self._lock:
            pair = self._adapters.get(key)
            return pair[0] if pair else None

    def get_default(self) -> Optional[GracyAdapter]:
        """获取默认适配器"""
        with self._lock:
            pair = self._adapters.get(self._default_key) if self._default_key else None
            return pair[0] if pair else None

    def get_default_tag(self) -> Optional[IdentityTag]:
        """获取默认适配器的 tag"""
        with self._lock:
            pair = self._adapters.get(self._default_key) if self._default_key else None
            return pair[1] if pair else None

    def get_by_platform(self, platform: str) -> List[Tuple[GracyAdapter, IdentityTag]]:
        """按平台类型查询所有适配器"""
        results = []
        with self._lock:
            for adapter, tag in self._adapters.values():
                if tag.platform == platform:
                    results.append((adapter, tag))
        return results

    @property
    def all_tags(self) -> List[IdentityTag]:
        """获取所有注册 tag"""
        with self._lock:
            return [tag for _, tag in self._adapters.values()]

    @property
    def all_adapters(self) -> List[GracyAdapter]:
        """获取所有适配器实例"""
        with self._lock:
            return [adapter for adapter, _ in self._adapters.values()]

    @property
    def count(self) -> int:
        """适配器数量"""
        with self._lock:
            return len(self._adapters)

    # ── 发送 ──

    def send(self, target: str, segments: List[GracyMsg], chat_type: str,
             tag: Optional[IdentityTag] = None) -> bool:
        """发送消息

        Args:
            target: 目标 ID
            segments: 消息段列表
            chat_type: "private" | "group"
            tag: 指定适配器，None=默认适配器
        """
        if tag is not None:
            adapter = self.get(tag)
            if adapter is None:
                _logger.error(f"[AdapterPool] 发送失败: tag {tag.log_tag} 未找到")
                return False
            return adapter.send(target, segments, chat_type)

        adapter = self.get_default()
        if adapter is None:
            _logger.error("[AdapterPool] 发送失败: 无默认适配器")
            return False
        return adapter.send(target, segments, chat_type)

    def broadcast(self, target: str, segments: List[GracyMsg], chat_type: str) -> Dict[str, bool]:
        """广播消息到所有适配器

        Returns:
            {identity_key: success}
        """
        results = {}
        with self._lock:
            items = list(self._adapters.items())
        for key, (adapter, tag) in items:
            try:
                ok = adapter.send(target, segments, chat_type)
                results[key] = ok
                _logger.info(f"[AdapterPool] 广播 {tag.log_tag}: {'成功' if ok else '失败'}")
            except Exception as e:
                results[key] = False
                _logger.error(f"[AdapterPool] 广播 {tag.log_tag} 异常: {e}")
        return results

    # ── 生命周期管理 ──

    def start_all(self, on_event: Callable[[GracyEvent], None]) -> None:
        """启动所有已注册适配器"""
        with self._lock:
            items = list(self._adapters.items())
        # 注册一个包装回调，为事件注入 source tag
        def _wrapped_on_event(event: GracyEvent) -> None:
            # 如果事件没有 source，尝试从适配器查找
            if event.source is None:
                _logger.debug(f"[AdapterPool] 事件无 source，保留原样: sender={event.sender_id}")
            on_event(event)

        for key, (adapter, tag) in items:
            try:
                adapter.start(_wrapped_on_event)
                _logger.info(f"[AdapterPool] 已启动: {tag.log_tag}")
            except Exception as e:
                _logger.error(f"[AdapterPool] 启动失败 {tag.log_tag}: {e}")

    def stop_all(self) -> None:
        """停止所有适配器"""
        with self._lock:
            items = list(self._adapters.items())
        for key, (adapter, tag) in items:
            try:
                adapter.stop()
                _logger.info(f"[AdapterPool] 已停止: {tag.log_tag}")
            except Exception as e:
                _logger.error(f"[AdapterPool] 停止失败 {tag.log_tag}: {e}")


# ── 全局单例 ──
adapter_pool = AdapterPool()
