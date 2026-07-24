"""Cron 表达式解析 — 5 位标准格式
支持:
  *            任意
  */5          每 N
  1,3,5        枚举
  1-5          范围
  1-5/2        范围+步进
"""

import re

_CRON_RE = re.compile(
    r"^(?P<min>\S+)\s+"
    r"(?P<hour>\S+)\s+"
    r"(?P<day>\S+)\s+"
    r"(?P<mon>\S+)\s+"
    r"(?P<dow>\S+)$"
)

_FIELD_RANGES = {
    "min": (0, 59),
    "hour": (0, 23),
    "day": (1, 31),
    "mon": (1, 12),
    "dow": (0, 6),
}


def _parse_field(field: str, lo: int, hi: int) -> set[int]:
    result = set()
    for part in field.split(","):
        part = part.strip()
        if not part:
            continue
        step = 1
        if "/" in part:
            part, step_str = part.split("/", 1)
            step = int(step_str)
        if part == "*":
            result.update(range(lo, hi + 1, step))
        elif "-" in part:
            a, b = part.split("-", 1)
            start, end = int(a), int(b)
            result.update(range(start, end + 1, step))
        else:
            result.add(int(part))
    return {v for v in result if lo <= v <= hi}


def parse_cron(spec: str) -> dict[str, set[int]] | None:
    m = _CRON_RE.match(spec.strip())
    if not m:
        return None
    parsed = {}
    for name in ("min", "hour", "day", "mon", "dow"):
        lo, hi = _FIELD_RANGES[name]
        vals = _parse_field(m.group(name), lo, hi)
        if not vals:
            return None
        parsed[name] = vals
    return parsed


def match_cron(parsed: dict[str, set[int]], now) -> bool:
    """now: datetime 对象，检查当前时间是否匹配 cron 表达式"""
    return (
        now.minute in parsed["min"]
        and now.hour in parsed["hour"]
        and now.day in parsed["day"]
        and now.month in parsed["mon"]
        and now.weekday() in parsed["dow"]
    )
