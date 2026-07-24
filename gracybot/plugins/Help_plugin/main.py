"""帮助插件 — 查询所有插件命令，返回帮助图片"""
import collections
import os
from graci import get_logger, on_command, plugin_handler, PluginContext
from graci import GracyImage
from graci import plugin_manager, config_manager
from .core.draw import GracyBotHelpDrawer

logger = get_logger("Help")

config_manager.register_plugin_config("帮助插件")

_drawer = None


def _get_drawer():
    global _drawer
    if _drawer is None:
        config = config_manager.get_plugin("帮助插件")
        _drawer = GracyBotHelpDrawer(config)
    return _drawer


@on_command("/help", "/帮助", "/菜单", "/helps")
@plugin_handler
async def handle_help(ctx: PluginContext):
    """生成帮助图片并发送"""
    # 收集所有插件命令
    from graci import plugin_manager
    plugin_commands = collections.defaultdict(list)
    for plugin in plugin_manager.registry:
        name = plugin.get("name", "未知插件")
        if name == "帮助插件":
            continue
        desc = plugin.get("description", "")
        cmd_descs = plugin.get("command_descriptions", {})
        for cmd in plugin.get("commands", []):
            cmd_desc = cmd_descs.get(cmd, "") or desc
            plugin_commands[name].append(f"{cmd}#{cmd_desc}" if cmd_desc else cmd)

    if not plugin_commands:
        await ctx.reply("没有找到任何插件或命令")
        return

    try:
        image = _get_drawer().draw_help_image(dict(plugin_commands))
        temp_path = os.path.join(os.path.dirname(__file__), "data", "temp_help.png")
        os.makedirs(os.path.dirname(temp_path), exist_ok=True)
        with open(temp_path, "wb") as f:
            f.write(image)
        await ctx.send(GracyImage(file_path=temp_path))
    except Exception as e:
        logger.error(f"生成帮助图片失败: {e}")
        await ctx.reply("生成帮助图片失败，请联系管理员")
