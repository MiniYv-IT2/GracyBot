"""
gracone_admin.py — Gracone 管理命令

职责:
1. /gracone 状态/管理命令
2. 插件禁用/启用（主人专属）
3. 插件搜索（GitHub API）/ 安装（git clone 到 nonebot_plugins）
"""

import sys
import os
import re
import asyncio
import subprocess
from urllib.request import urlopen, Request
from urllib.error import URLError
import json

from graci import on_command, plugin_handler, PluginContext, require_master, get_logger

from gracone_core import (
    GRACONE_VERSION,
    _loaded_nb_plugins,
    _disabled_nb_plugins,
    _plugin_dir,
    list_plugin_dir,
    save_disabled_plugins,
    scan_and_load_nb_plugins,
    full_reload,
)

logger = get_logger("Gracone.Admin")


# ════════════════════════════════════════════════════
# 主人校验
# ════════════════════════════════════════════════════

def _check_master(ctx: PluginContext) -> bool:
    """检查是否为主人"""
    from graci import security_manager
    is_master, _ = security_manager.check_master_permission(ctx.sender_id)
    return is_master


# ════════════════════════════════════════════════════
# 状态命令
# ════════════════════════════════════════════════════

@on_command("/gracone", "/gracone_status")
@plugin_handler
async def handle_gracone(ctx: PluginContext):
    """Gracone 兼容层管理命令

    子命令:
      /gracone                        — 显示状态
      /gracone disable <插件名>       — 禁用插件（主人）
      /gracone enable <插件名>        — 启用插件（主人）
      /gracone search <关键词>        — GitHub 搜索插件
      /gracone install <用户/仓库>    — git clone 安装到 nonebot_plugins
    """
    raw = ctx.raw_text.strip()
    parts = raw.split()

    if len(parts) >= 2:
        subcmd = parts[1].lower()
        args = parts[2:]

        if subcmd == "disable" and args:
            await _handle_disable(ctx, args[0])
            return
        elif subcmd == "enable" and args:
            await _handle_enable(ctx, args[0])
            return
        elif subcmd == "install" and args:
            await _handle_install(ctx, " ".join(args))
            return
        elif subcmd == "search" and args:
            await _handle_search(ctx, " ".join(args))
            return

    # 默认：显示状态
    plugins = list_plugin_dir()
    lines = [
        "【Gracone 兼容层 v{}】".format(GRACONE_VERSION),
        "Gracone 让 GracyBot 无缝运行 NoneBot 社区插件，",
        "像 Wine 兼容 Windows 应用一样，在插件层做转译。",
        "",
        "状态: ✓ 运行中",
        "NoneBot 插件数: {}/{}（已加载/总）".format(
            len(_loaded_nb_plugins), len(plugins)),
        "── 插件列表 ──",
    ]

    for p in plugins:
        if p["disabled"]:
            status = " [已禁用]"
        elif p["loaded"]:
            status = " ✓"
        else:
            status = " -"
        lines.append("  {}{} ({})".format(p["name"], status, p["type"]))

    if _disabled_nb_plugins:
        lines.append("── 管理 ──")
        lines.append("  /gracone disable <名称>  — 禁用插件（主人）")
        lines.append("  /gracone enable <名称>   — 启用插件（主人）")
        lines.append("  /gracone search <关键词> — GitHub 搜索插件")
        lines.append("  /gracone install <用户/仓库> — git clone 安装")

    await ctx.reply("\n".join(lines))


# ════════════════════════════════════════════════════
# 禁用/启用
# ════════════════════════════════════════════════════

async def _handle_disable(ctx: PluginContext, plugin_name: str):
    """禁用 NoneBot 插件（主人专属）"""
    if not _check_master(ctx):
        await ctx.reply("❌ 权限不足！只有机器人主人可以使用此命令")
        return

    plugins = list_plugin_dir()
    names = [p["name"] for p in plugins]
    if plugin_name not in names:
        await ctx.reply("❌ 未找到插件「{}」，可用插件: {}".format(
            plugin_name, ", ".join(names)))
        return

    if plugin_name in _disabled_nb_plugins:
        await ctx.reply("⚠️ 插件「{}」已被禁用".format(plugin_name))
        return

    _disabled_nb_plugins.add(plugin_name)
    save_disabled_plugins()
    await full_reload()

    await ctx.reply("✅ 已禁用插件「{}」，重启后仍然生效".format(plugin_name))
    logger.info(f"用户 {ctx.sender_id} 禁用了插件: {plugin_name}")


