"""示例 NoneBot 插件 — 复读机

测试用例:
    输入 "echo 你好" → 回复 "你说: 你好"
"""

from nonebot import on_command
from nonebot.rule import to_me
from nonebot.params import CommandArg
from nonebot.adapters import Message

# 创建 matcher — 注册 echo 命令
echo = on_command("echo", aliases={"复读"}, rule=to_me())

@echo.handle()
async def _(msg: Message = CommandArg()):
    """处理 echo 命令"""
    if msg and str(msg).strip():
        text = str(msg).strip()
        await echo.finish(f"你说: {text}")

@echo.handle()
async def handle_all(msg: Message = CommandArg()):
    """第二个 handler 兜底"""
    if msg and str(msg).strip():
        await echo.send(f"你说: {str(msg)}")
