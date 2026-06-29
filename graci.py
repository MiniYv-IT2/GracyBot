"""
graci — GracyBot 插件公共 API（外观层）

插件只需 from graci import xxx，不直接 from core.xxx。
框架内部重构时只改本文件转发，插件零改动。

用法:
    from graci import GracyText, GracyImage, GracyVoice, GracyAt, GracyReply, GracyMsg, GracyFile, GracyVideo, GracyForward
    from graci import gracy_send_msg, gracy_call_api
    from graci import on_command, on_regex, on_keyword
    from graci import plugin_handler, require_permission, rate_limit, cooldown
    from graci import PluginContext
"""

# ── 消息类型 ──
from core.gracy_adapter.message import GracyText
from core.gracy_adapter.message import GracyImage
from core.gracy_adapter.message import GracyVoice
from core.gracy_adapter.message import GracyAt
from core.gracy_adapter.message import GracyReply
from core.gracy_adapter.message import GracyMsg
from core.gracy_adapter.message import GracyFile
from core.gracy_adapter.message import GracyVideo
from core.gracy_adapter.message import GracyForward

# ── 发送函数 ──
from core.gracy_adapter.send import gracy_send_msg
from core.gracy_adapter.send import gracy_call_api
from core.gracy_adapter.send import gracy_get_platform_info

# ── 装饰器 ──
from core.decorators import (
    on_command, on_regex, on_keyword,
    gracy_plugin, plugin_handler,
    require_permission, require_master,
    rate_limit, cooldown,
    with_session, async_retry, background,
    PluginContext,
)
from core.decorators.registration import on_fallback
from core.decorators.registration import DECORATOR_COMMAND_REGISTRY

# ── 配置常量 ──
from core.config import BOT_VERSION
from core.config import MASTER_ID
from core.config import ROBOT_ID
from core.config import ROBOT_START_TIME
from core.config import LOG_ENCODING
from core.config import get_current_master_id
from core.config import get_current_robot_id

# ── 插件管理 ──
from core.plugin_manager import plugin_manager
from core.config_manager import config_manager

# ── 日志 ──
from core.utils import logger
from core.decorators.logger import with_logger, log_attrs

def get_logger(name: str):
    """插件用：获取 Gracy 子日志器，终端显示 [Gracy] [name]"""
    return logger.getChild(name)

# ── 安全 ──
from core.security import sanitize_log

# ── 监控 ──
from core.monitor import monitor_manager

# ── CLI ──
from core.tools.cli.plugins import register_cli_command

# ── Web 服务 ──
from core.webserv import Quart, send_from_directory, Blueprint, request, Config, serve

# ── Pipeline / Runtime ──
from core.pipeline import Stage
from core.runtime import RuntimeRegistry
from core.gracy_adapter.event import GracyEvent
from core.gracy_adapter.identity import IdentityTag

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
    # 安全 / 监控
    "sanitize_log", "monitor_manager",
    # CLI
    "register_cli_command",
    # Web 服务
    "Quart", "send_from_directory", "Blueprint", "request", "Config", "serve",
    # Gracone
    "Stage", "RuntimeRegistry", "GracyEvent", "IdentityTag",
]
