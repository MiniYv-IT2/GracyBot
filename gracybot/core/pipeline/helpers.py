"""Pipeline 通用辅助函数"""

from typing import Optional

from gracybot.core.decorators.context import PluginContext

_logger = __import__("logging").getLogger("Core.Pipeline")


def is_master(ctx: PluginContext, plugin: dict = None) -> bool:
    """检查发送者是否为该实例的主人

    优先级：实例 master_id > Runtime master_id
    """
    sender_id = str(ctx.sender_id)
    if ctx.runtime and str(ctx.runtime.master_id) == sender_id:
        return True
    if ctx.pool and ctx.adapter_tag:
        adapter = ctx.pool.get(ctx.adapter_tag)
        if adapter:
            inst_master = getattr(adapter, '_instance_master_id', None)
            if inst_master and str(inst_master) == sender_id:
                return True
    try:
        from gracybot.core.config import MASTER_ID
        if MASTER_ID and str(MASTER_ID) == sender_id:
            return True
    except Exception:
        pass
    return False
