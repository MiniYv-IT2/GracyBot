"""GracyBot 消息发送桥接 — 通过 AdapterPool 统一发送

用法:
    from core.gracy_adapter.send import gracy_send_msg

    await gracy_send_msg(target_id, GracyText("你好"), chat_type="group")

多适配器用法:
    # 向默认适配器发送
    await gracy_send_msg(target_id, GracyText("你好"), chat_type="group")

    # 向指定适配器发送（需要获取 tag）
    await gracy_send_msg(target_id, GracyText("你好"), chat_type="group", tag=my_tag)

消息链路:
    Pipeline 设置 RuntimeContext → send() 通过 RuntimeContext.get().adapter_tag 自动适配
"""

import asyncio
import logging
from typing import List, Optional

from core.gracy_adapter.message import GracyMsg
from core.gracy_adapter.identity import IdentityTag
from core.gracy_adapter.pool import adapter_pool
from style.styling import encrypt_user_id

_logger = logging.getLogger("Adapter.Send")


def _get_runtime_tag() -> Optional[IdentityTag]:
    """从当前消息上下文获取来源适配器标签"""
    try:
        from core.runtime import RuntimeContext
        runtime = RuntimeContext.get()
        if runtime:
            return runtime.adapter_tag
    except Exception:
        pass
    return None


async def gracy_send_msg(target: str, *segments: GracyMsg,
                         chat_type: str = "private",
                         tag: Optional[IdentityTag] = None) -> bool:
    """用结构化消息段发送消息

    Args:
        target: 目标 ID
        segments: GracyText / GracyImage / GracyAt ... 任意数量
        chat_type: "private" | "group"
        tag: 指定适配器标签，None=从消息上下文自动获取

    Returns:
        发送成功返回 True
    """
    if tag is None:
        tag = _get_runtime_tag()

    seg_list: List[GracyMsg] = list(segments)
    send_result = adapter_pool.send(target, seg_list, chat_type, tag=tag)
    if asyncio.iscoroutine(send_result):
        success = await send_result
    else:
        success = send_result
    preview = _segments_preview(segments)
    type_cn = "私聊" if chat_type == "private" else "群聊"
    status = "成功发送" if success else "发送失败"
    tag_str = tag.log_tag if tag else ""
    instance_attrs = {}
    if tag:
        # 从 tag 提取实例标识符
        parts = tag_str.strip("[]").split(":")
        if len(parts) >= 2:
            instance_attrs["instance"] = f"{parts[0]}-{parts[1]}"
    _logger.info(
        f"[消息发送] {status}{type_cn}消息{tag_str} | 目标: {encrypt_user_id(target)} | 内容预览: {preview}",
        extra={"log_attrs": instance_attrs} if instance_attrs else {},
    )
    return success


def _segments_preview(segments) -> str:
    """把消息段转成日志用摘要（最长 100 字符）"""
    parts = []
    for seg in segments:
        if isinstance(seg, str):
            parts.append(seg)
        elif hasattr(seg, 'text'):
            parts.append(seg.text)
        elif hasattr(seg, 'file_path'):
            parts.append("[图片]")
        elif hasattr(seg, 'url'):
            parts.append("[图片]")
        elif hasattr(seg, 'target_id'):
            parts.append(f"[@:{seg.target_id}]")
        else:
            parts.append(str(type(seg).__name__))
    preview = " | ".join(parts)
    if len(preview) > 100:
        preview = preview[:97] + "..."
    return preview


async def gracy_call_api(action: str, params: dict = None,
                         tag: Optional[IdentityTag] = None) -> Optional[dict]:
    """通过适配器调用平台 API

    Args:
        action: 平台特定的 API 名称
        params: action 参数字典
        tag: 指定适配器标签，None=从消息上下文自动获取

    Returns:
        成功返回 data 字段内容，失败返回 None
    """
    if tag is None:
        tag = _get_runtime_tag()
    adapter = adapter_pool.get(tag) if tag else adapter_pool.get_default()
    if adapter is None:
        _logger.error("[API] 无可用适配器")
        return None
    if hasattr(adapter, 'call_api'):
        result = adapter.call_api(action, params or {})
        if asyncio.iscoroutine(result):
            return await result
        return result
    return None


async def gracy_get_platform_info(tag: Optional[IdentityTag] = None) -> dict:
    """获取平台统计信息

    Args:
        tag: 指定适配器标签，None=从消息上下文自动获取
    """
    if tag is None:
        tag = _get_runtime_tag()
    adapter = adapter_pool.get(tag) if tag else adapter_pool.get_default()
    if adapter is None:
        return {"friend_count": None, "group_count": None, "platform": "unknown", "protocol_version": None}
    if hasattr(adapter, 'get_platform_info'):
        result = adapter.get_platform_info()
        if asyncio.iscoroutine(result):
            return await result
        return result
    return {"friend_count": None, "group_count": None, "platform": "unknown", "protocol_version": None}
