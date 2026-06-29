"""Stage: CommandMatcher — TOML + @on_command / @on_regex 命令匹配"""

import asyncio
import logging
import re
from typing import Optional

from core.pipeline import Stage
from core.decorators.context import PluginContext
from core.pipeline.helpers import is_master

_logger = logging.getLogger("Core.Pipeline")


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
            return ctx

        # ── 路径 A: TOML 命令匹配（并行过滤 + 优先级选胜者） ──
        from core.plugin_manager import plugin_manager

        async def _check_plugin(plugin: dict) -> Optional[dict]:
            matched_cmd = self._match_any(plugin.get("commands", []), raw_msg)
            if not matched_cmd:
                return None
            if ctx.chat_type not in plugin.get("chat_type", ["private", "group"]):
                return None
            if plugin.get("permission") == "master":
                if not is_master(ctx, plugin):
                    return None
            if ctx.chat_type == "group" and plugin.get("is_at_required", False) and not ctx.is_at_bot:
                return None
            return {"plugin": plugin, "matched_cmd": matched_cmd, "priority": plugin.get("priority", 50)}

        tasks = [_check_plugin(p) for p in plugin_manager.registry]
        results = await asyncio.gather(*tasks)
        matches = [r for r in results if r is not None]
        if matches:
            matches.sort(key=lambda x: x["priority"], reverse=True)
            best = matches[0]
            plugin = best["plugin"]
            ctx.command = best["matched_cmd"]
            ctx.plugin_name = plugin["name"]
            ctx.extra["priority"] = best["priority"]
            ctx.extra["handler_func"] = plugin.get("command_handlers", {}).get(ctx.command) or plugin.get("handler_func")
            ctx.extra["_match_source"] = "toml"
            _logger.debug(f"[CommandMatcher] TOML 并行匹配: {plugin['name']} → {best['matched_cmd']} (priority={best['priority']})")
            return ctx

        # ── 路径 B: @on_command / @on_regex 装饰器匹配 ──
        from core.decorators.registration import DECORATOR_COMMAND_REGISTRY

        for entry in DECORATOR_COMMAND_REGISTRY:
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

        ctx.extra["_match_source"] = "none"
        return ctx

    def _match_any(self, commands: list, raw_msg: str) -> Optional[str]:
        """匹配命令列表，返回最长匹配的命令"""
        candidates = []
        for cmd in commands:
            if cmd == "//":
                if re.search(r'(?:^|\s)//', raw_msg):
                    candidates.append(cmd)
            elif raw_msg == cmd or raw_msg.startswith(cmd + " ") or raw_msg.startswith(cmd + "\n"):
                candidates.append(cmd)
        if not candidates:
            return None
        return max(candidates, key=len)
