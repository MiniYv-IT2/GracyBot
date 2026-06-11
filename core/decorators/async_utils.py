"""异步工具装饰器 — @async_retry / @background

@async_retry: 自动重试异步函数
@background: 将同步函数转为后台异步任务
"""

import asyncio
import logging
from functools import wraps
from typing import Callable, Optional

_logger = logging.getLogger("Gracy.Decorators")


# ── @async_retry ──

def async_retry(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
):
    """异步重试装饰器

    Args:
        max_retries: 最大重试次数
        delay: 初始延迟秒数
        backoff: 每次重试延迟倍数
        exceptions: 可重试的异常类型
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exc = None
            current_delay = delay

            for attempt in range(1, max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    if attempt < max_retries:
                        _logger.warning(
                            f"[重试] {func.__name__} 第{attempt}次失败: {e} "
                            f"{current_delay}s 后重试"
                        )
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        _logger.error(
                            f"[重试] {func.__name__} 已达最大重试次数({max_retries}): {e}"
                        )

            raise last_exc

        return wrapper

    return decorator


# ── @background ──

def background(func: Callable) -> Callable:
    """后台任务装饰器

    将函数调用包装为 asyncio.create_task，不阻塞主流程。

    适用于：日志记录、通知推送等非关键路径操作。

    用法:
        @background
        async def log_something(x): ...

        await log_something("hello")  # 立即返回，不等待执行完毕
    """

    @wraps(func)
    async def wrapper(*args, **kwargs):
        task = asyncio.create_task(func(*args, **kwargs))
        # 捕获后台异常防止"未处理异常"警告
        task.add_done_callback(_log_task_exception)
        return task

    def _log_task_exception(task: asyncio.Task):
        try:
            exc = task.exception()
            if exc:
                _logger.error(
                    f"[后台任务] {func.__name__} 异常: {exc}",
                    exc_info=exc,
                )
        except asyncio.CancelledError:
            pass

    return wrapper
