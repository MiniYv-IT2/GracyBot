"""Pipeline 4 个 Stage — 从 handler.py 中迁移的横切逻辑

Stage1 SecurityFilter  → 频率限制、黑名单、输入验证
Stage2 CommandMatcher  → TOML + @on_command 命令匹配
Stage3 PluginHandler   → 权限校验、插件执行、计时、审计
Stage4 ResponseSender  → 消息发送
"""

import asyncio
import inspect
import platform
import time
import logging
from typing import Optional, Dict, Any

from core.pipeline import Stage
from core.decorators.context import PluginContext
from core.gracy_adapter.event import GracyEvent

_logger = logging.getLogger("GracyPipeline")


# ── 权限辅助 ──

def _is_master(ctx: PluginContext, plugin: dict = None) -> bool:
    """检查发送者是否为该实例的主人

    优先级：实例 master_id > Runtime master_id
    """
    sender_id = str(ctx.sender_id)
    # 先从适配器实例查（旧路径，P3 后统一走 Runtime）
    if ctx.runtime and str(ctx.runtime.master_id) == sender_id:
        return True
    if ctx.pool and ctx.adapter_tag:
        adapter = ctx.pool.get(ctx.adapter_tag)
        if adapter:
            inst_master = getattr(adapter, '_instance_master_id', None)
            if inst_master and str(inst_master) == sender_id:
                return True
    # 兜底：框架级 MASTER_ID（P3 删除）
    try:
        from core.config import MASTER_ID
        if MASTER_ID and str(MASTER_ID) == sender_id:
            return True
    except Exception:
        pass
    return False


# ══════════════════════════════════════════════════════════
# Stage 1: SecurityFilter
# ══════════════════════════════════════════════════════════

class SecurityFilter(Stage):
    """安全过滤器

    职责:
        - 黑名单预检（来自小禹插件）
        - 输入验证（XSS 防护）
        - sender_id 合法性校验
        - 完整日志记录（使用 styling 管道，保证格式与旧 handler 一致）
    """

    async def process(self, ctx: PluginContext) -> Optional[PluginContext]:
        _logger.debug(f"[SecurityFilter] 校验用户 {ctx.sender_id}")

        # ── 黑名单预检 ──
        try:
            from plugins.Xiaoyu_plugin.Xiaoyu_plugin import is_user_blocked
            if is_user_blocked(str(ctx.sender_id)):
                _logger.info(f"[黑名单拦截] 用户 {ctx.sender_id} 在黑名单中")
                return None  # 短路
        except ImportError:
            pass  # 小禹插件未加载时不拦截

        # ── 审计日志（每收到一条消息都记录） ──
        from core.security_manager import security_manager
        security_manager.log_audit_event(
            user_id=ctx.sender_id,
            action="message_received",
            resource=ctx.chat_type,
            success=True,
            details={
                "raw_message": ctx.raw_text[:200],
                "chat_type": ctx.chat_type,
            }
        )

        # ── 监控统计 ──
        try:
            from core.monitor import monitor_manager
            monitor_manager.record_message_received()
        except ImportError:
            pass

        # ── 日志记录（通过 styling 管道，还原原始格式） ──
        self._log_via_styling(ctx)

        return ctx  # 继续

    def _log_via_styling(self, ctx: PluginContext) -> None:
        """通过 logger_manager + styling 管道记录日志，保证与旧 handler 格式一致"""
        raw = ctx.raw_data or {}

        context = {
            'self_id': raw.get('self_id', ''),
            'user_id': raw.get('user_id', ctx.sender_id),
            'message_type': raw.get('message_type', ctx.chat_type),
            'raw_message': raw.get('raw_message', ctx.raw_text),
            'group_id': raw.get('group_id', ''),
            'group_name': raw.get('group_name', ''),
        }

        # 移除空值，与旧行为一致
        context = {k: v for k, v in context.items() if v}

        from core.logger_manager import logger_manager
        import logging
        logger_manager.log_with_context(
            _logger,
            logging.INFO,
            "[适配器回调] 收到消息",
            context=context,
        )


# ══════════════════════════════════════════════════════════
# Stage 1.5: BuiltinCommands
# ══════════════════════════════════════════════════════════

