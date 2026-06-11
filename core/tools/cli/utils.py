"""CLI 工具函数 — 项目发现、依赖安装、进程管理"""
import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Optional


def find_project_root() -> Optional[Path]:
    """确定 GracyBot 项目根目录

    优先级:
      1. GRACYBOT_HOME 环境变量
      2. CWD 向上找 bot.py
      3. pip 安装的 site-packages 目录
    """
    env = os.environ.get("GRACYBOT_HOME")
    if env:
        p = Path(env).resolve()
        if (p / "core").is_dir():
            return p

    # 2. CWD 向上找 bot.py
    cwd = Path.cwd().resolve()
    for p in [cwd] + list(cwd.parents):
        if (p / "bot.py").exists() and (p / "core").is_dir():
            return p

    # 3. pip 安装目录（site-packages/gracybot/ 的父目录）
    try:
        import core
        pip_root = Path(core.__file__).parent.parent.resolve()
        if (pip_root / "core").is_dir():
            return pip_root
    except Exception:
        pass

    return None


def is_local_project(root: Optional[Path]) -> bool:
    """判断是否为本地项目（有 bot.py）还是 pip 安装模式"""
    if not root:
        return False
    return (root / "bot.py").exists()


def find_config(root: Path) -> Path:
    """返回 config.json 路径"""
    return root / "config.json"


def find_plugins_dir(root: Path) -> Path:
    """返回插件目录路径"""
    return root / "plugins"


def in_venv() -> bool:
    """检测是否在虚拟环境中"""
    return hasattr(sys, "real_prefix") or (
        hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
    )


def pip_install(packages: list[str], req_file: Optional[str] = None, python: Optional[str] = None) -> bool:
    """安装依赖 — 自动穷举所有 flags 组合直到成功"""
    target = ["-r", req_file] if req_file else packages
    flags_list = [[], ["--user"], ["--break-system-packages"], ["--user", "--break-system-packages"]]
    py = python or sys.executable
    env = os.environ.copy()
    env.pop("PIP_REQUIRE_VIRTUALENV", None)
    for flags in flags_list:
        try:
            subprocess.check_call(
                [py, "-m", "pip", "install", *flags] + target,
                timeout=120, env=env,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            return True
        except Exception:
            continue
    return False


def get_platform_label() -> str:
    """返回平台标签: linux / macos / windows / termux / unknown"""
    import platform
    if "termux" in str(Path.home()):
        return "termux"
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    if system == "windows":
        return "windows"
    if system == "linux":
        return "linux"
    return "unknown"


def has_systemd() -> bool:
    """检测 Linux 是否有 systemd（含 --user）"""
    try:
        r = subprocess.run(
            ["systemctl", "--user", "show-environment"],
            capture_output=True, timeout=5
        )
        return r.returncode == 0
    except Exception:
        return False


def make_archive(root: Path, output: Path) -> Optional[Path]:
    """打包 GracyBot 目录（排除 venv、__pycache__、node_modules）"""
    import tarfile
    import time

    excludes = {
        "__pycache__", ".git", "node_modules", ".venv", "venv",
        ".env", "env", ".idea", ".vscode", "__MACOSX",
    }
    ext = ".tar.gz" if sys.platform != "win32" else ".zip"
    name = f"gracybot_backup_{int(time.time())}{ext}"
    dest = output / name

    if sys.platform == "win32":
        # zip
        shutil.make_archive(
            str(output / f"gracybot_backup_{int(time.time())}"),
            "zip",
            root_dir=root,
            base_dir=".",
            logger=None,
        )
        # shutil.make_archive 加后缀
        for f in output.iterdir():
            if f.name.startswith("gracybot_backup_") and f.suffix == ".zip":
                dest = f
                break
    else:
        with tarfile.open(dest, "w:gz") as tar:
            for f in root.rglob("*"):
                if any(p.name in excludes for p in f.relative_to(root).parents)\
                        or f.name in excludes:
                    continue
                if f.is_file():
                    tar.add(f, arcname=f.relative_to(root))
    return dest if dest.exists() else None
