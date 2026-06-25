"""OAuth2 鉴权 + 会话管理 + API 常量

提供 Access Token 的获取、缓存和刷新。
"""

import logging
import time
from typing import Optional

import aiohttp

_logger = logging.getLogger("Adapter.QQOfficial.auth")

API_BASE = "https://api.sgroup.qq.com"
SANDBOX_API_BASE = "https://sandbox.api.sgroup.qq.com"
WS_BASE = "wss://api.sgroup.qq.com"
SANDBOX_WS_BASE = "wss://sandbox.api.sgroup.qq.com"


class AuthMixin:
    """OAuth2 鉴权 Mixin — 提供 Token 和会话管理"""

    def _init_auth(self, app_id: str, app_secret: str, is_sandbox: bool = False):
        self._app_id = app_id
        self._app_secret = app_secret
        self._is_sandbox = is_sandbox
        self._api_base = SANDBOX_API_BASE if is_sandbox else API_BASE
        self._ws_base = SANDBOX_WS_BASE if is_sandbox else WS_BASE

        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def get_access_token(self) -> Optional[str]:
        """获取 Access Token（带缓存，提前 5 分钟刷新）"""
        now = time.time()
        if self._access_token and now < self._token_expires_at - 300:
            return self._access_token

        url = "https://bots.qq.com/app/getAppAccessToken"
        payload = {"appId": self._app_id, "clientSecret": self._app_secret}

        try:
            session = await self._get_session()
            async with session.post(url, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self._access_token = data.get("access_token")
                    expires_in = int(data.get("expires_in", 7200))
                    self._token_expires_at = now + expires_in
                    _logger.info(f"Access Token 获取成功，有效期 {expires_in}s")
                    return self._access_token
                error_body = await resp.text()
                _logger.error(f"获取 Token 失败: {resp.status} {error_body}")
                return None
        except Exception as e:
            _logger.error(f"获取 Token 异常: {e}")
            return None

    async def refresh_token(self) -> Optional[str]:
        self._access_token = None
        self._token_expires_at = 0
        return await self.get_access_token()
