"""GracyBot 插件 metadata.toml 解析器与校验器

TOML 规范（GracyBot 插件元数据标准）:

必填字段:
  [plugin]
  name, version, author, description

  [handler]
  entry                        # 入口函数名（同名 .py 中定义）

  [trigger]
  commands, chat_type, permission, is_at_required

可选字段:
  [plugin]
  icon                          # 插件图标相对路径
  dependencies                  # 依赖的其他插件列表

  [trigger]
  command_descriptions          # 每个命令的独立描述
"""

import os
from typing import Dict

try:
    import tomllib  # Python 3.11+
except ImportError:
    import tomli as tomllib  # Python 3.9/3.10 回退


# ── 必填字段清单 ──
REQUIRED_FIELDS = frozenset({
    "name", "version", "author", "description",
    "commands", "handler", "chat_type", "permission",
    "is_at_required",
})


class TOMLPluginError(Exception):
    """metadata.toml 校验失败异常"""
    def __init__(self, plugin_name: str, message: str):
        super().__init__(f"[{plugin_name}] metadata.toml: {message}")
        self.plugin_name = plugin_name
        self.message = message


def load_plugin_toml(toml_path: str, plugin_path: str) -> dict:
    """加载并校验 metadata.toml

    Args:
        toml_path:   metadata.toml 的绝对路径
        plugin_path: 插件目录的绝对路径

    Returns:
        校验通过后的扁平化元数据字典

    Raises:
        TOMLPluginError: 解析失败或缺少必填字段
    """
    plugin_name = os.path.basename(plugin_path)

    # ── 1. 解析 TOML 文件 ──
    try:
        with open(toml_path, "rb") as f:
            raw = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise TOMLPluginError(plugin_name, f"TOML 语法错误: {e}")
    except FileNotFoundError:
        raise TOMLPluginError(plugin_name, "文件不存在")
    except OSError as e:
        raise TOMLPluginError(plugin_name, f"文件读取失败: {e}")

    # ── 2. 提取各表并合并 ──
    plugin_section = raw.get("plugin", {})
    handler_section = raw.get("handler", {})
    trigger_section = raw.get("trigger", {})

    if not isinstance(plugin_section, dict):
        raise TOMLPluginError(plugin_name, "[plugin] 表必须是字典")
    if not isinstance(handler_section, dict):
        raise TOMLPluginError(plugin_name, "[handler] 表必须是字典")
    if not isinstance(trigger_section, dict):
        raise TOMLPluginError(plugin_name, "[trigger] 表必须是字典")

    meta = {}
    meta["name"]           = plugin_section.get("name")
    meta["version"]        = plugin_section.get("version")
    meta["author"]         = plugin_section.get("author")
    meta["description"]    = plugin_section.get("description")
    meta["icon"]           = plugin_section.get("icon")
    meta["priority"]       = plugin_section.get("priority", 50)
    meta["dependencies"]   = plugin_section.get("dependencies", [])

    meta["handler"]        = handler_section.get("entry")
    meta["commands"]       = trigger_section.get("commands")
    meta["chat_type"]      = trigger_section.get("chat_type")
    meta["permission"]     = trigger_section.get("permission")
    meta["is_at_required"] = trigger_section.get("is_at_required")
    meta["command_descriptions"] = trigger_section.get("command_descriptions", {})

    # ── 3. 严格校验必填字段 ──
    missing = [f for f in REQUIRED_FIELDS if meta.get(f) is None]

    if missing:
        raise TOMLPluginError(
            plugin_name,
            f"缺少必填字段: {', '.join(missing)}"
        )

    # ── 4. 类型校验 ──
    if not isinstance(meta["commands"], list) or len(meta["commands"]) == 0:
        raise TOMLPluginError(plugin_name, "commands 必须是非空列表")
    if not isinstance(meta["chat_type"], list):
        raise TOMLPluginError(plugin_name, "chat_type 必须是列表")
    for ct in meta["chat_type"]:
        if ct not in ("private", "group"):
            raise TOMLPluginError(plugin_name, f"chat_type 只能包含 'private'/'group'，收到: {ct}")
    if meta["permission"] not in ("all", "master"):
        raise TOMLPluginError(plugin_name, "permission 必须是 'all' 或 'master'")
    if not isinstance(meta["is_at_required"], bool):
        raise TOMLPluginError(plugin_name, "is_at_required 必须是布尔值")
    if not isinstance(meta["dependencies"], list):
        raise TOMLPluginError(plugin_name, "dependencies 必须是列表")
    if not isinstance(meta["priority"], int) or meta["priority"] < 0:
        raise TOMLPluginError(plugin_name, "priority 必须是正整数")

    # ── 5. 图标解析（可选，支持本地路径和 URL） ──
    if meta["icon"]:
        if not isinstance(meta["icon"], str):
            raise TOMLPluginError(plugin_name, "icon 必须是字符串路径或 URL")
        icon_val = meta["icon"].strip()
        if icon_val.startswith(("http://", "https://")):
            # 云端图标：直接存 URL
            meta["icon_path"] = icon_val
        else:
            # 本地图标：解析为绝对路径
            icon_abs = os.path.join(plugin_path, icon_val)
            meta["icon_path"] = icon_abs if os.path.exists(icon_abs) else None
    else:
        meta["icon_path"] = None

    return meta