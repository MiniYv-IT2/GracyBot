"""命令注册装饰器 — @on_command / @on_regex / @on_keyword / @gracy_plugin

注册中心 DECORATOR_COMMAND_REGISTRY 存储所有通过装饰器声明的命令映射。
plugin_manager.py 会扫描此注册中心，与 TOML 元数据合并。
"""

import re
import inspect
from typing import List, Callable, Dict, Optional, Set

# ── 全局注册中心 ──

# 注册中心中的每一项:
# {
#     "commands": ["/cmd1", "/cmd2"],        # @on_command 声明的命令
#     "handler_func": <wrapped_function>,     # 装饰器包装后的函数
#     "plugin_name": "MyPlugin",              # 来源插件名
#     "permission": "all",                    # @require_permission 指定的权限
#     "patterns": [],                         # @on_regex 声明的正则
#     "keywords": [],                         # @on_keyword 声明的关键词
#     "chat_type": ["private", "group"],      # 适用聊天类型（默认全部）
#     "is_at_required": False,               # 是否需要 @机器人
# }
DECORATOR_COMMAND_REGISTRY: List[Dict] = []

# ── 未匹配消息兜底处理器 ──
# 当 CommandMatcher 无匹配时，会按注册顺序依次调用这些 handler
FALLBACK_HANDLERS: List[Dict] = []


# ── @on_fallback ──

class OnFallbackDecorator:
    """@on_fallback 装饰器 — 处理未被任何插件匹配的消息

    用于 AI 对话等场景：PluginHandler 无匹配后，ResponseSender 会调用此 handler。
    """

    def __call__(self, func):
        func._gracy_fallback = True
        return func


def on_fallback() -> OnFallbackDecorator:
    """声明为未匹配消息兜底处理器"""
    return OnFallbackDecorator()


# ── @on_command ──

class OnCommandDecorator:
    """@on_command 装饰器的内部实现

    用法:
        @on_command("/info", "/status")
        @plugin_handler
        async def handler(ctx): ...
    """

    def __init__(self, *commands: str):
        if not commands:
            raise ValueError("@on_command 至少需要一个命令参数")
        self._commands = list(commands)

    def __call__(self, func):
        # 标记函数，供 plugin_manager 扫描
        func._gracy_on_command = self._commands
        return func


def on_command(*commands: str) -> OnCommandDecorator:
    """声明命令触发入口

    可叠加多个命令:
        @on_command("/info", "/status")
    """
    return OnCommandDecorator(*commands)


# ── @on_regex ──

class OnRegexDecorator:
    """@on_regex 装饰器 — 正则匹配触发"""

    def __init__(self, pattern: str, flags: int = re.IGNORECASE):
        self._pattern = pattern
        self._compiled = re.compile(pattern, flags)

    def __call__(self, func):
        func._gracy_on_regex = (self._pattern, self._compiled)
        return func


def on_regex(pattern: str, flags: int = re.IGNORECASE) -> OnRegexDecorator:
    """声明正则表达式匹配触发"""
    return OnRegexDecorator(pattern, flags)


# ── @on_keyword ──

class OnKeywordDecorator:
    """@on_keyword 装饰器 — 关键词匹配触发"""

    def __init__(self, *keywords: str):
        if not keywords:
            raise ValueError("@on_keyword 至少需要一个关键词")
        self._keywords = list(keywords)

    def __call__(self, func):
        func._gracy_on_keyword = self._keywords
        return func


def on_keyword(*keywords: str) -> OnKeywordDecorator:
    """声明关键词触发"""
    return OnKeywordDecorator(*keywords)


# ── @gracy_plugin — 插件类装饰器 ──

def gracy_plugin(
    name: str,
    version: str = "1.0.0",
    author: str = "",
    description: str = "",
    icon: str = "",
):
    """插件类装饰器：标记一个类为 GracyBot 插件

    类中所有被 @on_command 标记的方法会被自动扫描注册。

    用法:
        @gracy_plugin(name="MyPlugin", version="1.0.0")
        class MyPlugin:
            @on_command("/hello")
            @plugin_handler
            async def hello(self, ctx): ...
    """
    def decorator(cls):
        cls._gracy_plugin_meta = {
            "name": name,
            "version": version,
            "author": author,
            "description": description,
            "icon": icon,
        }

        # 扫描类中所有被 @on_command 标记的方法
        if not hasattr(cls, "_gracy_on_command_methods"):
            cls._gracy_on_command_methods = []

        for attr_name, attr_val in cls.__dict__.items():
            if callable(attr_val) and hasattr(attr_val, "_gracy_on_command"):
                commands = attr_val._gracy_on_command
                cls._gracy_on_command_methods.append({
                    "method_name": attr_name,
                    "commands": commands,
                    "handler_func": attr_val,
                })

        return cls

    return decorator


# ── 注册函数：将装饰器标记的函数注册到全局注册中心 ──

def _register_decorated_function(
    func,
    plugin_name: str = "",
    permission: str = "all",
    chat_type: Optional[List[str]] = None,
    is_at_required: bool = False,
):
    """将装饰器标记的函数注册到 DECORATOR_COMMAND_REGISTRY

    由 plugin_manager.py 在加载插件时调用。
    """
    entry = {
        "commands": [],
        "patterns": [],
        "keywords": [],
        "handler_func": func,
        "plugin_name": plugin_name,
        "permission": permission,
        "chat_type": chat_type or ["private", "group"],
        "is_at_required": is_at_required,
    }

    if hasattr(func, "_gracy_on_command"):
        entry["commands"] = func._gracy_on_command

    if hasattr(func, "_gracy_on_regex"):
        pattern, compiled = func._gracy_on_regex
        entry["patterns"] = [(pattern, compiled)]

    if hasattr(func, "_gracy_on_keyword"):
        entry["keywords"] = func._gracy_on_keyword

    if not any([entry["commands"], entry["patterns"], entry["keywords"]]):
        raise ValueError(f"函数 {func.__name__} 没有 @on_command/@on_regex/@on_keyword 标记")

    DECORATOR_COMMAND_REGISTRY.append(entry)
    return entry


# ── 清理 ──

def clear_registry():
    """清空注册中心（主要用于测试/热重载）"""
    DECORATOR_COMMAND_REGISTRY.clear()
    FALLBACK_HANDLERS.clear()


def _register_fallback_function(
    func,
    plugin_name: str = "",
    chat_type: Optional[List[str]] = None,
    permission: str = "all",
):
    """将 @on_fallback 标记的函数注册到 FALLBACK_HANDLERS

    由 plugin_manager.py 在加载插件时调用。
    """
    if not hasattr(func, "_gracy_fallback"):
        return
    entry = {
        "handler_func": func,
        "plugin_name": plugin_name,
        "chat_type": chat_type or ["private", "group"],
        "permission": permission,
    }
    # 去重
    for existing in FALLBACK_HANDLERS:
        if existing["handler_func"] == func:
            return
    FALLBACK_HANDLERS.append(entry)
