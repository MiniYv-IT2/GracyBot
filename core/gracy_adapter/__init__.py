"""GracyBot 适配器层 — 解耦插件与通信协议

提供:
- 消息段类型: GracyText, GracyImage, GracyAt, GracyReply, GracyVoice, GracyFile
- 入站事件: GracyEvent
- 适配器抽象: GracyAdapter
- 统一入口: GracyBot
- OneBot 平台: GracyOneBot (HTTP), GracyOneBotWS (WebSocket)
"""

from core.gracy_adapter.message import (
    GracyMsg,
    GracyText,
    GracyAt,
    GracyImage,
    GracyReply,
    GracyVoice,
    GracyFile,
    gracy_text,
    gracy_image,
)
from core.gracy_adapter.event import GracyEvent
from core.gracy_adapter.adapter import GracyAdapter
from core.gracy_adapter.gracy_bot import GracyBot

# 平台适配器按需导入，避免强制依赖
# from core.gracy_adapter.onebot import GracyOneBot, GracyOneBotWS

__all__ = [
    # 消息段
    "GracyMsg", "GracyText", "GracyAt", "GracyImage",
    "GracyReply", "GracyVoice", "GracyFile",
    "gracy_text", "gracy_image",
    # 事件 + 适配器
    "GracyEvent", "GracyAdapter",
    # 统一入口
    "GracyBot",
]
