import time
from typing import Optional, List, Dict, Any


class GracySession:
    """Gracy会话数据类 - 管理AI对话上下文和状态"""

    def __init__(
        self,
        session_id: str,
        sender_id: Optional[str] = None,
        target_id: Optional[str] = None,
        expire_minutes: int = 0
    ):
        self.session_id = session_id
        self.sender_id = sender_id
        self.target_id = target_id
        self.context: List[Dict[str, str]] = []
        self.state: Dict[str, Any] = {}
        self.created_at = time.time()
        self.expire_minutes = expire_minutes
        if expire_minutes > 0:
            self.expires_at = self.created_at + (expire_minutes * 60)
        else:
            self.expires_at = None  # None表示永不过期

    def is_expired(self) -> bool:
        """判断会话是否过期"""
        if self.expires_at is None:
            return False  # 永不过期
        return time.time() > self.expires_at

    def refresh(self, expire_minutes: Optional[int] = None) -> None:
        """刷新会话过期时间"""
        if expire_minutes is not None:
            self.expire_minutes = expire_minutes

        if self.expire_minutes > 0:
            self.expires_at = time.time() + (self.expire_minutes * 60)
        else:
            self.expires_at = None  # 永不过期

    def add_context(self, role: str, content: str) -> None:
        """添加AI对话上下文"""
        self.context.append({"role": role, "content": content})

    def get_context(self, limit: Optional[int] = None) -> List[Dict[str, str]]:
        """获取AI对话上下文"""
        if limit is None or len(self.context) <= limit:
            return list(self.context)
        return list(self.context[-limit:])

    def clear_context(self) -> None:
        """清空对话上下文"""
        self.context = []

    def set_state(self, key: str, value: Any) -> None:
        """设置会话状态"""
        self.state[key] = value

    def get_state(self, key: str, default: Any = None) -> Any:
        """获取会话状态"""
        return self.state.get(key, default)

    def clear_state(self) -> None:
        """清空会话状态"""
        self.state = {}

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于持久化）"""
        return {
            "session_id": self.session_id,
            "sender_id": self.sender_id,
            "target_id": self.target_id,
            "context": list(self.context),
            "state": dict(self.state),
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "expire_minutes": self.expire_minutes
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GracySession":
        """从字典恢复会话"""
        session = cls(
            session_id=data["session_id"],
            sender_id=data.get("sender_id"),
            target_id=data.get("target_id"),
            expire_minutes=data.get("expire_minutes", 0)
        )
        session.context = list(data.get("context", []))
        session.state = dict(data.get("state", {}))
        session.created_at = data["created_at"]
        session.expires_at = data.get("expires_at")
        return session
