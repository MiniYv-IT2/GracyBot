"""QQ 官方个人机器人 WebSocket Gateway 连接管理

处理 WebSocket 连接生命周期：
- 连接/断线重连
- 心跳保活
- 事件接收和分发
"""

import asyncio
import json
import logging
import random
from typing import Callable, Optional

import aiohttp

from core.gracy_adapter.event import GracyEvent
from core.gracy_adapter.identity import IdentityTag
from core.gracy_adapter.qq_official.api import QQOfficialAPI
from core.gracy_adapter.qq_official.protocol import parse_event

_logger = logging.getLogger("Gracy.QQOfficial.gateway")

# ── 调试埋点 ──
import urllib.request
_DEBUG_URL = "http://127.0.0.1:19809"
def _dbg(event: str, **kw):
    try:
        data = json.dumps({"event": event, **kw}).encode()
        urllib.request.urlopen(urllib.request.Request(f"{_DEBUG_URL}/debug", data=data), timeout=0.5)
    except:
        pass


class QQOfficialGateway:
    """QQ 官方个人机器人 WebSocket Gateway"""

    def __init__(
        self,
        api: QQOfficialAPI,
        on_event: Callable[[GracyEvent], None],
        tag: IdentityTag,
    ):
        self._api = api
        self._on_event = on_event
        self._tag = tag
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._heartbeat_interval: float = 0
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._running = False
        self._reconnect_delay = 1

    async def start(self):
        self._running = True
        while self._running:
            try:
                await self._connect()
            except Exception as e:
                if self._running:
                    _logger.error(f"[QQOfficial] 连接异常: {e}")
                    await asyncio.sleep(self._reconnect_delay)
                    self._reconnect_delay = min(self._reconnect_delay * 2, 60)
            else:
                self._reconnect_delay = 1

        _logger.info("[QQOfficial] Gateway 连接已停止")

    async def stop(self):
        self._running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None
        if self._ws and not self._ws.closed:
            await self._ws.close()
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def _connect(self):
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()

        # 从 API 获取 Gateway 地址
        ws_url = await self._api.get_gateway_url()
        if not ws_url:
            _logger.error("[QQOfficial] 无法获取 Gateway 地址")
            raise ConnectionError("获取 Gateway 地址失败")

        # 获取 Token
        token = await self._api.get_access_token()
        if not token:
            _logger.error("[QQOfficial] 无有效 Token")
            raise ConnectionError("无有效 Token")

        _logger.info(f"[QQOfficial] 正在连接: {ws_url}")
        async with self._session.ws_connect(
            ws_url,
            headers={"Authorization": f"QQBot {token}"},
            heartbeat=60,
        ) as ws:
            self._ws = ws
            _logger.info("[QQOfficial] WebSocket 连接成功")

            # 等待 Hello 并开始心跳
            hello_data = await ws.receive_json()
            self._handle_hello(hello_data)

            # 发送 Identify
            await self._send_identify(token)

            # 消息循环
            async for msg in ws:
                _dbg("ws_raw", type=str(msg.type), data=str(msg.data)[:200])
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        _dbg("ws_json", op=data.get("op"), t=data.get("t"))
                        await self._handle_message(data)
                    except Exception as e:
                        _logger.error(f"[QQOfficial] 处理消息异常: {e}")
                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    break

            _logger.warning(f"[QQOfficial] WebSocket 连接关闭: {ws.close_code}")

    async def _send_identify(self, token: str):
        """发送 Identify 鉴权包"""
        payload = {
            "op": 2,  # Identify
            "d": {
                "token": f"QQBot {token}",
                "intents": 1 << 25,  # C2C_MESSAGE + GROUP_AT_MESSAGE
                "shard": [0, 1],
            },
        }
        await self._ws.send_json(payload)
        _logger.info("[QQOfficial] 已发送 Identify 鉴权")

    async def _handle_message(self, data: dict):
        """处理接收到的 WebSocket 消息"""
        op = data.get("op")
        d = data.get("d", {})
        event_type = data.get("t", "")

        if op == 0:  # Dispatch — 事件分发
            if event_type in ("AT_MESSAGE_CREATE", "C2C_MESSAGE_CREATE", "GROUP_AT_MESSAGE_CREATE", "MESSAGE_CREATE"):
                # protocol.py 期望格式: {"type": "...", "data": {...}}
                parsed = {"type": event_type, "data": d}
                event = parse_event(parsed, self._tag)
                _dbg("parse_event_result", event_type=event_type, got_event=event is not None)
                if event:
                    self._on_event(event)
            else:
                _logger.debug(f"[QQOfficial] 未解析的事件: {event_type}")
        elif op == 7:  # Reconnect
            _logger.warning("[QQOfficial] 收到重连指令")
            raise ConnectionError("收到重连指令")
        elif op == 9:  # Invalid Session
            _logger.error("[QQOfficial] 会话无效，需要重新鉴权")
            raise ConnectionError("会话无效")
        else:
            _logger.debug(f"[QQOfficial] 未知 op 类型: {op}")

    def _handle_hello(self, data: dict):
        """处理 Hello 消息，启动心跳"""
        d = data.get("d", {})
        self._heartbeat_interval = d.get("heartbeat_interval", 41250) / 1000.0
        _logger.info(f"[QQOfficial] 心跳间隔: {self._heartbeat_interval}s")

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def _heartbeat_loop(self):
        """心跳保活循环"""
        while self._running:
            try:
                await asyncio.sleep(self._heartbeat_interval * random.uniform(0.8, 1.2))

                if self._ws and not self._ws.closed:
                    await self._ws.send_json({"op": 1, "d": None})
                    _logger.debug("[QQOfficial] 心跳已发送")
            except asyncio.CancelledError:
                break
            except Exception as e:
                _logger.error(f"[QQOfficial] 心跳异常: {e}")
                break
