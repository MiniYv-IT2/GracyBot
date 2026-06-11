"""系统管理 — 自启/卸载/备份/进程控制"""
import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from .utils import find_project_root, get_platform_label, has_systemd, make_archive


def setup_autostart(root: Path, enable: bool = True) -> bool:
    """设置开机自启

    策略:
      - Windows: schtasks（无需管理员，当前用户级）
      - Linux + systemd → systemctl --user
      - Linux + Termux → ~/.bashrc
      - macOS → launchctl plist
      - 其他 → ~/.bashrc
    """
    plat = get_platform_label()
    python = sys.executable
    script = str(root / "bot.py")

    if enable:
        return _enable_autostart(plat, python, script, root)
    else:
        return _disable_autostart(plat, python, script, root)


def _enable_autostart(plat: str, python: str, script: str, root: Path) -> bool:
    try:
        if plat == "windows":
            name = "GracyBot"
            username = os.environ.get("USERNAME", "")
            # 方式1：启动文件夹（无需管理员，推荐）
            startup = Path(os.environ.get(
                "APPDATA", ""
            )) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
            if startup.exists():
                bat = startup / f"{name}.bat"
                # Windows CMD 读取 .bat 使用系统默认编码（中文环境为 GBK）
                # cd /d 确保切到项目目录，否则 CWD 为 C:\Windows\System32
                bat.write_text(
                    f'@cd /d "{root}"\n@start "" "{python}" "{script}"\n',
                    encoding="gbk"
                )
                print("  ✅ 已添加开机自启（启动文件夹）")
                return True
            # 方式2：schtasks（需管理员，降级）
            task = f'''schtasks /create /tn "{name}" /tr "\"{python}\" \"{script}\"" /sc onlogon /f'''
            subprocess.check_call(task, shell=True, timeout=10)
            print("  ✅ 已添加开机自启（Windows 任务计划）")
            return True

        elif plat == "linux" and has_systemd():
            unit = f"""[Unit]
Description=GracyBot
After=network.target

[Service]
Type=simple
ExecStart={python} {script}
WorkingDirectory={root}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
"""
            unit_path = Path.home() / ".config" / "systemd" / "user" / "gracybot.service"
            unit_path.parent.mkdir(parents=True, exist_ok=True)
            unit_path.write_text(unit, encoding="utf-8")
            subprocess.check_call(["systemctl", "--user", "daemon-reload"], timeout=10)
            subprocess.check_call(["systemctl", "--user", "enable", "gracybot"], timeout=10)
            print("  ✅ 已添加 systemd --user 自启")
            return True

        elif plat == "termux":
            bashrc = Path.home() / ".bashrc"
            line = f"(cd {root} && {python} {script} &)"
            if line not in bashrc.read_text(encoding="utf-8"):
                with open(bashrc, "a", encoding="utf-8") as f:
                    f.write(f"\n# GracyBot autostart\n{line}\n")
            print("  ✅ 已添加 Termux 自启（~/.bashrc）")
            return True

        elif plat == "macos":
            label = "com.gracybot.runner"
            plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>{label}</string>
