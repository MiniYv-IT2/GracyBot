import subprocess
import platform
import time
import logging
import asyncio
from typing import Dict
import json
import os
import sys
import psutil
from concurrent.futures import ThreadPoolExecutor, as_completed

# 添加插件路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.config import (
    ROBOT_START_TIME,
    BOT_VERSION,
    MASTER_ID,
    LOG_ENCODING,
    get_current_robot_id,
)
from core.gracy_adapter.send import gracy_send_msg
from core.gracy_adapter.message import GracyImage, GracyText
from core.security import sanitize_log
logger = logging.getLogger("Gracy.SysInfo")

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "cache")

def _cache_get(key):
    p = os.path.join(CACHE_DIR, key + ".json")
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def _cache_set(key, value):
    os.makedirs(CACHE_DIR, exist_ok=True)
    p = os.path.join(CACHE_DIR, key + ".json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False)

try:
    from .core.draw import SysInfoDrawer
    logger.info("绘图模块加载成功")
except ImportError as e:
    logger.error(f"绘图模块导入失败: {e}")
    SysInfoDrawer = None

def _get_cpu_usage() -> float:
    try:
        usage = psutil.cpu_percent(interval=0.1)
        if usage < 0:
            return 0.0
        elif usage > 100:
            return 100.0
        return round(usage, 1)
    except Exception:
        return 0.0

async def _get_gpu_info() -> Dict:
    cached = _cache_get("gpu_info")
    if cached:
        return cached
    gpu_info = {"model": "未检测到GPU", "memory": "N/A"}
    try:
        system = platform.system()
        if system == "Linux":
            try:
                proc = await asyncio.create_subprocess_exec(
                    "lspci",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                try:
                    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=3)
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()
                    raise
                if proc.returncode == 0:
                    found = []
                    stdout_text = stdout.decode('utf-8', errors='replace')
                    for line in stdout_text.split('\n'):
                        if 'VGA' in line or '3D' in line or 'Display' in line:
                            device_info = line.split(':')[-1].strip()
                            device_info = device_info.replace('Corporation', '').replace('Inc.', '').replace('Ltd.', '').strip()
                            import re
                            device_info = re.sub(r'\s*\(rev\s+[0-9a-f]+\)', '', device_info).strip()
                            if device_info.startswith('Device '):
                                parts = device_info.split()
                                device_id = parts[1] if len(parts) > 1 else parts[0]
                                device_id = device_id.split('(rev')[0].strip()
                                found.append(f"GPU ({device_id})")
                            elif device_info:
                                device_info = device_info.split('(rev')[0].strip()
                                found.append(device_info)
                    if found:
                        gpu_info["model"] = "  ".join(found)
            except:
                pass
            if gpu_info["model"] == "未检测到GPU":
                try:
                    drm_dir = "/sys/class/drm"
                    if os.path.exists(drm_dir):
                        gpus = []
                        for entry in os.listdir(drm_dir):
                            uevent = os.path.join(drm_dir, entry, "device", "uevent")
                            if os.path.exists(uevent):
                                with open(uevent) as f:
                                    for line in f:
                                        if line.startswith("DRIVER="):
                                            drv = line.split("=", 1)[1].strip()
                                            if drv and drv not in ("rockchip-drm", "dummy", "vgem"):
                                                name = drv
                                                compat_path = os.path.join(drm_dir, entry, "device", "of_node", "compatible")
                                                if os.path.exists(compat_path):
                                                    try:
                                                        with open(compat_path) as cf:
                                                            raw = cf.read().strip('\x00').strip()
                                                            if raw:
                                                                name = raw.split(",")[-1] if "," in raw else raw
                                                    except:
                                                        pass
                                                gpus.append(name)
                                            break
                        if gpus:
                            seen = set()
                            unique = [g for g in gpus if not (g in seen or seen.add(g))]
                            gpu_info["model"] = "  ".join(unique)
                except:
                    pass
        elif system == "Windows":
            try:
                # wmic 在 Win11 24H2+ 已移除，改用 PowerShell Get-CimInstance
                proc = await asyncio.create_subprocess_exec(
                    "powershell", "-NoProfile", "-Command",
                    "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                try:
                    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5)
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()
                    raise
                if proc.returncode == 0:
                    # 过滤虚拟/远程显示适配器，所有真实 GPU 拼一行（双空格分隔）
                    virtual_keywords = ["virtual", "todesk", "mumu", "gameviewer", "remote",
                                       "parsec", "sunshine", "indirect", "displayonly"]
                    real_gpus = []
                    stdout_text = stdout.decode('utf-8', errors='replace')
                    for line in stdout_text.strip().split('\n'):
                        name = line.strip()
                        if not name or name.lower() == "name":
                            continue
                        if any(kw in name.lower() for kw in virtual_keywords):
                            continue
                        real_gpus.append(name)
                    if real_gpus:
                        gpu_info["model"] = "  ".join(real_gpus)
            except:
                pass
    except Exception:
        pass
    _cache_set("gpu_info", gpu_info)
    return gpu_info

async def _get_io_stats() -> Dict:
    io_stats = {"read_mb_s": "0.0MB/s", "write_mb_s": "0.0MB/s", "read_iops_str": "0 IOPS", "write_iops_str": "0 IOPS"}
    try:
        initial_io = psutil.disk_io_counters(perdisk=False)
        await asyncio.sleep(0.1)
        final_io = psutil.disk_io_counters(perdisk=False)
        
        if initial_io and final_io:
            read_bytes = final_io.read_bytes - initial_io.read_bytes
            write_bytes = final_io.write_bytes - initial_io.write_bytes
            
            read_count = final_io.read_count - initial_io.read_count
            write_count = final_io.write_count - initial_io.write_count
            
            def fmt_bytes(b):
                if b >= 1024*1024:
                    return f"{b/(1024*1024):.1f}MB/s"
                elif b >= 1024:
                    return f"{b/1024:.1f}KB/s"
                else:
                    return f"{b:.1f}B/s"
            
            io_stats["read_mb_s"] = fmt_bytes(read_bytes)
            io_stats["write_mb_s"] = fmt_bytes(write_bytes)
            io_stats["read_iops_str"] = f"{max(0, read_count)} IOPS"
            io_stats["write_iops_str"] = f"{max(0, write_count)} IOPS"
    except Exception as e:
        pass
    return io_stats

def _get_network_info() -> Dict:
    """获取网络信息（跨平台）"""
    network_info = {"type": "未知", "upload": 0, "download": 0}
    try:
        # 获取网络IO统计
        net_io = psutil.net_io_counters(pernic=True)
        
        # 检测网络类型和获取流量
        for iface, stats in net_io.items():
            # 跳过回环接口
            if iface.lower() in ['lo', 'loopback']:
                continue
            # 跳过无流量的接口
            if stats.bytes_recv == 0 and stats.bytes_sent == 0:
                continue
            
            # 取第一个有流量的接口，类型和流量同源
            if any(x in iface.lower() for x in ['eth', 'en', '以太网']):
                network_info["type"] = "以太网"
            elif any(x in iface.lower() for x in ['wlan', 'wi-fi', 'wifi', '无线']):
                network_info["type"] = "WiFi"
            else:
                network_info["type"] = "网络连接"
            
            network_info["download"] = stats.bytes_recv // (1024 * 1024)
            network_info["upload"] = stats.bytes_sent // (1024 * 1024)
            break
        
        # 遍历完都没找到有流量的非回环接口
        if network_info["type"] == "未知":
            network_info["type"] = "网络连接"
            
    except Exception as e:
        # 发生异常时设置默认值
        network_info["type"] = "网络连接"
    return network_info

async def _get_shell_terminal() -> Dict:
    """获取Shell和Terminal环境信息"""
    shell_info = {"shell": "未知", "terminal": "未知"}
    try:
        # Shell信息 - 获取bash版本
        shell_path = os.environ.get('SHELL', '')
        if shell_path and 'bash' in shell_path:
            try:
                proc = await asyncio.create_subprocess_exec(
                    "bash", "--version",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                try:
                    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=3)
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()
                    raise
                if proc.returncode == 0:
                    # 提取版本信息的第一行
                    stdout_text = stdout.decode('utf-8', errors='replace')
                    version_line = stdout_text.split('\n')[0]
                    shell_info["shell"] = version_line.replace("GNU bash，版本 ", "bash ").replace("GNU bash, version ", "bash ")
                else:
                    shell_info["shell"] = "bash"
            except:
                shell_info["shell"] = "bash"
        elif shell_path:
            shell_info["shell"] = shell_path.split('/')[-1]
        
        # 终端设备检测
        ssh_tty = os.environ.get('SSH_TTY', '')
        ssh_client = os.environ.get('SSH_CLIENT', '')
        term = os.environ.get('TERM', '')
        
        if ssh_tty:
            shell_info["terminal"] = ssh_tty
        elif ssh_client:
            shell_info["terminal"] = "SSH连接"
        elif term and term != 'unknown':
            # 没有真实tty但TERM存在，显示TERM类型
            shell_info["terminal"] = f"虚拟终端({term})"
        else:
            shell_info["terminal"] = "无终端设备"
            
    except Exception as e:
        shell_info["terminal"] = "无终端设备"
    return shell_info

async def _get_robot_info() -> Dict:
    robot_info = {
        "qq": get_current_robot_id(),
        "nickname": "GracyBot",
        "avatar_url": None,
        "friend_count": 0,
        "group_count": 0,
        "napcat_version": "未知",
        "plugin_count": 0,
        "command_count": 0,
        "python_package_count": 0
    }

    try:
        from core.gracy_adapter.send import gracy_get_platform_info
        platform_info = await gracy_get_platform_info()
        if platform_info.get("friend_count") is not None:
            robot_info["friend_count"] = platform_info["friend_count"]
        if platform_info.get("group_count") is not None:
            robot_info["group_count"] = platform_info["group_count"]
        if platform_info.get("protocol_version"):
            robot_info["napcat_version"] = platform_info["protocol_version"]
        if platform_info.get("nickname"):
            robot_info["nickname"] = platform_info["nickname"]
        if platform_info.get("user_id"):
            robot_info["qq"] = str(platform_info["user_id"])
    except Exception as e:
        logger.error(f"[SysInfo] 获取机器人/好友/群信息失败: {type(e).__name__}: {e}")
    try:
        from core.plugin_manager import plugin_manager
        robot_info["plugin_count"] = len(plugin_manager.registry)
        command_count = 0
        for plugin in plugin_manager.registry:
            command_count += len(plugin.get("commands", []))
        robot_info["command_count"] = command_count
    except Exception:
        pass

    cached_pkgs = _cache_get("package_count")
    if cached_pkgs is not None:
        robot_info["python_package_count"] = cached_pkgs
    else:
        try:
            from importlib.metadata import distributions
            cnt = len(list(distributions()))
            robot_info["python_package_count"] = cnt
            _cache_set("package_count", cnt)
        except Exception:
            pass

    if robot_info["qq"] != "未知" and not robot_info["avatar_url"]:
        robot_info["avatar_url"] = f"https://q1.qlogo.cn/g?b=qq&nk={robot_info['qq']}&s=640"

    return robot_info

async def get_system_info() -> Dict:
    """跨平台系统信息获取函数（使用psutil实现跨平台兼容）"""
    t0 = time.time()
    # 基础系统信息
    host_name = platform.node() or "未知主机"
    
    # 系统版本 - 跨平台兼容
    system = platform.system()
    if system == "Linux":
        # Linux系统尝试获取更详细的信息
        try:
            with open('/etc/os-release', 'r') as f:
                for line in f:
                    if line.startswith('PRETTY_NAME'):
                        system_version = line.split('=')[1].strip().strip('"')
                        break
                else:
                    system_version = platform.platform()
        except:
            system_version = platform.platform()
    else:
        # Windows和其他系统使用platform信息
        system_version = platform.platform()
    
    # 内核版本
    kernel_version = platform.release()
    
    # CPU信息 - 使用psutil跨平台获取
    try:
        # CPU型号使用py-cpuinfo获取（对AMD EPYC友好）
        cpu_cores = str(psutil.cpu_count(logical=False) or psutil.cpu_count())

        cached_cpu = _cache_get("cpu_info")
        if cached_cpu:
            cpu_final = cached_cpu
        else:
            try:
                import cpuinfo
                cpu_info_dict = cpuinfo.get_cpu_info()
                if cpu_info_dict:
                    cpu_info = cpu_info_dict.get('brand_raw',
                              cpu_info_dict.get('model_name',
                              cpu_info_dict.get('hardware',
                              cpu_info_dict.get('vendor_id', '未知处理器'))))
                else:
                    cpu_info = "未知处理器"
            except ImportError:
                cpu_info = platform.processor() or "未知处理器"
            # ARM Linux：优先用 device-tree SoC 名（如 RK3528），替代 cortex-a53 等架构名
            if sys.platform == "linux" and platform.machine() in ("aarch64", "armv7l", "armv8l"):
                try:
                    dt_compat = "/proc/device-tree/compatible"
                    if os.path.exists(dt_compat):
                        with open(dt_compat) as f:
                            raw = f.read().strip('\x00').strip()
                        if raw:
                            parts = raw.split()
                            if parts:
                                soc = parts[-1]
                                if "," in soc:
                                    vendor, chip = soc.split(",", 1)
                                    cpu_info = f"{vendor.capitalize()} {chip.upper()}"
                                else:
                                    cpu_info = soc.upper()
                except:
                    pass
            cpu_final = f"{cpu_info}（{cpu_cores}核）"
            _cache_set("cpu_info", cpu_final)
    except:
        cpu_final = "CPU信息获取失败"
    
    # 内存信息 - 使用psutil跨平台获取
    try:
        mem = psutil.virtual_memory()
        total_gb = round(mem.total / (1024**3), 1)
        used_gb = round(mem.used / (1024**3), 1)
        mem_final = f"总内存：{total_gb}GB，已用：{used_gb}GB"
    except:
        mem_final = "内存信息获取失败"
    
    # 磁盘信息 - 使用psutil跨平台获取所有分区
    disk_final = "磁盘信息获取失败"
    all_disks_info = []
    try:
        partitions = [p for p in psutil.disk_partitions() if p.fstype != 'squashfs' and not p.device.startswith('/dev/loop')]
        for part in partitions:
            try:
                usage = psutil.disk_usage(part.mountpoint)
                total_gb = round(usage.total / (1024**3), 1)
                used_gb = round(usage.used / (1024**3), 1)
                percent = round((usage.used / usage.total) * 100, 1)
                mount = part.mountpoint.rstrip("\\")
                all_disks_info.append(f"{mount} 总{total_gb}GB/已用{used_gb}GB({percent}%)")
            except (PermissionError, OSError):
                continue
        
        # 主磁盘用于进度圈显示（Windows取C盘，Linux取/）
        if system == "Windows":
            primary_path = "C:\\"
        else:
            primary_path = "/"
        primary = psutil.disk_usage(primary_path)
        p_total = round(primary.total / (1024**3), 1)
        p_used = round(primary.used / (1024**3), 1)
        p_percent = round((primary.used / primary.total) * 100, 1)
        disk_final = f"总容量：{p_total}GB，已用：{p_used}GB，使用率：{p_percent}%"
        if not all_disks_info:
            all_disks_info.append(disk_final)
    except:
        disk_final = "磁盘信息获取失败"
        all_disks_info = ["磁盘信息获取失败"]
    
    # 系统运行时长 - 使用psutil跨平台获取
    try:
        uptime_seconds = time.time() - psutil.boot_time()
        days = int(uptime_seconds // 86400)
        hours = int((uptime_seconds % 86400) // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        system_uptime = f"{days}天{hours}小时{minutes}分钟"
    except:
        system_uptime = "获取失败"
    
    # 机器人启动时长
    robot_uptime = "获取失败"
    try:
        if ROBOT_START_TIME and isinstance(ROBOT_START_TIME, (int, float)) and ROBOT_START_TIME > 0:
            sec = time.time() - ROBOT_START_TIME
            robot_uptime = f"{int(sec//86400)}天{int((sec%86400)//3600)}小时{int((sec%3600)//60)}分钟"
    except Exception as e:
        logger.error(f"机器人时长计算异常：{str(e)}")
    
    # 获取额外信息（从draw.py移植）
    t_extra = time.time()
    cpu_usage_task = asyncio.to_thread(_get_cpu_usage)
    gpu_info_task = _get_gpu_info()
    io_stats_task = _get_io_stats()
    net_info_task = asyncio.to_thread(_get_network_info)
    shell_task = _get_shell_terminal()
    
    # robot_info 可能因 NapCat API 超时阻塞 → 用 wait_for 限制时间
    robot_task = asyncio.wait_for(_get_robot_info(), timeout=3.0)
    
    cpu_usage, gpu_info, io_stats, network_info, shell_terminal = await asyncio.gather(
        cpu_usage_task, gpu_info_task, io_stats_task, net_info_task, shell_task
    )
    try:
        robot_info = await robot_task
    except (asyncio.TimeoutError, Exception):
        robot_info = {"qq": str(robot_id), "friend_count": None, "group_count": None,
                      "platform": "OneBot", "protocol_version": None, "nickname": None}
    
    t_done = time.time()
    logger.warning(f"[SysInfo⏱] total={t_done - t0:.1f}s gather={t_done - t_extra:.1f}s robot={robot_info.get('qq','?')} friend={robot_info.get('friend_count')} group={robot_info.get('group_count')}")
    
    # 返回完整信息字典
    return {
        # 基础信息
        "主机名称": host_name,
        "系统版本": system_version,
        "内核版本": kernel_version,
        "CPU信息": cpu_final,
        "内存信息": mem_final,
        "磁盘信息": disk_final,
        "所有磁盘": all_disks_info,
        "系统运行时长": system_uptime,
        "机器人启动时长": robot_uptime,
        "机器人版本": BOT_VERSION,
        "作者QQ": MASTER_ID,
        
        # 扩展信息
        "cpu_usage": cpu_usage,
        "gpu_info": gpu_info,
        "io_stats": io_stats,
        "network_info": network_info,
        "shell_terminal": shell_terminal,
        "robot_info": robot_info
    }

async def handle_status_cmd(target: str, chat_type: str):
    """发送系统状态图片"""
    t_start = time.time()
    info = await get_system_info()  # 获取完整系统信息
    
    # 检查绘图模块是否可用
    if SysInfoDrawer is None:
        logger.error("绘图模块未加载，无法发送系统状态")
        await gracy_send_msg(target, GracyText(text="❌ 系统状态绘图模块未加载，无法显示状态信息"), chat_type=chat_type)
        return
        
    try:
        # 生成最新状态图片（自动覆盖旧缓存）
        t_draw = time.time()
        drawer = SysInfoDrawer(info)
        img_path = await drawer.draw()
        t_send = time.time()
        logger.warning(f"[SysInfo⏱] 绘图={t_send - t_draw:.1f}s")
        # 图片消息（通过 GracyAdapter 适配层发送）
        if await gracy_send_msg(target, GracyImage(file_path=img_path), chat_type=chat_type):
            t_end = time.time()
            logger.warning(f"[SysInfo⏱] 发送={t_end - t_send:.1f}s | 总={t_end - t_start:.1f}s")
            logger.info(sanitize_log(f"✅ 发送系统状态图片到{target}"))
        else:
            logger.error(sanitize_log(f"❌ 发送系统状态图片失败，目标：{target}"))
    except Exception as e:
        logger.error(f"图片生成失败：{str(e)}")
        await gracy_send_msg(target, GracyText(text="❌ 系统状态图片生成失败，请检查日志"), chat_type=chat_type)

# 原有核心处理函数（完全保留，不做任何修改）
async def handle_sysinfo_plugin(self_bot, bot, message, user_id, chat_type, permission, logger):
    # 1. 提取并清理消息内容（过滤空格、@机器人符号，兼容群聊格式）
    raw_msg = message.get("text", "").strip()
    msg_content = raw_msg.replace(" ", "").replace("　", "").replace(f"@1972693082", "").replace(f"@机器人", "").strip()
    
    # 2. 确定目标ID（群聊=群ID，私聊=用户ID，避免发送失败）
    if chat_type == "group":
        target_id = message.get("raw_data", {}).get("group_id")
    else:
        target_id = user_id
    target_id = str(target_id) if target_id else user_id  # 容错处理，防止空值
    
    # 3. 指令匹配（保持原有功能逻辑不变）
    if msg_content in ["/运行状态", "/info", "/status"]:
        await handle_status_cmd(target_id, chat_type)
        logger.info(f"用户{user_id}（{chat_type}）查询系统状态，目标ID：{target_id}")
        return True
    
    # 4. 无效指令处理（放过其他插件指令，避免冲突）
    if msg_content.startswith("/") and msg_content not in ["/运行状态", "/info", "/status"]:
        bot(target_id, "无效指令！本插件仅支持：/运行状态、/info、/status", chat_type)
        logger.warning(f"用户{user_id}（{chat_type}）发送无效系统指令：{msg_content}")
    else:
        return  # 放行其他插件的指令，交给对应插件处理

__all__ = ["handle_sysinfo_plugin"]
