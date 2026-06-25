"""IdentityTag — 适配器身份标签

每个适配器实例携带一个唯一标签，用于：
1. 日志中区分消息来源（哪个平台哪个账号）
2. 事件溯源（event.source 回溯）
3. PluginContext 中让插件感知来源

设计：
    - platform: 协议类型（如 onebot / qq_official / telegram）
    - bot_name: 用户自定义别名（"主号" / "小号" / "MyBot"）
    - instance_id: 自动生成的短 UUID，保证唯一性，重连不变
"""

import uuid
from dataclasses import dataclass, field


def _short_uid() -> str:
    """生成 8 位短标识符"""
    return uuid.uuid4().hex[:8]


@dataclass
class IdentityTag:
    """适配器身份标签

    >>> tag = IdentityTag("onebot", "主号")
    >>> tag.log_tag
    '[onebot:主号:a1b2c3d4]'

    注：示例中的 onebot 仅作演示，实际 platform 值由适配器工厂决定。
    """
    platform: str
    bot_name: str = "default"
    conn_type: str = ""          # 连接方式，如 "HTTP" / "WS" / "WebSocket Gateway"，由工厂函数设置
    instance_id: str = field(default_factory=_short_uid)

    @property
    def log_tag(self) -> str:
        """日志标签，如 [onebot:主号:a1b2c3d4]（示例，实际取决于 platform/bot_name）"""
        return f"[{self.platform}:{self.bot_name}:{self.instance_id[:4]}]"

    @property
    def identity_key(self) -> str:
        """在 AdapterPool 中做 key 用的唯一键"""
        return f"{self.platform}:{self.bot_name}:{self.instance_id}"

    def __str__(self) -> str:
        return f"{self.platform}/{self.bot_name}#{self.instance_id[:4]}"
