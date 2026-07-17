"""OneBot 统一适配器 — HTTP + WebSocket 双通道自动选择

用法:
    from gracybot.core.gracy_adapter.onebot.adapter import OneBotAdapter

    adapter = OneBotAdapter(
        http_url="http://127.0.0.1:3000",
        ws_mode="reverse", ws_host="0.0.0.0", ws_port=8080,
    )
    adapter.start(on_event)

    # 发送消息（自动选 WS，WS 不可用时回退 HTTP）
    adapter.send(target, segments, chat_type)
"""

import logging
from typing import Callable, List, Optional

from gracybot.core.gracy_adapter.adapter import GracyAdapter
from gracybot.core.gracy_adapter.event import GracyEvent
from gracybot.core.gracy_adapter.message import GracyMsg
from gracybot.core.gracy_adapter.onebot.http import GracyOneBot
from gracybot.core.gracy_adapter.onebot.ws import GracyOneBotWS
from gracybot.core.gracy_adapter.onebot.http_routes import register_http_parser, _create_callback_route

_logger = logging.getLogger("Adapter.OneBot")


class OneBotAdapter(GracyAdapter):
    """OneBot 统一适配器

    内部维护 HTTP 和 WS 两个通道：
    - 发送消息：优先 WS（已连接），回退 HTTP
    - 接收消息：HTTP（Flask callback）+ WS（原生 asyncio）两条路径
    - 平台统计信息：优先从 WS API 获取，回退 HTTP
    """

    def __init__(
        self,
        # HTTP
        http_url: str = "http://127.0.0.1:3000",
        callback_port: int = 3002,
        # WS
        ws_mode: str = "",  # 空 = 不启动 WS
        ws_host: str = "0.0.0.0",
        ws_port: int = 8080,
        access_token: str = "",
        # 通用
        robot_id: str = "",
    ):
        self._http = GracyOneBot(
            napcat_url=http_url,
            callback_port=callback_port,
            robot_id=robot_id,
        )
        self._ws_enabled = bool(ws_mode)
        if self._ws_enabled:
            self._ws = GracyOneBotWS(
                mode=ws_mode,
                host=ws_host,
                port=ws_port,
                access_token=access_token,
                robot_id=robot_id,
            )
        else:
            self._ws = None
        self._robot_id = robot_id

    # ── 生命周期 ──

    def start(self, on_event: Callable[[GracyEvent], None]) -> None:
        """启动通道"""
        self._http.start(on_event)
        # 注册 HTTP parser 供 /callback 路由查找
        if self._robot_id:
            register_http_parser(self._robot_id, self._http)
        if self._ws_enabled:
            self._ws.start(on_event)
        _logger.info("[OneBotAdapter] 统一适配器启动完成")

    def stop(self) -> None:
        """停止通道"""
        if self._ws_enabled:
            self._ws.stop()
        _logger.info("[OneBotAdapter] 统一适配器已停止")

    # ── 发送消息 ──

    def send(self, target: str, segments: List[GracyMsg], chat_type: str) -> bool:
        """发送消息（WS 优先，未连接时自动暂存等待补发）"""
        if self._ws_enabled:
            return self._ws.send(target, segments, chat_type)
        return self._http.send(target, segments, chat_type)

    def call_api(self, action: str, params: dict = None) -> Optional[dict]:
        """调用 OneBot API（WS 优先，未连接时自动暂存等待补发）"""
        if self._ws_enabled:
            return self._ws.call_api(action, params or {})
        return self._http.call_api(action, params or {})

    def get_platform_info(self) -> dict:
        """获取平台统计信息"""
        if self._ws_enabled:
            return self._ws.get_platform_info()
        return self._http.get_platform_info()

    def is_ws_connected(self) -> bool:
        """WS 通道是否已连接"""
        return self._ws_enabled and self._ws._ws is not None

    def register_routes(self, app) -> None:
        """注册 /callback 路由"""
        _create_callback_route(app)
        _logger.info("[OneBotAdapter] HTTP 回调路由已注册")

    def get_http(self) -> GracyOneBot:
        """获取底层 HTTP 适配器（高级用法）"""
        return self._http

    def get_ws(self) -> Optional[GracyOneBotWS]:
        """获取底层 WS 适配器（未启用时返回 None）"""
        return self._ws if self._ws_enabled else None


# ============================================================
# 工厂函数
# ============================================================

def create_adapter(config: dict) -> GracyAdapter:
    """工厂函数：根据实例配置创建 OneBot 适配器实例

    Args:
        config: 实例配置字典（来自 storage/instances/<name>/config.json）

    Returns:
        OneBotAdapter 实例
    """
    raw_type = config.get("type", "http")

    if raw_type in ("ws_forward", "ws_reverse"):
        ws_mode = "forward" if raw_type == "ws_forward" else "reverse"
        adapter = OneBotAdapter(
            ws_mode=ws_mode,
            ws_host=config.get("host", "127.0.0.1"),
            ws_port=config.get("port", 8080),
            access_token=config.get("access_token", ""),
            robot_id=config.get("robot_id", ""),
        )
        adapter.conn_type_display = "WS (正向)" if raw_type == "ws_forward" else "WS (反向)"
    else:
        adapter = OneBotAdapter(
            http_url=config.get("http_url", "http://127.0.0.1:3000"),
            callback_port=config.get("callback_port", 3002),
            robot_id=config.get("robot_id", ""),
        )
        adapter.conn_type_display = "HTTP" if raw_type == "http" else raw_type.upper()
    return adapter
