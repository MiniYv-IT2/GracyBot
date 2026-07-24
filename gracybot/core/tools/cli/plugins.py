"""插件管理 — 安装/卸载/列表/CLI 注册"""
import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Callable, Optional

from .utils import find_project_root, find_plugins_dir, pip_install


def list_plugins(root: Path) -> list[dict]:
    """扫描 plugins/ 下所有有效的插件目录"""
    plugins_dir = find_plugins_dir(root)
    if not plugins_dir.is_dir():
        return []
    result = []
    for d in sorted(plugins_dir.iterdir()):
        if not d.is_dir():
            continue
        meta_file = d / "metadata.toml"
        if not meta_file.exists():
            continue
        # 读取 TOML 获取插件名
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib
        meta_name = d.name
        try:
            with open(meta_file, "rb") as f:
                raw = tomllib.load(f)
            meta_name = raw.get("plugin", {}).get("name", d.name)
        except Exception:
            pass
        req_file = d / "requirements.txt"
        result.append({
            "name": meta_name,
            "dir": d.name,
            "path": str(d),
            "has_requirements": req_file.exists(),
        })
    return result


def install_plugin(root: Path, source: str) -> bool:
    """安装插件

    Args:
        source: 插件目录名 / 本地路径 / Git URL / GitHub 简写
    """
    plugins_dir = find_plugins_dir(root)
    plugins_dir.mkdir(parents=True, exist_ok=True)

    # ── 如果 source 是已有插件目录名，重新安装依赖 ──
    existing = plugins_dir / source
    if existing.is_dir():
        req = existing / "requirements.txt"
        if req.exists():
            print(f"  📦 安装 {source} 的依赖...")
            pip_install([], req_file=str(req))
            print(f"  ✅ 依赖安装完成")
        else:
            print(f"  ℹ️  {source} 没有 requirements.txt")
        return True

    # GitHub 简写: "user/repo" → https://github.com/user/repo
    if "/" in source and not source.startswith(("http", "\\")):
        source = f"https://github.com/{source}.git"

    try:
        if source.endswith(".git"):
            name = source.rstrip("/").split("/")[-1].replace(".git", "")
            target = plugins_dir / name
            if target.exists():
                print(f"  ⚠️ 插件 {name} 已存在")
                return False
            subprocess.check_call(
                ["git", "clone", source, str(target)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60
            )
            print(f"  ✅ 克隆完成: {name}")
        else:
            src = Path(source).resolve()
            if not src.exists():
                print(f"  ❌ 路径不存在: {source}")
                return False
            name = src.name
            target = plugins_dir / name
            if target.exists():
                print(f"  ⚠️ 插件 {name} 已存在")
                return False
            shutil.copytree(src, target, ignore=shutil.ignore_patterns(
                "__pycache__", ".git", ".venv", "node_modules"
            ))
            print(f"  ✅ 复制完成: {name}")

        # 自动安装依赖
        req = target / "requirements.txt"
        if req.exists():
            print(f"  📦 安装依赖...")
            pip_install([], req_file=str(req))
        return True
    except subprocess.TimeoutExpired:
        print(f"  ❌ 操作超时（网络不佳？）")
        return False
    except Exception as e:
        print(f"  ❌ 安装失败: {e}")
        return False


def remove_plugin(root: Path, name: str) -> bool:
    """卸载插件"""
    plugins_dir = find_plugins_dir(root)
    target = plugins_dir / name
    if not target.exists():
        print(f"  ❌ 插件 {name} 不存在")
        return False
    shutil.rmtree(target, ignore_errors=True)
    print(f"  ✅ 已删除: {name}")
    return True
