"""QQ 官方 HTTP API 封装 — 统一入口

组合各功能 Mixin，对外暴露单一 QQOfficialAPI 类。
"""
from .auth import AuthMixin
from .media import MediaMixin
from .message import MessageMixin
from .bot import BotMixin


class QQOfficialAPI(AuthMixin, MediaMixin, MessageMixin, BotMixin):
    """QQ 官方 HTTP API 封装

    组合鉴权、媒体上传、消息发送、机器人信息等功能。
    """

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        is_sandbox: bool = False,
    ):
        self._init_auth(app_id, app_secret, is_sandbox)

    def __repr__(self) -> str:
        return f"QQOfficialAPI(app_id={self._app_id[:6]}..., sandbox={self._is_sandbox})"
