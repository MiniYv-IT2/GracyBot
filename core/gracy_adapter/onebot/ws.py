"""OneBot WebSocket 适配器 — 遵循 OneBot 11 标准

支持两种模式（统一使用 websockets 异步库）：
- 正向 WS（forward）：主动连接 OneBot 的 /ws 端点
- 反向 WS（reverse）：监听端口，等待 OneBot 客户端连接

依赖: pip install websockets

OneBot 11 标准 JSON 格式：
  入站: {"action": "send_msg", "params": {...}}
  出站: {"post_type": "message", ...}（与 HTTP 回调格式一致）

用法:
    # 正向
    adapter = GracyOneBotWS(mode="forward", host="127.0.0.1", port=3001)

    # 反向
    adapter = GracyOneBotWS(mode="reverse", host="0.0.0.0", port=8080)
"""

import asyncio
import json
import logging
import threading
import time
import queue
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, List, Optional

import websockets
import websockets.asyncio.client
import websockets.asyncio.server

from core.gracy_adapter.adapter import GracyAdapter
from core.gracy_adapter.event import GracyEvent
from core.gracy_adapter.message import GracyMsg
from core.gracy_adapter.onebot.cq import gracy_to_cq, cq_to_gracy


class GracyOneBotWS(GracyAdapter):
    """OneBot 11 WebSocket 适配器

    Args:
        mode: "forward"（主动连接）或 "reverse"（被动监听）
        host: 正向=OneBot 地址, 反向=监听地址
        port: 正向=OneBot WS 端口, 反向=监听端口
        access_token: OneBot access_token（可选）
        robot_id: 机器人 ID（用于 @检测）
    """

    def __init__(
        self,
        mode: str = "forward",
        host: str = "127.0.0.1",
        port: int = 3001,
        access_token: str = "",
        robot_id: str = "",
    ):
        if mode not in ("forward", "reverse"):
            raise ValueError(f"mode 必须为 'forward' 或 'reverse'，收到: {mode}")
        self._mode = mode
        self._host = host
        self._port = port
        self._access_token = access_token
        self._robot_id = robot_id
        self._on_event: Callable[[GracyEvent], None] | None = None
        self._running = False
        self._ws = None  # websockets 协议对象
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_thread: Optional[threading.Thread] = None
        self._api_lock = threading.Lock()  # 串行化 WS API 调用（多线程安全）
        self._api_condition = threading.Condition()  # API 响应等待
        self._api_responses: dict = {}  # echo → OneBot 响应数据
        self._api_send_queue: queue.Queue = queue.Queue()  # worker → recv_loop 发送队列
        self._queue_event: asyncio.Event | None = None  # 队列非空事件，唤醒 recv_loop
        self._pending_messages: list = []  # 未连接时暂存的消息，连上后补发
        self._event_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="ws_event_")
        self._logger = logging.getLogger("GracyOneBotWS")
        # 平台信息缓存，避免高频 API 调用刷屏日志
        self._platform_info_cache: dict | None = None
        self._platform_info_cache_time: float = 0.0
        self._platform_cache_lock = threading.Lock()  # 防多线程竞态重复更新

    # ── 出站：发送消息 ──

    def send(self, target: str, segments: List[GracyMsg], chat_type: str) -> bool:
        """发送消息到目标（走 WS send_msg action）"""
        cq_str = gracy_to_cq(segments)
        if not cq_str:
            self._logger.warning("[OneBotWS] 消息段列表为空")
            return False

        try:
            action_data = {
                "action": "send_msg",
                "params": {
                    "message_type": chat_type,
                    "user_id" if chat_type == "private" else "group_id": int(target),
                    "message": cq_str,
                },
                "echo": f"gracy_{int(time.time() * 1000)}",
            }
        except (ValueError, TypeError) as e:
            self._logger.error(f"[OneBotWS] 构造 send_msg 失败: target={target}, chat_type={chat_type}, err={e}")
            return False

        return self._ws_send(action_data)

    def call_api(self, action: str, params: dict = None, timeout: float = 5.0) -> Optional[dict]:
        """通过 WS 调用 OneBot API 并同步等待返回

        线程安全：使用 _api_lock 串行化，避免多条线程抢同一 recv。

        Args:
            action: OneBot action 名称（如 get_login_info, get_friend_list）
            params: action 参数
            timeout: 等待响应的超时时间（秒）

        Returns:
            成功返回 data 字段，失败返回 None
        """
        with self._api_lock:
            return self._call_api_impl(action, params, timeout)

    def _call_api_impl(self, action: str, params: dict, timeout: float) -> Optional[dict]:
        """call_api 的锁内实现 — 通过队列交 recv_loop 发送 + 条件变量等响应"""
        import time
        if not self._ws:
            self._logger.warning(f"[OneBotWS] call_api('{action}') 失败: 未连接")
            return None

        echo_id = f"gracy_api_{int(time.time() * 1000)}"
        t_api = time.time()
        action_data = {
            "action": action,
            "params": params or {},
            "echo": echo_id,
        }

        # 入队 → recv_loop 线程负责发送
        self._api_send_queue.put(action_data)
        # ★ 唤醒 recv_loop 立即 drain 队列，避免等 recv 超时
        if self._loop and self._loop.is_running() and self._queue_event:
            self._loop.call_soon_threadsafe(self._queue_event.set)

        # 等待 recv_loop 收到 API 响应后通知
        with self._api_condition:
            if echo_id not in self._api_responses:
                self._logger.debug(f"[OneBotWS] call_api('{action}') 等待响应 echo={echo_id}, timeout={timeout}s")
                self._api_condition.wait(timeout=timeout)
            data = self._api_responses.pop(echo_id, None)
            if data is None:
                self._logger.warning(f"[OneBotWS] call_api('{action}') 超时 耗时{time.time()-t_api:.1f}s: 未收到 echo={echo_id} 的响应")
                return None
            if data.get("status") == "ok":
                self._logger.debug(f"[OneBotWS⏱] call_api('{action}') 耗时 {time.time()-t_api:.1f}s")
                return data.get("data", {})
            self._logger.warning(
                f"[OneBotWS] API '{action}' 返回失败: "
                f"retcode={data.get('retcode')}, msg={data.get('msg', '')}"
            )
            return None

    def get_platform_info(self) -> dict:
        """获取 OneBot 平台统计信息（60 秒缓存，线程安全）"""
        import time
        from concurrent.futures import ThreadPoolExecutor
        now = time.time()
        # 快速路径：缓存有效则直接返回（无锁）
        if self._platform_info_cache is not None and (now - self._platform_info_cache_time) < 60:
            self._logger.debug(f"[OneBotWS⏱] get_platform_info 缓存命中")
            return self._platform_info_cache

        # 慢路径：加锁保证只有一个线程执行 API 调用
        with self._platform_cache_lock:
            # 双重检查：等锁期间其他线程可能已更新
            if self._platform_info_cache is not None and (time.time() - self._platform_info_cache_time) < 60:
                self._logger.debug(f"[OneBotWS⏱] get_platform_info 缓存命中（等锁后）")
                return self._platform_info_cache

            t_api = time.time()
            result = {
                "friend_count": None,
                "group_count": None,
                "platform": "OneBot",
                "protocol_version": None,
                "nickname": None,
            }
            try:
                with ThreadPoolExecutor(max_workers=4) as ex:
                    fut_friends = ex.submit(self.call_api, "get_friend_list")
                    fut_groups = ex.submit(self.call_api, "get_group_list")
                    fut_version = ex.submit(self.call_api, "get_version_info")
                    fut_login = ex.submit(self.call_api, "get_login_info")
                    friend_list = fut_friends.result(timeout=5)
                    group_list = fut_groups.result(timeout=5)
                    version_info = fut_version.result(timeout=5)
                    login_info = fut_login.result(timeout=5)
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
                self._logger.error(f"[OneBotWS] get_platform_info 失败: {type(e).__name__}: {e}")
            self._platform_info_cache = result
            self._platform_info_cache_time = time.time()
            self._logger.debug(f"[OneBotWS⏱] get_platform_info 耗时 {time.time() - t_api:.1f}s")
            return result

    # ── 入站：解析 OneBot JSON → GracyEvent ──

    def _parse_ws_message(self, data: dict) -> Optional[GracyEvent]:
        """将 OneBot WS 消息解析为 GracyEvent"""
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

        chat_type = data.get("message_type", "private")
        sender_id = str(data.get("user_id", ""))
        # 过滤机器人自己的消息（sub_type=self 或 userId==selfId 或 userId==robotId）
        if data.get("sub_type") == "self":
            return None
        self_id = str(data.get("self_id", ""))
        if self_id and sender_id == self_id:
            return None
        if self._robot_id and sender_id == self._robot_id:
            return None
        target_id = str(
            data.get("user_id", "") if chat_type == "private" else data.get("group_id", "")
        )
        raw_message = data.get("raw_message", "")
        # 自回显：OneBot 推送已发送消息时 raw_message 为空，直接丢弃
        if not raw_message.strip():
            return None
        nickname = ""
        if isinstance(data.get("sender"), dict):
            nickname = data["sender"].get("nickname", "")

        segments = cq_to_gracy(raw_message)

        raw_text = ""
        for seg in segments:
            from core.gracy_adapter.message import GracyText
            if isinstance(seg, GracyText):
                raw_text += seg.text

        is_at_bot = False
        if chat_type == "group" and self._robot_id:
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
        """启动 WebSocket 连接/监听（在独立线程运行 asyncio 事件循环）"""
        self._on_event = on_event
        self._running = True
        self._loop_thread = threading.Thread(
            target=self._run_loop, daemon=True, name="GracyWS-asyncio"
        )
        self._loop_thread.start()
        self._logger.info(f"[OneBotWS] {self._mode} 模式已启动 {self._host}:{self._port}")

    def stop(self) -> None:
        """停止 WebSocket 连接"""
        self._running = False
        self._pending_messages.clear()
        if self._loop and self._loop.is_running():
            # 调度关闭 WS 连接，让事件循环自然退出
            fut = asyncio.run_coroutine_threadsafe(self._close_ws(), self._loop)
            def _consume_close(f):
                try:
                    f.result()
                except Exception:
                    pass
            fut.add_done_callback(_consume_close)
        if self._loop_thread and self._loop_thread.is_alive():
            self._loop_thread.join(timeout=5)
        self._logger.info("[OneBotWS] 已停止")

    async def _close_ws(self) -> None:
        """优雅关闭 WS 连接"""
        if self._ws:
            await self._ws.close()
            self._ws = None

    async def _handle_connection(self, ws, label: str = "") -> None:
        """连接建立后的统一处理：补发暂存消息 → 收发循环

        正反向复用，消除重复代码。
        """
        self._ws = ws
        if label:
            self._logger.info(f"[OneBotWS] {label}")
        # 补发未连接时暂存的消息
        if self._pending_messages:
            self._logger.info(f"[OneBotWS] 补发 {len(self._pending_messages)} 条暂存消息")
            for data in self._pending_messages:
                try:
                    await ws.send(json.dumps(data, ensure_ascii=False))
                except Exception as e:
                    self._logger.error(f"[OneBotWS] 补发失败: {e}")
            self._pending_messages.clear()
        # 进入收发循环，直到连接断开
        await self._recv_loop(ws)
        self._ws = None

    # ── asyncio 事件循环 ──

    def _run_loop(self) -> None:
        """在独立线程中启动 asyncio 事件循环"""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._queue_event = asyncio.Event()
        try:
            if self._mode == "forward":
                self._loop.run_until_complete(self._forward_connect())
            else:
                self._loop.run_until_complete(self._reverse_listen())
        except Exception as e:
            self._logger.error(f"[OneBotWS] 事件循环异常退出: {type(e).__name__}: {e}")
        finally:
            self._loop.close()
            self._loop = None

    # ── 内部：正向连接 ──

    # ╔══════════════════════════════════════════════════════════════╗
    # ║ 架构约束（禁止违反，否则导致 call_api 死锁/超时）         ║
    # ║ 1. recv_loop 是本线程唯一 WS 收发者，绝不可阻塞          ║
    # ║ 2. 事件处理必须用 _event_executor.submit() 异步派发      ║
    # ║ 3. 其他线程发 API 请求必须走 _api_send_queue 队列        ║
    # ║ 4. API 响应通过 _api_condition 条件变量路由              ║
    # ╚══════════════════════════════════════════════════════════════╝

    async def _forward_connect(self) -> None:
        """主动连接 OneBot WS 端点，断线自动重连"""
        ws_url = f"ws://{self._host}:{self._port}"
        if self._access_token:
            ws_url += f"?access_token={self._access_token}"

        while self._running:
            try:
                async for ws in websockets.asyncio.client.connect(
                    ws_url,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=1,
                ):
                    await self._handle_connection(ws, f"正向连接成功: {ws_url}")
            except Exception as e:
                self._logger.error(f"[OneBotWS] 正向连接失败: {type(e).__name__}: {e}")

            # 断线重连
            if self._running:
                self._logger.info("[OneBotWS] 5秒后重连...")
                await asyncio.sleep(5)

    # ── 内部：反向监听 ──

    async def _reverse_listen(self) -> None:
        """监听端口，等待 OneBot 客户端连接"""
        self._logger.info(f"[OneBotWS] 反向监听 {self._host}:{self._port}")

        async def on_connect(ws):
            """每次有新客户端连入时回调"""
            addr = ws.remote_address
            await self._handle_connection(ws, f"反向连接接入: {addr}")

        server = await websockets.asyncio.server.serve(
            on_connect, self._host, self._port,
            ping_interval=20,
            ping_timeout=10,
            close_timeout=1,
        )

        # 保持 server 存活，直到停止
        while self._running:
            await asyncio.sleep(1)

        server.close()
        await server.wait_closed()

    # ── 内部：共享收发循环 ──

    async def _recv_loop(self, ws) -> None:
        """共享的接收循环（正反向通用）

        使用 asyncio.wait 双监听：
        - ws.recv()：接收 OneBot 推送的消息/API 响应
        - _queue_event：call_api 入队后触发，立即唤醒 drain 队列

        避免旧版「先 recv(timeout=0.5) 再 drain」带来的串行延迟。
        """
        while self._running:
            # ★ 消费 worker 线程入队的 API 请求（由本线程发送）
            await self._drain_api_send_queue_async(ws)

            # 双监听：recv 或 队列事件（入队即唤醒）
            self._queue_event.clear()
            recv_task = asyncio.create_task(ws.recv())
            event_task = asyncio.create_task(self._queue_event.wait())

            done, pending = await asyncio.wait(
                [recv_task, event_task],
                timeout=0.5,
                return_when=asyncio.FIRST_COMPLETED,
            )

            for task in pending:
                task.cancel()

            if recv_task in done:
                try:
                    raw = recv_task.result()
                except websockets.ConnectionClosed as e:
                    self._logger.warning(f"[OneBotWS] 远端关闭连接: {e}")
                    break
                if not isinstance(raw, str):
                    continue
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError as e:
                    self._logger.warning(f"[OneBotWS] JSON 解析失败: {e} | raw={raw[:200]}")
                    continue

                # API 响应（有 echo 字段 + status 是字符串）→ 路由给 call_api
                status_val = data.get("status")
                if isinstance(status_val, str) and "echo" in data:
                    echo = data.get("echo", "")
                    self._logger.debug(f"[OneBotWS] 收到 API 响应 echo={echo}, status={status_val}")
                    with self._api_condition:
                        self._api_responses[echo] = data
                        self._api_condition.notify_all()
                    continue

                # 事件消息 → EventBus → Pipeline
                event = self._parse_ws_message(data)
                if event:
                    try:
                        from core.event import event_bus
                        await event_bus.publish(event)
                    except Exception as e:
                        self._logger.error(f"[OneBotWS] EventBus 发送失败: {e}")
            # else: event fired or timeout → loop back to drain queue immediately

    async def _drain_api_send_queue_async(self, ws) -> None:
        """消费 worker 线程入队的 API 请求（异步版，recv_loop 内调用）"""
        while not self._api_send_queue.empty():
            action_data = self._api_send_queue.get_nowait()
            self._logger.debug(
                f"[OneBotWS] recv_loop 发送 API: "
                f"action={action_data.get('action')}, echo={action_data.get('echo')}"
            )
            try:
                await ws.send(json.dumps(action_data, ensure_ascii=False))
            except websockets.ConnectionClosed:
                # 连接断开时把请求放回队列，下次重连后重试
                self._api_send_queue.put(action_data)
                break

    # ── 内部辅助 ──

    def _ws_send(self, data: dict) -> bool:
        """线程安全的 WS 发送（可从任意线程调用）

        通过 asyncio.run_coroutine_threadsafe 将发送任务投递到事件循环线程执行。
        未连接时暂存到 _pending_messages，连上后自动补发。
        """
        if not self._ws or not self._loop or not self._loop.is_running():
            if self._running:
                self._pending_messages.append(data)
                count = len(self._pending_messages)
                self._logger.info(f"[OneBotWS] 未连接，消息暂存（共{count}条）")
                return False  # 未真正发送，告知调用方
            self._logger.warning("[OneBotWS] 未连接且已停止，无法发送")
            return False
        try:
            payload = json.dumps(data, ensure_ascii=False)
            fut = asyncio.run_coroutine_threadsafe(
                self._ws.send(payload), self._loop
            )
            # 消费 Future 异常，避免 Windows ProactorEventLoop 下
            # "_OverlappedFuture exception was never retrieved" 警告刷屏
            def _consume(f):
                try:
                    f.result()
                except Exception as e:
                    self._logger.debug(f"[OneBotWS] 发送异常（已消费）: {e}")
            fut.add_done_callback(_consume)
            return True
        except Exception as e:
            self._logger.error(f"[OneBotWS] 发送失败: {e}")
            return False