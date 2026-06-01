"""GracyBot 消息发送桥接 — 插件用 GracyMsg 发消息的便捷函数

用法:
    from core.gracy_adapter.send import gracy_send_msg
    from core.gracy_adapter.message import GracyImage

    gracy_send_msg(target_id, GracyImage(file_path="/tmp/1.png"), chat_type="group")
"""

import logging
import os
from typing import List, Optional

from core.gracy_adapter.message import GracyMsg
from core.gracy_adapter.onebot.http import GracyOneBot

_logger = logging.getLogger("Gracy.Send")

# 惰性单例适配器
_adapter = None  # 运行时可注入 WS 实例


def set_adapter(adapter) -> None:
    """注入适配器实例（main.py 启动时根据连接模式设置）"""
    global _adapter
    _adapter = adapter


def _get_adapter():
    """获取当前适配器单例（未注入时自动创建 HTTP 适配器）"""
    global _adapter
    if _adapter is None:
        from core.gracy_adapter.onebot.http import GracyOneBot as _HttpBot
        from core.config_manager import config_manager
        _adapter = _HttpBot(
            napcat_url=config_manager.get("napcat_http_url", "http://localhost:3000"),
            callback_port=config_manager.get("callback_port", 3002),
            robot_id=config_manager.get("robot_id", ""),
        )
    return _adapter


def gracy_send_msg(target: str, *segments: GracyMsg, chat_type: str = "private") -> bool:
    """用结构化消息段发送消息（替代 send_http_msg）

    Args:
        target: 目标 ID
        segments: GracyText / GracyImage / GracyAt ... 任意数量
        chat_type: "private" | "group"

    Returns:
        发送成功返回 True
    """
    adapter = _get_adapter()
    success = adapter.send(target, list(segments), chat_type)
    # 回复日志（沿用旧版 http 风格：中文标签 + 内容预览）
    preview = _segments_preview(segments)
    type_cn = "私聊" if chat_type == "private" else "群聊"
    status = "成功发送" if success else "发送失败"
    _logger.info(f"[消息发送] {status}{type_cn}消息 | 目标: {target} | 聊天类型: {type_cn} | 内容预览: {preview}")
    return success


def _segments_preview(segments) -> str:
    """把消息段转成日志用摘要（最长 60 字符）"""
    parts = []
    for seg in segments:
        if hasattr(seg, 'text'):
            parts.append(seg.text)
        elif hasattr(seg, 'file_path'):
            parts.append(f"[图片:{os.path.basename(seg.file_path)}]")
        elif hasattr(seg, 'target_id'):
            parts.append(f"[@:{seg.target_id}]")
        else:
            parts.append(str(type(seg).__name__))
    preview = " | ".join(parts)
    if len(preview) > 100:
        preview = preview[:97] + "..."
    return preview


def gracy_call_api(action: str, params: dict = None) -> Optional[dict]:
    """通过适配器调用平台 API（自动选择 HTTP/WS 通道）

    Args:
        action: 平台特定的 API 名称
        params: action 参数字典

    Returns:
        成功返回 data 字段内容，失败返回 None
    """
    adapter = _get_adapter()
    if hasattr(adapter, 'call_api'):
        return adapter.call_api(action, params or {})
    return None


def gracy_get_platform_info() -> dict:
    """通过适配器获取平台统计信息（跨平台统一接口）

    返回统一结构，各平台自行填充：
    {
        "friend_count": int | None,
        "group_count": int | None,
        "platform": str,
        "protocol_version": str | None,
    }
    """
    adapter = _get_adapter()
    if hasattr(adapter, 'get_platform_info'):
        return adapter.get_platform_info()
    return {
        "friend_count": None,
        "group_count": None,
        "platform": "unknown",
        "protocol_version": None,
    }