class BuiltinCommands(Stage):
    """内置命令处理器

    处理 /关机, /重启, /开机, /关于 等框架级命令。
    """

    async def process(self, ctx: PluginContext) -> Optional[PluginContext]:
        from core.security_manager import security_manager
        from core.config import BOT_VERSION
        from core.gracy_adapter.send import gracy_send_msg
        from core.gracy_adapter.message import GracyText
        from core.security import sanitize_log

        raw_msg = ctx.raw_text.strip()
        sender_id = str(ctx.sender_id)
        target_id = str(ctx.target_id)
        chat_type = ctx.chat_type
        is_master = _is_master(ctx)

        import threading, time, subprocess, os, sys, platform

        if raw_msg == "/关机":
            if is_master:
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
            if is_master:
                await gracy_send_msg(target_id, GracyText(text="🔄 正在执行重启操作...机器人将在5秒后重启"), chat_type=chat_type)
                _logger.info(f"[内置命令] 主人{sender_id}执行/重启命令")

                async def delayed_restart():
                    await asyncio.sleep(5)
                    # ── 先启动新进程，再退出当前进程 ──
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
            if is_master:
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
            security_manager.log_audit_event(
                user_id=sender_id, action="about_command",
                resource=None, success=True, event_type="command",
                details={"command": raw_msg[:50]}
            )
            about_content = (
                f"GracyBot v{BOT_VERSION[1:]}\n"
                f"├ 作者: 小禹\n"
                f"├ 定位: 跨平台 IM 轻量异步框架\n"
                f"├ 协议: OneBot 11 (HTTP/WS)\n"
                f"├ Python: {platform.python_version()}\n"
                f"├ 插件: 10 个已注册\n"
                f"└ 联系: QQ 192004908\n"
                f"\n/帮助 查看所有命令"
            )
            await gracy_send_msg(target_id, GracyText(text=about_content), chat_type=chat_type)
            _logger.info(f"[内置命令] 用户{sender_id}执行/关于命令")
            return None

        # 不是内置命令 → 继续
        return ctx


# ══════════════════════════════════════════════════════════
# Stage 2: CommandMatcher
# ══════════════════════════════════════════════════════════

