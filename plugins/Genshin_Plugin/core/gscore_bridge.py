"""
早柚核心(GsCore) WebSocket 桥接模块

负责：
  - 连接早柚核心 WebSocket 服务
  - 发送 MessageReceive 消息包
  - 接收 MessageSend 消息包
  - 自动重连 / 心跳保活
  - 图片下载与缓存
"""
import asyncio
import base64
import io
import json
import logging
import os
import time
import uuid
from typing import List, Optional, Tuple

import httpx

try:
    from PIL import Image

    _has_pil = True
except ImportError:
    _has_pil = False

try:
    import qrcode
    from qrcode.constants import ERROR_CORRECT_L

    _has_qrcode = True
except ImportError:
    _has_qrcode = False

_logger = logging.getLogger("Gracy.Genshin.GsCoreBridge")

# ── 默认配置 ──
GSCORE_HOST = "127.0.0.1"
GSCORE_PORT = 8765
BOT_ID = "gracybot"
RECONNECT_INTERVAL = 5  # 秒
TIMEOUT = 25  # 等待 GsCore 响应超时
COLLECT_WINDOW = 1.5  # 收集多条回复的时间窗口

# 数据目录（缓存图片用）
_PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CACHE_DIR = os.path.join(_PLUGIN_DIR, "data", "cache")


# ── GsCore 协议数据结构（轻量版，不依赖 msgspec） ──
def _make_message_receive(
    user_id: str,
    user_type: str,
    text: str,
    group_id: str = "",
    bot_id: str = BOT_ID,
) -> str:
    """构造 MessageReceive JSON 字符串"""
    msg_id = uuid.uuid4().hex[:12]
    payload = {
        "bot_id": bot_id,
        "bot_self_id": "",
        "msg_id": msg_id,
        "user_type": user_type,
        "user_id": user_id,
        "sender": {},
        "content": [{"type": "text", "data": text}],
    }
    if user_type == "group" and group_id:
        payload["group_id"] = group_id
    return json.dumps(payload, ensure_ascii=False)


def _parse_message_send(data: bytes) -> Optional[dict]:
    """解析 MessageSend 二进制响应"""
    try:
        return json.loads(data.decode("utf-8"))
    except Exception:
        return None


def _extract_messages(resp: dict) -> List[Tuple[str, str]]:
    """从 MessageSend 中提取 (type, data) 列表

    支持嵌套展开：
      - type=text     → ("text", data)
      - type=image    → ("image", data)
      - type=node     → 递归展开内部的 text/image
      - type=group    → 跳过（群组标识，非消息内容）
      - type=buttons  → 跳过（按钮，暂不支持）
      - type=log_*    → 跳过（GsCore 内部日志）
      - type=at       → 跳过
      - type=image_size → 跳过
    """
    items = []
    for msg in resp.get("content") or []:
        msg_type = msg.get("type", "")
        msg_data = msg.get("data", "")

        # 跳过元数据/日志类型
        if msg_type in ("group", "buttons", "at", "image_size") or msg_type.startswith("log_"):
            continue

        if msg_type == "node":
            if isinstance(msg_data, list):
                _recursive_extract(msg_data, items)
            elif isinstance(msg_data, str):
                items.append(("text", msg_data))
            continue

        if msg_type and msg_data is not None:
            items.append((msg_type, str(msg_data)))

    return items


def _recursive_extract(msg_list: list, items: List[Tuple[str, str]]):
    """递归提取嵌套消息列表"""
    for sub in msg_list:
        if not isinstance(sub, dict):
            continue
        sub_type = sub.get("type", "")
        sub_data = sub.get("data", "")

        if sub_type in ("group", "buttons", "at", "image_size") or sub_type.startswith("log_"):
            continue

        if sub_type == "node" and isinstance(sub_data, list):
            _recursive_extract(sub_data, items)
            continue

        if sub_type and sub_data is not None:
            items.append((sub_type, str(sub_data)))


# ── 米游社扫码登录（自定义实现，不依赖 GsCore） ──
# 使用 passport-api.miyoushe.com 新版接口（UIGF 推荐）

_MIHOYO_CREATE_QR = "https://passport-api.miyoushe.com/account/ma-cn-passport/web/createQRLogin"
_MIHOYO_CHECK_QR = "https://passport-api.miyoushe.com/account/ma-cn-passport/web/queryQRLoginStatus"


