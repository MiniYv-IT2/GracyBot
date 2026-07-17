"""
快速测试 - 加载 echo 插件并验证 matcher 匹配
直接运行: python tests/run_plugin_test.py
"""
import sys, os, importlib.util

# 此脚本直接放在 tests/ 目录下，手动设置 path
test_dir = os.path.dirname(os.path.abspath(__file__))
plugin_dir = os.path.dirname(test_dir)
if plugin_dir not in sys.path:
    sys.path.insert(0, plugin_dir)

# 需要添加 GracyBot 根目录到 path（使 core.xxx 可导入）
gracy_root = os.path.dirname(os.path.dirname(plugin_dir))  # e:\ai智能体\gracybot
if gracy_root not in sys.path:
    sys.path.insert(0, gracy_root)

# 注入命名空间（直接导入，不走 Gracone_Plugin.py）
import gracone_nonebot  # noqa: F401

# 注入真实实现
from gracone_nonebot import nonebot
from bridge.matcher_bridge import on_command, on_regex, on_keyword, matcher_manager
nonebot.on_command = on_command
nonebot.on_regex = on_regex
nonebot.on_keyword = on_keyword

# 加载 echo.py
echo_path = os.path.join(plugin_dir, "nonebot_plugins", "echo.py")
spec = importlib.util.spec_from_file_location("nonebot_plugins.echo", echo_path)
mod = importlib.util.module_from_spec(spec)
sys.modules["nonebot_plugins.echo"] = mod
spec.loader.exec_module(mod)

# 检查 matchers
ms = matcher_manager.get_matchers()
print(f"Matchers: {len(ms)}")
for m in ms:
    print(f"  {m}, handlers={len(m._handlers)}")

# 测试匹配
print()
for test in ["echo hello", "echo", "随意消息", "复读 测试"]:
    r = matcher_manager.find_matches(test, is_at_bot=True)
    print(f'  "{test}" (to_me=True) -> match={len(r)}: {[str(x) for x in r]}')

print()
for test in ["echo hello", "echo"]:
    r = matcher_manager.find_matches(test, is_at_bot=False)
    print(f'  "{test}" (to_me=False) -> match={len(r)}')
