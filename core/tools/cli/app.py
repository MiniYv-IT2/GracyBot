"""GracyBot CLI 主入口 — Typer 应用"""
import os
import sys
from pathlib import Path
from typing import Optional

# Windows 终端编码修复（避免 CP936 崩 emoji/特殊字符）
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import typer

from .plugins import (
    register_cli_command as _register_plugin_cmd,
    list_plugins,
    install_plugin,
    remove_plugin,
    _PLUGIN_CLI_COMMANDS,
)
from .system import (
    setup_autostart,
    uninstall_bot,
    backup_bot,
    run_bot_process,
    stop_bot_process,
)
from .instances import instance_cli
from .utils import find_project_root, is_local_project, get_platform_label, in_venv, pip_install
from core.plugin_manager import plugin_manager
import json

# ── Typer App ──
gracy_cli = typer.Typer(
    name="gracybot",
    help="GracyBot 命令行管理工具",
    no_args_is_help=True,
    add_completion=True,
)

# ── 子命令组 ──
plugin_cli = typer.Typer(help="插件管理")
config_cli = typer.Typer(help="配置管理")
gracy_cli.add_typer(plugin_cli, name="plugin")
gracy_cli.add_typer(config_cli, name="config")
gracy_cli.add_typer(instance_cli, name="instance")


# ── 共用函数 ──
def _ensure_root() -> Path:
    """获取项目根目录（本地项目或 pip 安装后的当前工作目录）"""
    root = find_project_root()
    if root:
        return root
    # pip 安装模式：当前目录作为工作目录
    return Path.cwd()


def _ensure_local_root() -> Path:
    """仅限本地项目（需要 bot.py 和 plugins/ 目录）"""
    root = find_project_root()
    if root and is_local_project(root):
        return root
    typer.echo("❌ 此命令需要在 GracyBot 项目目录下运行")
    typer.echo("   请 cd 到包含 bot.py 的目录，或克隆项目仓库")
    raise typer.Exit(1)


# ═══════════════════════════ 核心命令 ═══════════════════════════


@gracy_cli.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """无参数时显示帮助"""
    if ctx.invoked_subcommand is None:
        typer.echo(gracy_cli.get_help())


@gracy_cli.command("run")
def cmd_run(
    debug: bool = typer.Option(False, "--debug", "-d", help="调试模式"),
    no_webui: bool = typer.Option(False, "--no-webui", help="不启动 Web 面板"),
):
    """启动机器人"""
    root = _ensure_root()

    if is_local_project(root):
        # 本地项目模式：用 bot.py 子进程启动
        run_bot_process(root, debug=debug, no_webui=no_webui)
    else:
        # pip 安装模式：直接运行（无需 bot.py）
        import asyncio
        from core.main import run_bot

        # 配置文件路径由 config_manager 自动查找（向上找项目根目录）


        if debug:
            os.environ["GRACY_DEBUG"] = "1"
        elif "GRACY_DEBUG" in os.environ:
            del os.environ["GRACY_DEBUG"]
        if no_webui:
            os.environ["GRACY_NO_WEBUI"] = "1"
        elif "GRACY_NO_WEBUI" in os.environ:
            del os.environ["GRACY_NO_WEBUI"]

        print("  🚀 启动 GracyBot ...")
        try:
            asyncio.run(run_bot())
        except KeyboardInterrupt:
            print("\n  🛑 已停止")
        except Exception as e:
            print(f"  ❌ 启动失败: {e}")
            sys.exit(1)


@gracy_cli.command("stop")
def cmd_stop():
    """停止机器人"""
    stop_bot_process()


@gracy_cli.command("restart")
def cmd_restart(
    debug: bool = typer.Option(False, "--debug", "-d", help="调试模式"),
    no_webui: bool = typer.Option(False, "--no-webui", help="不启动 Web 面板"),
):
    """重启机器人"""
    cmd_stop()
    cmd_run(debug=debug, no_webui=no_webui)


