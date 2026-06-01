"""GracyUI 插件 — Web 管理面板前端

通过 Flask 内嵌 Web 服务提供可视化 Bot 管理界面。
前端项目基于 React + TypeScript + Vite + TailwindCSS。
"""

PLUGIN_META = {
    "name": "GracyUI管理面板",
    "version": "v1.9.2",
    "author": "GracyBot开发者",
    "description": "Web可视化Bot管理面板，提供仪表盘、好友管理、插件管理、日志中心等模块，支持跨平台适配层通用",
    "commands": [
        "/管理面板",
        "/webui",
        "/dashboard",
    ],
    "handler": "handle_gracy_ui",
    "chat_type": ["private", "group"],
    "permission": "all",
    "is_at_required": False,
    "command_descriptions": {
        "/管理面板": "打开或获取Web管理面板访问地址",
        "/webui": "打开Web管理面板（英文别名）",
        "/dashboard": "获取仪表盘信息概览",
    },
}
