PLUGIN_META = {
    "name": "LLM_Chat",
    "commands": ["//", "/chat帮助", "/设置OpenAI", "/新增人设", "/删除人设", "/查看人设列表", "/切换人设", "/清除记忆", "/persona", "/+persona", "/-persona", "/persona=", "/戳一戳开关", "/戳一戳状态", "/设置上下文数量", "/查看配置"],
    "handler": "handle_llm_chat",
    "chat_type": ["private", "group"],
    "permission": "all",
    "is_at_required": True,
    "description": "AI对话插件，支持多人设切换、上下文记忆、定时任务、戳一戳互动",
    "version": "1.4.3",
    "author": "GracyBot开发团队"
}

from .core.poke_handler import handle_poke_event
from .core.scheduler import start_scheduler
from core.config import NAPCAT_HTTP_URL

start_scheduler(NAPCAT_HTTP_URL)
