"""GracyBot 入站事件 — 平台无关的统一消息结构

无论消息来自 OneBot HTTP、WebSocket 还是未来的 Discord/Telegram，
所有入站消息归一化为 GracyEvent 再交给插件处理。

每个事件携带 source（IdentityTag），标识消息来源适配器。
"""

from dataclasses import dataclass, field
from typing import List, Optional

from gracybot.core.gracy_adapter.message import GracyMsg
from gracybot.core.gracy_adapter.identity import IdentityTag


@dataclass
class GracyEvent:
    """统一入站事件（平台无关）

    每个字段均为必填，适配器负责从平台原始数据中提取填充。
    """

    sender_id: str                                # 发送者 ID
    target_id: str                                # 目标 ID（私聊=发送者QQ，群聊=群号）
    chat_type: str                                # "private" | "group"
    segments: List[GracyMsg] = field(default_factory=list)  # 结构化消息段
    raw_text: str = ""                            # 纯文本摘要（向后兼容现有插件）
    message_id: str = ""                          # 平台消息 ID
    nickname: str = ""                            # 发送者昵称
    is_at_bot: bool = False                       # 是否 @了机器人（仅群聊有意义）
    raw_data: dict = field(default_factory=dict)  # 平台原始数据（透传给需要深入访问的插件）
    source: Optional[IdentityTag] = None           # 消息来源适配器标签（多适配器时区分）

    # ── 事件控制 ──
    cancelled: bool = False                        # 是否被拦截（EventBus 订阅者可设置）

    def cancel(self):
        """拦截此事件，阻止进入 Pipeline"""
        self.cancelled = True

    @property
    def plain_text(self) -> str:
        """提取所有文本段拼接为纯文本"""
        parts = []
        for seg in self.segments:
            from gracybot.core.gracy_adapter.message import GracyText
            if isinstance(seg, GracyText):
                parts.append(seg.text)
        return "".join(parts)
