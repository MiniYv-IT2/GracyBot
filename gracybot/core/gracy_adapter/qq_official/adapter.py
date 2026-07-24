"""QQ 官方个人机器人适配器 — 统一入口

实现 GracyAdapter 抽象类，整合：
- QQOfficialAPI: HTTP REST API（OAuth2、发消息）
- QQOfficialGateway: WebSocket Gateway 连接管理
- protocol: 协议转换（官方格式 ↔ GracyEvent/GracyMsg）
- sender: 消息发送高层封装
- bind: 主从绑定管理

用法:
    from gracybot.core.gracy_adapter.qq_official import QQOfficialAdapter

    adapter = QQOfficialAdapter(
        app_id="your_app_id",
        app_secret="your_app_secret",
        is_sandbox=True,
        robot_id="your_robot_id",
    )
    adapter.start(on_event=event_handler)
"""

import asyncio
import logging
import time
from typing import Callable, List, Optional

from gracybot.core.gracy_adapter.adapter import GracyAdapter
from gracybot.core.gracy_adapter.event import GracyEvent
from gracybot.core.gracy_adapter.identity import IdentityTag
from gracybot.core.gracy_adapter.message import GracyMsg, GracyText

from gracybot.core.gracy_adapter.qq_official.api import QQOfficialAPI
from gracybot.core.gracy_adapter.qq_official.gateway import QQOfficialGateway
from gracybot.core.gracy_adapter.qq_official.bind import MasterBinding
from gracybot.core.gracy_adapter.qq_official.sender import send_message

_logger = logging.getLogger("Adapter.QQOfficial")

# ── 调试埋点 ──
import urllib.request
_DEBUG_URL = "http://127.0.0.1:19809"
def _dbg(event: str, **kw):
    try:
        import json as _j
        data = _j.dumps({"event": event, **kw}).encode()
        urllib.request.urlopen(urllib.request.Request(f"{_DEBUG_URL}/debug", data=data), timeout=0.5)
    except:
        pass


class QQOfficialAdapter(GracyAdapter):
    """QQ 官方个人机器人适配器"""

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        is_sandbox: bool = False,
        robot_id: str = "",
        config_path: str = "",
    ):
        self._app_id = app_id
        self._app_secret = app_secret
        self._is_sandbox = is_sandbox
        self._robot_id = robot_id
        self._config_path = config_path

        self._on_event: Optional[Callable[[GracyEvent], None]] = None
        self._api = QQOfficialAPI(app_id, app_secret, is_sandbox)
        self._gateway: Optional[QQOfficialGateway] = None

        self._platform_info_cache: Optional[dict] = None
        self._platform_info_cache_time: float = 0
        self._binding = MasterBinding(config_path)

        # 被动回复状态
        self._last_msg_id: str = ""
        self._last_msg_id_time: float = 0.0

    # ── 生命周期 ──

    def start(self, on_event: Callable[[GracyEvent], None]) -> None:
        self._binding._runtime = self._runtime
        self._binding.load_state()

        def wrapped_event(event: GracyEvent) -> None:
            _dbg("adapter_wrapped_event", sender_id=event.sender_id, chat_type=event.chat_type, raw_text=str(event.raw_text)[:50])
            self._last_msg_id = event.message_id or ""
            self._last_msg_id_time = time.time()
            if self._handle_bind_command_sync(event):
                _dbg("adapter_bind_captured")
                return
            _dbg("adapter_forward_to_framework")
            if on_event:
                on_event(event)

        self._on_event = wrapped_event
        self._last_msg_id = ""
        self._last_msg_id_time = 0.0
        self._gateway = QQOfficialGateway(self._api, wrapped_event, self.tag)

        try:
            loop = asyncio.get_event_loop()
            loop.create_task(self._async_start())
        except RuntimeError:
            _logger.error("启动失败: 无运行中的事件循环")

    async def _async_start(self):
        _logger.info(f"正在启动适配器 (sandbox={self._is_sandbox})...")
        await self._gateway.start()
        _logger.info("适配器启动成功")

    def stop(self) -> None:
        _logger.info("正在停止适配器...")
        if self._gateway:
            try:
                loop = asyncio.get_event_loop()
                loop.create_task(self._gateway.stop())
            except RuntimeError:
                _logger.warning("停止 Gateway 失败: 无运行中的事件循环")

        try:
            loop = asyncio.get_event_loop()
            loop.create_task(self._api.close())
        except RuntimeError:
            pass
        _logger.info("适配器已停止")

    # ── 主从绑定 ──

    def _handle_bind_command_sync(self, event: GracyEvent) -> bool:
        text = (event.raw_text or "").strip()
        if event.chat_type != "private" or text not in ("/master_set", "/unbind"):
            return False
        loop = asyncio.get_event_loop()
        loop.create_task(self._handle_bind_command(event))
        return True

    async def _handle_bind_command(self, event: GracyEvent) -> bool:
        text = (event.raw_text or "").strip()
        sender_id = event.sender_id or ""
        chat_type = event.chat_type or "private"
        if chat_type != "private":
            return False

        async def _notify(msg: str):
            from gracybot.core.gracy_adapter.send import gracy_send_msg
            await gracy_send_msg(sender_id, GracyText(text=msg), chat_type=chat_type, tag=self.tag)

        if text == "/master_set":
            if self._binding.is_bound:
                await _notify("❌ 已经绑定了主人，无法再次绑定。如需更换请先输入 /unbind 解绑。")
                return True
            if self._binding.bind(sender_id):
                await _notify("✅ 主人绑定成功！您已被设为该机器人的主人。")
            return True

        if text == "/unbind":
            if not self._binding.is_bound:
                await _notify("❌ 当前未绑定主人，无需解绑。请输入 /master_set 进行绑定。")
                return True
            if self._binding.unbind(sender_id):
                await _notify("✅ 解绑成功！现在可以重新绑定新主人。")
            else:
                await _notify("❌ 只有当前绑定的主人才能解绑。")
            return True

        return False

    # ── 消息发送 ──

    async def send(self, target: str, segments: List[GracyMsg], chat_type: str) -> bool:
        return await send_message(
            api=self._api,
            target=target,
            segments=segments,
            chat_type=chat_type,
            last_msg_id=self._last_msg_id,
            last_msg_id_time=self._last_msg_id_time,
            tag=self.tag,
        )

    # ── 平台信息 ──

    async def get_platform_info(self) -> dict:
        now = time.time()
        if self._platform_info_cache and (now - self._platform_info_cache_time) < 60:
            return self._platform_info_cache

        bot_info = await self._api.get_bot_info()
        result = {
            "friend_count": None,
            "group_count": None,
            "platform": "QQOfficial",
            "protocol_version": "v2",
        }
        if bot_info:
            result["protocol_version"] = f"v2 (bot: {bot_info.get('username', 'unknown')})"

        self._platform_info_cache = result
        self._platform_info_cache_time = now
        return result

    def call_api(self, action: str, params: dict = None) -> Optional[dict]:
        return None


# backward compatibility: 从 factory 导出 create_adapter
from .factory import create_adapter  # noqa: E402, F401
