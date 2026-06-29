"""Satori WebSocket Gateway 连接管理

处理 WebSocket 连接生命周期：
- 连接/断线重连
- 心跳保活
- 事件接收和分发
"""

import asyncio
import json
import logging
from typing import Callable, Optional

import aiohttp

from core.gracy_adapter.event import GracyEvent
from core.gracy_adapter.identity import IdentityTag
from core.gracy_adapter.satori.protocol import SatoriOpcode, parse_satori_event
from core.gracy_adapter.satori.event import satori_event_to_gracy

_logger = logging.getLogger("Adapter.Satori.gateway")


class SatoriGateway:
    """Satori WebSocket Gateway"""

    def __init__(
        self,
        host: str,
        port: int,
        token: str,
        on_event: Callable[[GracyEvent], None],
        tag: IdentityTag,
    ):
        self._host = host
        self._port = port
        self._token = token
        self._on_event = on_event
        self._tag = tag
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._heartbeat_interval: float = 30.0
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._running = False
        self._reconnect_delay = 1
        self._max_reconnect = 10
        self._reconnect_count = 0
        self._pending: dict = {}  # 用于存储等待响应的 API 调用

    async def start(self):
        """启动 Gateway 连接"""
        self._running = True
        self._reconnect_count = 0

        while self._running and self._reconnect_count < self._max_reconnect:
            try:
                await self._connect()
            except Exception as e:
                if self._running:
                    _logger.error(f"Satori Gateway 连接异常: {e}")
                    self._reconnect_count += 1
                    await asyncio.sleep(self._reconnect_delay)
                    self._reconnect_delay = min(self._reconnect_delay * 2, 60)
            else:
                self._reconnect_delay = 1
                self._reconnect_count = 0

        if self._reconnect_count >= self._max_reconnect:
            _logger.error(f"Satori Gateway 达到最大重连次数 {self._max_reconnect}")

        _logger.info("Satori Gateway 连接已停止")

    async def stop(self):
        """停止 Gateway 连接"""
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
        """建立 WebSocket 连接"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()

        ws_url = f"ws://{self._host}:{self._port}"
        headers = {}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        _logger.info(f"正在连接 Satori Gateway: {ws_url}")

        async with self._session.ws_connect(
            ws_url,
            headers=headers,
            heartbeat=60,
        ) as ws:
            self._ws = ws
            _logger.info("Satori WebSocket 连接成功")

            # 等待 Hello
            hello_data = await ws.receive_json()
            self._handle_hello(hello_data)

            # 发送 Identify
            await self._send_identify()

            # 消息循环
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        await self._handle_message(data)
                    except Exception as e:
                        _logger.error(f"处理 Satori 消息异常: {e}")
                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    break

            _logger.warning(f"Satori WebSocket 连接关闭: {ws.close_code}")

    async def _send_identify(self):
        """发送 Identify 鉴权包"""
        payload = {
            "op": SatoriOpcode.IDENTIFY.value,
            "d": {
                "token": self._token,
            },
        }
        await self._ws.send_json(payload)
        _logger.info("已发送 Satori Identify 鉴权")

    async def call_api(self, action: str, params: dict = None) -> dict:
        """调用 Satori API
        
        Satori 协议通过 WebSocket 发送 REQUEST 消息，服务端返回 RESPONSE。
        
        Args:
            action: API 名称，如 create_message, get_channels 等
            params: API 参数字典
            
        Returns:
            API 返回的数据字典，超时或失败返回空字典
        """
        if not self._ws or self._ws.closed:
            _logger.error("Satori WebSocket 未连接，无法调用 API")
            return {}
        
        import uuid
        echo = f"gracy_{uuid.uuid4().hex[:12]}"
        
        payload = {
            "op": 6,  # REQUEST opcode
            "d": {
                "action": action,
                "params": params or {},
            },
            "echo": echo,
        }
        
        # 创建 Future 等待响应
        future = asyncio.get_event_loop().create_future()
        self._pending[echo] = future
        
        try:
            await self._ws.send_json(payload)
            _logger.debug(f"Satori API 调用已发送: {action}")
            
            # 等待响应，超时 30 秒
            result = await asyncio.wait_for(future, timeout=30)
            return result
        except asyncio.TimeoutError:
            _logger.error(f"Satori API 调用超时: {action}")
            return {}
        except Exception as e:
            _logger.error(f"Satori API 调用异常: {e}")
            return {}
        finally:
            self._pending.pop(echo, None)

    async def _handle_message(self, data: dict):
        """处理接收到的 WebSocket 消息"""
        op = data.get("op")

        if op == SatoriOpcode.EVENT.value:
            # 事件分发
            event_data = parse_satori_event(data)
            if event_data:
                event = satori_event_to_gracy(event_data, self._tag)
                if event and self._on_event:
                    self._on_event(event)
        elif op == SatoriOpcode.RECONNECT.value:
            _logger.warning("Satori Gateway 收到重连指令")
            raise ConnectionError("收到重连指令")
        elif op == SatoriOpcode.INVALID_SESSION.value:
            _logger.error("Satori Gateway 会话无效，需要重新鉴权")
            raise ConnectionError("会话无效")
        elif op == SatoriOpcode.HEARTBEAT.value:
            _logger.debug("Satori Gateway 收到心跳确认")
        elif op == 6:  # RESPONSE
            echo = data.get("echo")
            if echo and echo in self._pending:
                self._pending[echo].set_result(data.get("d", {}))
                _logger.debug(f"Satori API 响应已收到: {echo}")
        else:
            _logger.debug(f"Satori Gateway 未知 op 类型: {op}")

    def _handle_hello(self, data: dict):
        """处理 Hello 消息，启动心跳"""
        d = data.get("d", {})
        self._heartbeat_interval = d.get("heartbeat_interval", 30.0) / 1000.0
        _logger.info(f"Satori Gateway 心跳间隔: {self._heartbeat_interval}s")

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def _heartbeat_loop(self):
        """心跳保活循环"""
        while self._running:
            try:
                await asyncio.sleep(self._heartbeat_interval * 0.9)

                if self._ws and not self._ws.closed:
                    await self._ws.send_json({
                        "op": SatoriOpcode.HEARTBEAT.value,
                        "d": None,
                    })
                    _logger.debug("Satori Gateway 心跳已发送")
            except asyncio.CancelledError:
                break
            except Exception as e:
                _logger.error(f"Satori Gateway 心跳异常: {e}")
                break
