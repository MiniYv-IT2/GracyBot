"""日志中枢 API — 读取 GracyBot 日志目录"""
import os
import re
import time as _time_module
from datetime import datetime
from quart import Blueprint, request

logs_bp = Blueprint("logs", __name__, url_prefix="/api")

_LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "logs")
_LOG_DIR = os.path.abspath(_LOG_DIR)

# Flask 启动时间 — 只显示此时间之后的日志
_BOOT_TIME = datetime.now()

# 日志行正则：格式为 "时间 - 模块名 - 级别 - 消息内容"
# 例: 2026-05-29 00:12:26 - GracyBot - INFO - 日志系统初始化完成
_LOG_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) - (.+?) - (\w+) - (.+)$"
)
_TIME_FMT = "%Y-%m-%d %H:%M:%S"

# 首次请求标记，用于确定 boot 时间戳
_since_ts = None


def _get_since_timestamp() -> datetime:
    """获取日志起始时间：首次请求时从最后一条日志的时间往回推 3 秒"""
    global _since_ts
    if _since_ts is not None:
        return _since_ts

    # 尝试从日志文件中找到 bot 启动的那条日志的时间
    log_file = _find_latest_log()
    if log_file:
        try:
            with open(log_file, "r", encoding="utf-8", errors="replace") as fh:
                lines = fh.readlines()
            # 倒着找 "====== GracyBot v1.x.x 启动 ======" 的日志
            for line in reversed(lines[-2000:]):
                m = _LOG_RE.match(line.strip())
                if m and "启动" in m.group(4) and "GracyBot" in m.group(4):
                    _since_ts = datetime.strptime(m.group(1), _TIME_FMT)
                    return _since_ts
        except Exception:
            pass
    # 兜底：Flask 启动时间
    _since_ts = _BOOT_TIME
    return _since_ts


def _parse_log_line(line: str) -> dict | None:
    """解析单行日志，返回 {time, level, source, message} 或 None
    非标准格式的行返回 message_only=True 标记，由调用方合并到上一条"""
    line = line.strip()
    if not line:
        return None
    m = _LOG_RE.match(line)
    if not m:
        return {"time": "", "level": "", "source": "", "message": line, "_cont": True}
    return {
        "time": m.group(1),
        "level": m.group(3).upper(),
        "source": m.group(2),
        "message": m.group(4),
    }


def _find_latest_log() -> str | None:
    """找最新的非空日志文件"""
    if not os.path.isdir(_LOG_DIR):
        return None
    candidates = []
    for f in os.listdir(_LOG_DIR):
        if f.endswith(".log"):
            fp = os.path.join(_LOG_DIR, f)
            if os.path.getsize(fp) > 0:
                candidates.append((os.path.getmtime(fp), fp))
    if candidates:
        candidates.sort(reverse=True)
        return candidates[0][1]
    return None


@logs_bp.route("/logs")
async def api_logs():
    """获取日志列表（仅显示本次启动后的，支持翻页）"""
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 100, type=int)
    level_filter = request.args.get("level", "").upper()

    since = _get_since_timestamp()
    log_file = _find_latest_log()

    entries: list[dict] = []
    total = 0
    if log_file:
        try:
            with open(log_file, "r", encoding="utf-8", errors="replace") as fh:
                lines = fh.readlines()
                pending_cont: list[str] = []
                for line in reversed(lines[-8000:]):
                    parsed = _parse_log_line(line)
                    if not parsed:
                        continue
                    if parsed.get("_cont"):
                        pending_cont.append(parsed["message"])
                        continue
                    if pending_cont:
                        parsed["message"] = parsed["message"] + "\n" + "\n".join(reversed(pending_cont))
                        pending_cont.clear()
                    # 按时间过滤：只取启动后的
                    if parsed["time"]:
                        try:
                            t = datetime.strptime(parsed["time"], _TIME_FMT)
                            if t < since:
                                break  # 已到启动时间之前的日志，停止
                        except ValueError:
                            pass
                    if level_filter and parsed["level"] != level_filter:
                        continue
                    entries.append(parsed)
                    if len(entries) >= page_size * page:
                        break
                entries.reverse()
                total = len(entries)
        except Exception:
            total = 0

    start = (page - 1) * page_size
    entries = entries[start : start + page_size]

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "entries": entries,
        "since": since.strftime(_TIME_FMT) if since else "",
    }