"""安全装饰器 — 权限校验 / 频率限制 / 冷却时间

从 dispatch_plugin_cmd 中提取横切关注点，改为声明式装饰器。

叠加顺序（从下到上）:
    @on_command("/cmd")
    @require_permission("master")
    @rate_limit(max_calls=5, period=60)
    @cooldown(seconds=3)
    @plugin_handler
    async def handler(ctx): ...
"""

import asyncio
import time
import logging
from functools import wraps
from typing import Callable, Dict, Optional

from core.security_manager import security_manager

_logger = logging.getLogger("Gracy.Decorators")


# ── @require_permission ──

def require_permission(level: str = "all"):
    """权限校验装饰器

    Args:
        level: 权限级别 — "all" | "master" | "admin" | "use_plugins" | "basic_query"
    """
    def decorator(func):
        func._gracy_permission = level
        return func

    return decorator


def require_master(func=None):
    """快捷装饰器：仅主人可用（等价于 @require_permission("master")）"""
    if func is None:
        return require_permission("master")
    return require_permission("master")(func)


# ── @rate_limit — 频率限制 ──

# 全局频率限制计数器 {key: [(timestamp, ...)]}
_rate_limit_counters: Dict[str, list] = {}
_rate_limit_lock = asyncio.Lock()


def rate_limit(max_calls: int = 10, period: int = 60):
    """频率限制装饰器

    对每个 sender_id 限制在 period 秒内最多调用 max_calls 次。

    Args:
        max_calls: 周期内最大调用次数
        period: 周期秒数
    """
    def decorator(func):
        func._gracy_rate_limit = (max_calls, period)
        return func

    return decorator


# ── @cooldown — 冷却时间 ──

_cooldown_timestamps: Dict[str, float] = {}
_cooldown_lock = asyncio.Lock()


def cooldown(seconds: int = 3):
    """冷却时间装饰器

    对每个 (sender_id, command) 设置冷却时间，期间内重复触发被忽略。

    Args:
        seconds: 冷却秒数
    """
    def decorator(func):
        func._gracy_cooldown = seconds
        return func

    return decorator


# ── 运行时校验函数（由 @plugin_handler 调用） ──

async def check_permission_decorator(sender_id: str, required_level: str) -> bool:
    """运行时权限校验"""
    allowed, _ = security_manager.check_permission(sender_id, required_level)
    return allowed


async def check_rate_limit_decorator(
    sender_id: str,
    command: str,
    max_calls: int,
    period: int,
) -> bool:
    """运行时频率限制检查"""
    key = f"{sender_id}:{command}"

    async with _rate_limit_lock:
        now = time.time()
        history = _rate_limit_counters.get(key, [])

        # 清除过期记录
        cutoff = now - period
        history = [t for t in history if t > cutoff]

        if len(history) >= max_calls:
            return False  # 超限

        history.append(now)
        _rate_limit_counters[key] = history
        return True


async def check_cooldown_decorator(
    sender_id: str,
    command: str,
    seconds: int,
) -> bool:
    """运行时冷却时间检查"""
    key = f"{sender_id}:{command}"

    async with _cooldown_lock:
        last = _cooldown_timestamps.get(key, 0)
        now = time.time()

        if now - last < seconds:
            return False  # 冷却中

        _cooldown_timestamps[key] = now
        return True
