import os
import json
import time
import logging
from typing import Optional, Dict, List, Any
from threading import Lock, Thread
from .gracy_session import GracySession

try:
    from gracybot.core.config import LOG_LEVEL
except ImportError:
    LOG_LEVEL = "INFO"


class GracySessionManager:
    """Gracy会话管理器 - 管理所有会话"""

    def __init__(self, config_path: Optional[str] = None):
        self._sessions: Dict[str, GracySession] = {}
        self._lock = Lock()
        self._logger = logging.getLogger("Core.Session")

        self._config = self._load_config(config_path)
        self._default_expire_minutes = self._config.get("default_expire_minutes", 30)
        self._max_context_messages = self._config.get("max_context_messages", 50)
        self._auto_cleanup_interval = self._config.get("auto_cleanup_interval", 60)
        self._shared_group_session = self._config.get("shared_group_session", False)

        self._cleanup_thread: Optional[Thread] = None
        self._running = False
        self._start_auto_cleanup()

    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """加载配置文件"""
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(__file__),
                "config",
                "gracy_session_config.json"
            )

        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                self._logger.warning(f"加载配置失败: {e}，使用默认配置")

        return {
            "default_expire_minutes": 0,
            "auto_cleanup_interval": 60,
            "max_context_messages": 50,
            "shared_group_session": False
        }

    def _start_auto_cleanup(self) -> None:
        """启动自动清理线程"""
        def cleanup_loop():
            while self._running:
                self.cleanup_expired_sessions()
                time.sleep(self._auto_cleanup_interval)

        self._running = True
        self._cleanup_thread = Thread(target=cleanup_loop, daemon=True)
        self._cleanup_thread.start()

    def _generate_session_id(self, sender_id: Optional[str], target_id: Optional[str]) -> str:
        """生成会话ID"""
        if target_id:
            if self._shared_group_session:
                return f"group:{target_id}"
            else:
                return f"{target_id}:{sender_id}" if sender_id else f"group:{target_id}"
        return f"private:{sender_id}" if sender_id else "private:global"

    def create_session(
        self,
        sender_id: Optional[str] = None,
        target_id: Optional[str] = None
    ) -> GracySession:
        """创建新会话"""
        session_id = self._generate_session_id(sender_id or "", target_id)
        session = GracySession(
            session_id=session_id,
            sender_id=sender_id,
            target_id=target_id,
            expire_minutes=self._default_expire_minutes
        )

        with self._lock:
            self._sessions[session_id] = session

        self._logger.debug(f"创建会话: {session_id}")
        return session

    def get_session(
        self,
        sender_id: Optional[str] = None,
        target_id: Optional[str] = None
    ) -> Optional[GracySession]:
        """获取会话（不存在返回None）"""
        session_id = self._generate_session_id(sender_id, target_id)
        session = self._sessions.get(session_id)

        if session and session.is_expired():
            return None

        if session:
            session.refresh(self._default_expire_minutes)

        return session

    def get_or_create_session(
        self,
        sender_id: Optional[str] = None,
        target_id: Optional[str] = None
    ) -> GracySession:
        """获取或创建会话"""
        session = self.get_session(sender_id, target_id)
        if session is None:
            session = self.create_session(sender_id, target_id)
        return session

    def destroy_session(
        self,
        sender_id: Optional[str] = None,
        target_id: Optional[str] = None
    ) -> bool:
        """销毁会话"""
        session_id = self._generate_session_id(sender_id, target_id)

        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                self._logger.debug(f"销毁会话: {session_id}")
                return True

        return False

    def cleanup_expired_sessions(self) -> int:
        """清理过期会话，返回清理数量"""
        expired_count = 0

        with self._lock:
            expired_ids = [
                sid for sid, s in self._sessions.items()
                if s.is_expired()
            ]
            for sid in expired_ids:
                del self._sessions[sid]
                expired_count += 1

        if expired_count > 0:
            self._logger.debug(f"清理了 {expired_count} 个过期会话")

        return expired_count

    def get_all_sessions(self) -> List[GracySession]:
        """获取所有会话"""
        with self._lock:
            return list(self._sessions.values())

    def shutdown(self) -> None:
        """关闭会话管理器"""
        self._running = False
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5)


# ========== 全局实例和便捷函数 ==========
_manager: Optional[GracySessionManager] = None


def gracy_get_session_manager() -> GracySessionManager:
    """获取会话管理器单例"""
    global _manager
    if _manager is None:
        _manager = GracySessionManager()
    return _manager


def gracy_get_session(sender_id: Optional[str] = None, target_id: Optional[str] = None) -> Optional[GracySession]:
    """获取会话"""
    return gracy_get_session_manager().get_session(sender_id, target_id)


def gracy_get_or_create_session(sender_id: Optional[str] = None, target_id: Optional[str] = None) -> GracySession:
    """获取或创建会话"""
    return gracy_get_session_manager().get_or_create_session(sender_id, target_id)


def gracy_create_session(sender_id: Optional[str] = None, target_id: Optional[str] = None) -> GracySession:
    """创建会话"""
    return gracy_get_session_manager().create_session(sender_id, target_id)


def gracy_destroy_session(sender_id: Optional[str] = None, target_id: Optional[str] = None) -> bool:
    """销毁会话"""
    return gracy_get_session_manager().destroy_session(sender_id, target_id)


def gracy_add_context(
    session: GracySession,
    role: str,
    content: str
) -> None:
    """添加AI对话上下文"""
    session.add_context(role, content)


def gracy_get_context(
    session: GracySession,
    limit: Optional[int] = None
) -> List[Dict[str, str]]:
    """获取AI对话上下文"""
    if limit is None:
        limit = gracy_get_session_manager()._max_context_messages
    return session.get_context(limit)


def gracy_clear_context(session: GracySession) -> None:
    """清空对话上下文"""
    session.clear_context()


def gracy_set_state(session: GracySession, key: str, value: Any) -> None:
    """设置会话状态"""
    session.set_state(key, value)


def gracy_get_state(session: GracySession, key: str, default: Any = None) -> Any:
    """获取会话状态"""
    return session.get_state(key, default)


def gracy_session(
    auto_refresh: bool = True,
    expire_minutes: Optional[int] = 0
):
    """
    Gracy会话装饰器 - 自动管理会话

    使用示例:
        @gracy_session()
        def handle_message(data: dict, session: GracySession):
            # session会自动注入
            gracy_add_context(session, "user", data["text"])
            # ...

    参数:
        auto_refresh: 自动刷新过期时间
        expire_minutes: 自定义过期时间（分钟）
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            sender_id = kwargs.get("sender_id")
            target_id = kwargs.get("target_id")

            if not sender_id and not target_id and len(args) > 0:
                first_arg = args[0]
                if isinstance(first_arg, dict):
                    sender_id = first_arg.get("sender_id")
                    target_id = first_arg.get("target_id")

            if not sender_id and not target_id:
                return func(*args, **kwargs)

            session = gracy_get_or_create_session(sender_id, target_id)

            if auto_refresh:
                manager = gracy_get_session_manager()
                session.refresh(expire_minutes or manager._default_expire_minutes)

            kwargs["session"] = session

            return func(*args, **kwargs)

        return wrapper
    return decorator