async def _handle_enable(ctx: PluginContext, plugin_name: str):
    """启用 NoneBot 插件（主人专属）"""
    if not _check_master(ctx):
        await ctx.reply("❌ 权限不足！只有机器人主人可以使用此命令")
        return

    plugins = list_plugin_dir()
    names = [p["name"] for p in plugins]
    if plugin_name not in names:
        await ctx.reply("❌ 未找到插件「{}」，可用插件: {}".format(
            plugin_name, ", ".join(names)))
        return

    if plugin_name not in _disabled_nb_plugins:
        await ctx.reply("⚠️ 插件「{}」未被禁用".format(plugin_name))
        return

    _disabled_nb_plugins.discard(plugin_name)
    save_disabled_plugins()
    await full_reload()

    await ctx.reply("✅ 已启用插件「{}」，重启后仍然生效".format(plugin_name))
    logger.info(f"用户 {ctx.sender_id} 启用了插件: {plugin_name}")


# ════════════════════════════════════════════════════
# 安装（git clone）/ 搜索（GitHub API）
# ════════════════════════════════════════════════════

async def _handle_search(ctx: PluginContext, keyword: str):
    """通过 GitHub API 搜索 NoneBot 插件（主人专属）
    
    搜索名称/描述包含关键词的 nonebot 插件仓库，
    返回 GitHub 地址供安装。
    """
    if not _check_master(ctx):
        await ctx.reply("❌ 权限不足！只有机器人主人可以使用此命令")
        return

    await ctx.reply("� 正在通过 GitHub 搜索「{}」...".format(keyword))

    try:
        query = "nonebot-plugin-{}+in:name,description,topics".format(
            keyword.replace(" ", "+"))
        url = ("https://api.github.com/search/repositories?"
               "q={}&sort=stars&order=desc&per_page=10".format(query))

        req = Request(url, headers={
            "User-Agent": "GracyBot-Gracone/1.0",
            "Accept": "application/vnd.github.v3+json",
        })
        resp = await asyncio.get_event_loop().run_in_executor(
            None, lambda: urlopen(req, timeout=15))
        data = json.loads(resp.read().decode("utf-8"))

        items = data.get("items", [])
        if not items:
            await ctx.reply(
                "未找到与「{}」相关的 NoneBot 插件\n"
                "可尝试: https://github.com/search?q=nonebot-plugin-{}".format(
                    keyword, keyword.replace(" ", "+")))
            return

        lines = ["🔍 GitHub 搜索结果（nonebot-plugin-{}）:".format(keyword)]
        for i, repo in enumerate(items[:8], 1):
            name = repo["full_name"]
            stars = repo["stargazers_count"]
            desc = repo.get("description") or "（无描述）"
            if len(desc) > 50:
                desc = desc[:50] + "..."
            lines.append("{}. {} ⭐{}".format(i, name, stars))
            lines.append("   {}".format(desc))
            lines.append("   {}".format(repo.get("html_url", "")))

        lines.append("")
        lines.append("安装: /gracone install <用户/仓库>")
        lines.append("例如: /gracone install noneplugin/nonebot-plugin-cchess")

        await ctx.reply("\n".join(lines))

    except URLError as e:
        if hasattr(e, 'code') and e.code == 403:
            msg = ("GitHub API 限流了，请稍后再试\n"
                   "或手动浏览: https://github.com/search?q=nonebot-plugin-")
        else:
            msg = "GitHub 搜索失败: {}".format(str(e)[:200])
        await ctx.reply(msg)
    except asyncio.TimeoutError:
        await ctx.reply("⏱️ GitHub 搜索超时，请稍后再试")
    except Exception as e:
        await ctx.reply("❌ 搜索异常: {}".format(str(e)[:200]))


