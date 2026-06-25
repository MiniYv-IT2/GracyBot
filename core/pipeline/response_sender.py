"""Stage: ResponseSender — 兜底处理（自动回复 + catch_all 插件分发）"""

import inspect
import logging
from typing import Optional

from core.pipeline import Stage
from core.decorators.context import PluginContext

_logger = logging.getLogger("Core.Pipeline")


class ResponseSender(Stage):
    """响应发送器

    处理未被插件匹配的消息：自动回复匹配 → 兜底插件分发（如 LLM_Chat）。
    """

    async def process(self, ctx: PluginContext) -> Optional[PluginContext]:
        raw_msg = ctx.raw_text.strip()
        if not raw_msg:
            return None

        # ── 自动回复匹配 ──
        from core.config_manager import config_manager
        auto_replies = config_manager.get("auto_replies", {})
        if auto_replies and isinstance(auto_replies, dict):
            for keyword, reply in auto_replies.items():
                if keyword in raw_msg:
                    from core.gracy_adapter.send import gracy_send_msg
                    from core.gracy_adapter.message import GracyText
                    await gracy_send_msg(
                        ctx.target_id,
                        GracyText(text=reply),
                        chat_type=ctx.chat_type,
                        tag=ctx.adapter_tag,
                    )
                    _logger.info(f"[自动回复] 关键词 '{keyword}' → 已回复用户 {ctx.sender_id}")
                    return None

        # ── 兜底处理器（@on_fallback，如 LLM_Chat） ──
        from core.decorators.registration import FALLBACK_HANDLERS
        for entry in FALLBACK_HANDLERS:
            if ctx.chat_type not in entry.get("chat_type", ["private", "group"]):
                continue
            handler_func = entry["handler_func"]
            _logger.debug(f"[ResponseSender] 兜底分发: {entry.get('plugin_name', 'unknown')}")
            from core.gracy_adapter.send import gracy_send_msg
            async def _fb_send(*args, **kwargs):
                return await gracy_send_msg(*args, **kwargs, tag=ctx.adapter_tag)
            result = handler_func(
                ctx.plugin_manager,
                _fb_send,
                self._build_plugin_data(ctx),
                ctx.sender_id,
                ctx.chat_type,
                "all",
                _logger,
            )
            if inspect.iscoroutine(result):
                await result
            return None

        return None

    def _build_plugin_data(self, ctx: PluginContext) -> dict:
        return {
            "text": ctx.text or ctx.raw_text,
            "nickname": ctx.nickname,
            "images": ctx.images,
            "ats": ctx.ats,
            "target_id": ctx.target_id,
            "chat_type": ctx.chat_type,
            "raw_data": ctx.raw_data,
            "is_at_bot": ctx.is_at_bot,
        }
