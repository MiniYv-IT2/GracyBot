"""帮助插件元信息文件
提供机器人命令帮助功能，生成帮助图片
"""

PLUGIN_META = {
    "name": "帮助插件",
    "version": "1.1.3",
    "description": "查看所有命令，包括插件，返回一张帮助图片",
    "commands": ["/help", "/帮助", "/菜单", "/helps"],
    "handler": "handle_help",
    "chat_type": ["private", "group"],
    "permission": "all",
    "is_at_required": False,
    "dependencies": []
}