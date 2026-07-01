"""
Gracy会话管理命令处理器 - 手动管理会话

提供:
- /清理会话  - 清理当前会话
- /清理会话 @xxx - 清理指定用户会话（主人）
- /查看会话  - 查看当前会话状态
- /查看会话 @xxx - 查看指定用户会话状态（主人）

依赖:
- core.gracy_session.gracy_session_manager
- core.gracy_adapter.send (gracy_send_msg)
- core.gracy_adapter.message (GracyText)
"""

import logging
from typing import Optional

logger = logging.getLogger("Core.Session")


def _extract_target_user(raw_msg: str) -> Optional[str]:
    """从消息中提取 @ 的目标用户ID

    支持格式:
    - /清理会话 @123456
    - /清理会话 123456
    """
    import re
    # 尝试匹配 @xxxxx 或 纯数字
    text_match = re.search(r'@(\d+)', raw_msg)
    if text_match:
        return text_match.group(1)

    # 尝试直接匹配末尾的数字（作为用户ID）
    parts = raw_msg.strip().split()
    for part in parts:
        if part.strip().isdigit():
            return part.strip()
        if part.strip().startswith('@') and part.strip()[1:].isdigit():
            return part.strip()[1:]

    return None


def handle_session_command(
    plugin_manager,
    send_msg_func,
    plugin_data: dict,
    sender_id: str,
    chat_type: str,
    permission: str,
    base_logger
) -> None:
    """会话管理命令处理器 - 处理 /清理会话 和 /查看会话 指令

    参数与插件 handler 保持一致，可直接注册为插件或内置命令调用。
    """
    from core.security_manager import security_manager
    from core.gracy_session import (
        gracy_get_session,
        gracy_get_or_create_session,
        gracy_destroy_session,
        gracy_clear_context,
        gracy_get_context,
    )

    raw_msg = plugin_data.get("text", "").strip()
    target_id = plugin_data.get("target_id", sender_id)
    nickname = plugin_data.get("nickname", "用户")

    # 判断命令类型
    is_clear = any(cmd in raw_msg for cmd in ["/清理会话", "/清空会话", "/删除会话"])
    is_view = "/查看会话" in raw_msg

    if not is_clear and not is_view:
        return

    # 提取目标用户（@xxx 情况）
    target_user = _extract_target_user(raw_msg)

    # 如果指定了目标用户，检查主人权限
    if target_user:
        is_master, msg = security_manager.check_master_permission(sender_id)
        if not is_master:
            reply = "⚠️ 权限不足！只有机器人主人才可以管理其他用户的会话"
            send_msg_func(target_id, GracyText(text=reply), chat_type=chat_type)
            logger.warning(
                f"[会话管理] 用户{sender_id}尝试管理其他用户会话，权限不足"
            )
            return
        target_sender = target_user
    else:
        target_sender = sender_id

    # 根据指令类型处理
    if is_clear:
        _handle_clear_session(send_msg_func, target_id, chat_type, target_sender, nickname)
    elif is_view:
        _handle_view_session(send_msg_func, target_id, chat_type, target_sender, nickname)


def _handle_clear_session(
    send_msg_func,
    target_id: str,
    chat_type: str,
    target_sender: str,
    nickname: str
) -> None:
    """处理清理会话"""
    from core.gracy_adapter.message import GracyText
    from core.gracy_session import gracy_get_session
    from core.gracy_session.gracy_session_manager import gracy_get_session_manager

    manager = gracy_get_session_manager()

    # 尝试清理会话
    success = manager.destroy_session(target_sender, target_id if chat_type == "group" else None)

    if success:
        reply = f"✅ 会话已清理成功！"
        target_str = f"用户{target_sender}"
        if chat_type == "group":
            target_str += f" 在群{target_id}"
        logger.info(f"[会话管理] {target_str} 的会话已清理")
    else:
        # 会话不存在，也视为成功（创建新的）
        from core.gracy_session import gracy_create_session
        gracy_create_session(target_sender, target_id if chat_type == "group" else None)
        reply = f"✅ 会话已重置！"
        target_str = f"用户{target_sender}"
        if chat_type == "group":
            target_str += f" 在群{target_id}"
        logger.info(f"[会话管理] {target_str} 会话不存在，已创建新会话")

    send_msg_func(target_id, GracyText(text=reply), chat_type=chat_type)


def _handle_view_session(
    send_msg_func,
    target_id: str,
    chat_type: str,
    target_sender: str,
    nickname: str
) -> None:
    """处理查看会话"""
    from core.gracy_adapter.message import GracyText
    from core.gracy_session import gracy_get_session

    session = gracy_get_session(target_sender, target_id if chat_type == "group" else None)

    if session is None:
        reply = f"📭 当前没有活跃会话"
        logger.info(f"[会话管理] 用户{target_sender} 没有活跃会话")
        send_msg_func(target_id, GracyText(text=reply), chat_type=chat_type)
        return

    # 构建会话信息
    context_count = len(session.context)
    is_expired = "是" if session.is_expired() else "否"
    expire_info = "永不过期" if session.expires_at is None else f"{session.expire_minutes}分钟"

    group_info = f"群组: {target_id}" if chat_type == "group" else "私聊"
    session_type = "共享会话" if chat_type == "group" and session.sender_id is None else "独立会话"

    lines = [
        f"📋 会话信息 ({group_info})",
        f"• 会话ID: {session.session_id[:20]}...",
        f"• 用户: {session.sender_id or '群共享'}",
        f"• 类型: {session_type}",
        f"• 上下文消息数: {context_count} 条",
        f"• 过期策略: {expire_info}",
        f"• 已过期: {is_expired}",
    ]

    reply = "\n".join(lines)
    logger.info(
        f"[会话管理] 用户{target_sender} 查看会话: {context_count}条上下文, "
        f"过期策略: {expire_info}"
    )
    send_msg_func(target_id, GracyText(text=reply), chat_type=chat_type)
