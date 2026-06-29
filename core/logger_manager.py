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

# ── 项目根目录探测 ──
_cwd = os.getcwd()
_gh = os.environ.get("GRACYBOT_HOME", "")
if _gh and os.path.isdir(os.path.join(_gh, 'logs')):
    project_root = _gh
elif os.path.isdir(os.path.join(_cwd, 'logs')) or os.path.isfile(os.path.join(_cwd, 'bot.py')):
    project_root = _cwd
else:
    project_root = _cwd
sys.path.insert(0, project_root)
sys.path.append(os.path.join(project_root, 'style'))

try:
    from style.log_colors import colorize_level, colorize_message, supports_color
except ImportError:
    def colorize_level(level_name): return level_name
    def colorize_message(message, level='INFO'): return message
    def supports_color(): return False

try:
    from style.styling import format_context_to_chinese, format_message_to_chinese, encrypt_user_id
except ImportError:
    def format_context_to_chinese(context_data): return str(context_data)
    def format_message_to_chinese(message): return str(message)
    def encrypt_user_id(user_id): return str(user_id)

LOG_DIR = os.path.join(project_root, 'logs')

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


class StructuredLogFormatter(logging.Formatter):
    """结构化日志格式化器"""
    def __init__(self, structured: bool = False, include_stack_info: bool = False, force_no_color: bool = False):
        self.structured = structured
        self.include_stack_info = include_stack_info
        self.force_no_color = force_no_color
        super().__init__(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    def format(self, record: logging.LogRecord) -> str:
        if self.structured:
            return self._format_structured(record)
        return self._format_console(record)

    def _format_structured(self, record: logging.LogRecord) -> str:
        log_data = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }
        try:
            from core.gracy_adapter.pool import adapter_pool
            default = adapter_pool.get_default()
            if default and hasattr(default, '_instance_robot_id'):
                log_data['robot_id'] = default._instance_robot_id
        except Exception:
            pass
        if hasattr(record, 'context'):
            log_data['context'] = record.context
        if record.exc_info:
            log_data['error'] = {'type': record.exc_info[0].__name__, 'message': str(record.exc_info[1])}
            if self.include_stack_info:
                log_data['stack_trace'] = ''.join(traceback.format_exception(*record.exc_info))
        return json.dumps(log_data, ensure_ascii=False)

    def _format_console(self, record: logging.LogRecord) -> str:
        original_message = record.getMessage()
        # 中文格式化 + 上下文
        if hasattr(record, 'context') and record.context:
            try:
                chinese_ctx = format_context_to_chinese(record.context)
                chinese_msg = format_message_to_chinese(original_message)
                if "[回调基础] 收到消息" in chinese_msg:
                    msg_type = record.context.get('chat_type', '') if isinstance(record.context, dict) else ''
                    if msg_type == 'private':
                        chinese_msg = "[私聊消息] " + chinese_msg.replace("[回调基础] 收到消息", "收到私聊消息")
                    elif msg_type == 'group':
                        chinese_msg = "[群聊消息] " + chinese_msg.replace("[回调基础] 收到消息", "收到群聊消息")
                    else:
                        chinese_msg = "[消息] " + chinese_msg.replace("[回调基础] 收到消息", "收到消息")
                final_message = f"{chinese_msg} | {chinese_ctx}" if chinese_ctx else chinese_msg
            except Exception:
                final_message = f"{original_message} | {str(record.context)}"
        else:
            try:
                final_message = format_message_to_chinese(original_message)
            except Exception:
                final_message = original_message

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        level_name = getattr(record, 'original_levelname', record.levelname)

        if self.force_no_color:
            # 文件日志：统一新格式（无颜色）
            try:
                from core.tools.log_tool import parse_logger_name, build_attrs, format_console_line
                category, module = parse_logger_name(record.name)
                attrs = build_attrs(record)
                return format_console_line(timestamp, category, level_name, module, attrs, final_message)
            except Exception:
                return f"{timestamp} - {record.name} - {level_name} - {final_message}"
        else:
            # 控制台：新格式 [分类] [模块] [属性]
            try:
                from core.tools.log_tool import parse_logger_name, build_attrs, format_console_line
                category, module = parse_logger_name(record.name)
                attrs = build_attrs(record)
                use_color = getattr(record, 'color_enabled', False)
                if use_color:
                    cl = colorize_level(level_name)
                    cm = colorize_message(final_message, level_name)
                    return format_console_line(timestamp, category, cl, module, attrs, cm)
                return format_console_line(timestamp, category, level_name, module, attrs, final_message)
            except Exception:
                return f"{timestamp} - {record.name} - {level_name} - {final_message}"


