"""日志装饰器 — 插件级日志注入与属性管理

用法:
    # 1. 插件入口文件使用 @with_logger，自动生成 logger
    from core.decorators.logger import with_logger, log_attrs

    @with_logger(category="Gracy")
    class MyPlugin:
        def __init__(self):
            self._logger.info("插件已初始化")

    # 2. 函数级使用 @log_attrs 动态添加属性
    @on_command("/help")
    @log_attrs(priority="P50")
    @plugin_handler
    async def handler(ctx):
        _logger.info("收到命令")  # 自动带 priority="P50"

    # 3. 也可以不用装饰器，手动创建
    import logging
    _logger = logging.getLogger("Gracy.MyPlugin")
"""

import contextvars
import functools
import inspect
import logging
from typing import Any, Dict, Optional

# 当前上下文的日志属性，由 @log_attrs 设置，build_attrs 读取
_log_attrs_ctx: contextvars.ContextVar[Dict[str, Any]] = contextvars.ContextVar(
    "_log_attrs_ctx", default=None
)


def with_logger(category: str = "Gracy", name: Optional[str] = None):
    """为插件类自动注入 logger 实例

    用法:
        @with_logger(category="Gracy")
        class HelpPlugin:
            def __init__(self):
                self._logger.info("启动")  # ← 自动可用

    生成的 logger 名: f"{category}.{name}"（name 未指定时使用类名）

    Args:
        category: 分类名，默认 "Gracy"
        name: 模块名，默认取类名
    """
    def decorator(cls):
        logger_name = f"{category}.{name or cls.__name__}"
        logger = logging.getLogger(logger_name)

        original_init = cls.__init__

        @functools.wraps(original_init)
        def new_init(self, *args, **kwargs):
            self._logger = logger
            original_init(self, *args, **kwargs)

        cls.__init__ = new_init
        cls._logger = logger
        return cls

    return decorator


def log_attrs(**attrs: Any):
    """为函数执行期间的 LogRecord 注入额外属性

    属性会显示在终端日志的 [模块] 和 [消息] 之间。
    支持叠加、覆盖（传 None 清除该属性）。

    用法:
        @log_attrs(priority="P50", instance="qq_official-官方机器人")
        @plugin_handler
        async def handler(ctx):
            _logger.info("消息已处理")  # 自动带 P50 和实例信息
    """
    def decorator(func):
        # 把属性挂到函数上，给框架层（如 Pipeline）读取
        base = getattr(func, "_gracy_log_attrs", {})
        merged = {**base, **{k: v for k, v in attrs.items() if v is not None}}
        func._gracy_log_attrs = merged

        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                prev = _log_attrs_ctx.get()
                _log_attrs_ctx.set(merged)
                try:
                    return await func(*args, **kwargs)
                finally:
                    _log_attrs_ctx.set(prev)
            async_wrapper._gracy_log_attrs = merged
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                prev = _log_attrs_ctx.get()
                _log_attrs_ctx.set(merged)
                try:
                    return func(*args, **kwargs)
                finally:
                    _log_attrs_ctx.set(prev)
            sync_wrapper._gracy_log_attrs = merged
            return sync_wrapper

    return decorator


def get_log_attrs(func) -> Dict[str, Any]:
    """获取函数上挂载的日志属性"""
    return getattr(func, "_gracy_log_attrs", {})


def get_context_attrs() -> Dict[str, Any]:
    """获取当前上下文的日志属性（由 @log_attrs 设置）"""
    return _log_attrs_ctx.get() or {}
