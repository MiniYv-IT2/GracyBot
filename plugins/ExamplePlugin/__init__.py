"""示例插件元信息文件
演示如何使用版本控制和依赖管理功能
"""

PLUGIN_META = {
    "name": "示例插件",
    "version": "1.0.0",  # 插件版本号
    "description": "展示版本控制和依赖管理功能的示例插件",
    "commands": ["示例", "version", "示例依赖"],
    "handler": "handle_example",
    "chat_type": ["private", "group"],
    "permission": "all",
    "is_at_required": False,
    # 定义插件依赖
    "dependencies": [
        # 这里可以添加依赖的插件，格式：
        # {"name": "依赖插件名称", "min_version": "最低版本号", "max_version": "最高版本号（可选）"}
        # 例如：
        # {"name": "基础插件", "min_version": "1.2.0"}
    ],
    "command_descriptions": {
        "示例": "查看示例插件基本功能演示",
        "version": "查看所有已加载插件的版本与依赖信息",
        "示例依赖": "了解插件依赖管理功能的使用说明"

    }
}