async def _create_qrcode() -> Optional[dict]:
    """调用 passport API 创建二维码（带完整请求头）"""
    import random
    import string
    device_id = ''.join(random.choices(string.ascii_letters + string.digits, k=64))
    headers = {
        "x-rpc-app_id": "bll8iq97cem8",
        "x-rpc-device_id": device_id,
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Linux; Android 13; PHK110 Build/SKQ1.221119.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/118.0.0.0 Mobile Safari/537.36 miHoYoBBS/2.70.1",
        "Referer": "https://webstatic.mihoyo.com/",
        "Origin": "https://webstatic.mihoyo.com/",
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                _MIHOYO_CREATE_QR,
                headers=headers,
                timeout=15,
            )
            data = resp.json()
            _logger.info(f"[扫码] 创建二维码响应: retcode={data.get('retcode')}")
            if data.get("retcode") != 0:
                _logger.warning(f"[扫码] 创建二维码失败: {data}")
                return None
            url: str = data["data"]["url"]
            ticket: str = data["data"]["ticket"]
            _logger.info(f"[扫码] 二维码已创建, ticket={ticket[:16]}...")
            return {"url": url, "ticket": ticket, "device_id": device_id}
    except Exception as e:
        _logger.warning(f"[扫码] 创建二维码异常: {e}")
        return None


async def _poll_qrcode(
    ticket: str, device_id: str, timeout: int = 120
) -> Optional[dict]:
    """轮询扫码状态（passport API），成功返回带 Set-Cookie 的完整响应"""
    payload = {"ticket": ticket}
    deadline = time.time() + timeout

    while time.time() < deadline:
        await asyncio.sleep(2)
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    _MIHOYO_CHECK_QR,
                    json=payload,
                    headers={
                        "x-rpc-app_id": "bll8iq97cem8",
                        "x-rpc-device_id": device_id,
                        "Content-Type": "application/json",
                        "User-Agent": "Mozilla/5.0 (Linux; Android 13; PHK110 Build/SKQ1.221119.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/118.0.0.0 Mobile Safari/537.36 miHoYoBBS/2.70.1",
                        "Referer": "https://webstatic.mihoyo.com/",
                        "Origin": "https://webstatic.mihoyo.com/",
                    },
                    timeout=15,
                )
                data = resp.json()
                retcode = data.get("retcode", 0)
                if retcode == -3501:
                    _logger.warning("[扫码] 二维码已过期")
                    return None
                if retcode != 0:
                    _logger.warning(f"[扫码] 查询状态异常: retcode={retcode}")
                    continue

                status = data.get("data", {}).get("status", "Created")
                _logger.info(f"[扫码] 状态: {status}")

                if status == "Confirmed":
                    _logger.info("[扫码] 已确认，提取 Cookie...")
                    # passport API 通过 Set-Cookie 返回登录凭证
                    set_cookies = resp.headers.get_list("set-cookie")
                    cookie_str = "; ".join(set_cookies) if set_cookies else ""
                    _logger.info(f"[扫码] 获取到 {len(set_cookies)} 个 set-cookie")
                    return {"status": "Confirmed", "cookie_raw": cookie_str, "raw_cookies": set_cookies}

                if status == "Scanned":
                    _logger.info("[扫码] 已扫描，等待确认...")

        except Exception as e:
            _logger.warning(f"[扫码] 轮询异常: {e}")
            continue

    _logger.warning("[扫码] 轮询超时")
    return None