class CommandMatcher(Stage):
    """命令匹配器

    职责:
        - 遍历 PLUGIN_REGISTRY 匹配 TOML commands
        - 遍历 DECORATOR_COMMAND_REGISTRY 匹配 @on_command
        - 匹配结果写入 ctx.matched_command / ctx.matched_plugin
    """

    async def process(self, ctx: PluginContext) -> Optional[PluginContext]:
        raw_msg = ctx.raw_text.strip()
        if not raw_msg:
            return ctx  # 空消息不匹配任何命令，继续走后续逻辑

        # ── 路径 A: TOML 命令匹配（并行过滤 + 优先级选胜者） ──
        from core.plugin_manager import plugin_manager

        async def _check_plugin(plugin: dict) -> Optional[dict]:
            """异步检查单个插件是否匹配，返回匹配结果或 None"""
            matched_cmd = self._match_any(plugin.get("commands", []), raw_msg)
            if not matched_cmd:
                return None
            if ctx.chat_type not in plugin.get("chat_type", ["private", "group"]):
                return None
            if plugin.get("permission") == "master":
                if not _is_master(ctx, plugin):
                    return None
            if ctx.chat_type == "group" and plugin.get("is_at_required", False) and not ctx.is_at_bot:
                return None
            return {"plugin": plugin, "matched_cmd": matched_cmd, "priority": plugin.get("priority", 50)}

        tasks = [_check_plugin(p) for p in plugin_manager.registry]
        results = await asyncio.gather(*tasks)
        matches = [r for r in results if r is not None]
        if matches:
            # 按 priority 降序取最高优先级
            matches.sort(key=lambda x: x["priority"], reverse=True)
            best = matches[0]
            plugin = best["plugin"]
            ctx.command = best["matched_cmd"]
            ctx.plugin_name = plugin["name"]
            ctx.extra["handler_func"] = plugin.get("handler_func")
            ctx.extra["_match_source"] = "toml"
            _logger.debug(f"[CommandMatcher] TOML 并行匹配: {plugin['name']} → {best['matched_cmd']} (priority={best['priority']})")
            return ctx  # 匹配成功，继续到 PluginHandler

        # ── 路径 B: @on_command / @on_regex 装饰器匹配 ──
        from core.decorators.registration import DECORATOR_COMMAND_REGISTRY

        for entry in DECORATOR_COMMAND_REGISTRY:
            # B1: @on_command 精确匹配
            commands = entry.get("commands", [])
            matched_cmd = self._match_any(commands, raw_msg)
            if matched_cmd:
                e_ct = entry.get("chat_type", ["private", "group"])
                if ctx.chat_type not in e_ct:
                    continue
                ctx.command = matched_cmd
                ctx.plugin_name = entry.get("plugin_name", "decorator")
                ctx.extra["handler_func"] = entry["handler_func"]
                ctx.extra["_match_source"] = "decorator"
                _logger.debug(f"[CommandMatcher] 装饰器匹配: {ctx.plugin_name} → {matched_cmd}")
                return ctx

            # B2: @on_regex 正则匹配
            patterns = entry.get("patterns", [])
            for pattern_str, compiled in patterns:
                m = compiled.search(raw_msg)
                if m:
                    e_ct = entry.get("chat_type", ["private", "group"])
                    if ctx.chat_type not in e_ct:
                        continue
                    ctx.command = f"regex:{pattern_str}"
                    ctx.plugin_name = entry.get("plugin_name", "decorator")
                    ctx.extra["handler_func"] = entry["handler_func"]
                    ctx.extra["_match_source"] = "decorator"
                    ctx.extra["_regex_match"] = m
                    _logger.debug(f"[CommandMatcher] 正则匹配: {ctx.plugin_name} → {pattern_str}")
                    return ctx

        # 无匹配 → 继续到后续逻辑（可能走 AI 对话）
        ctx.extra["_match_source"] = "none"
        return ctx

    def _match_any(self, commands: list, raw_msg: str) -> Optional[str]:
        """匹配命令列表，返回最长匹配的命令

        匹配规则:
          - // 特殊处理（正则匹配消息开头或空格后的 //）
          - 普通命令: 精确匹配或前缀 + 空格/结尾匹配
          - 多个命令匹配时返回最长的（解决 /异环 vs /异环角色 冲突）
        """
        import re
        candidates = []
        for cmd in commands:
            if cmd == "//":
                if re.search(r'(?:^|\s)//', raw_msg):
                    candidates.append(cmd)
            elif raw_msg == cmd or raw_msg.startswith(cmd + " ") or raw_msg.startswith(cmd + "\n"):
                candidates.append(cmd)
        if not candidates:
            return None
        # 返回最长匹配（处理前缀冲突）
        return max(candidates, key=len)


# ══════════════════════════════════════════════════════════
# Stage 3: PluginHandler
# ══════════════════════════════════════════════════════════

class PluginHandler(Stage):
    """插件执行器

    职责:
        - 调用 plugin_manager.get_matched_plugin 获取完整插件信息
        - 执行 handler_func
        - 计时 + 监控上报
        - 异常捕获 + 审计日志
    """

    async def process(self, ctx: PluginContext) -> Optional[PluginContext]:
        handler_func = ctx.extra.get("handler_func", None)
        if not handler_func:
            return ctx  # 无匹配插件，继续

        start_time = time.time()
        plugin_name = ctx.plugin_name

        # ── 注入 ctx.send / ctx.reply（新风格使用） ──
        from core.gracy_adapter.send import gracy_send_msg
        from core.gracy_adapter.message import GracyText
        if ctx.send is None:
            async def _send(*segs, ct=None):
                return await gracy_send_msg(
                    ctx.target_id, *segs, chat_type=ct or ctx.chat_type,
                    tag=ctx.adapter_tag,
                )
            ctx.send = _send
        if ctx.reply is None:
            async def _reply(text):
                return await gracy_send_msg(
                    ctx.target_id, GracyText(text=text), chat_type=ctx.chat_type,
                    tag=ctx.adapter_tag,
                )
            ctx.reply = _reply

        try:
            # 判断 handler 签名：新风格 ctx，旧风格 7 参数
            sig = inspect.signature(handler_func)
            params = list(sig.parameters.keys())

            if len(params) == 1 and params[0] in ("ctx", "self"):
                # 新风格：@plugin_handler 包装 或 PluginContext
                if inspect.iscoroutinefunction(handler_func):
                    await handler_func(ctx)
                else:
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(None, handler_func, ctx)
            else:
                # 旧风格：7 参数 (pm, send, data, sender_id, chat_type, perm, logger)
                _logger.debug(f"[PluginHandler] 旧风格调用: {plugin_name}")
                # 包装 send 函数，自动注入来源适配器 tag
                async def _ph_send(*args, **kwargs):
                    return await gracy_send_msg(*args, **kwargs, tag=ctx.adapter_tag)
                result = handler_func(
                    ctx.plugin_manager,
                    _ph_send,
                    self._build_plugin_data(ctx),
                    ctx.sender_id,
                    ctx.chat_type,
                    "all",
                    _logger,
                )
                if inspect.iscoroutine(result):
                    await result

            elapsed = time.time() - start_time
            _logger.info(
                f"[PluginHandler] 成功: {plugin_name} "
                f"命令={ctx.command} 耗时={elapsed:.3f}s"
            )

        except Exception as e:
            elapsed = time.time() - start_time
            _logger.error(
                f"[PluginHandler] 异常: {plugin_name} "
                f"命令={ctx.command} 耗时={elapsed:.3f}s 错误={e}",
                exc_info=True,
            )

        return None  # 无论成功失败都短路（已处理）

    def _build_plugin_data(self, ctx: PluginContext) -> dict:
        """为旧风格 handler 构建 plugin_data 字典"""
        return {
            "text": ctx.text or ctx.raw_text,
            "nickname": ctx.nickname,
            "images": ctx.images,
            "ats": ctx.ats,
            "target_id": ctx.target_id,
            "chat_type": ctx.chat_type,
            "raw_data": ctx.raw_data,
            "is_at_bot": ctx.is_at_bot,
        }


