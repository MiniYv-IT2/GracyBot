"""GracyBot Runtime 运行时模块 — 每个 QQ 账号绑定一个 Runtime 实例

提供 Runtime 数据类、全局注册表、上下文透传、数据路径工具。
"""

from .runtime import Runtime, RuntimeRegistry, RuntimeContext
from .data import get_global_path, get_instance_path, deep_merge

__all__ = [
    "Runtime",
    "RuntimeRegistry",
    "RuntimeContext",
    "get_global_path",
    "get_instance_path",
    "deep_merge",
]
