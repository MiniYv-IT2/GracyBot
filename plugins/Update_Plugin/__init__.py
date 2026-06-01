# 插件元信息（供插件管理器识别，精准匹配插件功能）
PLUGIN_META = {
    "name": "Update_Plugin",  # 插件唯一名称，与目录/核心文件一致
    "commands": ["/系统更新", "/确认更新", "/取消更新", "/开启自动更新", "/关闭自动更新"],  # 所有触发指令
    "handler": "handle_update_plugin",  # 核心处理函数名（插件入口函数）
    "chat_type": ["private", "group"],  # 支持私聊、群聊场景
    "permission": "master",  # 仅主人可用
    "is_at_required": False,  # 群聊无需@机器人即可触发
    "description": "系统更新插件，用于检测GitHub仓库更新、版本管理和自动/手动更新控制",
    "version": "v1.0.0",
    "author": "GracyBot开发者"
}