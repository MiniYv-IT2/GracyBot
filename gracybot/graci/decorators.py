"""装饰器组件"""

from gracybot.core.decorators import (
    on_command, on_regex, on_keyword,
    gracy_plugin, plugin_handler,
    require_permission, require_master,
    rate_limit, cooldown,
    with_session, async_retry, background,
)
from gracybot.core.decorators.registration import on_fallback
from gracybot.core.decorators.registration import DECORATOR_COMMAND_REGISTRY
from gracybot.core.decorators.logger import with_logger, log_attrs
from gracybot.core.decorators.context import PluginContext

__all__ = [
    "on_command", "on_regex", "on_keyword",
    "gracy_plugin", "plugin_handler", "on_fallback",
    "require_permission", "require_master",
    "rate_limit", "cooldown",
    "with_session", "async_retry", "background",
    "with_logger", "log_attrs",
    "DECORATOR_COMMAND_REGISTRY",
]
