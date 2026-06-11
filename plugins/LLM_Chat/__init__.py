"""LLM_Chat — AI对话插件

元数据已迁移到 metadata.toml，PluginManager 优先读取 TOML。
"""

from .core.poke_handler import handle_poke_event
from .core.scheduler import start_scheduler

start_scheduler()
