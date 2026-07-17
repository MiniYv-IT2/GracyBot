"""GracyBot 顶级包

用法:
    from gracybot.graci import on_command, PluginContext
"""

from gracybot.core import (
    Core, core,
    get_plugin_manager, get_config_manager,
    get_logger_manager, get_runtime_registry,
    logger, __version__,
)

__all__ = [
    "Core", "core",
    "get_plugin_manager", "get_config_manager",
    "get_logger_manager", "get_runtime_registry",
    "logger", "__version__",
]
