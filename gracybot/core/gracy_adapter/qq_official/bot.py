"""机器人信息 + Gateway 接入点

提供 QQ 官方 API 的机器人信息查询和 WebSocket 地址获取。
"""

import asyncio
import logging
from typing import Optional

_logger = logging.getLogger("Adapter.QQOfficial.bot")


class BotMixin:
    """机器人信息 Mixin — 依赖 AuthMixin 的 token 和 api_base"""

    async def get_gateway_url(self) -> Optional[str]:
        """获取 WebSocket Gateway 接入点地址"""
        token = await self.get_access_token()
        if not token:
            return None

        url = f"{self._api_base}/gateway"
        headers = {"Authorization": f"QQBot {token}"}

        try:
            session = await self._get_session()
            resp = await asyncio.wait_for(session.get(url, headers=headers), timeout=10)
            async with resp:
                if resp.status == 200:
                    data = await resp.json()
                    ws_url = data.get("url", "")
                    _logger.info(f"Gateway 接入点获取成功: {ws_url}")
                    return ws_url
                return None
        except asyncio.TimeoutError:
            return None
        except Exception:
            return None

    async def get_bot_info(self) -> Optional[dict]:
        """获取机器人信息"""
        token = await self.get_access_token()
        if not token:
            return None

        url = f"{self._api_base}/v1/me"
        headers = {"Authorization": f"QQBot {token}"}

        try:
            session = await self._get_session()
            resp = await asyncio.wait_for(session.get(url, headers=headers), timeout=10)
            async with resp:
                if resp.status == 200:
                    return await resp.json()
                return None
        except asyncio.TimeoutError:
            return None
        except Exception:
            return None
