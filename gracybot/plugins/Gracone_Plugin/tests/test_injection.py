"""
测试 gracone_nonebot 命名空间注入是否正常工作（独立测试，不依赖 bridge）

运行: 
    cd plugins/Gracone_Plugin && python -m tests.test_injection
"""

import sys
import os

plugin_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if plugin_dir not in sys.path:
    sys.path.insert(0, plugin_dir)

# 导入 gracone_nonebot 执行命名空间注入
import gracone_nonebot  # noqa: F401

# 手动把 on_command 等换成本地模拟版本（不含 bridge 相对导入）
from gracone_nonebot import (
    nonebot, Message, MessageSegment, 
    PrivateMessageEvent, GroupMessageEvent, Sender, Event,
    FinishedException, PluginMetadata,
)
from gracone_nonebot import nb_matcher as nb_matcher_mod

# 手动替换 on_command 为最简版本
class _SimpleMatcher:
    def __init__(self, matcher_type, cmds=(), pattern=None, keywords=()):
        self.matcher_type = matcher_type
        self.cmds = tuple(c.lstrip('/').strip() for c in cmds)
        self.pattern = pattern
        self.keywords = keywords
        self.block = True
        self._handlers = []
    def handle(self):
        def deco(f):
            self._handlers.append(f)
            return f
        return deco
    def send(self, msg, **kw):
        pass
    async def finish(self, msg=None, **kw):
        pass
    def __repr__(self):
        return f"_SimpleMatcher({self.matcher_type}, cmds={self.cmds})"

def _on_command(*cmds, **kw):
    m = _SimpleMatcher("command", cmds=cmds)
    return m

nonebot.on_command = _on_command
nonebot.on_regex = lambda pattern, **kw: _SimpleMatcher("regex", pattern=pattern)
nonebot.on_keyword = lambda keywords, **kw: _SimpleMatcher("keyword", keywords=tuple(keywords))

print("=" * 60)
print("Gracone 命名空间注入测试")
print("=" * 60)
print()

# ── 测试 import 路径 ──
print("--- 测试 import 路径 ---")

from nonebot import on_command, on_regex, on_keyword, get_bot
print("  [✓] from nonebot import on_command, on_regex, on_keyword, get_bot")

from nonebot.rule import to_me, startswith
print("  [✓] from nonebot.rule import to_me, startswith")

from nonebot.params import CommandArg, EventMessage, EventPlainText
print("  [✓] from nonebot.params import CommandArg, EventMessage")

from nonebot.permission import USER, SUPERUSER
print("  [✓] from nonebot.permission import USER, SUPERUSER")

from nonebot.exception import FinishedException, StopPropagation, PausedException
print("  [✓] from nonebot.exception import FinishedException, StopPropagation")

from nonebot.matcher import current_bot, current_event, current_matcher
print("  [✓] from nonebot.matcher import current_bot, current_event")

from nonebot.plugin import PluginMetadata, require, get_plugin
print("  [✓] from nonebot.plugin import PluginMetadata, require")

from nonebot.adapters import Event as AdapterEvent, Bot, Message, MessageSegment
print("  [✓] from nonebot.adapters import Event, Bot, Message, MessageSegment")

from nonebot.adapters.onebot.v11 import (
    Message as OB11Msg, MessageSegment as OB11Seg,
    PrivateMessageEvent, GroupMessageEvent, Sender, Anonymous,
)
print("  [✓] from nonebot.adapters.onebot.v11 import ...")

from nonebot.adapters.onebot.v11.event import PokeNotifyEvent
print("  [✓] from nonebot.adapters.onebot.v11.event import PokeNotifyEvent")

from nonebot.adapters.onebot.v11.message import Message, MessageSegment
print("  [✓] from nonebot.adapters.onebot.v11.message import Message, MessageSegment")

print()
print("  ✓ 所有 import 路径通过!")

# ── 测试 Message/MessageSegment ──
print()
print("--- 测试 Message/MessageSegment ---")

msg = Message("你好世界")
assert msg.extract_plain_text() == "你好世界", "extract_plain_text 失败"
print(f"  [✓] Message('你好世界') -> '{msg.extract_plain_text()}'")

msg2 = Message([MessageSegment.text("Hello"), MessageSegment.at("123")])
assert len(msg2) == 2
print(f"  [✓] 组合消息: {len(msg2)} 段")

assert isinstance(MessageSegment.text("t"), MessageSegment)
assert isinstance(MessageSegment.image(file="x.png"), MessageSegment)
assert isinstance(MessageSegment.at("123"), MessageSegment)
assert isinstance(MessageSegment.reply("456"), MessageSegment)
assert isinstance(MessageSegment.face(12), MessageSegment)
print("  [✓] MessageSegment 工厂方法全部正常")

# Message 拼接
m3 = Message("你好") + MessageSegment.at("123")
assert len(m3) == 2
print("  [✓] Message + MessageSegment 拼接正常")

m4 = "Hi " + Message("world")
assert len(m4) == 2
print("  [✓] str + Message 拼接正常")

# ── 测试事件 ──
print()
print("--- 测试事件 ---")

pe = PrivateMessageEvent(user_id=12345, message=Message("hi"))
assert pe.user_id == 12345
assert pe.post_type == "message"
assert pe.message_type == "private"
print(f"  [✓] PrivateMessageEvent: user_id={pe.user_id}, type={pe.message_type}")

ge = GroupMessageEvent(user_id=12345, group_id=67890, message=Message("hi"))
assert ge.group_id == 67890
assert ge.message_type == "group"
print(f"  [✓] GroupMessageEvent: user_id={ge.user_id}, group_id={ge.group_id}")

# ── 测试 on_command ──
print()
print("--- 测试 on_command ---")

m = on_command("echo", "复读")
assert m.matcher_type == "command"
assert "echo" in m.cmds
print(f"  [✓] on_command('echo', '复读') -> cmds={m.cmds}")

@m.handle()
async def test_handler(event, bot):
    pass

assert len(m._handlers) == 1
print("  [✓] @matcher.handle() 注册 handler 成功")

# ── 测试 sys.modules 注册情况 ──
print()
print("--- 验证 sys.modules ---")

nb_modules = [k for k in sys.modules if k.startswith('nonebot')]
print(f"  sys.modules 中 'nonebot' 前缀模块数: {len(nb_modules)}")
for name in sorted(nb_modules):
    print(f"    - {name}")

print()
print("=" * 60)
print("✓ 所有测试通过! Gracone 命名空间注入工作正常。")
print("=" * 60)
