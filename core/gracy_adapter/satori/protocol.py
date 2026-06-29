"""Satori 协议常量和类型定义

Satori 是一个通用聊天机器人协议，支持多平台接入。
参考文档：https://satori.js.org/
"""

import logging
from enum import Enum
from typing import Optional

_logger = logging.getLogger("Adapter.Satori.protocol")


class SatoriOpcode(Enum):
    """Satori WebSocket 操作码"""
    EVENT = 0           # 事件分发
    HEARTBEAT = 1       # 心跳
    IDENTIFY = 2        # 鉴权
    RECONNECT = 7       # 重连请求
    INVALID_SESSION = 9 # 无效会话


class SatoriEventType(Enum):
    """Satori 事件类型"""
    MESSAGE_CREATED = "message_created"
    MESSAGE_UPDATED = "message_updated"
    MESSAGE_DELETED = "message_deleted"
    MEMBER_ADDED = "member_added"
    MEMBER_REMOVED = "member_removed"
    FRIEND_REQUEST = "friend_request"
    # ... 其他事件类型


# Satori 消息段类型
SATORI_MSG_TEXT = "text"
SATORI_MSG_IMAGE = "image"
SATORI_MSG_AT = "at"
SATORI_MSG_REPLY = "reply"
SATORI_MSG_VOICE = "voice"
SATORI_MSG_FILE = "file"
SATORI_MSG_VIDEO = "video"
SATORI_MSG_AUDIO = "audio"
SATORI_MSG_AUTHOR = "author"
SATORI_MSG_QUOTE = "quote"
SATORI_MSG_PLAIN = "plain"
SATORI_MSG_RAW = "raw"
SATORI_MSG_BR = "br"
SATORI_MSG_HR = "hr"
SATORI_MSG_ICON = "icon"
SATORI_MSG_LINK = "link"
SATORI_MSG澎湃新闻 = "澎湃新闻"
SATORI_MSG_KATEX = "katex"
SATORI_MSG_CODE = "code"
SATORI_MSG_CODE_BLOCK = "code-block"
SATORI_MSG_SPLASH = "splash"
SATORI_MSG_STRONG = "strong"
SATORI_MSG_EM = "em"
SATORI_MSG_INS = "ins"
SATORI_MSG_DEL = "del"
SATORI_MSG_SUP = "sup"
SATORI_MSG_SUB = "sub"
SATORI_MSG_SPOILER = "spoiler"
SATORI_MSG_LINK_TEXT = "link-text"
SATORI_MSG_LINK_URL = "link-url"
SATORI_MSG_LINK_TITLE = "link-title"
SATORI_MSG_LINK_AUTHOR = "link-author"
SATORI_MSG_LINK_DESCRIPTION = "link-description"
SATORI_MSG_LINK_IMAGE = "link-image"
SATORI_MSG_LINK_VIDEO = "link-video"
SATORI_MSG_LINK_AUDIO = "link-audio"
SATORI_MSG_LINK_FILE = "link-file"
SATORI_MSG_LINK_AUTHOR_IMAGE = "link-author-image"
SATORI_MSG_LINK_AUTHOR_URL = "link-author-url"
SATORI_MSG_LINK_AUTHOR_NAME = "link-author-name"
SATORI_MSG_LINK_EMOJI = "link-emoji"
SATORI_MSG_LINK_EMOJI_URL = "link-emoji-url"
SATORI_MSG_LINK_EMOJI_ANIMATED = "link-emoji-animated"


def parse_satori_event(raw: dict) -> Optional[dict]:
    """解析 Satori 事件

    Args:
        raw: Satori WebSocket 消息

    Returns:
        解析后的事件数据，失败返回 None
    """
    op = raw.get("op")
    if op != SatoriOpcode.EVENT.value:
        return None

    d = raw.get("d", {})
    event_type = d.get("type", "")
    if not event_type:
        _logger.debug("Satori 事件无类型")
        return None

    return d
