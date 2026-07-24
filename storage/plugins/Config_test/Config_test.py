"""配置测试插件 — 测试插件配置管理系统的合并与迁移功能

命令：
  /config          — 查看当前插件配置
  /config_set <键> <值> — 修改插件配置
"""

import json

from graci import on_command, plugin_handler, PluginContext, get_logger
from graci import config_manager

logger = get_logger("Config_test")

CONFIG_SCHEMA = {
    "greeting": {"type": "str", "default": "Hello", "description": "问候语"},
    "max_results": {"type": "int", "default": 20, "description": "最大结果数（已更新）"},
    "enable_logging": {"type": "bool", "default": True, "description": "是否启用日志"},
    "timeout": {"type": "int", "default": 30, "description": "请求超时秒数"},
}


def _load_cfg():
    return config_manager.register_plugin_config("Config_test", CONFIG_SCHEMA)


_cached_config = _load_cfg()


@on_command("/config")
@plugin_handler
async def handle_config(ctx: PluginContext):
    """查看当前插件配置"""
    cfg = config_manager.get_plugin("Config_test")
    lines = [f"📋 Config_test 配置:"]
    for k, v in cfg.items():
        default = CONFIG_SCHEMA.get(k, {}).get("default", "—")
        lines.append(f"  {k} = {v!r}  (default: {default!r})")
    await ctx.reply("\n".join(lines))
    logger.info(f"用户 {ctx.sender_id} 查看了配置")


@on_command("/config_set")
@plugin_handler
async def handle_config_set(ctx: PluginContext):
    """修改插件配置: /config_set <键> <值>"""
    args = ctx.raw_text[len(ctx.command):].strip().split(maxsplit=1)
    if len(args) != 2:
        await ctx.reply("用法：/config_set <键> <值>\n例：/config_set greeting 大家好")
        return

    key, value = args

    schema = CONFIG_SCHEMA.get(key)
    if not schema:
        await ctx.reply(f"未知配置项: {key}，可用项: {', '.join(CONFIG_SCHEMA.keys())}")
        return

    try:
        if schema["type"] == "int":
            value = int(value)
        elif schema["type"] == "bool":
            value = value.lower() in ("true", "1", "yes", "y")
    except (ValueError, TypeError):
        await ctx.reply(f"值类型不匹配，{key} 应为 {schema['type']} 类型")
        return

    success = config_manager.update_plugin("Config_test", {key: value})
    if success:
        cfg = config_manager.get_plugin("Config_test")
        await ctx.reply(f"已更新 {key} = {cfg[key]!r}")
        logger.info(f"用户 {ctx.sender_id} 修改配置 {key}={value}")
    else:
        await ctx.reply("❌ 配置更新失败")
