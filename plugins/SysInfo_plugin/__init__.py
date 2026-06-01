PLUGIN_META = {
    "name": "SysInfo_plugin",  
    "commands": ["/运行状态", "/info", "/status"],  
    "handler": "handle_sysinfo_plugin",  
    "chat_type": ["private", "group"], 
    "permission": "all", 
    "is_at_required": False,  
    "description": "系统状态查询插件，展示机器人运行信息、系统资源占用等详情",
    "version": "v1.1.0",
    "author": "GracyBot开发者"
}