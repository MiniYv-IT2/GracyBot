"""小禹插件 — 核心控制中枢
功能：系统时间查询 | 复读机 | 主人/机器人QQ变更 | 黑名单管理（持久化，重启有效）| 热重载开关
热重载验证通过 ✅
"""

import os
import re
import json
import time
import threading
from datetime import datetime
from typing import Tuple, List, Optional

from graci import get_current_master_id, get_logger, gracy_send_msg, gracy_call_api, GracyImage, GracyText
from .core.draw import XiaoyuHelpDrawer
import asyncio

logger = get_logger("Xiaoyu")

# 帮助图绘制器（模块级单例）
_xiaoyu_drawer = None

def _get_drawer():
    global _xiaoyu_drawer
    if _xiaoyu_drawer is None:
        _xiaoyu_drawer = XiaoyuHelpDrawer()
    return _xiaoyu_drawer

# 缓存图片路径（固定文件名，每次新生成自动替换上一张）
XIAOYU_HELP_IMG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "temp_xiaoyu_help.png")

# ═══════════════ 黑名单路径常量 ═══════════════
BLOCKLIST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "blocklist")
BLOCKLIST_CONFIG = os.path.join(BLOCKLIST_DIR, "config.json")
BLOCKLIST_CACHE = os.path.join(BLOCKLIST_DIR, "cache.json")

# 热重载标记文件（gracybot 根目录）
HOTRELOAD_FLAG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "hotreload.json"
)


# ═══════════════ 黑名单核心逻辑 ═══════════════
def _ensure_blocklist_dir():
    os.makedirs(BLOCKLIST_DIR, exist_ok=True)