class _SafeRotatingFileHandler(logging.handlers.TimedRotatingFileHandler):
    """Windows 安全的轮转 handler"""
    def doRollover(self):
        try:
            super().doRollover()
        except PermissionError:
            pass


class _ConsoleHandler(logging.Handler):
    """队列驱动的控制台处理器"""
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
            self._queue.put_nowait(self.format(record))
        except Exception:
            self.handleError(record)


class LoggerManager:
    """日志管理器"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loggers = {}
            cls._instance._setup_completed = False
        return cls._instance

    def _create_file_handler(self, filename, level, structured=True, backup_count=7, include_stack=False):
        log_file = os.path.join(LOG_DIR, filename)
        handler = _SafeRotatingFileHandler(
            log_file, when='midnight', interval=1, backupCount=backup_count, encoding=LOG_ENCODING
        )
        handler.setLevel(level)
        handler.setFormatter(StructuredLogFormatter(structured=structured, include_stack_info=include_stack, force_no_color=True))
        return handler

    def _create_console_handler(self, level):
        handler = _ConsoleHandler()
        handler.setLevel(level)
        handler.setFormatter(StructuredLogFormatter(structured=False))
        color_filter = logging.Filter()
        color_filter.filter = lambda r: setattr(r, 'color_enabled', supports_color()) or True
        handler.addFilter(color_filter)
        return handler

    def setup(self, log_level: str = LOG_LEVEL, structured: bool = False) -> bool:
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
            root_logger = logging.getLogger()
            root_logger.setLevel(getattr(logging, log_level))
            for h in root_logger.handlers[:]:
                root_logger.removeHandler(h)

            root_logger.addHandler(self._create_console_handler(getattr(logging, log_level)))
            root_logger.addHandler(self._create_file_handler('gracybot.log', logging.DEBUG, structured, 7, True))
            root_logger.addHandler(self._create_file_handler('gracybot_error.log', logging.ERROR, structured, 14, True))

            for silenced in ("launart", "aiohttp.access", "aiohttp.client", "aiohttp.internal"):
                logging.getLogger(silenced).setLevel(logging.WARNING)
                logging.getLogger(silenced).propagate = False

            # HTTP 日志器
            http_logger = self.get_logger('GracyBot-HTTP')
            for h in http_logger.handlers[:]:
                http_logger.removeHandler(h)
            http_logger.addHandler(self._create_file_handler('gracybot_http.log', logging.INFO, structured, 7, False))

            # Gracy 日志器只传播
            gracy_logger = self.get_logger('Gracy')
            for h in gracy_logger.handlers[:]:
                gracy_logger.removeHandler(h)
            gracy_logger.propagate = True

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
        if name not in self._loggers:
            self._loggers[name] = logging.getLogger(name)
        return self._loggers[name]

    def set_level(self, level: str, logger_name: Optional[str] = None) -> bool:
        try:
            log_level = getattr(logging, level)
            if logger_name:
                (self._loggers.get(logger_name) or logging.getLogger(logger_name)).setLevel(log_level)
            else:
                logging.getLogger().setLevel(log_level)
                for h in logging.getLogger().handlers:
                    if isinstance(h, logging.StreamHandler):
                        h.setLevel(log_level)
            self.get_logger('GracyBot').info(f"日志级别 {'全局' if not logger_name else f'日志器 {logger_name}'} 设置为 {level}")
            return True
        except Exception as e:
            print(f"❌ 设置日志级别失败: {str(e)}")
            return False

    def log_with_context(self, logger, level, message="无日志消息", context=None, exc_info=False, **kwargs) -> None:
        if isinstance(logger, str):
            logger = self.get_logger(logger)
        if not hasattr(logger, 'log'):
            print(f"❌ 无效的logger对象: {type(logger)}")
            return

        extra = {}
        if context:
            extra['context'] = context

        if isinstance(level, str):
            mapping = {'DEBUG': logging.DEBUG, 'INFO': logging.INFO, 'WARNING': logging.WARNING,
                       'ERROR': logging.ERROR, 'CRITICAL': logging.CRITICAL, 'SUCCESS': logging.INFO}
            extra['original_levelname'] = level.upper()
            level = mapping.get(level.upper(), logging.INFO)

        if isinstance(message, dict):
            message = json.dumps(message, ensure_ascii=False)

        logger.log(level, message, extra=extra, exc_info=exc_info)

    # 兼容旧 API
    def setup_logging(self, log_level: str = LOG_LEVEL, debug_mode: bool = False) -> bool:
        return self.setup(log_level=log_level, structured=debug_mode)


# ── 全局实例 ──
logger_manager = LoggerManager()
logger = logger_manager.get_logger('Gracy')
