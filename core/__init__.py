"""GracyBot 核心模块统一导入文件

此模块提供核心组件的统一导出，简化其他模块的导入路径，提高代码可维护性。
"""

# 核心管理器
def _get_plugin_manager():
    """延迟导入插件管理器，避免循环依赖"""
    from .plugin_manager import plugin_manager
    return plugin_manager

def _get_security_manager():
    """延迟导入安全管理器，避免循环依赖"""
    from .security_manager import security_manager
    return security_manager

def _get_config_manager():
    """延迟导入配置管理器，避免循环依赖"""
    from .config_manager import config_manager
    return config_manager

def _get_monitor_manager():
    """延迟导入监控管理器，避免循环依赖"""
    from .monitor import monitor_manager
    return monitor_manager

def _get_logger_manager():
    """延迟导入日志管理器，避免循环依赖"""
    from .logger_manager import logger_manager
    return logger_manager

def _get_runtime_registry():
    """延迟导入 Runtime 注册表，避免循环依赖"""
    from .runtime import RuntimeRegistry
    return RuntimeRegistry

# 使用属性描述器实现延迟加载
class LazyLoader:
    """延迟加载属性描述器"""
    def __init__(self, loader_func):
        self.loader_func = loader_func
        self.__doc__ = loader_func.__doc__
    
    def __get__(self, instance, owner):
        value = self.loader_func()
        setattr(owner, self.name, value)
        return value
    
    def __set_name__(self, owner, name):
        self.name = name

class Core:
    """核心组件容器类，提供统一的核心组件访问入口"""
    
    # 延迟加载的核心管理器
    plugin_manager = LazyLoader(_get_plugin_manager)
    security_manager = LazyLoader(_get_security_manager)
    config_manager = LazyLoader(_get_config_manager)
    monitor_manager = LazyLoader(_get_monitor_manager)
    logger_manager = LazyLoader(_get_logger_manager)
    runtime_registry = LazyLoader(_get_runtime_registry)

# 创建核心组件实例
core = Core()

# 导出核心组件
def get_plugin_manager():
    """获取插件管理器实例"""
    return core.plugin_manager

def get_security_manager():
    """获取安全管理器实例"""
    return core.security_manager

def get_config_manager():
    """获取配置管理器实例"""
    return core.config_manager

def get_monitor_manager():
    """获取监控管理器实例"""
    return core.monitor_manager

def get_logger_manager():
    """获取日志管理器实例"""
    return core.logger_manager

def get_runtime_registry():
    """获取 Runtime 注册表实例"""
    return core.runtime_registry

# 导出主要工具函数和常量（容错导入，避免缺依赖时崩整个包）
try:
    from core.handler import callback_base
except ImportError:
    callback_base = None

try:
    from core.utils import logger, sanitize_log
except ImportError:
    logger = None
    sanitize_log = None

# 版本信息（懒加载，避免导入时触发配置系统）
def _get_version():
    from core.config import BOT_VERSION
    return BOT_VERSION.removeprefix('v')

__version__ = _get_version()
__all__ = [
    # 核心管理器访问函数
    "get_plugin_manager",
    "get_security_manager",
    "get_config_manager",
    "get_monitor_manager",
    "get_logger_manager",
    "get_runtime_registry",
    # 核心组件实例（延迟加载）
    "core",
    # 主要函数
    "callback_base",
    "sanitize_log",
    # 日志对象
    "logger",
    # 版本信息
    "__version__"
]

# 模块加载完成日志（仅子进程打印，避免热重载双重输出）
import os as _os
if _os.environ.get("WERKZEUG_RUN_MAIN") == "true":
    logger.info(f"✅ 核心模块加载完成，版本: v{__version__}")
