"""GracyBot 插件元数据加载模块 — TOML 解析 + 校验

提供:
- load_plugin_toml(): 读取 metadata.toml 并校验必填字段
- TOMLPluginError: 校验失败异常
- REQUIRED_FIELDS: 必填字段清单
"""

from .validator import load_plugin_toml, TOMLPluginError, REQUIRED_FIELDS

__all__ = [
    "load_plugin_toml",
    "TOMLPluginError",
    "REQUIRED_FIELDS",
]