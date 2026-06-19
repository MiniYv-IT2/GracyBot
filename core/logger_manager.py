import os
import json
import logging
import logging.handlers
import sys
import traceback
import threading
import queue
from datetime import datetime
from typing import Dict, Any, Optional

from core.config import LOG_ENCODING, LOG_LEVEL

# 设置导入路径：优先 GRACYBOT_HOME，然后 CWD（有 logs 或 bot.py），最后默认 CWD
_cwd = os.getcwd()
_gh = os.environ.get("GRACYBOT_HOME", "")
if _gh and os.path.isdir(os.path.join(_gh, 'logs')):
    project_root = _gh
elif os.path.isdir(os.path.join(_cwd, 'logs')) or os.path.isfile(os.path.join(_cwd, 'bot.py')):
    project_root = _cwd
else:
    # pip 安装后无 GRACYBOT_HOME 时，默认用当前工作目录
    project_root = _cwd
sys.path.insert(0, project_root)
sys.path.append(os.path.join(project_root, 'style'))

try:
    from style.log_colors import colorize_level, colorize_message, supports_color
except ImportError:
    # 颜色模块备用实现
    def colorize_level(level_name):
        return level_name
    
    def colorize_message(message, level='INFO'):
        return message
    
    def supports_color():
        return False

try:
    from style.styling import format_context_to_chinese, format_message_to_chinese, encrypt_user_id
except ImportError:
    # 样式模块备用实现（简化版）
    def format_context_to_chinese(context_data):
        return str(context_data)
    
    def format_message_to_chinese(message):
        return str(message)
    
    def encrypt_user_id(user_id):
        """加密用户ID为'用户****后4位'格式"""
        return str(user_id)

# 日志目录
LOG_DIR = os.path.join(project_root, 'logs')

# Windows 终端编码修复（模块加载后立即生效，覆盖所有 print/logging 输出）
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

