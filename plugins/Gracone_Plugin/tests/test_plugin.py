"""
测试加载 NoneBot 插件并验证 Matcher 注册和事件匹配

运行:
    cd plugins/Gracone_Plugin && python -m tests.test_plugin
"""

import sys
import os
import importlib.util

plugin_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if plugin_dir not in sys.path:
    sys.path.insert(0, plugin_dir)

# 注入命名空间
import gracone_nonebot  # noqa: F401

# 注入真实 on_command 实现
from bridge.matcher_bridge import (
    matcher_manager, dispatch_event,
    on_command, on_regex, on_keyword, on_message,
)
from gracone_nonebot import nonebot

nonebot.on_command = on_command
nonebot.on_regex = on_regex
nonebot.on_keyword = on_keyword
nonebot.on_message = on_message

print("=" * 60)
print("Gracone 插件加载测试")
print("=" * 60)

# 1. 模拟加载 echo 插件
print("\n--- 1. 模拟加载 NoneBot 插件 ---")

echo_plugin_path = os.path.join(plugin_dir, "nonebot_plugins", "echo.py")
spec = importlib.util.spec_from_file_location("nonebot_plugins.echo", echo_plugin_path)
mod = importlib.util.module_from_spec(spec)
sys.modules["nonebot_plugins.echo"] = mod
spec.loader.exec_module(mod)

print(f"  已加载: echo.py")

# 2. 验证 matcher 注册
print("\n--- 2. 验证 Matcher 注册 ---")
all_matchers = matcher_manager.get_matchers()
print(f"  已注册 Matcher 数: {len(all_matchers)}")
for m in all_matchers:
    print(f"    - {m}")
    print(f"      handlers: {len(m._handlers)} 个, block={m.block}")

# 3. 测试事件匹配
print("\n--- 3. 测试事件匹配 ---")

class FakeGracyEvent:
    def __init__(self, raw_text, sender_id="123", target_id="456", 
                 chat_type="group", is_at_bot=True):
        self.raw_text = raw_text
        self.sender_id = sender_id
        self.target_id = target_id
        self.chat_type = chat_type
        self.is_at_bot = is_at_bot
        self.message_id = "msg_001"
        self.nickname = "测试用户"
        self.segments = []
        self.raw_data = {"self_id": "789"}

# 测试1: echo 命令 with @
event1 = FakeGracyEvent("echo 你好世界", is_at_bot=True)
matched = matcher_manager.find_matches(event1.raw_text, event1.is_at_bot, event1.chat_type)
print(f"  'echo 你好世界' (to_me=True): 匹配 {len(matched)} 个")
for m in matched:
    print(f"    -> {m}")

# 测试2: echo 命令 without @ (to_me 应阻止)
event2 = FakeGracyEvent("echo 你好世界", is_at_bot=False)
matched2 = matcher_manager.find_matches(event2.raw_text, event2.is_at_bot, event2.chat_type)
print(f"  'echo 你好世界' (to_me=False): 匹配 {len(matched2)} 个")
for m in matched2:
    print(f"    -> {m}")

# 测试3: 不匹配的命令
event3 = FakeGracyEvent("随意消息")
matched3 = matcher_manager.find_matches(event3.raw_text, event3.is_at_bot, event3.chat_type)
print(f"  '随意消息': 匹配 {len(matched3)} 个")

# 测试4: keyword 匹配
test_matcher = on_keyword({"签到", "打卡"})
matched4 = test_matcher.match_event("来签到", is_at_bot=False)
print(f"  '来签到' match keyword {{签到}}? {matched4}")

# 测试5: regex 匹配
test_regex = on_regex(r"天气\s*\w+")
matched5 = test_regex.match_event("天气 北京")
print(f"  '天气 北京' match regex? {matched5}")
matched6 = test_regex.match_event("今天天气不错")
print(f"  '今天天气不错' match regex? {matched6}")

print("\n" + "=" * 60)
print("✓ 插件加载和事件匹配测试完成!")
print("=" * 60)