@gracy_cli.command("status")
def cmd_status():
    """查看运行状态"""
    root = _ensure_root()
    plat = get_platform_label()

    # 懒加载避免触发机器人日志系统
    from core.config import BOT_VERSION, MASTER_ID
    from core.gracy_adapter.pool import adapter_pool

    default = adapter_pool.get_default()
    robot_id = getattr(default, '_instance_robot_id', '') if default else ''

    typer.echo(f"  GracyBot {BOT_VERSION}")
    typer.echo(f"  项目路径: {root}")
    typer.echo(f"  Bot ID: {robot_id or '（未配置）'}  |  管理员: {MASTER_ID}")
    typer.echo(f"  平台: {plat}  |  虚拟环境: {'是' if in_venv() else '否'}")
    typer.echo(f"  Python: {sys.version.split()[0]}")

    # 检查进程
    import subprocess
    try:
        # 根据连接模式检测
        from core.config import CALLBACK_PORT, config_manager
        mode = config_manager.get("connection_mode", "http")
        if mode in ("http", "http_reverse"):
            port = CALLBACK_PORT
        elif mode == "ws_reverse":
            port = config_manager.get("ws_port", 3001)
        else:  # ws_forward
            # 正向 WS 查 callback 端口（也开着）
            port = CALLBACK_PORT

        if plat == "windows":
            r = subprocess.run(
                f'netstat -ano | findstr ":{port}" 2>nul',
                capture_output=True, text=True, shell=True, timeout=5
            )
            running = bool(r.stdout.strip())
        else:
            r = subprocess.run(
                f'netstat -tlnp 2>/dev/null | grep ":{port} "',
                capture_output=True, text=True, shell=True, timeout=5
            )
            running = bool(r.stdout.strip())
        typer.echo(f"  运行状态: {'✅ 运行中' if running else '⏹️  未运行'}")
    except Exception:
        typer.echo("  运行状态: ⚠️ 无法检测")


@gracy_cli.command("version")
def cmd_version():
    """显示版本"""
    from core.config import BOT_VERSION as v
    typer.echo(f"GracyBot {v}")


# ═══════════════════════════ 快捷命令 ═══════════════════════════


@gracy_cli.command("ins")
def cmd_ins(
    package: str = typer.Argument(..., help="包名或插件目录名"),
    is_plugin: bool = typer.Option(False, "--plugin", "-p", help="安装插件依赖"),
):
    """快速安装包 / 插件依赖"""
    # 先检查是否是已有插件目录名
    if not is_plugin:
        root = find_project_root() or Path.cwd()
        plugins_dir = root / "plugins"
        existing = plugins_dir / package
        if existing.is_dir() and (existing / "requirements.txt").exists():
            # 自动走插件依赖安装
            req = existing / "requirements.txt"
            typer.echo(f"  📦 检测到插件 {package}，安装依赖...")
            pip_install([], req_file=str(req))
            typer.echo(f"  ✅ 安装完成")
            return

    # 普通 Python 包安装
    typer.echo(f"  📦 安装 {package}...")
    pip_install([package])
    typer.echo(f"  ✅ 安装完成")


@gracy_cli.command("set")
def cmd_set(
    key: str = typer.Argument(..., help="配置项 (master / bot)"),
    value: str = typer.Argument(..., help="配置值"),
):
    """快捷设置配置"""
    cfg_file = find_project_root() / "config.json" if find_project_root() else Path.cwd() / "config.json"

    key_map = {
        "master": "master_id",
        "bot": "robot_id",
        "master_id": "master_id",
        "robot_id": "robot_id",
    }
    real_key = key_map.get(key, key)
    if real_key not in ("master_id", "robot_id"):
        typer.echo(f"  ❌ 不支持的配置项: {key}")
        typer.echo(f"  支持: master, bot (robot)")
        raise typer.Exit(1)

    cfg = {}
    if cfg_file.exists():
        cfg = json.loads(cfg_file.read_text(encoding="utf-8"))

    cfg[real_key] = value
    cfg_file.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    typer.echo(f"  ✅ {real_key} = {value}")


# ═══════════════════════════ 插件管理 ═══════════════════════════


@plugin_cli.command("list")
def cmd_plugin_list():
    """列出已安装插件"""
    root = _ensure_local_root()
    plugins = list_plugins(root)
    if not plugins:
        typer.echo("  ℹ️  没有安装任何插件")
        return
    typer.echo(f"  共 {len(plugins)} 个插件:")
    for p in plugins:
        deps = " 📦" if p["has_requirements"] else ""
        typer.echo(f"    • {p['name']}{deps}")


@plugin_cli.command("install")
def cmd_plugin_install(
    source: str = typer.Argument(..., help="本地路径 / Git URL / GitHub user/repo"),
):
    """安装插件（自动安装依赖）"""
    root = _ensure_local_root()
    install_plugin(root, source)


@plugin_cli.command("remove")
def cmd_plugin_remove(
    name: str = typer.Argument(..., help="插件名称（目录名）"),
):
    """卸载插件"""
    root = _ensure_local_root()
    remove_plugin(root, name)


@gracy_cli.command("disable")
def cmd_disable(
    name: str = typer.Argument(..., help="插件目录名"),
):
    """禁用插件（下次启动生效）"""
    root = find_project_root() or Path.cwd()
    plugins_dir = root / "plugins"
    target = plugins_dir / name
    if not target.is_dir():
        typer.echo(f"  ❌ 插件 {name} 不存在（目录: {plugins_dir}）")
        raise typer.Exit(1)

    disabled = plugin_manager.load_disabled_plugins()
    if name in disabled:
        typer.echo(f"  ⚠️ 插件 {name} 已被禁用")
        return
    disabled.add(name)
    plugin_manager.save_disabled_plugins(disabled)
    typer.echo(f"  ✅ 已禁用插件 {name}（下次启动生效）")


