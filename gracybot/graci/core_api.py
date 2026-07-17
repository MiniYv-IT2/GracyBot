"""核心 API 组件（发送、配置、服务等）"""

# ── 发送函数 ──
from gracybot.core.gracy_adapter.send import gracy_send_msg
from gracybot.core.gracy_adapter.send import gracy_call_api
from gracybot.core.gracy_adapter.send import gracy_get_platform_info

# ── 配置常量 ──
from gracybot.core.config import BOT_VERSION
from gracybot.core.config import MASTER_ID
from gracybot.core.config import ROBOT_ID
from gracybot.core.config import ROBOT_START_TIME
from gracybot.core.config import LOG_ENCODING
from gracybot.core.config import get_current_master_id
from gracybot.core.config import get_current_robot_id

# ── 插件管理 ──
from gracybot.core.plugin_manager import plugin_manager
from gracybot.core.config_manager import config_manager

# ── 日志 ──
from gracybot.core.utils import logger

def get_logger(name: str):
    """插件用：获取 Gracy 子日志器，终端显示 [Gracy] [name]"""
    return logger.getChild(name)

# ── 安全 ──
from gracybot.core.security import sanitize_log

# ── 监控 ──
from gracybot.core.monitor import monitor_manager

# ── CLI ──
from gracybot.core.tools.cli.plugins import register_cli_command

# ── Web 服务 ──
from gracybot.core.webserv import Quart, send_from_directory, Blueprint, request, Config, serve

# ── Pipeline / Runtime ──
from gracybot.core.pipeline import Stage
from gracybot.core.runtime import RuntimeRegistry
from gracybot.core.gracy_adapter.event import GracyEvent
from gracybot.core.gracy_adapter.identity import IdentityTag
