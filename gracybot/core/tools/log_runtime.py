"""Runtime 实例独立日志器

为每个机器人实例创建独立的日志文件 (logs/instances/<name>/runtime.log)。
"""

import os
import logging
from typing import Optional, Set

from gracybot.core.logger_manager import _SafeRotatingFileHandler, LOG_DIR, LOG_ENCODING

RUNTIME_LOG_DIR = os.path.join(LOG_DIR, 'instances')
_RUNTIME_LOGGER_NAMES: Set[str] = set()


def setup_runtime_logger(instance_name: str, bot_name: str = None) -> logging.Logger:
    """为 Runtime 创建独立的子日志器

    日志器名称: "Gracy.<bot_name>"（终端显示为 [Gracy] [<bot_name>]）
    传播策略: propagate=True，日志同步到 Root Logger → 终端
    独立文件: logs/instances/<instance_name>/runtime.log

    Args:
        instance_name: 实例目录名（storage/instances/<name>）
        bot_name: 实例显示名称，默认同 instance_name

    Returns:
        配置好的 Logger 实例
    """
    display_name = bot_name or instance_name
    logger = logging.getLogger(f"Gracy.{display_name}")
    _RUNTIME_LOGGER_NAMES.add(display_name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = True

    # 清除已有 handler（避免热重载重复添加）
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # 为该实例创建独立文件 handler
    instance_log_dir = os.path.join(RUNTIME_LOG_DIR, instance_name)
    os.makedirs(instance_log_dir, exist_ok=True)

    log_path = os.path.join(instance_log_dir, "runtime.log")
    handler = _SafeRotatingFileHandler(
        log_path,
        when='midnight',
        interval=1,
        backupCount=7,
        encoding=LOG_ENCODING,
    )
    handler.setLevel(logging.DEBUG)

    # 文件日志格式化器（force_no_color=True 确保文件日志无颜色码）
    from gracybot.core.logger_manager import StructuredLogFormatter
    handler.setFormatter(
        StructuredLogFormatter(structured=False, include_stack_info=True, force_no_color=True)
    )
    logger.addHandler(handler)

    return logger
