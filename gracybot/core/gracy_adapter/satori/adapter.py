"""Satori 适配器 — 基于 satori-python-client 的多平台接入

支持平台：QQ（通过 NapCat+Koishi）、Telegram、Discord、飞书（Lark）、微信（WeChat/WeCom）、钉钉（DingTalk）、Kook、Minecraft 等（通过 Satori 协议）

实现 GracyAdapter 抽象类，整合 satori-python-client：
- App: Satori 客户端连接管理
- event: 事件转换（Satori Event → GracyEvent）
- message: 消息转换

用法:
    from gracybot.core.gracy_adapter.satori import SatoriAdapter

    adapter = SatoriAdapter(host="127.0.0.1", port=5140, token="your-token")
    adapter.start(on_event=event_handler)
"""

import asyncio
import json
import logging
import os
from typing import Callable, List, Optional

from gracybot.core.gracy_adapter.adapter import GracyAdapter
from gracybot.core.gracy_adapter.event import GracyEvent
from gracybot.core.gracy_adapter.identity import IdentityTag
from gracybot.core.gracy_adapter.message import GracyMsg, GracyText

_logger = logging.getLogger("Adapter.Satori")


class SatoriAdapter(GracyAdapter):
    """Satori 协议适配器（基于 satori-python-client）"""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 5140,
        token: str = "",
        path: str = "",
        config: dict = None,
    ):
        self._host = host
        self._port = port
        self._token = token
        self._path = path
        self._config = config or {}

        self._on_event: Optional[Callable[[GracyEvent], None]] = None
        self._app = None
        self._account = None
        self._self_id: str = ""
        self._self_name: str = ""
        self._login_cache: dict = {}
        self._platform_info_cache: Optional[dict] = None
        self._platform_info_cache_time: float = 0
        self._task: Optional[asyncio.Task] = None
        self._ready: asyncio.Event = asyncio.Event()
        self._pending_messages: list = []  # 未连接时暂存的消息

    # ── 生命周期 ──

    def start(self, on_event: Callable[[GracyEvent], None]) -> None:
        """启动适配器，开始监听消息"""
        self._on_event = on_event

        try:
            loop = asyncio.get_event_loop()
            self._task = loop.create_task(self._async_start())
        except RuntimeError:
            _logger.error("Satori 适配器启动失败: 无运行中的事件循环")

    async def _async_start(self):
        """异步启动 Satori 客户端"""
        from satori.client import App, WebsocketsInfo

        try:
            from loguru import logger as loguru_logger
            loguru_logger.disable("launart")
            loguru_logger.disable("satori")
        except ImportError:
            pass

        _logger.info(f"Satori 适配器正在启动 ({self._host}:{self._port}{self._path})...")

        self._app = App(
            WebsocketsInfo(
                host=self._host,
                port=self._port,
                path=self._path,
                token=self._token or None,
            )
        )

        adapter_self = self

        async def _on_account_update(account, state):
            """账号状态更新回调"""
            adapter_self._account = account
            if hasattr(account, 'self_id'):
                adapter_self._self_id = str(account.self_id)
            try:
                login = await account.protocol.login_get()
                if login and login.user:
                    adapter_self._login_cache = {
                        "user_id": str(login.user.id),
                        "nickname": login.user.name or login.user.nick or "",
                        "avatar_url": login.user.avatar or "",
                    }
                try:
                    friends = await account.protocol.call_api("friend.list", {})
                    if isinstance(friends, dict) and "data" in friends:
                        adapter_self._login_cache["friend_count"] = len(friends["data"])
                except Exception:
                    pass
                try:
                    guilds = await account.protocol.call_api("guild.list", {})
                    if isinstance(guilds, dict) and "data" in guilds:
                        adapter_self._login_cache["group_count"] = len(guilds["data"])
                except Exception:
                    pass
            except Exception:
                pass
            if not adapter_self._ready.is_set():
                adapter_self._ready.set()
                _logger.info(f"Satori 连接就绪，account: {account}, state: {state}")
                # 补发暂存消息（OneBot 同款逻辑）
                if adapter_self._pending_messages:
                    _logger.debug(f"补发 {len(adapter_self._pending_messages)} 条暂存消息")
                    pending = adapter_self._pending_messages[:]
                    adapter_self._pending_messages.clear()
                    for target, segments, chat_type in pending:
                        try:
                            await adapter_self.send(target, segments, chat_type)
                        except Exception as e:
                            _logger.error(f"[Satori] 补发失败: {e}")

        self._app.lifecycle_callbacks.append(_on_account_update)

        @self._app.register
        async def _handle_event(account, event):
            """Satori 事件回调 → GracyEvent"""
            adapter_self._account = account
            if not adapter_self._ready.is_set():
                adapter_self._ready.set()
            _logger.debug(f"收到事件: type={event.type}")
            try:
                gracy_event = _satori_event_to_gracy(event, adapter_self.tag)
                if gracy_event and adapter_self._on_event:
                    _logger.debug(f"事件转换成功: {gracy_event.raw_text}")
                    adapter_self._on_event(gracy_event)
                else:
                    _logger.debug(f"事件转换返回 None: type={event.type}")
            except Exception as e:
                _logger.error(f"Satori 事件转换异常: {e}", exc_info=True)

        _logger.debug(f"event_callbacks 数量: {len(self._app.event_callbacks)}")
        await self._app.run_async()

    def stop(self) -> None:
        """停止适配器，释放资源"""
        _logger.info("Satori 适配器正在停止...")
        self._pending_messages.clear()
        if self._task and not self._task.done():
            self._task.cancel()
        if self._app:
            try:
                loop = asyncio.get_event_loop()
                loop.create_task(self._app.shutdown())
            except RuntimeError:
                pass
        _logger.info("Satori 适配器已停止")

    # ── 消息发送 ──

    async def send(self, target: str, segments: List[GracyMsg], chat_type: str) -> bool:
        """发送消息到指定目标

        Args:
            target: 目标 ID（用户QQ号或群号）
            segments: GracyMsg 消息段列表
            chat_type: "private" | "group"
        """
        if not segments:
            return False

        _logger.info(f"send called: target={target!r} chat_type={chat_type!r}")

        # 未连接时暂存（OneBot 同款逻辑）
        if not self._ready.is_set() or not self._account:
            self._pending_messages.append((target, segments, chat_type))
            _logger.debug(f"未连接，消息暂存（共{len(self._pending_messages)}条）")
            return False

        try:
            from satori.element import Image, Audio, File, Video, At
            from gracybot.core.gracy_adapter.message import GracyText, GracyImage, GracyVoice, GracyFile, GracyForward, GracyAt as GracyAtMsg

            elements = []
            for seg in segments:
                if isinstance(seg, GracyText):
                    if seg.text:
                        elements.append(seg.text)
                elif isinstance(seg, GracyImage):
                    url = seg.url or seg.file_path
                    if url:
                        if url.startswith(("http://", "https://", "data:")):
                            elements.append(Image(src=url))
                        else:
                            from gracybot.core.gracy_adapter.satori.message import _file_to_data_url
                            data_url = _file_to_data_url(url)
                            if data_url:
                                elements.append(Image(src=data_url))
                elif isinstance(seg, GracyVoice):
                    if seg.file_path:
                        if seg.file_path.startswith(("http://", "https://", "data:")):
                            elements.append(Audio(src=seg.file_path))
                        else:
                            elements.append(Audio.of(path=seg.file_path))
                elif isinstance(seg, GracyFile):
                    url = seg.url or seg.file_path
                    if url:
                        if url.startswith(("http://", "https://", "data:")):
                            elements.append(File(src=url))
                        else:
                            elements.append(File.of(path=url))
                elif isinstance(seg, GracyVideo):
                    url = seg.url or seg.file_path
                    if url:
                        if url.startswith(("http://", "https://", "data:")):
                            elements.append(Video(src=url))
                        else:
                            elements.append(Video.of(path=url))
                elif isinstance(seg, GracyAtMsg):
                    elements.append(At(id=seg.target_id))

            if not elements:
                return False

            if target.startswith("private:") or target.startswith("group:"):
                channel_id = target
            elif chat_type == "private":
                channel_id = f"private:{target}"
            else:
                channel_id = target
            try:
                await asyncio.wait_for(
                    self._account.protocol.send_message(
                        channel=channel_id,
                        message=elements,
                    ),
                    timeout=15.0,
                )
            except asyncio.TimeoutError:
                _logger.error(f"发送超时(15s): {chat_type} -> {target}")
                return False
            _logger.info(f"消息发送成功: {chat_type} -> {target}")
            return True
        except Exception as e:
            _logger.error(f"发送异常: {e}", exc_info=True)
            return False

    # ── 平台信息 ──

    def get_platform_info(self) -> dict:
        import time
        now = time.time()
        if self._platform_info_cache and (now - self._platform_info_cache_time) < 60:
            return self._platform_info_cache

        result = {
            "friend_count": None,
            "group_count": None,
            "platform": "Satori",
            "protocol_version": "1.0",
            "user_id": None,
            "nickname": None,
        }

        if self._login_cache:
            result.update(self._login_cache)

        self._platform_info_cache = result
        self._platform_info_cache_time = now
        return result

    # ── 工厂函数 ──

    @staticmethod
    def create_adapter(config: dict) -> "SatoriAdapter":
        """根据配置创建 SatoriAdapter 实例"""
        host = config.get("host", "127.0.0.1")
        port = config.get("port", 5140)
        token = config.get("token", "")
        path = config.get("path", "")

        adapter = SatoriAdapter(
            host=host,
            port=port,
            token=token,
            path=path,
            config=config,
        )
        adapter.conn_type_display = "WebSocket"
        return adapter


