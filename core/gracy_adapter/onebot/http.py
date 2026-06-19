"""OneBot HTTP 适配器 — 基于 OneBot 11 HTTP API

入站：复用现有 Flask /callback → 解析 OneBot JSON → GracyEvent
出站：GracyMsg → CQ 码 → POST NapCat HTTP API

用法:
    from core.gracy_adapter.onebot.http import GracyOneBot

    adapter = GracyOneBot(napcat_url="http://127.0.0.1:3000", callback_port=3002)
    adapter.send(target, [GracyText("hello")], "private")
"""

import asyncio
import json
import logging
import time
from typing import Callable, List, Optional

import aiohttp

from core.gracy_adapter.adapter import GracyAdapter
from core.gracy_adapter.event import GracyEvent
from core.gracy_adapter.message import GracyMsg
from core.gracy_adapter.onebot.cq import gracy_to_cq, cq_to_gracy


class GracyOneBot(GracyAdapter):
    """OneBot 11 HTTP 适配器

    入站：OneBot POST CQ 码 JSON → cq_to_gracy() → GracyEvent
    出站：GracyMsg → gracy_to_cq() → POST /send_private_msg 或 /send_group_msg

    Attributes:
        napcat_url: NapCat HTTP API 地址（默认 http://127.0.0.1:3000）
        callback_port: Flask 回调监听端口（默认 3002）
        robot_id: 机器人 ID（用于群聊 @bot 检测，由调用方注入）
    """

    def __init__(
        self,
        napcat_url: str = "http://127.0.0.1:3000",
        callback_port: int = 3002,
        robot_id: str = "",
    ):
        self._napcat_url = napcat_url.rstrip("/")
        self._callback_port = callback_port
        self._robot_id = robot_id
        self._on_event: Callable[[GracyEvent], None] | None = None
        self._logger = logging.getLogger("GracyOneBot")
        self._platform_info_cache: dict | None = None
        self._platform_info_cache_time: float = 0
        self._session: aiohttp.ClientSession | None = None

    # ── 出站：发送消息 ──

    async def send(self, target: str, segments: List[GracyMsg], chat_type: str) -> bool:
        """发送消息到目标

        Args:
            target: 目标 ID（私聊=用户QQ，群聊=群号）
            segments: GracyMsg 列表
            chat_type: "private" | "group"
        """
        cq_str = gracy_to_cq(segments)
        if not cq_str:
            self._logger.warning("[OneBot] 消息段列表为空，跳过发送")
            return False

        if chat_type == "private":
            url = f"{self._napcat_url}/send_private_msg"
            payload = {"user_id": int(target), "message": cq_str}
        else:
            url = f"{self._napcat_url}/send_group_msg"
            payload = {"group_id": int(target), "message": cq_str}

        try:
            session = await self._get_session()
            async with session.post(
                url,
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json; charset=utf-8"},
                timeout=aiohttp.ClientTimeout(total=None),
            ) as resp:
                if resp.status != 200:
                    self._logger.error(f"[OneBot] HTTP状态码 {resp.status}")
                    return False
                result = await resp.json()
                success = result.get("retcode") == 0
                if not success:
                    self._logger.error(f"[OneBot] 发送失败: {result.get('msg', '未知错误')}")
                return success
        except (asyncio.TimeoutError, TimeoutError):
            self._logger.error("[OneBot] 发送超时")
            return False
        except aiohttp.ClientError as e:
            self._logger.error(f"[OneBot] 连接 NapCat 失败: {e}")
            return False
        except Exception as e:
            self._logger.error(f"[OneBot] 发送异常: {e}")
            return False

    # ── 入站：解析 OneBot JSON → GracyEvent ──

    def parse_event(self, data: dict) -> GracyEvent | None:
        """将 OneBot 原始 JSON 解析为 GracyEvent

        由外部 Flask /callback 调用，传入 request.get_json() 结果。
        返回 None 表示非消息事件（心跳/metaevent等），应忽略。
        """
        post_type = data.get("post_type", "")
        if post_type == "meta_event":
            return None
        if post_type not in ("message", "notice"):
            return None
        # 过滤输入状态通知（对方正在输入...），避免产生空消息日志
        if data.get("notice_type") == "notify" and data.get("sub_type") == "input_status":
            return None
        # 点赞通知不是消息，没有内容可处理
        if data.get("notice_type") == "like":
            return None

        # ── 过滤机器人自己的消息（自回显） ──
        if data.get("sub_type") == "self":
            return None
        self_id = str(data.get("self_id", ""))
        sender_id = str(data.get("user_id", ""))
        if self_id and sender_id == self_id:
            return None
        if self._robot_id and sender_id == self._robot_id:
            return None

        chat_type = data.get("message_type", "private")
        target_id = str(
            data.get("user_id", "") if chat_type == "private" else data.get("group_id", "")
        )
        raw_message = data.get("raw_message", "")
        # 没有消息内容（如纯通知事件），直接丢弃
        if not raw_message.strip():
            return None
        nickname = ""
        if isinstance(data.get("sender"), dict):
            nickname = data["sender"].get("nickname", "")

        # 解析 CQ 码 → GracyMsg 列表
        segments = cq_to_gracy(raw_message)

        # 提取纯文本
        raw_text = ""
        for seg in segments:
            from core.gracy_adapter.message import GracyText
            if isinstance(seg, GracyText):
                raw_text += seg.text

        # 判断是否 @了机器人
        is_at_bot = False
        if chat_type == "group":
            if self._robot_id:
                for seg in segments:
                    from core.gracy_adapter.message import GracyAt
                    if isinstance(seg, GracyAt) and seg.target_id == self._robot_id:
                        is_at_bot = True
                        break

        return GracyEvent(
            sender_id=sender_id,
            target_id=target_id,
            chat_type=chat_type,
            segments=segments,
            raw_text=raw_text,
            message_id=str(data.get("message_id", "")),
            nickname=nickname,
            is_at_bot=is_at_bot,
            raw_data=data,
        )

    # ── 生命周期 ──

    def start(self, on_event: Callable[[GracyEvent], None]) -> None:
        """注册事件回调（Flask 服务由 core.main 独立启动）"""
        self._on_event = on_event

    def stop(self) -> None:
        """释放资源"""
        self._on_event = None
        if self._session:
            asyncio.ensure_future(self._session.close())
            self._session = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建 aiohttp 会话（惰性初始化）"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    # ── API 调用 ──

    async def call_api(self, action: str, params: dict = None) -> Optional[dict]:
        """通过 HTTP 调用 OneBot API"""
        try:
            url = f"{self._napcat_url}/{action}"
            session = await self._get_session()
            async with session.post(
                url,
                data=json.dumps(params or {}, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json; charset=utf-8"},
                timeout=aiohttp.ClientTimeout(total=None),
            ) as resp:
                if resp.status != 200:
                    self._logger.warning(f"[OneBot] API '{action}' HTTP状态码 {resp.status}")
                    return None
                result = await resp.json()
                if result.get("retcode") == 0:
                    return result.get("data")
                self._logger.warning(f"[OneBot] API '{action}' 返回失败: {result.get('msg', '')}")
                return None
        except Exception as e:
            self._logger.debug(f"[OneBot] HTTP API '{action}' 调用失败: {e}")
            return None

    async def get_platform_info(self) -> dict:
        """获取 OneBot 平台统计信息（60 秒缓存，避免高频调用刷屏日志）"""
        now = time.time()
        if self._platform_info_cache is not None and (now - self._platform_info_cache_time) < 60:
            return self._platform_info_cache

        result = {
            "friend_count": None,
            "group_count": None,
            "platform": "OneBot",
            "protocol_version": None,
            "nickname": None,
        }
        try:
            friend_list, group_list, version_info, login_info = await asyncio.gather(
                self.call_api("get_friend_list"),
                self.call_api("get_group_list"),
                self.call_api("get_version_info"),
                self.call_api("get_login_info"),
            )
            if isinstance(friend_list, list):
                result["friend_count"] = len(friend_list)
            if isinstance(group_list, list):
                result["group_count"] = len(group_list)
            if isinstance(version_info, dict):
                app_name = version_info.get("app_name", "")
                app_ver = version_info.get("app_version", "")
                result["protocol_version"] = f"{app_name} {app_ver}".strip()
            if isinstance(login_info, dict):
                result["nickname"] = login_info.get("nickname", "")
        except Exception as e:
            self._logger.error(f"[OneBot] get_platform_info 失败: {type(e).__name__}: {e}")
        self._platform_info_cache = result
        self._platform_info_cache_time = now
        return result

    # ── 内部 ──

    @property
    def callback_port(self) -> int:
        return self._callback_port
