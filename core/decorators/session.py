"""@with_session — 会话自动注入装饰器

自动获取/创建会话并注入到 ctx.session，
无需手动调用 gracy_get_or_create_session。

用法:
    @on_command("/chat")
    @with_session
    @plugin_handler
    async def handler(ctx):
        ctx.session  # 已有值
        ctx.session.add_message(...)
"""

from functools import wraps
from typing import Callable, Optional

from .context import PluginContext


def with_session(func: Callable) -> Callable:
    """会话自动注入装饰器

    在执行 handler 前自动获取/创建会话，
    结果注入 ctx.session。

    与 @plugin_handler 配合使用（@with_session 在内层）:
        @on_command("/chat")
        @plugin_handler      ← 先执行
        @with_session        ← 后执行
        async def handler(ctx):
            ctx.session  ← 可用
    """

    @wraps(func)
    async def wrapper(ctx: PluginContext) -> None:
        # 延迟导入，避免循环依赖
        from core.gracy_session.gracy_session_manager import (
            gracy_get_or_create_session,
        )

        session = gracy_get_or_create_session(
            sender_id=ctx.sender_id,
            target_id=ctx.target_id if ctx.chat_type == "group" else None,
        )
        ctx.session = session

        return await func(ctx)

    return wrapper
