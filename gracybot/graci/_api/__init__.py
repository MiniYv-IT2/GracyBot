"""核心 API 组件（发送、配置、服务等）"""
from gracybot.core.gracy_adapter.send import gracy_send_msg
from gracybot.core.gracy_adapter.send import gracy_call_api
from gracybot.core.gracy_adapter.send import gracy_get_platform_info

from gracybot.core.config import BOT_VERSION
from gracybot.core.config import MASTER_ID
from gracybot.core.config import ROBOT_ID
from gracybot.core.config import ROBOT_START_TIME
from gracybot.core.config import LOG_ENCODING
from gracybot.core.config import get_current_master_id
from gracybot.core.config import get_current_robot_id

from gracybot.core.plugin_manager import plugin_manager
from gracybot.core.config_manager import config_manager

from gracybot.core.utils import logger

def get_logger(name: str):
    return logger.getChild(name)

from gracybot.core.security import sanitize_log

from gracybot.core.tools.paths import get_logs_dir
from gracybot.core.tools.paths import get_storage_dir
from gracybot.core.tools.paths import get_res_config_dir
from gracybot.core.tools.paths import get_res_dir

from gracybot.core.db_manager import get_db

from gracybot.core.monitor import monitor_manager

from gracybot.core.webserv import Quart, send_from_directory, Blueprint, request, Config, serve

from gracybot.core.pipeline import Stage
from gracybot.core.runtime import RuntimeRegistry
from gracybot.core.gracy_adapter.event import GracyEvent
from gracybot.core.gracy_adapter.identity import IdentityTag

__all__ = [
    "gracy_send_msg", "gracy_call_api", "gracy_get_platform_info",
    "BOT_VERSION", "MASTER_ID", "ROBOT_ID", "ROBOT_START_TIME", "LOG_ENCODING",
    "get_current_master_id", "get_current_robot_id",
    "plugin_manager", "config_manager",
    "logger", "get_logger",
    "sanitize_log", "monitor_manager",
    "get_logs_dir", "get_storage_dir", "get_res_config_dir",
    "get_res_dir",
    "get_db",
    "Quart", "send_from_directory", "Blueprint", "request", "Config", "serve",
    "Stage", "RuntimeRegistry", "GracyEvent", "IdentityTag",
]
