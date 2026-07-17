"""GracyBot 适配器层 — 解耦插件与通信协议

提供:
- 消息段类型: GracyText, GracyImage, GracyAt, GracyReply, GracyVoice, GracyFile, GracyVideo, GracyForward
- 入站事件: GracyEvent
- 适配器抽象: GracyAdapter
- 统一入口: GracyBot
"""

from gracybot.core.gracy_adapter.message import (
    GracyMsg,
    GracyText,
    GracyAt,
    GracyImage,
    GracyReply,
    GracyVoice,
    GracyFile,
    GracyVideo,
    GracyForward,
    gracy_text,
    gracy_image,
)
from gracybot.core.gracy_adapter.event import GracyEvent
from gracybot.core.gracy_adapter.adapter import GracyAdapter
from gracybot.core.gracy_adapter.gracy_bot import GracyBot

__all__ = [
    # 消息段
    "GracyMsg", "GracyText", "GracyAt", "GracyImage",
    "GracyReply", "GracyVoice", "GracyFile", "GracyVideo", "GracyForward",
    "gracy_text", "gracy_image",
    # 事件 + 适配器
    "GracyEvent", "GracyAdapter",
    # 统一入口
    "GracyBot",
]
