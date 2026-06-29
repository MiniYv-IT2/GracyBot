"""API 桥接 — 模拟 NoneBot Bot 实例，将所有操作翻译为 GracyBot API

NoneBot 插件的 handler 接收到的 Bot 参数实际上是 GraconeBot 实例，
它的 send_msg / call_api 等方法最终调用 gracy_send_msg / gracy_call_api。
"""

from typing import Any, Dict, List, Optional

from graci import gracy_send_msg, gracy_call_api, get_logger
from graci import IdentityTag
from graci import GracyText

from bridge.message_translator import nb_to_gracy_segments
from bridge.event_translator import nb_to_gracy_event
from context import GraconeContext

logger = get_logger("Gracone.API")

# 当前消息上下文的 Bot 实例（NoneBot 插件通常通过依赖注入获取）
_current_bot: Optional['GraconeBot'] = None
_current_bots: Dict[str, 'GraconeBot'] = {}


class GraconeBot:
    """Gracone 模拟的 OneBot V11 Bot 实例
    
    实现了 NoneBot Bot 接口的子集，足够欺骗大多数 NoneBot 插件。
    """
    
    def __init__(self, self_id: str = "0", adapter_tag: Optional[IdentityTag] = None):
        self.self_id = self_id
        self.adapter_tag = adapter_tag
        self._call_api_history: List[dict] = []
    
    async def send_msg(self, message_type: str = "private", user_id: int = 0,
                       group_id: int = 0, message: Any = None, **kwargs) -> dict:
        """模拟 Bot.send_msg — 翻译为 gracy_send_msg
        
        Args:
            message_type: "private" 或 "group"
            user_id: 目标用户 ID
            group_id: 目标群 ID（群聊时）
            message: OneBot Message 或 str
            **kwargs: 其他参数
            
        Returns:
            dict: 包含 message_id 的响应
        """
        if message_type == "group":
            target = str(group_id)
        else:
            target = str(user_id)
        
        # 转换消息段
        if isinstance(message, str):
            segments = [GracyText(text=message)]
        elif hasattr(message, '__iter__'):
            segments = nb_to_gracy_segments(message)
        else:
            segments = [GracyText(text=str(message))]
        
        # 发送
        success = await gracy_send_msg(
            target=target,
            *segments,
            chat_type=message_type,
            tag=self.adapter_tag,
        )
        
        return {"message_id": str(id(message)) if success else "0"}
    
    async def send_private_msg(self, user_id: int = 0, message: Any = None, **kwargs) -> dict:
        """模拟 Bot.send_private_msg"""
        return await self.send_msg(message_type="private", user_id=user_id, 
                                   message=message, **kwargs)
    
    async def send_group_msg(self, group_id: int = 0, message: Any = None, **kwargs) -> dict:
        """模拟 Bot.send_group_msg"""
        return await self.send_msg(message_type="group", group_id=group_id,
                                   message=message, **kwargs)
    
    async def call_api(self, api: str, **params) -> Optional[dict]:
        """模拟 Bot.call_api — 翻译为 gracy_call_api
        
        Args:
            api: API 名称（如 "send_msg", "get_group_info" 等）
            **params: API 参数
            
        Returns:
            API 响应或 None
        """
        logger.debug(f"call_api: {api} params={params}")
        self._call_api_history.append({"api": api, "params": params})
        
        if api == "send_msg":
            return await self.send_msg(**params)
        elif api == "send_private_msg":
            return await self.send_private_msg(**params)
        elif api == "send_group_msg":
            return await self.send_group_msg(**params)
        
        # 其他 API 通过 gracy_call_api 转译
        result = await gracy_call_api(api, params, tag=self.adapter_tag)
        return result
    
    def __repr__(self) -> str:
        return f"GraconeBot(self_id={self.self_id})"


def setup_current_bot(bot: GraconeBot):
    """设置当前消息上下文的 Bot 实例"""
    global _current_bot
    _current_bot = bot
    _current_bots[str(bot.self_id)] = bot


def get_current_bot() -> Optional[GraconeBot]:
    """获取当前消息上下文的 Bot 实例"""
    return _current_bot


def get_all_bots() -> Dict[str, GraconeBot]:
    """获取所有 Bot 实例"""
    return dict(_current_bots)


def create_bot_for_event(gracy_event, adapter_tag=None) -> GraconeBot:
    """为事件创建或获取对应的 Bot 实例"""
    self_id = "0"
    raw_data = getattr(gracy_event, 'raw_data', {}) or {}
    
    # 从 raw_data 提取机器人自身 ID
    if isinstance(raw_data, dict):
        self_id = str(raw_data.get('self_id', raw_data.get('robot_id', '0')))
    
    bot = GraconeBot(self_id=self_id, adapter_tag=adapter_tag)
    return bot
