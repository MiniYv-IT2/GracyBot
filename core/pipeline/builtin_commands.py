"""Stage: BuiltinCommands — 框架级内置命令（/关机, /重启, /开机, /关于）"""

import asyncio
import logging
import platform
import subprocess
import os
import sys
from typing import Optional

from core.pipeline import Stage
from core.decorators.context import PluginContext
from core.pipeline.helpers import is_master

_logger = logging.getLogger("Core.Pipeline")


class BuiltinCommands(Stage):
    """内置命令处理器

    处理 /关机, /重启, /开机, /关于 等框架级命令。
    """

    async def process(self, ctx: PluginContext) -> Optional[PluginContext]:
        from core.config import BOT_VERSION
        from core.gracy_adapter.send import gracy_send_msg
        from core.gracy_adapter.message import GracyText

        raw_msg = ctx.raw_text.strip()
        sender_id = str(ctx.sender_id)
        target_id = str(ctx.target_id)
        chat_type = ctx.chat_type
        is_master_user = is_master(ctx)

        if raw_msg == "/关机":
            if is_master_user:
                await gracy_send_msg(target_id, GracyText(text="🛑 正在执行关机操作...机器人将在3秒后关闭"), chat_type=chat_type)
                _logger.info(f"[内置命令] 主人{sender_id}执行/关机命令")

                async def delayed_shutdown():
                    await asyncio.sleep(3)
                    try:
                        proc = await asyncio.create_subprocess_exec(
                            'systemctl', 'stop', 'bot.service',
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE,
                        )
                        _, _ = await proc.communicate()
                        if proc.returncode == 0:
                            _logger.info("[关机指令] systemd关机成功")
                            return
                    except Exception:
                        pass
                    try:
                        from core.main import safe_shutdown
                        safe_shutdown()
                        return
                    except ImportError:
                        pass
                    os._exit(0)

                asyncio.ensure_future(delayed_shutdown())
            else:
                await gracy_send_msg(target_id, GracyText(text="⚠️ 权限不足！只有主人可以执行关机操作"), chat_type=chat_type)
                _logger.warning(f"[安全防护] 用户{sender_id}尝试关机，权限不足")
            return None

        if raw_msg == "/重启":
            if is_master_user:
                await gracy_send_msg(target_id, GracyText(text="🔄 正在执行重启操作...机器人将在5秒后重启"), chat_type=chat_type)
                _logger.info(f"[内置命令] 主人{sender_id}执行/重启命令")

                async def delayed_restart():
                    await asyncio.sleep(5)
                    if platform.system() == "Windows":
                        subprocess.Popen(
                            [sys.executable] + sys.argv,
                            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                            close_fds=True,
                        )
                    else:
                        subprocess.Popen(
                            [sys.executable] + sys.argv,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        )
                    await asyncio.sleep(1)
                    os._exit(0)

                asyncio.ensure_future(delayed_restart())
            else:
                await gracy_send_msg(target_id, GracyText(text="⚠️ 权限不足！只有主人可以执行重启操作"), chat_type=chat_type)
                _logger.warning(f"[安全防护] 用户{sender_id}尝试重启，权限不足")
            return None

        if raw_msg == "/开机":
            if is_master_user:
                await gracy_send_msg(target_id, GracyText(text="🚀 正在执行开机操作...机器人服务将在3秒后启动"), chat_type=chat_type)
                _logger.info(f"[内置命令] 主人{sender_id}执行/开机命令")

                async def delayed_startup():
                    await asyncio.sleep(3)
                    try:
                        proc = await asyncio.create_subprocess_exec(
                            'systemctl', 'start', 'bot.service',
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE,
                        )
                        _, _ = await proc.communicate()
                        if proc.returncode == 0:
                            _logger.info("[开机指令] systemd启动成功")
                            return
                    except Exception:
                        pass
                    if platform.system() == "Windows":
                        subprocess.Popen(
                            [sys.executable] + sys.argv,
                            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                            close_fds=True,
                        )
                    else:
                        subprocess.Popen([sys.executable] + sys.argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    _logger.info("[开机指令] 新进程已启动")

                asyncio.ensure_future(delayed_startup())
            else:
                await gracy_send_msg(target_id, GracyText(text="⚠️ 权限不足！只有主人可以执行开机操作"), chat_type=chat_type)
                _logger.warning(f"[安全防护] 用户{sender_id}尝试开机，权限不足")
            return None

        if raw_msg == "/关于":
            try:
                from core.gracy_adapter.pool import adapter_pool
                tags = adapter_pool.all_tags
                adapter_lines = [f"├ {t.platform}/{t.bot_name}{' (' + t.conn_type_display + ')' if t.conn_type_display else ''}" for t in tags]
                adapter_str = "\n".join(adapter_lines) if adapter_lines else "无"
            except Exception:
                adapter_str = "未知"

            try:
                from core.plugin_manager import plugin_manager
                plugin_count = len(plugin_manager.registry)
            except Exception:
                plugin_count = 0

            about_content = (
                f"GracyBot v{BOT_VERSION[1:]}\n"
                f"├ 作者: 小禹\n"
                f"├ 定位: 跨平台 IM 轻量异步框架\n"
                f"├ 适配器:\n{adapter_str}\n"
                f"├ Python: {platform.python_version()}\n"
                f"├ 插件: {plugin_count} 个已注册\n"
                f"└ 联系: QQ 192004908\n"
                f"\n/帮助 查看所有命令"
            )
            await gracy_send_msg(target_id, GracyText(text=about_content), chat_type=chat_type)
            _logger.info(f"[内置命令] 用户{sender_id}执行/关于命令")
            return None

        return ctx
