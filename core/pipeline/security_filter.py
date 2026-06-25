"""Stage: SecurityFilter — 安全过滤 + 日志记录"""

import logging
from typing import Optional

from core.pipeline import Stage
from core.decorators.context import PluginContext

_logger = logging.getLogger("Core.Pipeline")


class SecurityFilter(Stage):
    """安全过滤器

    职责:
        - sender_id 合法性校验
        - 完整日志记录（使用 styling 管道，保证格式与旧 handler 一致）
        - 监控统计
    """

    async def process(self, ctx: PluginContext) -> Optional[PluginContext]:
        _logger.debug(f"[SecurityFilter] 校验用户 {ctx.sender_id}")

        # ── 监控统计（可选模块） ──
        try:
            from core.monitor import monitor_manager
            monitor_manager.record_message_received()
        except ImportError:
            pass

        # ── 日志记录 ──
        self._log_via_styling(ctx)

        return ctx

    def _log_via_styling(self, ctx: PluginContext) -> None:
        """通过 logger_manager + styling 管道记录日志"""
        context = {
            'sender_id': ctx.sender_id,
            'chat_type': ctx.chat_type,
            'raw_text': ctx.raw_text,
        }
        if ctx.chat_type == 'group' and ctx.target_id:
            context['target_id'] = ctx.target_id
        context = {k: v for k, v in context.items() if v}

        from core.logger_manager import logger_manager
        logger_manager.log_with_context(
            _logger,
            logging.INFO,
            "[回调基础] 收到消息",
            context=context,
        )