class StructuredLogFormatter(logging.Formatter):
    """结构化日志格式化器，支持JSON和人类可读格式"""
    def __init__(self, structured: bool = False, include_stack_info: bool = False, force_no_color: bool = False):
        self.structured = structured
        self.include_stack_info = include_stack_info
        self.force_no_color = force_no_color  # 文件日志强制去色，防止控制台 filter 泄漏
        if structured:
            super().__init__()
        else:
            super().__init__(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
    

    
    def _format_context_to_chinese(self, context_data):
        """将上下文数据转换为中文显示格式"""
        return format_context_to_chinese(context_data)
    
    def _format_message_to_chinese(self, message):
        """将消息内容转换为中文格式"""
        try:
            return format_message_to_chinese(message)
        except Exception:
            return str(message)
    
    def format(self, record: logging.LogRecord) -> str:
        if self.structured:
            # 构建结构化日志数据
            log_data = {
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'level': record.levelname,
                'logger': record.name,
                'message': record.getMessage(),
                'process': record.process,
                'thread': record.threadName
            }

            # robot_id 从 AdapterPool 获取（多实例时取第一个有值的）
            try:
                from core.gracy_adapter.pool import adapter_pool
                default = adapter_pool.get_default()
                if default and hasattr(default, '_instance_robot_id'):
                    log_data['robot_id'] = default._instance_robot_id
                else:
                    log_data['robot_id'] = ''
            except Exception:
                log_data['robot_id'] = ''
            
            # 添加额外的上下文信息
            if hasattr(record, 'context'):
                log_data['context'] = record.context
            
            # 添加错误信息
            if record.exc_info:
                log_data['error'] = {
                    'type': record.exc_info[0].__name__,
                    'message': str(record.exc_info[1])
                }
                if self.include_stack_info:
                    log_data['stack_trace'] = ''.join(
                        traceback.format_exception(*record.exc_info)
                    )
            
            return json.dumps(log_data, ensure_ascii=False)
        else:
            # 处理消息和上下文
            original_message = record.getMessage()
            
            # 强制使用中文格式化和颜色
            if hasattr(record, 'context') and record.context:
                try:
                    chinese_context = self._format_context_to_chinese(record.context)
                    chinese_message = self._format_message_to_chinese(original_message)
                    
                    # 特殊处理：处理"[回调基础] 收到消息"格式
                    if "[回调基础] 收到消息" in chinese_message:
                        # 从上下文中提取消息类型信息
                        message_type = ""
                        if isinstance(record.context, dict):
                            message_type = record.context.get('message_type', '')
                        
                        # 根据消息类型格式化
                        if message_type == 'private':
                            chinese_message = "[私聊消息] " + chinese_message.replace("[回调基础] 收到消息", "收到私聊消息")
                        elif message_type == 'group':
                            chinese_message = "[群聊消息] " + chinese_message.replace("[回调基础] 收到消息", "收到群聊消息")
                        else:
                            chinese_message = "[消息] " + chinese_message.replace("[回调基础] 收到消息", "收到消息")
                    final_message = f"{chinese_message} | {chinese_context}" if chinese_context else chinese_message
                except Exception:
                    # 如果中文格式化失败，使用原始消息
                    final_message = f"{original_message} | {str(record.context)}"
            else:
                try:
                    final_message = self._format_message_to_chinese(original_message)
                except Exception:
                    final_message = original_message
            
            # 构建基础格式
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            logger_name = record.name
            level_name = getattr(record, 'original_levelname', record.levelname)
            
            # 从 Gracy.<bot_name> 格式提取实例名，替换 logger 名称显示为 [主号]
            # 只对 setup_runtime_logger 注册的实例生效
            if logger_name.startswith("Gracy.") and "." in logger_name:
                inst = logger_name.split(".", 1)[1]
                if inst and inst in _RUNTIME_LOGGER_NAMES:
                    logger_name = f"[{inst}]"
            
            # 使用颜色格式（仅控制台启用颜色时；文件日志 force_no_color 永远去色）
            try:
                use_color = False if self.force_no_color else getattr(record, 'color_enabled', False)
                if use_color:
                    colored_level = colorize_level(level_name)
                    colored_message = colorize_message(final_message, level_name)
                else:
                    colored_level = level_name
                    colored_message = final_message
                formatted = f"{timestamp} - {logger_name} - {colored_level} - {colored_message}"
            except Exception:
                # 如果颜色格式化失败，使用无颜色格式
                formatted = f"{timestamp} - {logger_name} - {level_name} - {final_message}"
            
            return formatted

class _SafeRotatingFileHandler(logging.handlers.TimedRotatingFileHandler):
    """Windows 安全的轮转 handler——轮转失败时静默继续写，不崩溃"""
    def doRollover(self):
        try:
            super().doRollover()
        except PermissionError:
            pass


class _ConsoleHandler(logging.Handler):
    """后台线程 + 队列驱动的控制台处理器

    所有 log record 通过线程安全队列投递到后台消费线程，
    后台线程独立于主线程和 hypercorn 事件循环，确保终端输出永不卡死。
    """

    _queue: queue.Queue = queue.Queue(maxsize=1000)
    _thread: threading.Thread = None
    _started: bool = False
    _lock: threading.Lock = threading.Lock()

    @classmethod
    def _ensure_thread(cls):
        if cls._started:
            return
        with cls._lock:
            if cls._started:
                return
            cls._started = True
            cls._thread = threading.Thread(target=cls._consumer, daemon=True, name="ConsoleWriter")
            cls._thread.start()

    @classmethod
    def _consumer(cls):
        """后台消费者线程 — 从队列取日志并 print 到控制台"""
        while True:
            try:
                text = cls._queue.get(timeout=30)
                while text is not None:
                    print(text, flush=True)
                    cls._queue.task_done()
                    text = cls._queue.get(timeout=1)
            except queue.Empty:
                continue
            except Exception:
                pass

    def __init__(self):
        super().__init__()
        self._ensure_thread()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self._queue.put_nowait(msg)
        except Exception:
            self.handleError(record)


class LoggerManager:
    """企业级日志管理器"""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loggers = {}
            cls._instance._setup_completed = False
        return cls._instance
    
    def setup_logging(self, log_level: str = LOG_LEVEL, debug_mode: bool = False) -> bool:
        """设置日志系统（兼容旧版API）"""
        # 将debug_mode转换为structured参数
        # 在debug_mode下使用结构化日志
        return self.setup(log_level=log_level, structured=debug_mode)
    
    def _create_rotating_file_handler(self, filename, level, structured=True, backup_count=7, include_stack_info=False):
        """创建轮转文件处理器"""
        log_file = os.path.join(LOG_DIR, filename)
        handler = _SafeRotatingFileHandler(
            log_file,
            when='midnight',
            interval=1,
            backupCount=backup_count,
            encoding=LOG_ENCODING
        )
        handler.setLevel(level)
        formatter = StructuredLogFormatter(structured=structured, include_stack_info=include_stack_info, force_no_color=True)
        handler.setFormatter(formatter)
        return handler
    
    def _create_console_handler(self, level, structured=False):
        """创建控制台处理器"""
        # 用 _ConsoleHandler，直接 print(flush=True) 输出
        # 不依赖 sys.stdout，避免 hypercorn 接管事件循环后 stdout 被劫持
        handler = _ConsoleHandler()
        handler.setLevel(level)
        formatter = StructuredLogFormatter(structured=structured, include_stack_info=False)
        handler.setFormatter(formatter)

        # 添加颜色支持过滤器
        def add_color_support(record):
            record.color_enabled = supports_color()
            return True
        
        color_filter = logging.Filter()
        color_filter.filter = add_color_support
        handler.addFilter(color_filter)

        return handler
    
    def setup(self, log_level: str = LOG_LEVEL, structured: bool = False) -> bool:
        """设置日志系统"""
        try:
            # 创建日志目录
            if not os.path.exists(LOG_DIR):
                os.makedirs(LOG_DIR, exist_ok=True)
            
            # 根日志记录器设置
            root_logger = logging.getLogger()
            root_logger.setLevel(getattr(logging, log_level))
            
            # 清除已有的处理器
            for handler in root_logger.handlers[:]:
                root_logger.removeHandler(handler)
            
            # 添加控制台处理器
            console_handler = self._create_console_handler(getattr(logging, log_level), structured=False)
            root_logger.addHandler(console_handler)
            
            # logging.StreamHandler.emit() 自带 flush，无需 reconfigure stdout
            
            # 添加文件处理器
            file_handler = self._create_rotating_file_handler('gracybot.log', logging.DEBUG, structured, 7, True)
            root_logger.addHandler(file_handler)
            
            # 添加错误日志文件处理器
            error_handler = self._create_rotating_file_handler('gracybot_error.log', logging.ERROR, structured, 14, True)
            root_logger.addHandler(error_handler)
            
            # 创建HTTP访问日志
            http_logger = self.get_logger('GracyBot-HTTP')
            http_handler = self._create_rotating_file_handler('gracybot_http.log', logging.INFO, structured, 7, False)
            
            # 清除HTTP日志器的处理器，只保留我们的文件处理器
            for handler in http_logger.handlers[:]:
                http_logger.removeHandler(handler)
            http_logger.addHandler(http_handler)
            
            # HTTP日志器传播到根日志器，确保所有日志都被记录
            # http_logger.propagate = True
            
            # Gracy日志器传播到根日志器（由根日志器统一输出到文件和控制台）
            http_pure_logger = self.get_logger('Gracy')
            http_pure_logger.propagate = True
            
            # 清除HTTP-Pure日志器的处理器，避免重复输出
            for handler in http_pure_logger.handlers[:]:
                http_pure_logger.removeHandler(handler)
            
            self._setup_completed = True

            main_logger = self.get_logger('GracyBot')
            main_logger.info(f"日志系统初始化完成，级别: {log_level}")
            main_logger.info(f"日志文件目录: {LOG_DIR}")
            main_logger.info(f"结构化日志: {'是' if structured else '否'}")
            
            return True
        except Exception as e:
            print(f"❌ 日志系统初始化失败: {str(e)}")
            return False
    
    def get_logger(self, name: str) -> logging.Logger:
        """获取指定名称的日志器"""
        if name not in self._loggers:
            logger = logging.getLogger(name)
            self._loggers[name] = logger
        
        return self._loggers[name]
    
    def set_level(self, level: str, logger_name: Optional[str] = None) -> bool:
        """动态设置日志级别"""
        try:
            log_level = getattr(logging, level)
            
            if logger_name:
                # 设置特定日志器级别
                if logger_name in self._loggers:
                    self._loggers[logger_name].setLevel(log_level)
                else:
                    logging.getLogger(logger_name).setLevel(log_level)
                self.get_logger('GracyBot-Logger').info(f"日志器 {logger_name} 级别设置为 {level}")
            else:
                # 设置根日志器级别
                root_logger = logging.getLogger()
                root_logger.setLevel(log_level)
                # 更新所有处理器的级别
                for handler in root_logger.handlers:
                    if isinstance(handler, logging.StreamHandler):
                        handler.setLevel(log_level)
                self.get_logger('GracyBot-Logger').info(f"全局日志级别设置为 {level}")
            
            return True
        except Exception as e:
            print(f"❌ 设置日志级别失败: {str(e)}")
            return False
    
    def log_with_context(self, logger, level, message="无日志消息", context=None, exc_info=False, **kwargs) -> None:
        """带上下文信息的日志记录"""
        # 检查logger是否为字符串类型
        if isinstance(logger, str):
            logger = self.get_logger(logger)
        
        # 确保logger是有效的logging.Logger对象
        if not hasattr(logger, 'log'):
            print(f"❌ 无效的logger对象: {type(logger)}")
            return
        
        # 保存原始级别名称用于颜色显示
        original_levelname = None
        
        # 智能处理level参数
        if isinstance(level, str):
            level_mapping = {
                'DEBUG': logging.DEBUG,
                'INFO': logging.INFO,
                'WARNING': logging.WARNING,
                'ERROR': logging.ERROR,
                'CRITICAL': logging.CRITICAL,
                'SUCCESS': logging.INFO
            }
            original_levelname = level.upper()
            level = level_mapping.get(original_levelname, logging.INFO)
        elif not isinstance(level, int):
            level = logging.INFO
        
        # 预处理消息
        processed_message = message
        if isinstance(message, dict):
            processed_message = json.dumps(message, ensure_ascii=False)
        
        # 使用extra参数传递上下文信息
        extra_params = {}
        if context:
            extra_params['context'] = context
        
        # 传递原始级别名称，以便格式化器正确显示颜色
        if original_levelname == 'SUCCESS':
            extra_params['original_levelname'] = 'SUCCESS'
        
        logger.log(level, processed_message, extra=extra_params, exc_info=exc_info)

# ══════════════════════════════════════════════════════════
# Runtime 独立日志器设置
# ══════════════════════════════════════════════════════════

RUNTIME_LOG_DIR = os.path.join(LOG_DIR, 'instances')

# 已注册的 Runtime 实例显示名称（供格式化器识别 [主号] 来自真实实例）
_RUNTIME_LOGGER_NAMES: set = set()


def setup_runtime_logger(instance_name: str, bot_name: str = None) -> logging.Logger:
    """为 Runtime 创建独立的子日志器

    日志器名称: "Gracy.<bot_name>"（终端显示为 [<bot_name>]）
    传播策略: propagate=True，日志同步到 Root Logger → 终端
    独立文件: logs/instances/<instance_name>/runtime.log

    Args:
        instance_name: 实例目录名（style/instances/<name>）
        bot_name: 实例显示名称（如"主号"、"小号"），默认同 instance_name

    Returns:
        配置好的 Logger 实例
    """
    display_name = bot_name or instance_name
    logger = logging.getLogger(f"Gracy.{display_name}")
    _RUNTIME_LOGGER_NAMES.add(display_name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = True  # ← 同步打印到终端（Root Logger 的 SanitizeLogFilter 自动脱敏）

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
    handler.setFormatter(StructuredLogFormatter(structured=False, include_stack_info=True, force_no_color=True))
    logger.addHandler(handler)

    logger.info(f"[Runtime:{instance_name}] 独立日志已初始化: {os.path.relpath(log_path)}")

    return logger


# 创建全局日志管理器实例
logger_manager = LoggerManager()

# 兼容旧代码的全局日志实例
logger = logger_manager.get_logger('Gracy')
