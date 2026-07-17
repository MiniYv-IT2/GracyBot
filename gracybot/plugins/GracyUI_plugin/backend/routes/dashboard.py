"""仪表盘 API — 系统状态 / 好友 / 群聊"""
import time
import platform
import asyncio
import psutil
from graci import Blueprint

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/api")

_BOOT_TIME = time.time()

# CPU 名称缓存（60 秒）
_cpu_name_cache: str = ""
_cpu_name_cache_time: float = 0.0
_cpu_name_lock = asyncio.Lock()


async def _async_get_cpu_name() -> str:
    """异步获取 CPU 名称，60 秒缓存"""
    global _cpu_name_cache, _cpu_name_cache_time
    now = time.time()
    if _cpu_name_cache and (now - _cpu_name_cache_time) < 60:
        return _cpu_name_cache
    async with _cpu_name_lock:
        # double-check
        if _cpu_name_cache and (now - _cpu_name_cache_time) < 60:
            return _cpu_name_cache
        name = await asyncio.to_thread(_sync_get_cpu_name, now)
        return name


def _sync_get_cpu_name(now: float) -> str:
    """同步获取 CPU 名称（在后台线程执行）"""
    global _cpu_name_cache, _cpu_name_cache_time
    name = ""
    try:
        if platform.system() == "Windows":
            import subprocess
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-CimInstance Win32_Processor | Select-Object -ExpandProperty Name"],
                capture_output=True, text=True, timeout=5)
            if r.returncode == 0:
                name = r.stdout.strip().split("\n")[0].strip()
        elif platform.system() == "Linux":
            try:
                with open("/proc/cpuinfo", "r") as f:
                    for line in f:
                        if line.startswith("model name"):
                            name = line.split(":", 1)[1].strip()
                            break
            except Exception:
                pass
        elif platform.system() == "Darwin":
            import subprocess
            r = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"],
                               capture_output=True, text=True, timeout=5)
            if r.returncode == 0:
                name = r.stdout.strip()
    except Exception:
        pass
    _cpu_name_cache = name
    _cpu_name_cache_time = now
    return name


async def _async_get_all_disks_usage():
    """异步获取所有磁盘的合计用量，返回 (used_gb, total_gb)"""
    return await asyncio.to_thread(_sync_get_all_disks_usage)


def _sync_get_all_disks_usage():
    """同步获取磁盘用量（在后台线程执行）"""
    total_used = 0
    total_total = 0
    try:
        for part in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(part.mountpoint)
                total_used += usage.used
                total_total += usage.total
            except (PermissionError, OSError):
                continue
    except Exception:
        pass
    if total_total == 0:
        try:
            u = psutil.disk_usage("/")
            total_used = u.used
            total_total = u.total
        except Exception:
            pass
    return round(total_used / (1024**3), 1), round(total_total / (1024**3), 1)


def _get_uptime() -> str:
    """人类可读的运行时间"""
    secs = int(time.time() - _BOOT_TIME)
    days, r = divmod(secs, 86400)
    hours, r = divmod(r, 3600)
    mins, _ = divmod(r, 60)
    parts = []
    if days:
        parts.append(f"{days}天")
    if hours:
        parts.append(f"{hours}小时")
    parts.append(f"{mins}分")
    return " ".join(parts)


@dashboard_bp.route("/dashboard/system")
async def api_system():
    """系统资源：CPU / 内存 / 磁盘 / 运行时间 / 操作系统"""
    mem = psutil.virtual_memory()

    # 异步执行阻塞操作
    cpu_percent_task = asyncio.to_thread(psutil.cpu_percent, interval=0.3)
    cpu_name_task = _async_get_cpu_name()
    disk_task = _async_get_all_disks_usage()

    cpu_pct, cpu_name, (disk_used_gb, disk_total_gb) = await asyncio.gather(
        cpu_percent_task, cpu_name_task, disk_task
    )

    disk_pct = round((disk_used_gb / disk_total_gb * 100) if disk_total_gb > 0 else 0, 1)
    return {
        "cpu_percent": round(cpu_pct, 1),
        "cpu_name": cpu_name,
        "memory_percent": round(mem.percent, 1),
        "memory_used_gb": round(mem.used / (1024**3), 1),
        "memory_total_gb": round(mem.total / (1024**3), 1),
        "disk_percent": disk_pct,
        "disk_used_gb": disk_used_gb,
        "disk_total_gb": disk_total_gb,
        "uptime": _get_uptime(),
        "os": platform.system(),
        "hostname": platform.node(),
    }


@dashboard_bp.route("/dashboard/stats")
async def api_stats():
    """仪表盘卡片数据：好友数 / 群聊数"""
    friend_count = 0
    group_count = 0
    try:
        from graci import gracy_get_platform_info
        info = await gracy_get_platform_info()
        friend_count = info.get("friend_count", 0) or 0
        group_count = info.get("group_count", 0) or 0
    except Exception:
        pass

    try:
        from graci import BOT_VERSION
    except Exception:
        BOT_VERSION = os.environ.get("GRACY_BOT_VERSION", "unknown")

    return {
        "friend_count": friend_count,
        "group_count": group_count,
        "system_version": BOT_VERSION,
    }