def _make_qr_image(url: str) -> bytes:
    """根据 URL 生成二维码 PNG 图片 bytes（橙色风格，与原 GsCore 一致）"""
    qr = qrcode.QRCode(version=1, error_correction=ERROR_CORRECT_L, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color=(255, 134, 36), back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ── 图片下载 ──
async def _download_image(url_or_b64: str) -> Optional[str]:
    """下载图片到缓存目录，返回本地路径

    支持：
      - HTTP/HTTPS URL
      - base64://<data>  内嵌 base64 图片
    """
    try:
        os.makedirs(_CACHE_DIR, exist_ok=True)
        fname = f"gs_{uuid.uuid4().hex[:8]}.png"
        local_path = os.path.join(_CACHE_DIR, fname)

        if url_or_b64.startswith("base64://"):
            b64_data = url_or_b64[len("base64://"):]
            img_bytes = base64.b64decode(b64_data)
            with open(local_path, "wb") as f:
                f.write(img_bytes)
            _logger.debug(f"图片已缓存(base64): {local_path} ({len(img_bytes)} bytes)")
            return local_path

        # HTTP/HTTPS URL
        ext = ".png"
        if "." in url_or_b64:
            ext = "." + url_or_b64.rsplit(".", 1)[-1].split("?")[0]
        local_path = os.path.join(_CACHE_DIR, f"gs_{uuid.uuid4().hex[:8]}{ext}")

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url_or_b64, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            with open(local_path, "wb") as f:
                f.write(resp.content)

        _logger.debug(f"图片已缓存: {local_path} ({len(resp.content)} bytes)")
        return local_path
    except Exception as e:
        _logger.warning(f"图片下载失败: {url_or_b64[:60]} → {e}")
        return None


def _display_qr_in_terminal(img_bytes: bytes, file_path: str = ""):
    """将二维码保存到文件 + 终端 Unicode 渲染"""
    # ★ 先保存文件，确保有图可扫
    try:
        os.makedirs(_CACHE_DIR, exist_ok=True)
        qr_file = os.path.join(_CACHE_DIR, "qrcode_latest.png")
        with open(qr_file, "wb") as f:
            f.write(img_bytes)
        print(f"\n  [QR] 图片已保存 → {qr_file}  可用手机扫码\n")
    except Exception as e:
        _logger.warning(f"[QR] 保存文件失败: {e}")

    if not _has_pil:
        _logger.warning("[终端二维码] 需要 Pillow: pip install Pillow")
        return

    try:
        raw = Image.open(io.BytesIO(img_bytes))

        # RGBA → RGB 白底
        if raw.mode == "RGBA":
            bg = Image.new("RGBA", raw.size, (255, 255, 255, 255))
            bg.paste(raw, mask=raw.split()[3])
            raw = bg.convert("RGB")
        elif raw.mode != "RGB":
            raw = raw.convert("RGB")

        # 灰度 → 阈值二值化 0/255
        gray = raw.convert("L")
        ow, oh = gray.size
        # 先分析像素范围，自适应阈值
        all_pix = list(gray.getdata())
        mid = sorted(all_pix)[len(all_pix) // 2]
        # QR 码是双峰的，取中值作为阈值
        th = mid
        bw = gray.point(lambda x: 0 if x < th else 255, "1")

        # 裁剪白边：用反转灰度找内容区域
        inv_gray = gray.point(lambda x: 255 - x)
        bbox = inv_gray.getbbox()
        if bbox:
            # bbox 是 (L,T,R,B)，对应原图的内容区
            crop = bw.crop(bbox)
        else:
            crop = bw

        # 裁正方形
        cw, ch = crop.size
        side = min(cw, ch)
        crop_sq = crop.crop((0, 0, side, side))

        # NEAREST 缩到显示尺寸
        show = 50
        small = crop_sq.resize((show, show), Image.NEAREST)
        pix = list(small.getdata())

        blacks = sum(1 for p in pix if p == 0)
        print(f"  QR {ow}x{oh} → {show}x{show}  黑={blacks}/{show*show}")
        if blacks == 0:
            print("  ⚠ 黑色像素为0")

        print("=" * (show + 2))
        print("  手机米游社 APP 扫码 ↓")
        for y in range(0, show, 2):
            line = ""
            for x in range(show):
                t = pix[y * show + x]
                b = pix[(y + 1) * show + x] if y + 1 < show else 255
                if t == 0 and b == 0:
                    line += "█"
                elif t == 0 and b == 255:
                    line += "▀"
                elif t == 255 and b == 0:
                    line += "▄"
                else:
                    line += " "
            print(line)
        print("=" * (show + 2))
        _logger.info(f"[终端二维码] 已打印，扫码后可发 /签到 验证")
    except Exception as e:
        _logger.warning(f"[终端二维码] 失败: {e}")


# ── WebSocket 客户端 ──
class GsCoreClient:
    """GsCore WebSocket 客户端（单例）"""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._initialized = True
        self._ws = None
        self._connected = False
        self._reconnect_task = None
        self._listen_task = None
        self._recv_queue: asyncio.Queue[dict] = asyncio.Queue()
        self._lock = asyncio.Lock()
        self._running = False

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def ws_url(self) -> str:
        return f"ws://{GSCORE_HOST}:{GSCORE_PORT}/ws/{BOT_ID}"

    async def start(self):
        """启动连接（自动重连）"""
        if self._running:
            return
        self._running = True
        self._reconnect_task = asyncio.create_task(self._keep_connected())

    async def stop(self):
        """停止连接"""
        self._running = False
        if self._ws:
            await self._ws.close()
        if self._reconnect_task:
            self._reconnect_task.cancel()

    async def _keep_connected(self):
        """持续运行，断线自动重连"""
        while self._running:
            try:
                import websockets

                _logger.info(f"正在连接 GsCore: {self.ws_url}")
                self._ws = await websockets.connect(self.ws_url, ping_interval=20, max_size=20*1024*1024)
                self._connected = True
                _logger.info(f"✅ GsCore 已连接: {self.ws_url}")

                # 启动监听任务
                self._listen_task = asyncio.create_task(self._listen())

                # 等待连接断开
                await self._ws.wait_closed()
            except asyncio.CancelledError:
                break
            except Exception as e:
                _logger.warning(f"GsCore 连接失败: {e}，{RECONNECT_INTERVAL}s 后重试")
            finally:
                self._connected = False
                if self._listen_task and not self._listen_task.done():
                    self._listen_task.cancel()
                self._listen_task = None
                self._ws = None

            if self._running:
                await asyncio.sleep(RECONNECT_INTERVAL)

    async def _listen(self):
        """监听 WebSocket 消息"""
        try:
            while self._connected and self._ws:
                raw = await self._ws.recv()
                raw_type = type(raw).__name__
                _logger.debug(f"[WsRecv] 收到数据: type={raw_type}, len={len(raw) if hasattr(raw, '__len__') else '?'}")
                if isinstance(raw, bytes):
                    try:
                        text = raw.decode("utf-8")
                        _logger.debug(f"[WsRecv] 原始内容(前200): {text[:200]}")
                        resp = _parse_message_send(raw)
                        if resp:
                            _logger.debug(f"[WsRecv] 解析成功, content={resp.get('content')}")
                            await self._recv_queue.put(resp)
                        else:
                            _logger.warning(f"[WsRecv] 解析失败, raw={text[:200]}")
                    except Exception as e:
                        _logger.warning(f"[WsRecv] 处理异常: {e}")
                elif isinstance(raw, str):
                    _logger.warning(f"[WsRecv] 收到字符串消息(非bytes): {raw[:200]}")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            _logger.debug(f"Ws监听结束: {e}")

    async def send_command(self, user_id: str, user_type: str, text: str, group_id: str = "", timeout: int = TIMEOUT, collect_window: float = COLLECT_WINDOW) -> List[Tuple[str, str]]:
        """发送命令到 GsCore 并等待返回（线程安全）

        返回: [(type, data), ...]  type 可为 "text" / "image"
        timeout: 等待超时秒数，扫码登录建议 90s
        collect_window: 收到首条后继续收集的时间窗口，扫码登录建议 90s（等待用户扫码结果）
        """
        if not self._connected:
            return [("text", "⚠️ GsCore 未连接，请等待重连后重试")]

        async with self._lock:
            msg_json = _make_message_receive(user_id, user_type, text, group_id)
            try:
                await self._ws.send(msg_json.encode("utf-8"))
                _logger.debug(f"→ 发送 GsCore: {text[:60]}")
            except Exception as e:
                self._connected = False
                return [("text", f"❌ GsCore 发送失败: {e}")]

            # 收集回复（首条 + 短窗口内多条）
            results: List[Tuple[str, str]] = []
            deadline = time.time() + timeout
            first_arrived = False
            collect_deadline = 0.0

            while True:
                remaining = deadline - time.time()
                if remaining <= 0:
                    break

                # 首条等待用完整超时，后续用收集窗口
                wait = remaining
                if first_arrived:
                    remaining_collect = collect_deadline - time.time()
                    if remaining_collect <= 0:
                        break
                    wait = min(remaining, remaining_collect)

                try:
                    resp = await asyncio.wait_for(
                        self._recv_queue.get(),
                        timeout=wait,
                    )
                    items = _extract_messages(resp)
                    results.extend(items)

                    if not first_arrived:
                        first_arrived = True
                        collect_deadline = time.time() + collect_window

                except asyncio.TimeoutError:
                    break

            # 超时了：强制标记断连，让后台 _keep_connected 重连
            if not results:
                _logger.warning(f"[GsCore] 命令超时（{text[:40]}），触发重连...")
                self._connected = False
                # 关闭旧连接以触发 _keep_connected 自动重连
                if self._ws:
                    try:
                        await self._ws.close()
                    except Exception:
                        pass
                    self._ws = None

            return results if results else [("text", "⏳ GsCore 查询超时，请稍后重试")]

    async def wait_for_message(self, timeout: int = 90) -> Optional[List[Tuple[str, str]]]:
        """等待 GsCore 推送的下一条消息（不持有锁，扫码后等登录结果用）"""
        # 清空队列中已有的过期消息
        while not self._recv_queue.empty():
            try:
                self._recv_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        try:
            resp = await asyncio.wait_for(self._recv_queue.get(), timeout=timeout)
            return _extract_messages(resp)
        except asyncio.TimeoutError:
            return None


# ── 全局单例 ──
_gscore_client = GsCoreClient()
_GSCORE_DISABLED = os.environ.get("GSCORE_DISABLED", "0") == "1"


def get_client() -> GsCoreClient:
    if _GSCORE_DISABLED:
        return None
    return _gscore_client