async def _handle_install(ctx: PluginContext, repo: str):
    """通过 git clone 安装 NoneBot 插件到 nonebot_plugins（主人专属）
    
    接受格式:
      - user/repo          → 自动拼接 github.com
      - 完整 GitHub URL    → 直接 clone
    
    安装后自动重载，禁用则用 /gracone disable
    """
    if not _check_master(ctx):
        await ctx.reply("❌ 权限不足！只有机器人主人可以使用此命令")
        return

    # 解析仓库地址
    repo = repo.strip().rstrip("/")
    if repo.startswith("https://"):
        clone_url = repo
        # 从 URL 提取 repo 名
        repo_name = repo.rstrip(".git").split("/")[-1]
    elif "/" in repo and not repo.startswith("http"):
        clone_url = "https://github.com/{}.git".format(repo)
        repo_name = repo.split("/")[-1]
    else:
        await ctx.reply("❌ 格式错误！请使用 user/repo 或完整 GitHub URL")
        return

    # 检查是否已经存在
    existing_plugins = list_plugin_dir()
    existing_names = [p["name"] for p in existing_plugins]
    plugin_dir_name = repo_name.replace("nonebot-plugin-", "").replace("-", "_")
    if repo_name in existing_names or plugin_dir_name in existing_names:
        await ctx.reply("⚠️ 插件「{}」已存在，无需重复安装".format(
            repo_name))
        return

    await ctx.reply("� 正在克隆「{}」...".format(clone_url))

    try:
        # 创建临时目录
        import tempfile
        import shutil

        tmpdir = tempfile.mkdtemp(prefix="gracone_install_")
        target_dir = os.path.join(tmpdir, repo_name)

        proc = await asyncio.create_subprocess_exec(
            "git", "clone", "--depth=1", clone_url, target_dir,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=120)
        output = (stderr or b"").decode("utf-8", errors="replace")

        if proc.returncode != 0:
            shutil.rmtree(tmpdir, ignore_errors=True)
            error = output[:300]
            if "could not read Username" in error:
                error = "需要认证的私有仓库，请确认仓库是公开的"
            await ctx.reply("❌ git clone 失败:\n{}".format(error))
            return

        # 自动检测插件目录结构
        # 常见结构: nonebot_plugin_xxx/  或  xxx/ 或  src/nonebot_plugin_xxx/
        plugin_src = None
        for entry in os.scandir(target_dir):
            if entry.is_dir() and not entry.name.startswith((".", "_")):
                # 优先匹配 nonebot_plugin_ 前缀的目录
                if "nonebot_plugin" in entry.name or entry.name == repo_name:
                    plugin_src = entry.path
                    break
        if not plugin_src:
            # 找包含 __init__.py 的目录
            for entry in os.scandir(target_dir):
                if entry.is_dir():
                    init_file = os.path.join(entry.path, "__init__.py")
                    if os.path.exists(init_file):
                        plugin_src = entry.path
                        break

        # 如果没有找到子包结构，整个仓库就是一个插件
        if plugin_src:
            dest_name = os.path.basename(plugin_src)
            dest = _plugin_dir / dest_name
            if dest.exists():
                shutil.rmtree(dest, ignore_errors=True)
            shutil.copytree(plugin_src, dest)
        else:
            # 整个仓库作为插件目录
            dest = _plugin_dir / repo_name
            if dest.exists():
                shutil.rmtree(str(dest), ignore_errors=True)
            shutil.copytree(target_dir, str(dest))

        # 清理临时目录
        shutil.rmtree(tmpdir, ignore_errors=True)

        # 重新加载
        count = await full_reload()
        await ctx.reply(
            "✅ 安装成功！已加载到 nonebot_plugins/{}\n"
            "当前已加载 {} 个 NoneBot 插件".format(
                plugin_src and os.path.basename(plugin_src) or repo_name,
                count))

    except asyncio.TimeoutError:
        await ctx.reply("⏱️ 克隆超时（120s），请检查网络或手动安装")
    except FileNotFoundError:
        await ctx.reply("❌ 未找到 git 命令，请确保已安装 Git\n"
                        "或手动将插件文件夹放到 nonebot_plugins 目录")
    except Exception as e:
        await ctx.reply("❌ 安装异常: {}".format(str(e)[:200]))
