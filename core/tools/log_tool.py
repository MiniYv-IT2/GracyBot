"""日志工具核心函数 — 纯函数，不依赖任何框架模块

职责：
  - parse_logger_name() — 把 Logger 名拆分为 [分类] [模块名]
  - build_attrs() — 从 LogRecord extra 构建属性列表
  - format_console_line() — 组装终端显示行
  - format_file_line() — 组装文件日志行（保留完整 Logger 名）

可独立测试：from core.tools.log_tool import parse_logger_name
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


# ── 分类映射规则 ──
# 优先级: 精确匹配前缀 > 泛匹配
CATEGORY_PREFIXES: Dict[str, str] = {
    "Core.":        "Core",
    "Adapter.":     "Adapter",
    "Tool.":        "Tool",
    "Gracy.":       "Gracy",
    "GracyUI":      "GracyUI",
    "Gracone.":     "Gracy",
    "Gracone":      "Gracy",
}


def parse_logger_name(name: str) -> Tuple[str, str]:
    """将 Logger 名称拆分为 (分类, 模块名)

    Args:
        name: 原始 Logger 名称，如 "Gracy.Help"、"Adapter.QQOfficial.gateway"

    Returns:
        (category, module) 元组，如 ("Gracy", "Help")、("Adapter", "QQOfficial.gateway")
        未知分类时 category 返回 "?", module 返回原名
    """
    # 精确前缀匹配
    for prefix, category in CATEGORY_PREFIXES.items():
        if name.startswith(prefix):
            module = name[len(prefix):]
            return category, module if module else ""

    # 无前缀 / 未知命名 → 取第一个 . 前的部分作为分类
    if "." in name:
        parts = name.split(".", 1)
        return parts[0], parts[1]

    # 没有 . → 整个作为分类，模块名为空
    return name, ""


def build_attrs(record: Any) -> List[str]:
    """从 LogRecord 的 extra 字段构建属性列表

    支持 extra 中的任意键值，值可以是 str、int、None。
    中括号内的属性按传入顺序排列。

    Args:
        record: logging.LogRecord 实例

    Returns:
        属性字符串列表，如 ["P50", "main-bot"]
    """
    attrs: List[str] = []

    # 1. 读取 extra 中定义的属性（手动传）
    log_attrs: Optional[Dict[str, Any]] = getattr(record, "log_attrs", None)
    if log_attrs and isinstance(log_attrs, dict):
        for key, value in log_attrs.items():
            if value is not None:
                attrs.append(str(value))

    # 2. 读取上下文属性（@log_attrs 装饰器注入）
    if not attrs:
        from core.decorators.logger import get_context_attrs
        ctx_attrs = get_context_attrs()
        if ctx_attrs:
            for key, value in ctx_attrs.items():
                if value is not None:
                    attrs.append(str(value))

    return attrs


def format_console_line(
    timestamp: str,
    category: str,
    level: str,
    module: str,
    attrs: List[str],
    message: str,
) -> str:
    """组装终端显示行

    格式: {timestamp} - [{category}] - {level} - [{module}] [{attr1}] ... {message}

    Args:
        timestamp: 时间戳字符串
        category: 分类名
        level: 日志级别
        module: 模块名
        attrs: 属性列表
        message: 日志消息

    Returns:
        格式化后的字符串
    """
    parts = [f"{timestamp} - [{category}] - {level}"]

    if module:
        parts.append(f" - [{module}]")
    else:
        parts.append("")

    for attr in attrs:
        parts.append(f" [{attr}]")

    parts.append(f" - {message}")
    return "".join(parts)


def format_file_line(
    timestamp: str,
    logger_name: str,
    level: str,
    message: str,
) -> str:
    """组装文件日志行（保留完整 Logger 名）

    格式: {timestamp} - {logger} - {level} - {message}

    Args:
        timestamp: 时间戳字符串
        logger_name: 完整 Logger 名称
        level: 日志级别
        message: 日志消息

    Returns:
        格式化后的字符串
    """
    return f"{timestamp} - {logger_name} - {level} - {message}"
