"""PluginContext — 插件处理器的统一上下文

替代当前 dispatch_plugin_cmd 中 7 个散落参数，
通过 @plugin_handler 自动注入。
"""

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Any, Optional


@dataclass
class PluginContext:
    """插件执行时的完整上下文（平台无关）

    所有字段由 @plugin_handler 装饰器自动填充，
    插件 handler 只需 def handler(ctx: PluginContext) 即可。
    """

    # ── 消息来源 ──
    sender_id: str = ""                    # 发送者 QQ/ID
    target_id: str = ""                    # 目标 ID（私聊=发送者, 群聊=群组 ID）
    chat_type: str = "private"             # "private" | "group"
    nickname: str = ""                     # 发送者昵称

    # ── 消息内容 ──
    raw_text: str = ""                     # 原始文本
    text: str = ""                         # 净化后的文本
    images: List[str] = field(default_factory=list)   # 图片文件 ID 列表
    ats: List[str] = field(default_factory=list)      # @的用户 ID 列表
    is_at_bot: bool = False                # 是否 @了机器人

    # ── 元数据 ──
    command: str = ""                      # 匹配到的触发指令
    plugin_name: str = ""                  # 当前插件名称
    raw_data: dict = field(default_factory=dict)  # 平台原始数据（透传）

    # ── 工具函数（由框架注入） ──
    send: Optional[Callable] = None        # 发送消息函数
    reply: Optional[Callable] = None       # 快捷回复
    logger: Optional[Callable] = None      # 当前插件日志器
    session: Any = None                    # 会话对象（@with_session 时注入）

    # ── 运行时（由框架注入，替代 adapter_tag/pool/plugin_manager） ──
    runtime: Any = None                    # 当前消息所属 Runtime 实例

    @property
    def adapter_tag(self) -> Any:
        """消息来源适配器标签（从 Runtime 获取）"""
        return self.runtime.adapter_tag if self.runtime else None

    @property
    def pool(self) -> Any:
        """AdapterPool 实例（从 Runtime 获取）"""
        return self.runtime.adapter_pool if self.runtime else None

    @property
    def plugin_manager(self) -> Any:
        """插件管理器（从 Runtime 获取）"""
        return self.runtime.plugin_manager if self.runtime else None

    # ── 运行时元信息 ──
    start_time: float = 0.0                # handler 开始时间
    extra: Dict[str, Any] = field(default_factory=dict)  # 扩展字段
