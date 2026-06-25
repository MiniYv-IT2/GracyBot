"""核心 @plugin_handler 装饰器 — 统一包装插件处理器

职责（替代 dispatch_plugin_cmd 中的手动逻辑）：
    1. 权限校验：调用 @require_permission 声明的权限
    2. 频率限制：调用 @rate_limit 声明的限制
    3. 冷却时间：调用 @cooldown 声明的冷却
    4. 执行计时 + 监控上报
    5. 异常捕获 + 审计日志
    6. 同步/异步自动兼容

用法:
    @on_command("/info")
    @require_permission("all")
    @plugin_handler
    async def handler(ctx: PluginContext):
        await ctx.send("Hello")
"""

import asyncio
import time
import logging
import inspect
from functools import wraps
from typing import Callable, Optional

from .context import PluginContext
from .security import (
    check_permission_decorator,
    check_rate_limit_decorator,
    check_cooldown_decorator,
)

_logger = logging.getLogger("Core.Decorators")


def plugin_handler(func: Callable) -> Callable:
    """核心装饰器：包装插件处理器函数

    Pipeline 的 PluginHandler 检测到 handler 签名为 (ctx) 时，
    会将 PluginContext 直接传入此装饰器。
    """
    is_async = inspect.iscoroutinefunction(func)

    @wraps(func)
    async def wrapper(ctx: PluginContext) -> None:
        """执行包装后的插件处理器"""
        ctx.start_time = time.time()

        # ── 权限校验 ──
        perm_level = getattr(func, "_gracy_permission", getattr(wrapper, "_gracy_permission", None))
        if perm_level and perm_level != "all":
            allowed = await check_permission_decorator(ctx.sender_id, perm_level)
            if not allowed:
                _logger.warning(
                    f"[装饰器] 权限不足: 用户{ctx.sender_id} 命令={ctx.command} "
                    f"需要={perm_level}"
                )
                return

        # ── 频率限制 ──
        rl = getattr(func, "_gracy_rate_limit", getattr(wrapper, "_gracy_rate_limit", None))
        if rl:
            max_calls, period = rl
            allowed = await check_rate_limit_decorator(ctx.sender_id, ctx.command, max_calls, period)
            if not allowed:
                _logger.warning(
                    f"[装饰器] 频率超限: 用户{ctx.sender_id} 命令={ctx.command} "
                    f"{max_calls}/{period}s"
                )
                return

        # ── 冷却时间 ──
        cd = getattr(func, "_gracy_cooldown", getattr(wrapper, "_gracy_cooldown", None))
        if cd:
            allowed = await check_cooldown_decorator(ctx.sender_id, ctx.command, cd)
            if not allowed:
                _logger.debug(
                    f"[装饰器] 冷却中: 用户{ctx.sender_id} 命令={ctx.command}"
                )
                return

        # ── 执行 handler ──
        try:
            if is_async:
                await func(ctx)
            else:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, func, ctx)

            elapsed = time.time() - ctx.start_time
            _logger.info(
                f"[装饰器] 执行成功: 插件={ctx.plugin_name} "
                f"命令={ctx.command} 耗时={elapsed:.3f}s"
            )

        except Exception as e:
            elapsed = time.time() - ctx.start_time
            _logger.error(
                f"[装饰器] 执行异常: 插件={ctx.plugin_name} "
                f"命令={ctx.command} 耗时={elapsed:.3f}s 错误={e}",
                exc_info=True,
            )

    # 透传装饰器元数据（用于外层装饰器读取）
    wrapper._gracy_permission = getattr(func, "_gracy_permission", None)
    wrapper._gracy_rate_limit = getattr(func, "_gracy_rate_limit", None)
    wrapper._gracy_cooldown = getattr(func, "_gracy_cooldown", None)

    return wrapper
