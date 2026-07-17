"""GracyBot 装饰器体系 — 声明式插件开发

装饰器加载顺序（从下往上/从内到外）:
    @on_command("/cmd")
    @require_permission("all")
    @plugin_handler
    async def handler(ctx): ...

执行顺序（从上往下/从外到内）：

    1. @on_command → 注册到全局命令池
    2. @require_permission → 权限校验
    3. @plugin_handler → 参数注入 + 计时 + 异常捕获
    4. handler() → 业务逻辑
"""

from .context import PluginContext
from .registration import on_command, on_regex, on_keyword, gracy_plugin, DECORATOR_COMMAND_REGISTRY
from .security import require_permission, require_master, rate_limit, cooldown
from .handler import plugin_handler
from .session import with_session
from .async_utils import async_retry, background

__all__ = [
    "PluginContext",
    "on_command", "on_regex", "on_keyword", "gracy_plugin", "DECORATOR_COMMAND_REGISTRY",
    "require_permission", "require_master", "rate_limit", "cooldown",
    "plugin_handler",
    "with_session",
    "async_retry", "background",
]
