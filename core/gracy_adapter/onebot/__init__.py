"""OneBot 平台适配器

遵循 OneBot 11 标准，支持 NapCat 等兼容客户端。
"""

from core.gracy_adapter.onebot.http import GracyOneBot
from core.gracy_adapter.onebot.ws import GracyOneBotWS

__all__ = [
    "GracyOneBot",
    "GracyOneBotWS",
]
