
"""GracyBot 会话管理模块 - 统一管理AI对话上下文

提供:
- 会话数据类: GracySession
- 会话管理器: GracySessionManager
- 便捷函数: gracy_get_session, gracy_get_or_create_session, gracy_add_context 等

特点:
- 不绑定任何插件
- 跨平台兼容
- 不依赖通信层
- JSON配置驱动
- 只管AI对话，不冗余
"""

from .gracy_session import GracySession
from .gracy_session_manager import (
    GracySessionManager,
    gracy_get_session_manager,
    gracy_get_session,
    gracy_get_or_create_session,
    gracy_create_session,
    gracy_destroy_session,
    gracy_add_context,
    gracy_get_context,
    gracy_clear_context,
    gracy_set_state,
    gracy_get_state,
    gracy_session,
)
from .gracy_session_handler import handle_session_command

__all__ = [
    "GracySession",
    "GracySessionManager",
    "gracy_get_session_manager",
    "gracy_get_session",
    "gracy_get_or_create_session",
    "gracy_create_session",
    "gracy_destroy_session",
    "gracy_add_context",
    "gracy_get_context",
    "gracy_clear_context",
    "gracy_set_state",
    "gracy_get_state",
    "gracy_session",
    "handle_session_command",
]