@gracy_cli.command("enable")
def cmd_enable(
    name: str = typer.Argument(..., help="插件目录名"),
):
    """启用插件（下次启动生效）"""
    disabled = plugin_manager.load_disabled_plugins()
    if name not in disabled:
        typer.echo(f"  ℹ️ 插件 {name} 未被禁用")
        return
    disabled.discard(name)
    plugin_manager.save_disabled_plugins(disabled)
    typer.echo(f"  ✅ 已启用插件 {name}（下次启动生效）")


@gracy_cli.command("disabled")
def cmd_disabled():
    """查看已禁用的插件"""
    disabled = plugin_manager.load_disabled_plugins()
    if not disabled:
        typer.echo("  ℹ️ 没有已禁用的插件")
        return
    typer.echo(f"  共 {len(disabled)} 个已禁用插件:")
    for p in sorted(disabled):
        typer.echo(f"    • {p}")


# ═══════════════════════════ 配置管理 ═══════════════════════════


@config_cli.command("show")
def cmd_config_show():
    """查看配置"""
    root = _ensure_root()
    cfg_file = root / "config.json"
    if cfg_file.exists():
        import json
        cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
        for k, v in cfg.items():
            v_str = str(v)
            if len(v_str) > 60:
                v_str = v_str[:57] + "..."
            typer.echo(f"  {k}: {v_str}")
    else:
        typer.echo("  ℹ️  配置文件不存在")


@config_cli.command("edit")
def cmd_config_edit():
    """编辑配置（打开系统编辑器）"""
    root = _ensure_root()
    cfg_file = root / "config.json"
    if not cfg_file.exists():
        cfg_file.write_text("{\n  \n}\n", encoding="utf-8")
    plat = get_platform_label()
    try:
        if plat == "windows":
            subprocess.run(["notepad", str(cfg_file)], check=True)
        elif plat == "macos":
            subprocess.run(["open", str(cfg_file)], check=True)
        else:
            editor = (subprocess.run(
                ["which", "nano", "vim", "vi"],
                capture_output=True, text=True
            ).stdout.split()[0])
            subprocess.run([editor, str(cfg_file)], check=True)
        typer.echo("  ✅ 配置已保存")
    except Exception as e:
        typer.echo(f"  ⚠️ 无法打开编辑器: {e}")
        typer.echo(f"  请手动编辑: {cfg_file}")


# ═══════════════════════════ 系统管理 ═══════════════════════════


@gracy_cli.command("autostart")
def cmd_autostart(
    enable: bool = typer.Argument(True, help="true=启用, false=禁用"),
):
    """设置开机自启"""
    root = _ensure_local_root()
    setup_autostart(root, enable=enable)


@gracy_cli.command("backup")
def cmd_backup():
    """备份机器人（代码 + 数据）"""
    root = _ensure_local_root()
    backup_bot(root)


@gracy_cli.command("uninstall")
def cmd_uninstall(
    no_backup: bool = typer.Option(False, "--no-backup", help="不备份直接卸载"),
):
    """卸载机器人"""
    root = _ensure_local_root()
    typer.echo(f"  即将卸载 GracyBot: {root}")
    if not no_backup:
        typer.echo("  将先进行备份")
    if typer.confirm("  确定继续？"):
        uninstall_bot(root, backup_first=not no_backup)
    else:
        typer.echo("  已取消")


@gracy_cli.command("info")
def cmd_info():
    """显示系统环境信息"""
    import platform
    typer.echo(f"  系统: {platform.system()} {platform.release()}")
    typer.echo(f"  Python: {sys.version}")
    typer.echo(f"  虚拟环境: {in_venv()}")
    typer.echo(f"  当前目录: {Path.cwd()}")
    root = find_project_root()
    typer.echo(f"  项目根目录: {root or '未找到（pip 模式）'}")


# ═══════════════════════════ 第三方插件命令注入 ═══════════════════════════


def register_cli_command(name: str, handler, help_text: str = ""):
    """注册第三方插件 CLI 子命令

    在插件模块导入时调用此函数，即可在 gracybot <name> 中执行。
    """
    _register_plugin_cmd(name, handler, help_text)

    # 动态注入到 gracy_cli
    import functools

    @gracy_cli.command(name=name, help=help_text or handler.__doc__)
    def plugin_cmd():
        handler()

    # 保留原始名字便于后续查找
    plugin_cmd.__orig_name__ = name
    return plugin_cmd


# 应用已注册的插件命令
def _apply_plugin_commands():
    for name, info in _PLUGIN_CLI_COMMANDS.items():
        if name not in [c.name for c in gracy_cli.registered_commands]:
            register_cli_command(name, info["handler"], info["help"])


_apply_plugin_commands()


# ── 直接运行入口 ──
if __name__ == "__main__":
    gracy_cli()