<key>ProgramArguments</key><array><string>{python}</string><string>{script}</string></array>
<key>WorkingDirectory</key><string>{root}</string>
<key>RunAtLoad</key><true/>
<key>KeepAlive</key><true/>
<key>StandardOutPath</key><string>{root}/logs/stdout.log</string>
<key>StandardErrorPath</key><string>{root}/logs/stderr.log</string>
</dict></plist>"""
            plist_path = Path.home() / "Library" / "LaunchAgents" / f"{label}.plist"
            plist_path.parent.mkdir(parents=True, exist_ok=True)
            plist_path.write_text(plist, encoding="utf-8")
            subprocess.check_call(["launchctl", "load", str(plist_path)], timeout=10)
            print("  ✅ 已添加 macOS LaunchAgent 自启")
            return True

        else:
            # 降级 ~/.bashrc / ~/.zshrc
            for rc in [Path.home() / ".bashrc", Path.home() / ".zshrc"]:
                if rc.exists():
                    text = rc.read_text(encoding="utf-8")
                    line = f"(cd {root} && {python} {script} &)"
                    if line not in text:
                        with open(rc, "a", encoding="utf-8") as f:
                            f.write(f"\n# GracyBot autostart\n{line}\n")
                    break
            print(f"  ✅ 已添加开机自启（~/.bashrc）")
            return True

    except Exception as e:
        print(f"  ⚠️ 设置自启失败: {e}")
        print("  请手动添加开机自启命令:", f"{python} {script}")
        return False


def _disable_autostart(plat: str, python: str, script: str, root: Path) -> bool:
    try:
        if plat == "windows":
            # 删启动文件夹脚本
            startup = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "GracyBot.bat"
            if startup.exists():
                startup.unlink()
            # 删 schtasks（可能不存在，容错）
            try:
                subprocess.check_call("schtasks /delete /tn GracyBot /f", shell=True, timeout=10)
            except Exception:
                pass
            print("  ✅ 已移除开机自启")
            return True
        elif plat == "linux" and has_systemd():
            subprocess.check_call(["systemctl", "--user", "disable", "gracybot"], timeout=10)
            unit = Path.home() / ".config" / "systemd" / "user" / "gracybot.service"
            if unit.exists():
                unit.unlink()
            subprocess.check_call(["systemctl", "--user", "daemon-reload"], timeout=10)
            print("  ✅ 已移除 systemd 自启")
            return True
        elif plat == "macos":
            label = "com.gracybot.runner"
            plist_path = Path.home() / "Library" / "LaunchAgents" / f"{label}.plist"
            subprocess.check_call(["launchctl", "unload", str(plist_path)], timeout=10)
            if plist_path.exists():
                plist_path.unlink()
            print("  ✅ 已移除 macOS 自启")
            return True
        else:
            print("  ⚠️ 请手动删除 ~/.bashrc 中的 GracyBot 启动行")
            return False
    except Exception as e:
        print(f"  ⚠️ 移除自启失败: {e}")
        return False


def uninstall_bot(root: Path, backup_first: bool = True):
    """卸载 GracyBot

    步骤:
      1. 可选备份
      2. 移除自启
      3. 删除目录
    """
    if backup_first:
        print("  📦 先进行备份...")
        bak_dir = Path.cwd() / "gracybot_backup"
        bak_dir.mkdir(exist_ok=True)
        archive = make_archive(root, bak_dir)
        if archive:
            print(f"  ✅ 备份完成: {archive}")
    _disable_autostart(get_platform_label(), sys.executable, str(root / "bot.py"), root)
    print(f"  🗑️  删除 {root} ...")
    shutil.rmtree(root, ignore_errors=True)
    print("  ✅ GracyBot 已卸载")


def backup_bot(root: Path) -> Optional[Path]:
    """备份机器人（数据 + 代码）"""
    bak_dir = Path.cwd() / "gracybot_backup"
    bak_dir.mkdir(exist_ok=True)
    archive = make_archive(root, bak_dir)
    if archive:
        print(f"  ✅ 备份完成: {archive}")
    else:
        print("  ❌ 备份失败")
    return archive


def run_bot_process(root: Path, debug: bool = False, no_webui: bool = False):
    """启动机器人（子进程）—— 自动检测 venv / 系统 Python"""
    # 检测项目根目录是否有虚拟环境
    venv_python = None
    for venv_dir in ["venv", ".venv", "env", ".env"]:
        candidate = root / venv_dir
        if sys.platform == "win32":
            py = candidate / "Scripts" / "python.exe"
        else:
            py = candidate / "bin" / "python"
        if py.exists():
            venv_python = str(py)
            break

    if venv_python:
        python = venv_python
        print(f"  📁 使用虚拟环境: {os.path.basename(os.path.dirname(os.path.dirname(venv_python)))}")
    else:
        python = sys.executable

    # 检查核心依赖（有 requirements.txt 就一次性装）
    req_file = root / "requirements.txt"
    if req_file.exists():
        r = subprocess.run(
            [python, "-c", "import typer, quart, hypercorn, requests, websockets, psutil"],
            capture_output=True, timeout=5
        )
        if r.returncode != 0:
            print(f"  📦 安装核心依赖 ...")
            from .utils import pip_install
            if not pip_install([], req_file=str(req_file), python=python):
                print(f"  ❌ 核心依赖安装失败")
                sys.exit(1)

    script = str(root / "bot.py")
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    if debug:
        env["GRACY_DEBUG"] = "1"
    elif "GRACY_DEBUG" in env:
        del env["GRACY_DEBUG"]
    if no_webui:
        env["GRACY_NO_WEBUI"] = "1"
    elif "GRACY_NO_WEBUI" in env:
        del env["GRACY_NO_WEBUI"]

    print(f"  🚀 启动 GracyBot ...")
    try:
        subprocess.check_call([python, script], env=env, cwd=str(root))
    except KeyboardInterrupt:
        print("\n  🛑 已停止")
    except Exception as e:
        print(f"  ❌ 启动失败: {e}")
        sys.exit(1)


def stop_bot_process():
    """停止运行中的 GracyBot（通过进程名 + 命令行匹配）"""
    plat = get_platform_label()

    try:
        if plat == "windows":
            # 按端口查进程杀掉（hypercorn / WS 端口）
            killed = False
            for port_try in [3001, 3002, 5090]:
                r = subprocess.run(
                    f'netstat -ano | findstr ":{port_try} "',
                    capture_output=True, text=True, shell=True, timeout=5
                )
                for line in r.stdout.strip().split("\n"):
                    parts = line.strip().split()
                    if len(parts) >= 5 and parts[1].endswith(f":{port_try}"):
                        pid = parts[-1]
                        if pid.isdigit():
                            subprocess.run(f'taskkill /f /pid {pid} 2>nul', shell=True, timeout=5)
                            killed = True
            if killed:
                print("  ✅ 已停止")
            else:
                print("  ℹ️  没有找到运行中的 GracyBot")
        else:
            subprocess.check_call(
                ["pkill", "-f", "python.*bot.py"],
                timeout=5,
            )
            print("  ✅ 已停止")
    except Exception as e:
        print(f"  ⚠️ 停止失败: {e}")
