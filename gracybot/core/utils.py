import json
import logging
from typing import Optional, Dict, Any

# 从 core 包导入配置模块
from gracybot.core.config import AUTO_REPLIES, LOG_LEVEL, DEBUG_MODE

# 导入配置管理器
from gracybot.core.config_manager import config_manager

# 先导入logger_manager但不使用，避免循环导入问题
from gracybot.core.logger_manager import LoggerManager

# 创建日志管理器实例
logger_manager = LoggerManager()

# 初始化日志系统
logger_manager.setup_logging(
    log_level=LOG_LEVEL,
    debug_mode=DEBUG_MODE  # 调试模式下使用结构化日志
)

# 创建日志实例
logger = logger_manager.get_logger('Gracy')

# 可选：日志脱敏过滤器（core.security 不存在时跳过）
try:
    from gracybot.core.security import SanitizeLogFilter
    _sanitize_filter = SanitizeLogFilter()
    logger_manager.get_logger('').addFilter(_sanitize_filter)
    for _name in ['GracyBot', 'Gracy', 'GracyBot-Plugin', 'Gracy.Send', 'GracyPipeline', 'GracyEvent']:
        logger_manager.get_logger(_name).addFilter(_sanitize_filter)
except ImportError:
    pass

# ========== 自动回复工具（全局复用，关键词匹配逻辑） ==========
def handle_auto_reply(msg: str) -> Optional[str]:
    """
    关键词自动回复匹配（基于配置文件AUTO_REPLIES）
    :param msg: 用户输入消息
    :return: 匹配到关键词返回回复内容，无匹配返回None
    """
    if not msg:
        return None
    
    # 转换为小写进行匹配，提高匹配率
    msg_lower = msg.lower()
    
    # 记录匹配过程（DEBUG级别）
    logger.debug(f"[自动回复] 尝试匹配消息：{msg[:50]}{'...' if len(msg) > 50 else ''}")
    
    # 优先匹配最长的关键词，避免短关键词错误匹配
    sorted_keywords = sorted(AUTO_REPLIES.keys(), key=len, reverse=True)
    
    for keyword in sorted_keywords:
        if keyword.lower() in msg_lower:
            reply = AUTO_REPLIES[keyword]
            logger_manager.log_with_context(
                logger, 
                logging.INFO, 
                "[自动回复] 关键词匹配成功",
                context={
                    "keyword": keyword,
                    "reply_preview": reply[:30] + ("..." if len(reply) > 30 else "")
                }
            )
            return reply
    
    logger.debug("[自动回复] 未匹配到任何关键词")
    return None
