"""GracyBot 统一入口 — 插件通过此类发送消息，与适配器解耦

用法:
    from gracybot.core.gracy_adapter.gracy_bot import GracyBot

    bot = GracyBot(adapter)
    bot.send(target, GracyText("你好"), GracyImage(file_path="/tmp/1.png"), chat_type="group")
"""

from typing import List

from gracybot.core.gracy_adapter.adapter import GracyAdapter
from gracybot.core.gracy_adapter.message import GracyMsg, GracyText, gracy_text


class GracyBot:
    """GracyBot 统一入口

    上层（插件、handler）通过 GracyBot.send() 发送消息，
    无需关心底层是 OneBot HTTP 还是 WebSocket。
    """

    def __init__(self, adapter: GracyAdapter):
        self._adapter = adapter

    def send(self, target: str, *segments: GracyMsg, chat_type: str = "private") -> bool:
        """发送消息

        支持多种调用方式：
            bot.send(target, GracyText("你好"), chat_type="group")
            bot.send(target, GracyImage(file_path="/tmp/1.png"))
        """
        seg_list: List[GracyMsg] = list(segments)
        return self._adapter.send(target, seg_list, chat_type)

    def reply_text(self, event: "GracyEvent", text: str) -> bool:
        """快捷文本回复（自动匹配目标）"""
        return self.send(event.target_id, gracy_text(text), chat_type=event.chat_type)

    def _get_adapter(self) -> GracyAdapter:
        """（内部）获取底层适配器"""
        return self._adapter
