"""易搜助手 — 多引擎浏览器搜索与网页浏览插件"""

PLUGIN_META = {
    "name": "易搜助手",
    "version": "v1.0.0",
    "author": "GracyBot开发者",
    "description": "多引擎浏览器搜索与网页浏览插件，支持必应、百度、谷歌、搜狗、Yandex五大搜索引擎，搜索结果以手机截图风格竖屏图片展示",
    "commands": [
        "/搜索", "搜索",
        "/必应搜索",
        "/百度搜索",
        "/谷歌搜索",
        "/搜狗搜索",
        "/Yandex搜索",
        "/浏览"
    ],
    "handler": "handle_easysearch",
    "chat_type": ["private", "group"],
    "permission": "all",
    "is_at_required": False,
    "command_descriptions": {
        "/搜索": "使用默认搜索引擎搜索关键词（例：/搜索 Python教程）",
        "/必应搜索": "使用必应搜索关键词",
        "/百度搜索": "使用百度搜索关键词",
        "/谷歌搜索": "使用谷歌搜索关键词",
        "/搜狗搜索": "使用搜狗搜索关键词",
        "/Yandex搜索": "使用Yandex搜索关键词",
        "/浏览": "直接浏览完整URL网页内容（例：/浏览 https://example.com）"
    },
    "dependencies": []
}