# ══════════════════════════════════════════════════════════
# Stage 4: ResponseSender
# ══════════════════════════════════════════════════════════

class ResponseSender(Stage):
    """响应发送器

    处理未被插件匹配的消息：将消息分发给注册为 catch_all 的插件（如 LLM_Chat）。
    """

    async def process(self, ctx: PluginContext) -> Optional[PluginContext]:
        raw_msg = ctx.raw_text.strip()
        if not raw_msg:
            return None

        # ── 自动回复匹配（config.json 里的 auto_replies，比 AI 优先） ──
        from core.config_manager import config_manager
        auto_replies = config_manager.get("auto_replies", {})
        if auto_replies and isinstance(auto_replies, dict):
            for keyword, reply in auto_replies.items():
                if keyword in raw_msg:
                    from core.gracy_adapter.send import gracy_send_msg
                    from core.gracy_adapter.message import GracyText
                    await gracy_send_msg(
                        ctx.target_id,
                        GracyText(text=reply),
                        chat_type=ctx.chat_type,
                        tag=ctx.adapter_tag,
                    )
                    _logger.info(f"[自动回复] 关键词 '{keyword}' → 已回复用户 {ctx.sender_id}")
                    return None  # 已处理，终止

        # ── 查找注册的兜底处理器（@on_fallback，如 LLM_Chat） ──
        from core.decorators.registration import FALLBACK_HANDLERS
        for entry in FALLBACK_HANDLERS:
            if ctx.chat_type not in entry.get("chat_type", ["private", "group"]):
                continue
            handler_func = entry["handler_func"]
            _logger.debug(f"[ResponseSender] 兜底分发: {entry.get('plugin_name', 'unknown')}")
            from core.gracy_adapter.send import gracy_send_msg
            # 包装 send 函数，自动注入来源适配器 tag
            async def _fb_send(*args, **kwargs):
                return await gracy_send_msg(*args, **kwargs, tag=ctx.adapter_tag)
            result = handler_func(
                ctx.plugin_manager,
                _fb_send,
                self._build_plugin_data(ctx),
                ctx.sender_id,
                ctx.chat_type,
                "all",
                _logger,
            )
            if inspect.iscoroutine(result):
                await result
            return None  # 已处理，终止

        return None  # 无兜底处理器，终止

    def _build_plugin_data(self, ctx: PluginContext) -> dict:
        return {
            "text": ctx.text or ctx.raw_text,
            "nickname": ctx.nickname,
            "images": ctx.images,
            "ats": ctx.ats,
            "target_id": ctx.target_id,
            "chat_type": ctx.chat_type,
            "raw_data": ctx.raw_data,
            "is_at_bot": ctx.is_at_bot,
        }
