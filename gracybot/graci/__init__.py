"""
graci — GracyBot 插件公共 API 包

用法:
    from graci import GracyText, GracyImage
    from graci import on_command, plugin_handler
    from graci import PluginContext
"""

from .messages import (
    GracyText, GracyImage, GracyVoice, GracyAt,
    GracyReply, GracyMsg, GracyFile, GracyVideo, GracyForward,
)
from .decorators import (
    on_command, on_regex, on_keyword,
    gracy_plugin, plugin_handler,
    require_permission, require_master,
    rate_limit, cooldown,
    with_session, async_retry, background,
    with_logger, log_attrs,
    on_fallback, DECORATOR_COMMAND_REGISTRY,
)
from .context import PluginContext
from .core_api import (
    gracy_send_msg, gracy_call_api, gracy_get_platform_info,
    BOT_VERSION, MASTER_ID, ROBOT_ID, ROBOT_START_TIME, LOG_ENCODING,
    get_current_master_id, get_current_robot_id,
    plugin_manager, config_manager,
    logger, get_logger,
    sanitize_log, monitor_manager,
    get_logs_dir, get_storage_dir, get_res_config_dir,
    register_cli_command,
    Quart, send_from_directory, Blueprint, request, Config, serve,
    Stage, RuntimeRegistry, GracyEvent, IdentityTag,
    get_db,
)

__all__ = [
    # 消息类型
    "GracyText", "GracyImage", "GracyVoice", "GracyAt", "GracyReply", "GracyMsg", "GracyFile", "GracyVideo", "GracyForward",
    # 发送函数
    "gracy_send_msg", "gracy_call_api", "gracy_get_platform_info",
    # 装饰器
    "on_command", "on_regex", "on_keyword",
    "gracy_plugin", "plugin_handler", "on_fallback",
    "require_permission", "require_master",
    "rate_limit", "cooldown",
    "with_session", "async_retry", "background",
    "PluginContext", "DECORATOR_COMMAND_REGISTRY",
    # 配置
    "BOT_VERSION", "MASTER_ID", "ROBOT_ID", "ROBOT_START_TIME", "LOG_ENCODING",
    "get_current_master_id", "get_current_robot_id",
    # 核心服务
    "plugin_manager", "config_manager", "logger", "get_logger", "with_logger", "log_attrs",
    # 路径工具
    "get_logs_dir", "get_storage_dir", "get_res_config_dir",
    # 数据库
    "get_db",
    # 安全 / 监控
    "sanitize_log", "monitor_manager",
    # CLI
    "register_cli_command",
    # Web 服务
    "Quart", "send_from_directory", "Blueprint", "request", "Config", "serve",
    # Gracone
    "Stage", "RuntimeRegistry", "GracyEvent", "IdentityTag",
]