def _load_blocklist() -> dict:
    """加载黑名单配置，不存在则返回默认"""
    _ensure_blocklist_dir()
    if os.path.exists(BLOCKLIST_CONFIG):
        try:
            with open(BLOCKLIST_CONFIG, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    default = {"enabled": False, "users": []}
    _save_blocklist(default)
    return default


def _save_blocklist(config: dict):
    """保存黑名单配置 + 同步更新缓存"""
    _ensure_blocklist_dir()
    with open(BLOCKLIST_CONFIG, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    # 同步缓存：仅存用户集合，加速查询
    cache = {"enabled": config["enabled"], "users_set": list(set(config.get("users", [])))}
    with open(BLOCKLIST_CACHE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)


def _load_blocklist_cache() -> dict:
    """优先读缓存，不存在则回退到配置文件"""
    _ensure_blocklist_dir()
    if os.path.exists(BLOCKLIST_CACHE):
        try:
            with open(BLOCKLIST_CACHE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    # 回退：从配置重建缓存
    config = _load_blocklist()
    return {"enabled": config["enabled"], "users_set": config.get("users", [])}


def is_user_blocked(user_id: str) -> bool:
    """外部调用：检查用户是否在黑名单中（handler.py 预检用）"""
    cache = _load_blocklist_cache()
    if not cache.get("enabled", False):
        return False
    return str(user_id) in [str(u) for u in cache.get("users_set", [])]


def _validate_qq(qq: str) -> Tuple[bool, str]:
    """校验QQ号：5-11 位纯数字"""
    qq = qq.strip()
    if not qq.isdigit():
        return False, f"「{qq}」不是纯数字，请输入正确QQ号"
    if len(qq) < 5:
        return False, f"「{qq}」长度不足（{len(qq)}位），QQ号至少5位"
    if len(qq) > 11:
        return False, f"「{qq}」长度超出（{len(qq)}位），QQ号最多11位"
    return True, ""


def _update_config_json(key: str, value: str) -> bool:
    """使用框架配置管理器更新配置"""
    try:
        from graci import plugin_manager
        plugin_manager.set_plugin_config("Xiaoyu_plugin", key, value)
        return True
    except Exception as e:
        logger.error(f"更新配置失败: {str(e)}")
        return False


# ═══════════════ 主处理函数 ═══════════════
async def handle_xiaoyu(plugin_manager, gracy_send_msg, data, sender_id, chat_type, permission, log_func):
    """小禹插件入口 — 7参数标准签名"""
    raw_msg = data.get("text", "").strip() if isinstance(data, dict) else str(data)
    target_id = str(data.get("raw_data", {}).get("user_id" if chat_type == "private" else "group_id", sender_id))

    async def _reply(text: str):
        """统一回复：通过 GracyAdapter 适配层发送消息"""
        if text:
            await gracy_send_msg(target_id, GracyText(text=text), chat_type=chat_type)

    # ── 黑名单拦截 ──
    if is_user_blocked(sender_id):
        logger.debug(f"黑名单拦截用户 {sender_id}")
        return

    # ── 时间查询（所有人可用）──
    time_aliases = ["/查看时间", "/几点了", "/时间", "/时间查询", "/time"]
    if any(raw_msg.strip() == alias for alias in time_aliases):
        await _reply(_cmd_time(sender_id))
        return

    # ── 复读机（所有人可用）──
    if raw_msg.startswith("/复读 "):
        content = raw_msg[len("/复读 "):].strip()
        if content:
            await _reply(content)
        return

    # ── 赞我（所有人可用，自动给自己点10个赞）──
    if raw_msg.strip() == "/赞我":
        await _reply(await _cmd_like_me(sender_id))
        return

    # ── 小禹帮助（所有人可用，无斜杠）──
    if raw_msg.strip() == "小禹帮助":
        await _cmd_xiaoyu_help(target_id, chat_type, sender_id)
        return

    # ── 以下命令仅主人可用 ──
    if str(sender_id) != str(get_current_master_id()):
        await _reply("⚠️ 权限不足，仅主人可执行此操作")
        return

    # ── 更改主人QQ ──
    if raw_msg.startswith("/更改主人"):
        await _reply(_cmd_change_master(raw_msg, sender_id))
        return

    # ── 更改机器人QQ ──
    if raw_msg.startswith("/更改机器人"):
        await _reply(_cmd_change_robot(raw_msg, sender_id))
        return

    # ── 互换主人/机器人QQ ──
    if raw_msg.startswith("/互换主人"):
        await _reply(_cmd_swap_identity(raw_msg, sender_id))
        return

    # ── 黑名单管理 ──
    if raw_msg.startswith("/黑名单"):
        await _reply(_cmd_blacklist(raw_msg, sender_id))
        return

    # ── 热重载开关 ──
    if raw_msg.startswith("/热重载"):
        await _reply(_cmd_hotreload(raw_msg, sender_id))
        return

    # ── 安装插件依赖 ──
    if raw_msg.startswith("/安装依赖"):
        await _reply(await _cmd_install_deps(raw_msg, sender_id))
        return

    # ── 点赞（仅主人）──
    if raw_msg.startswith("/点赞"):
        await _reply(await _cmd_like(raw_msg, sender_id))
        return

    # ── 戳一戳（仅主人）──
    if raw_msg.startswith("/戳一戳"):
        await _reply(await _cmd_poke(raw_msg, sender_id))
        return


# ═══════════════ 命令实现 ═══════════════
def _cmd_time(sender_id) -> str:
    """显示当前系统时间"""
    now = datetime.now()
    weekday_map = ["一", "二", "三", "四", "五", "六", "日"]
    weekday = weekday_map[now.weekday()]
    lines = [
        "🕐 **系统时间**",
        f"📅 日期：{now.strftime('%Y年%m月%d日')} 星期{weekday}",
        f"⏰ 时间：{now.strftime('%H:%M:%S')}",
        f"🌏 时区：北京时间 (UTC+8)",
    ]
    logger.info(f"用户 {_safe_id(sender_id)} 查询系统时间")
    return "\n".join(lines)


def _cmd_change_master(raw_msg, sender_id) -> str:
    """更改主人QQ"""
    parts = raw_msg.split(maxsplit=1)
    if len(parts) < 2:
        return "⚠️ 用法：/更改主人 <新主人QQ号>"
    new_master = parts[1].strip()
    valid, err = _validate_qq(new_master)
    if not valid:
        return f"⚠️ {err}"

    if not _update_config_json("master_id", new_master):
        return "❌ 配置文件更新失败，请检查权限"

    logger.info(f"主人 {_safe_id(sender_id)} 将主人QQ变更为 {new_master}")
    return f"✅ 主人QQ已变更为 {new_master}（重启后完全生效）"


def _cmd_change_robot(raw_msg, sender_id) -> str:
    """更改机器人QQ"""
    parts = raw_msg.split(maxsplit=1)
    if len(parts) < 2:
        return "⚠️ 用法：/更改机器人 <新机器人QQ号>"
    new_robot = parts[1].strip()
    valid, err = _validate_qq(new_robot)
    if not valid:
        return f"⚠️ {err}"

    if not _update_config_json("robot_id", new_robot):
        return "❌ 配置文件更新失败，请检查权限"

    logger.info(f"主人 {_safe_id(sender_id)} 将机器人QQ变更为 {new_robot}")
    return f"✅ 机器人QQ已变更为 {new_robot}（重启后完全生效）"


def _cmd_swap_identity(raw_msg, sender_id) -> str:
    """互换主人QQ和机器人QQ（防填反）"""
    try:
        from graci import config_manager
        from graci import plugin_manager
        old_master = str(config_manager.get("master_id", ""))
        old_robot = str(config_manager.get("robot_id", ""))
        if not old_master or not old_robot:
            return "⚠️ 配置中缺少 master_id 或 robot_id，无法互换"

        # 互换
        plugin_manager.set_plugin_config("Xiaoyu_plugin", "master_id", old_robot)
        plugin_manager.set_plugin_config("Xiaoyu_plugin", "robot_id", old_master)
    except Exception as e:
        logger.error(f"互换身份失败: {str(e)}")
        return "❌ 配置文件读写失败，请检查权限"

    logger.info(f"主人 {_safe_id(sender_id)} 互换了主人QQ和机器人QQ：{old_master} ↔ {old_robot}")
    return f"✅ 已互换！主人QQ → {old_robot}，机器人QQ → {old_master}（重启后完全生效）"


def _cmd_blacklist(raw_msg: str, sender_id: str) -> str:
    """黑名单管理：打开/关闭/添加/删除/列表"""
    parts = raw_msg.split(maxsplit=1)
    if len(parts) < 2:
        return _blacklist_usage()

    sub_cmd = parts[1].strip()
    config = _load_blocklist()

    # ── 打开 ──
    if sub_cmd == "打开":
        config["enabled"] = True
        _save_blocklist(config)
        logger.info(f"主人 {_safe_id(sender_id)} 打开了黑名单模式；当前黑名单人数：{len(config['users'])}")
        return "🛡️ 黑名单模式已**打开**，被添加的用户将无法获得任何回复"

    # ── 关闭 ──
    if sub_cmd == "关闭":
        config["enabled"] = False
        _save_blocklist(config)
        logger.info(f"主人 {_safe_id(sender_id)} 关闭了黑名单模式")
        return "🔓 黑名单模式已**关闭**，所有用户恢复正常回复"

    # ── 列表 ──
    if sub_cmd in ("列表", "list"):
        users = config.get("users", [])
        enabled = config.get("enabled", False)
        status = "🟢 已启用" if enabled else "⚪ 已关闭"
        if not users:
            return f"📋 黑名单 {status}\n当前无黑名单用户"
        user_list = "\n".join(f"  • {u}" for u in users)
        logger.info(f"主人 {_safe_id(sender_id)} 查看黑名单列表")
        return f"📋 黑名单 {status}（共 {len(users)} 人）\n{user_list}"

    # ── 添加 ──
    if sub_cmd.startswith("添加"):
        qq_str = sub_cmd[2:].strip()  # 去掉 "添加"
        return _blacklist_add(config, qq_str, sender_id)

    # ── 删除 ──
    if sub_cmd.startswith("删除") or sub_cmd.startswith("移除"):
        qq_str = sub_cmd[2:].strip()  # 去掉 "删除" 或 "移除"
        return _blacklist_remove(config, qq_str, sender_id)

    return _blacklist_usage()


def _blacklist_add(config: dict, qq_str: str, sender_id: str) -> str:
    """批量添加QQ号到黑名单"""
    if not qq_str:
        return "⚠️ 用法：/黑名单 添加 <QQ号1> <QQ号2> ..."

    qq_list = qq_str.split()
    success = []
    failed = []
    existing = set(config.get("users", []))

    for qq in qq_list:
        valid, err = _validate_qq(qq)
        if not valid:
            failed.append(f"「{qq}」{err}")
            continue
        if qq in existing:
            failed.append(f"「{qq}」已在黑名单中")
            continue
        existing.add(qq)
        success.append(qq)

    if success:
        config["users"] = list(existing)
        _save_blocklist(config)
        logger.info(f"主人 {_safe_id(sender_id)} 添加 {len(success)} 个QQ到黑名单：{success}")

    result = []
    if success:
        result.append(f"✅ 已添加 {len(success)} 个QQ到黑名单：{', '.join(success)}")
    if failed:
        result.append(f"⚠️ {len(failed)} 个失败：\n" + "\n".join(f"  {f}" for f in failed))
    if not result:
        result.append("⚠️ 未添加任何用户")
    return "\n".join(result)


def _blacklist_remove(config: dict, qq_str: str, sender_id: str) -> str:
    """从黑名单移除QQ号"""
    if not qq_str:
        return "⚠️ 用法：/黑名单 删除 <QQ号>"

    qq = qq_str.split()[0]  # 删除只取第一个
    users = config.get("users", [])

    if qq not in users:
        return f"⚠️ 「{qq}」不在黑名单中"

    users.remove(qq)
    config["users"] = users
    _save_blocklist(config)
    logger.info(f"主人 {_safe_id(sender_id)} 从黑名单移除了 {qq}")
    return f"✅ 已将「{qq}」从黑名单移除"


def _blacklist_usage() -> str:
    return (
        "📋 **黑名单管理**（仅主人可用）\n"
        "  /黑名单 打开          — 启用黑名单模式\n"
        "  /黑名单 关闭          — 关闭黑名单模式\n"
        "  /黑名单 添加 <QQ号>   — 添加用户（支持多个空格分隔）\n"
        "  /黑名单 删除 <QQ号>   — 移除用户\n"
        "  /黑名单 列表          — 查看黑名单"
    )


def _safe_id(user_id) -> str:
    """脱敏显示QQ号"""
    s = str(user_id)
    return f"{s[:3]}****{s[-3:]}" if len(s) >= 6 else "***"



async def _cmd_like_me(sender_id: str) -> str:
    """赞我：给自己点10个赞（所有人可用）"""
    try:
        await gracy_call_api("send_like", {"user_id": int(sender_id), "times": 10})
        logger.info(f"用户 {_safe_id(sender_id)} 赞了自己 10 次")
        return f"✅ 已给你点了 10 个赞！"
    except Exception as e:
        logger.error(f"赞我失败: {e}", exc_info=True)
        return f"❌ 点赞失败：{e}"


async def _cmd_like(raw_msg: str, sender_id: str) -> str:
    """点赞：/点赞 <QQ号> [次数]（默认10次）
    通过 NapCat 的 send_like API 实现
    """
    parts = raw_msg.split(maxsplit=2)
    if len(parts) < 2:
        return "⚠️ 用法：/点赞 <QQ号> [次数]\n示例：/点赞 123456789 10"

    qq = parts[1].strip()
    valid, err = _validate_qq(qq)
    if not valid:
        return f"⚠️ {err}"

    times = 10
    if len(parts) >= 3:
        try:
            times = int(parts[2].strip())
            if times < 1:
                return "⚠️ 点赞次数不能小于1"
            if times > 20:
                return "⚠️ 单次点赞次数不能超过20，请注意频率限制"
        except ValueError:
            return "⚠️ 次数必须为数字"

    try:
        result = await gracy_call_api("send_like", {"user_id": int(qq), "times": times})
        # send_like 是空返回 API（retcode=0 但无 data 字段），返回 None 也是成功
        logger.info(f"主人 {_safe_id(sender_id)} 给 {qq} 点了 {times} 个赞")
        return f"✅ 已给 {qq} 发送 {times} 个赞！"
    except Exception as e:
        logger.error(f"点赞失败: {e}", exc_info=True)
        return f"❌ 点赞失败：{e}"


async def _cmd_poke(raw_msg: str, sender_id: str) -> str:
    """戳一戳：/戳一戳 <QQ号>
    通过 NapCat 的 friend_poke API 实现
    """
    parts = raw_msg.split(maxsplit=1)
    if len(parts) < 2:
        return "⚠️ 用法：/戳一戳 <QQ号>\n示例：/戳一戳 123456789"

    qq = parts[1].strip()
    valid, err = _validate_qq(qq)
    if not valid:
        return f"⚠️ {err}"

    try:
        result = await gracy_call_api("friend_poke", {"user_id": int(qq)})
        if result is not None and result.get("status") == "ok":
            logger.info(f"主人 {_safe_id(sender_id)} 戳了戳 {qq}")
            return f"✅ 已戳了戳 {qq}！"
        else:
            # friend_poke 可能在某些版本返回不同，忽略具体响应
            logger.info(f"主人 {_safe_id(sender_id)} 戳了戳 {qq}，响应: {result}")
            return f"✅ 已尝试戳一戳 {qq}"
    except Exception as e:
        logger.error(f"戳一戳失败: {e}", exc_info=True)
        return f"❌ 戳一戳失败：{e}"


def _cmd_hotreload(raw_msg: str, sender_id: str) -> str:
    """热重载开关：/热重载 开启 或 /热重载 关闭（仅主人，写入标记后自动重启）"""
    parts = raw_msg.split(maxsplit=1)
    if len(parts) < 2:
        return "⚠️ 用法：/热重载 开启 或 /热重载 关闭"

    sub = parts[1].strip()
    if sub == "开启":
        _write_hotreload_flag(True)
        logger.info(f"主人 {_safe_id(sender_id)} 开启了热重载，即将重启")
        _restart_bot()
        return "🔄 热重载已**开启**，机器人将在 2 秒后自动重启生效"

    elif sub == "关闭":
        _write_hotreload_flag(False)
        logger.info(f"主人 {_safe_id(sender_id)} 关闭了热重载，即将重启")
        _restart_bot()
        return "⚪ 热重载已**关闭**，机器人将在 2 秒后自动重启生效（此后修改代码需手动重启）"

    return "⚠️ 未知参数，用法：/热重载 开启 或 /热重载 关闭"


def _restart_bot():
    """先启动新进程再退出当前进程，确保无论热重载开关状态都能自动重启"""
    import subprocess
    import platform as _platform
    def _do_restart():
        time.sleep(2)
        try:
            if _platform.system() == "Windows":
                subprocess.Popen([sys.executable] + sys.argv, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                # Linux/Mac 用 os.execv 原子替换当前进程，避免端口冲突
                os.execv(sys.executable, [sys.executable] + sys.argv)
        except Exception as e:
            logger.error(f"启动新进程失败: {e}")
        sys.exit(0)
    threading.Thread(target=_do_restart, daemon=True).start()


def _write_hotreload_flag(enabled: bool):
    """写入热重载标记文件"""
    with open(HOTRELOAD_FLAG, "w", encoding="utf-8") as f:
        json.dump({"enabled": enabled}, f, ensure_ascii=False, indent=2)


async def _cmd_xiaoyu_help(target_id, chat_type, sender_id):
    """小禹帮助：生成帮助图片并发送（缓存覆盖）"""
    try:
        drawer = _get_drawer()
        img_bytes = drawer.draw()
        # 写入缓存（固定文件名，每次覆盖替换上一张）
        os.makedirs(os.path.dirname(XIAOYU_HELP_IMG), exist_ok=True)
        with open(XIAOYU_HELP_IMG, "wb") as f:
            f.write(img_bytes)
        # 发送帮助图片（通过 GracyAdapter 适配层）
        await gracy_send_msg(target_id, GracyImage(file_path=XIAOYU_HELP_IMG), chat_type=chat_type)
        logger.info(f"用户 {_safe_id(sender_id)} 查看了小禹帮助")
    except Exception as e:
        logger.error(f"生成帮助图片失败: {str(e)}")
        await gracy_send_msg(target_id, GracyText(text="⚠️ 生成帮助图片失败，请联系管理员"), chat_type=chat_type)


async def _cmd_install_deps(raw_msg: str, sender_id: str) -> str:
    """安装指定插件的依赖：/安装依赖 <插件目录名>（仅主人）"""
    import sys as _sys
    import asyncio
    parts = raw_msg.split(maxsplit=1)
    if len(parts) < 2:
        return "⚠️ 用法：/安装依赖 <插件目录名>\n示例：/安装依赖 Easysearch"

    plugin_dirname = parts[1].strip()
    plugins_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    plugin_dir = os.path.join(plugins_root, plugin_dirname)
    req_file = os.path.join(plugin_dir, "requirements.txt")

    if not os.path.isdir(plugin_dir):
        return f"⚠️ 插件目录「{plugin_dirname}」不存在，请确认已解压到 plugins/ 下"

    if not os.path.exists(req_file):
        return f"⚠️ 插件「{plugin_dirname}」没有 requirements.txt，无需安装依赖"

    # 读取依赖列表
    try:
        with open(req_file, "r", encoding="utf-8") as f:
            deps = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    except Exception as e:
        logger.error(f"读取 {req_file} 失败: {e}")
        return f"❌ 读取 requirements.txt 失败: {e}"

    if not deps:
        return f"⚠️ 插件「{plugin_dirname}」的 requirements.txt 为空"

    logger.info(f"主人 {_safe_id(sender_id)} 正在为插件 {plugin_dirname} 安装依赖：{deps}")

    # 执行 pip install（异步）
    try:
        proc = await asyncio.create_subprocess_exec(
            _sys.executable, "-m", "pip", "install", "-r", req_file,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
        if proc.returncode == 0:
            logger.info(f"插件 {plugin_dirname} 依赖安装成功")
            return f"✅ 插件「{plugin_dirname}」依赖安装成功！\n已安装：{', '.join(deps)}"
        else:
            err_msg = stderr.decode("utf-8", errors="ignore").strip().split("\n")[-1] if stderr else "未知错误"
            logger.error(f"插件 {plugin_dirname} 依赖安装失败: {err_msg}")
            return f"❌ 依赖安装失败：{err_msg}"
    except asyncio.TimeoutError:
        logger.error(f"插件 {plugin_dirname} 依赖安装超时")
        return "❌ 安装超时（超过 120 秒），请检查网络或手动安装"
    except Exception as e:
        logger.error(f"插件 {plugin_dirname} 依赖安装异常: {e}")
        return f"❌ 安装异常: {e}"
