PLUGIN_META = {
    "name": "小禹截屏助手",
    "commands": ["/屏幕截图", "/保存截图"],
    "handler": "handle_screenshot",
    "chat_type": ["private", "group"],
    "permission": "master",
    "is_at_required": False,
    "description": "屏幕截图插件，主人专属，支持截图发送与保存",
    "command_descriptions": {
        "/屏幕截图": "截取当前电脑屏幕并发送截图",
        "/保存截图": "将最近一次截图保存到本地"
    },
    "version": "v1.0.0",
    "author": "GracyBot开发者"
}
