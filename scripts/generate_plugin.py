"""10 层架构插件模板生成器 — 零依赖，只 stdlib

用法：
  python scripts/generate_plugin.py plugins/MyPlugin
  python scripts/generate_plugin.py plugins/MyPlugin --name 我的插件
  python scripts/generate_plugin.py plugins/MyPlugin --name 我的插件 --author "开发者"
"""

import os
import sys
import argparse

TEMPLATE_MAIN = '''\
"""{{ NAME }} — {{ DESC }}

命令：
  /{{ CMD }} <参数>   — 功能说明
  /{{ CMD }}          — 功能说明
"""

import os
import time
from typing import Optional

import httpx

from graci import on_command, plugin_handler, PluginContext, get_logger
from graci import GracyText, GracyImage, GracyVoice, GracyAt, GracyReply, GracyMsg
from graci import GracyFile, GracyVideo, GracyForward
from graci import (
    on_fallback,
    require_master, require_permission,
    rate_limit, cooldown,
    get_current_master_id, get_current_robot_id,
    plugin_manager, on_regex, on_keyword,
    gracy_send_msg, gracy_call_api, gracy_get_platform_info,
    gracy_plugin, DECORATOR_COMMAND_REGISTRY,
    background, with_session, async_retry,
    sanitize_log, monitor_manager,
    BOT_VERSION, MASTER_ID, ROBOT_ID, ROBOT_START_TIME, LOG_ENCODING,
    config_manager,
    Stage, RuntimeRegistry, GracyEvent, IdentityTag,
    register_cli_command, log_attrs, with_logger,
)

logger = get_logger("{{ LOG_TAG }}")

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(PLUGIN_DIR, "data")
CACHE_DIR = os.path.join(DATA_DIR, "cache")

_visit_count: int = 0
_last_result: Optional[str] = None

def _greeting(name: str) -> str:
    return f"Hello, {name}!"

async def _fetch_quote() -> Optional[str]:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get("https://api.quotable.io/random")
            resp.raise_for_status()
            data = resp.json()
            return data.get("content")
    except Exception as e:
        logger.warning(f"获取名言失败: {e}")
        return None

@on_command("/{{ CMD }}")
@plugin_handler
async def handle_{{ CMD }}(ctx: PluginContext):
    """处理 /{{ CMD }} 命令"""
    args = ctx.raw_text[len(ctx.command):].strip()
    await ctx.reply(args or "Hello!")

@on_command("/admin")
@require_master
@plugin_handler
async def handle_admin(ctx: PluginContext):
    """仅主人可用"""
    global _visit_count
    info = (
        f"Bot v{BOT_VERSION}\\n"
        f"主人: {get_current_master_id()}\\n"
        f"运行: {ROBOT_START_TIME}\\n"
        f"访问: {_visit_count}"
    )
    await ctx.reply(info)

@on_command("/quote")
@rate_limit(max_calls=5, period=60)
@plugin_handler
async def handle_quote(ctx: PluginContext):
    """随机名言（每分钟限 5 次）"""
    quote = await _fetch_quote()
    await ctx.reply(quote or "获取失败，稍后再试")

@on_fallback()
@plugin_handler
async def handle_fallback(ctx: PluginContext):
    """兜底 — 接住所有未匹配消息"""
    await ctx.reply(f"未理解: {ctx.raw_text}")

logger.info("插件加载完成")
'''

TEMPLATE_METADATA_TOML = '''\
[plugin]
name        = "{{ NAME }}"
version     = "1.0.0"
author      = "{{ AUTHOR }}"
description = "{{ DESC }}"
priority    = 50
icon        = ""
dependencies = []

[handler]
entry       = "handle_{{ CMD }}"

[trigger]
commands       = ["/{{ CMD }}"]
chat_type      = ["private", "group"]
permission     = "all"
is_at_required = false

[trigger.command_descriptions]
"/{{ CMD }}" = "功能说明"
'''

TEMPLATE_INIT = '''"""{{ NAME }} — {{ DESC }}"""
'''

def _render(template: str, name: str, tag: str, cmd: str, desc: str, author: str) -> str:
    return (
        template
        .replace("{{ NAME }}", name)
        .replace("{{ LOG_TAG }}", tag)
        .replace("{{ CMD }}", cmd)
        .replace("{{ DESC }}", desc)
        .replace("{{ AUTHOR }}", author)
    )


def generate(output_dir: str, plugin_name: str, author: str, description: str):
    basename = os.path.basename(output_dir.rstrip("/\\"))
    tag = basename.replace("_plugin", "").replace("-plugin", "").replace("Plugin", "")
    cmd = basename.lower().replace("-", "").replace("_", "").replace("plugin", "")
    if not cmd:
        cmd = "hello"

    os.makedirs(output_dir, exist_ok=True)

    files = {
        os.path.join(output_dir, f"{basename}.py"):
            _render(TEMPLATE_MAIN, plugin_name, tag, cmd, description, author),
        os.path.join(output_dir, "metadata.toml"):
            _render(TEMPLATE_METADATA_TOML, plugin_name, tag, cmd, description, author),
        os.path.join(output_dir, "__init__.py"):
            _render(TEMPLATE_INIT, plugin_name, tag, cmd, description, author),
    }

    for path, content in files.items():
        with open(path, "w", encoding="utf-8") as f:
            f.write(content.lstrip("\n"))
        print(f"  created  {path}")

    os.makedirs(os.path.join(output_dir, "data", "cache"), exist_ok=True)
    print(f"  created  {os.path.join(output_dir, 'data', 'cache')}\\")
    print(f"\\nDone -> {output_dir}")


def main():
    parser = argparse.ArgumentParser(description="生成 10 层架构插件模板")
    parser.add_argument("output", help="输出目录 (如 plugins/MyPlugin)")
    parser.add_argument("--name", default=None, help="插件中文名 (默认自动从目录名派生)")
    parser.add_argument("--author", default="Anonymous", help="作者名")
    parser.add_argument("--desc", default="请补充插件描述", help="一句话描述")
    args = parser.parse_args()

    basename = os.path.basename(args.output.rstrip("/\\"))
    plugin_name = args.name or basename

    if os.path.exists(args.output):
        print(f"warning: {args.output} already exists, overwriting files")

    generate(args.output, plugin_name, args.author, args.desc)


if __name__ == "__main__":
    main()
