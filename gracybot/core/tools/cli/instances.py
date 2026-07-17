"""实例管理 — gracy instance <list|add|enable|disable|remove>"""

import os
import json
import shutil
from pathlib import Path
from typing import Optional

import typer

from gracybot.core.tools.paths import get_instances_dir

instance_cli = typer.Typer(help="实例管理（storage/instances/<name>/）")


def _instances_dir() -> Path:
    return Path(get_instances_dir())


def _list_instances() -> list[dict]:
    """列出所有实例及其状态"""
    inst_dir = _instances_dir()
    if not inst_dir.is_dir():
        return []

    results = []
    for entry in sorted(inst_dir.iterdir()):
        cfg_path = entry / "config.json"
        if not cfg_path.is_file():
            continue
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            results.append({
                "name": entry.name,
                "enabled": cfg.get("enabled", True),
                "platform": cfg.get("platform", "?"),
                "bot_name": cfg.get("bot_name", "?"),
                "robot_id": cfg.get("robot_id", ""),
                "master_id": cfg.get("master_id", ""),
                "type": cfg.get("type", "?"),
            })
        except Exception:
            results.append({"name": entry.name, "enabled": False, "error": True})
    return results


@instance_cli.command("list")
def cmd_list():
    """列出所有实例"""
    instances = _list_instances()
    if not instances:
        typer.echo("  ℹ️  没有实例（storage/instances/<name>/config.json）")
        typer.echo("  💡 使用 gracy instance add <name> 创建")
        return

    typer.echo(f"  共 {len(instances)} 个实例：")
    typer.echo()
    for inst in instances:
        status = "🟢 启用" if inst.get("enabled") else "🔴 禁用"
        if inst.get("error"):
            typer.echo(f"  {status}  {inst['name']}  ⚠️  配置损坏")
            continue
        robot = inst.get("robot_id", "")
        master = inst.get("master_id", "")
        typer.echo(f"  {status}  {inst['name']}")
        typer.echo(f"        平台: {inst['platform']} | 名称: {inst['bot_name']}")
        typer.echo(f"        类型: {inst['type']} | robot_id: {robot} | master: {master}")
        typer.echo()


@instance_cli.command("add")
def cmd_add(
    name: str = typer.Argument(..., help="实例目录名，如 main_bot"),
    robot_id: str = typer.Option("", "--robot", "-r", help="机器人 ID"),
    master_id: str = typer.Option("", "--master", "-m", help="主人/管理员 ID"),
    platform: str = typer.Option("", "--platform", "-p", help="平台类型（如 onebot / qq_official）"),
    bot_name: str = typer.Option("", "--bot-name", "-b", help="Bot 显示名称"),
    conn_type: str = typer.Option("http", "--type", "-t", help="连接类型: http/ws"),
):
    """创建新实例（交互式或静默）"""
    inst_dir = _instances_dir() / name
    if inst_dir.exists():
        typer.echo(f"  ❌ 实例 {name} 已存在: {inst_dir}")
        raise typer.Exit(1)

    # 交互式补全缺失字段
    if not robot_id:
        robot_id = typer.prompt("  机器人 ID", default="")
    if not master_id:
        master_id = typer.prompt("  主人 ID", default="")
    if not bot_name:
        bot_name = typer.prompt("  Bot 显示名称", default=name)

    http_url = ""
    host = ""
    port = 0
    access_token = ""

    if conn_type == "http":
        http_url = typer.prompt("  HTTP API 地址", default="http://127.0.0.1:3000")
    else:
        host = typer.prompt("  WS 地址", default="127.0.0.1")
        p = typer.prompt("  WS 端口", default="3001")
        port = int(p) if p.isdigit() else 3001
        access_token = typer.prompt("  Access Token（可选）", default="")

    # 创建目录和配置文件
    inst_dir.mkdir(parents=True, exist_ok=True)
    cfg = {
        "platform": platform,
        "bot_name": bot_name,
        "enabled": True,
        "type": conn_type,
        "robot_id": robot_id,
        "master_id": master_id,
    }
    if conn_type == "http":
        cfg["http_url"] = http_url
    else:
        cfg["host"] = host
        cfg["port"] = port
        if access_token:
            cfg["access_token"] = access_token

    cfg_path = inst_dir / "config.json"
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

    typer.echo(f"  ✅ 实例 {name} 已创建")
    typer.echo(f"     配置文件: {cfg_path}")
    typer.echo(f"     platform={platform} type={conn_type} robot={robot_id} master={master_id}")
    typer.echo("  💡 重启生效: gracy stop && gracy run")


@instance_cli.command("enable")
def cmd_enable(
    name: str = typer.Argument(..., help="实例名"),
):
    """启用实例"""
    _set_enabled(name, True)


@instance_cli.command("disable")
def cmd_disable(
    name: str = typer.Argument(..., help="实例名"),
):
    """禁用实例"""
    _set_enabled(name, False)


def _set_enabled(name: str, enabled: bool):
    """设置实例启用/禁用"""
    cfg_path = _instances_dir() / name / "config.json"
    if not cfg_path.is_file():
        typer.echo(f"  ❌ 实例 {name} 不存在")
        raise typer.Exit(1)

    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    cfg["enabled"] = enabled
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

    status = "启用" if enabled else "禁用"
    typer.echo(f"  ✅ 实例 {name} 已{status}")
    if enabled:
        typer.echo("  💡 重启生效: gracy stop && gracy run")
    else:
        typer.echo("  (下次启动将跳过此实例)")


@instance_cli.command("remove")
def cmd_remove(
    name: str = typer.Argument(..., help="实例名"),
    force: bool = typer.Option(False, "--force", "-f", help="强制删除，不确认"),
):
    """删除实例（删除目录及所有文件）"""
    inst_dir = _instances_dir() / name
    if not inst_dir.is_dir():
        typer.echo(f"  ❌ 实例 {name} 不存在")
        raise typer.Exit(1)

    if not force:
        confirm = typer.confirm(f"  ⚠️  确定要删除实例 {name} 吗？(不可恢复)")
        if not confirm:
            typer.echo("  已取消")
            return

    shutil.rmtree(inst_dir)
    typer.echo(f"  ✅ 实例 {name} 已删除")
