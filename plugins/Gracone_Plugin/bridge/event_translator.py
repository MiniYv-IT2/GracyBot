"""事件翻译器 — GracyEvent ↔ NoneBot 通用 Event 双向转换

平台无关设计，直接翻译为 nonebot.adapters.MessageEvent，
不引入任何 OneBot V11 特定类型。
"""

import time
from typing import Any, Optional

from core.gracy_adapter.event import GracyEvent

from bridge.message_translator import gracy_to_nb_message, nb_to_gracy_segments


def gracy_to_nb_event(gracy_event: GracyEvent, bot_self_id: str = "") -> Any:
    """将 GracyEvent 转换为 NoneBot 通用 MessageEvent
    
    Args:
        gracy_event: GracyBot 原始事件
        bot_self_id: 机器人自身 ID
        
    Returns:
        MessageEvent 实例（平台无关通用类型）
    """
    from gracone_nonebot import MessageEvent, Message
    
    # 转换消息段
    segments = getattr(gracy_event, 'segments', []) or []
    nb_message = gracy_to_nb_message(segments)
    
    # 获取字段
    sender_id = str(getattr(gracy_event, 'sender_id', '0') or '0')
    target_id = getattr(gracy_event, 'target_id', '')
    raw_text = getattr(gracy_event, 'raw_text', '') or ''
    message_id = getattr(gracy_event, 'message_id', '') or ''
    nickname = getattr(gracy_event, 'nickname', '') or ''
    chat_type = getattr(gracy_event, 'chat_type', 'private') or 'private'
    is_at_bot = getattr(gracy_event, 'is_at_bot', False)
    self_id = str(bot_self_id) if bot_self_id else "0"
    now = int(time.time())
    
    # 创建通用消息事件
    event = MessageEvent(
        user_id=sender_id,
        message=nb_message,
        raw_message=raw_text,
        message_type=chat_type,   # "private" | "group"
        to_me=is_at_bot,
        time=now,
        self_id=self_id,
    )
    event._gracy_event = gracy_event
    event._nickname = nickname
    event._target_id = target_id
    event._message_id = message_id
    return event


def nb_to_gracy_event(nb_event: Any, gracy_event: Optional[GracyEvent] = None) -> GracyEvent:
    """将 NoneBot 通用 Event 转换回 GracyEvent（反向，用于 send 回写）
    
    Args:
        nb_event: NoneBot Event 实例
        gracy_event: 原始的 GracyEvent（如有则直接返回）
        
    Returns:
        GracyEvent 实例
    """
    if gracy_event:
        return gracy_event
    
    user_id = str(getattr(nb_event, 'user_id', '0'))
    message = getattr(nb_event, 'message', None)
    message_type = getattr(nb_event, 'message_type', 'private')
    
    if message_type == 'group':
        target_id = getattr(nb_event, '_target_id', user_id)
    else:
        target_id = user_id
    
    segments = []
    if message:
        segments = nb_to_gracy_segments(message)
    
    raw_message = str(getattr(nb_event, 'raw_message', 
                     getattr(nb_event, 'raw_text', '')))
    
    return GracyEvent(
        sender_id=user_id,
        target_id=str(target_id),
        chat_type=message_type,
        segments=segments,
        raw_text=raw_message,
        message_id=str(getattr(nb_event, '_message_id', '')),
        nickname=getattr(nb_event, '_nickname', ''),
        is_at_bot=getattr(nb_event, 'to_me', False),
        raw_data={},
        source="gracone",
    )
