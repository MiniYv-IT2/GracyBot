"""Satori 事件转换 — Satori Event → GracyEvent

职责：
- satori_event_to_gracy: 将 Satori 事件转换为 GracyEvent
"""

import logging
from typing import Optional

from core.gracy_adapter.event import GracyEvent
from core.gracy_adapter.identity import IdentityTag
from core.gracy_adapter.satori.message import satori_to_gracy, extract_plain_text
from core.gracy_adapter.message import GracyText, GracyAt

_logger = logging.getLogger("Adapter.Satori.event")


def satori_event_to_gracy(
    satori_event: dict,
    tag: IdentityTag,
) -> Optional[GracyEvent]:
    """将 Satori 事件转换为 GracyEvent

    Args:
        satori_event: Satori 事件数据
        tag: 来源适配器标签

    Returns:
        转换成功返回 GracyEvent，不关心的事件返回 None
    """
    event_type = satori_event.get("type", "")

    # 处理不同类型的事件
    if event_type == "message_created":
        return _handle_message_created(satori_event, tag)
    elif event_type in ("member_added", "member_removed"):
        _logger.debug(f"Satori 群组成员变动事件: {event_type}")
        return None
    elif event_type == "friend_request":
        _logger.debug("Satori 好友请求事件")
        return None
    elif event_type == "message_updated":
        _logger.debug("Satori 消息更新事件")
        return None
    elif event_type == "message_deleted":
        _logger.debug("Satori 消息删除事件")
        return None
    else:
        _logger.debug(f"忽略 Satori 事件类型: {event_type}")
        return None

def _handle_message_created(satori_event: dict, tag: IdentityTag) -> Optional[GracyEvent]:
    """处理消息创建事件"""
    # 提取消息数据
    message = satori_event.get("message", {})
    if not message:
        _logger.debug("Satori 事件无消息数据")
        return None

    # 提取发送者
    user = satori_event.get("user", {})
    sender_id = user.get("id", "")
    nickname = user.get("name", "")

    if not sender_id:
        _logger.debug("Satori 事件无发送者 ID")
        return None

    # 提取目标
    channel = satori_event.get("channel", {})
    target_id = channel.get("id", "")
    channel_type = channel.get("type", "")

    # 判断私聊/群聊
    chat_type = "private" if channel_type == "private" else "group"

    # 转换消息内容
    content = message.get("content", "")
    segments = satori_to_gracy(content)

    # 提取纯文本
    raw_text = extract_plain_text(segments).strip()

    # 提取消息 ID
    message_id = message.get("id", "")

    # 检测 @机器人
    self_id = satori_event.get("self", {}).get("id", "")
    is_at_bot = any(
        seg.target_id == self_id
        for seg in segments
        if isinstance(seg, GracyAt)
    )

    return GracyEvent(
        sender_id=sender_id,
        target_id=target_id or sender_id,
        chat_type=chat_type,
        segments=segments,
        raw_text=raw_text,
        message_id=message_id,
        nickname=nickname,
        is_at_bot=is_at_bot,
        raw_data=satori_event,
        source=tag,
    )