def create_adapter(config: dict) -> "SatoriAdapter":
    """模块级工厂函数，供 main.py 动态加载调用"""
    return SatoriAdapter.create_adapter(config)


def _satori_event_to_gracy(event, tag: IdentityTag) -> Optional[GracyEvent]:
    """将 satori-python 的 Event 转换为 GracyEvent"""
    from satori.model import ChannelType
    from gracybot.core.gracy_adapter.message import GracyAt

    # 只处理消息创建事件（Satori 协议用连字符）
    if event.type != "message-created":
        _logger.debug(f"忽略 Satori 事件类型: {event.type}")
        return None

    # 提取消息数据
    message = event.message
    if not message:
        return None

    user = event.user
    if not user:
        return None

    sender_id = str(user.id) if user.id else ""
    nickname = user.name or ""

    if not sender_id:
        return None

    self_id = ""
    for src in ("login", "self", "account"):
        obj = getattr(event, src, None)
        if obj:
            uid = getattr(obj, "user_id", None) or getattr(getattr(obj, "user", None), "id", None)
            if uid:
                self_id = str(uid)
                break

    if self_id and sender_id == self_id:
        _logger.debug(f"忽略自身消息: sender={sender_id}")
        return None

    channel = event.channel
    guild = getattr(event, 'guild', None)

    if channel and hasattr(channel, 'type'):
        chat_type = "private" if channel.type == ChannelType.DIRECT else "group"
    else:
        chat_type = "private"

    if chat_type == "private":
        target_id = str(channel.id) if channel else ""
    else:
        target_id = str(guild.id) if guild else (str(channel.id) if channel else "")
    _logger.info(f"target={target_id} chat={chat_type} ch_id={channel.id if channel else '?'} guild_id={guild.id if guild else '?'} ch_type={channel.type if channel else '?'}")

    from gracybot.core.gracy_adapter.satori.message import satori_to_gracy, extract_plain_text
    elements = getattr(message, 'message', None) or message.content
    segments = satori_to_gracy(elements)
    raw_text = extract_plain_text(segments).strip()

    message_id = str(message.id) if message.id else ""

    # 检测 @机器人
    is_at_bot = any(
        seg.target_id == self_id
        for seg in segments
        if isinstance(seg, GracyAt)
    ) if self_id else False

    raw_data = {"satori_event": event} if hasattr(event, '__dict__') else {}
    if chat_type == "group" and guild:
        raw_data["group_id"] = guild.id

    return GracyEvent(
        sender_id=sender_id,
        target_id=target_id or sender_id,
        chat_type=chat_type,
        segments=segments,
        raw_text=raw_text,
        message_id=message_id,
        nickname=nickname,
        is_at_bot=is_at_bot,
        raw_data=raw_data,
        source=tag,
    )
