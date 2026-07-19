#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GracyBot 日志颜色配置
简洁实用的日志级别颜色映射
"""

# ANSI 颜色代码
class Colors:
    """颜色常量定义"""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    
    # 基本颜色
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    
    # 亮色
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'
    
    # 粉色（使用亮洋红色作为粉色）
    PINK = '\033[95m'
    # 真正的紫色
    PURPLE = '\033[38;5;141m'  # 更深的紫色


# 日志级别颜色映射 - 新颜色方案
LOG_LEVEL_COLORS = {
    'DEBUG': Colors.BRIGHT_MAGENTA,  # 紫色 - 调试信息
    'INFO': Colors.BRIGHT_BLUE,      # 蓝色 - 正常信息
    'WARNING': Colors.BRIGHT_YELLOW, # 橘黄色 - 警告信息
    'ERROR': Colors.BRIGHT_RED,      # 亮红色 - 错误信息
    'CRITICAL': Colors.BRIGHT_MAGENTA + Colors.BOLD,  # 亮紫色加粗 - 严重错误
    'SUCCESS': Colors.PINK,          # 粉色 - 成功信息
}

# 消息类型颜色映射
MESSAGE_TYPE_COLORS = {
    '[私聊消息]': Colors.PINK,        # 粉色 - 私聊消息
    '[群聊消息]': Colors.PURPLE,      # 真正的紫色 - 群聊消息
    '[消息]': Colors.CYAN,            # 青色 - 通用消息标记
    '消息类型: 私聊': Colors.PINK,     # 粉色 - 私聊消息（新格式）
    '消息类型: 群聊': Colors.PURPLE,   # 真正的紫色 - 群聊消息（新格式）
    '私聊消息发送成功': Colors.PINK,   # 粉色 - 私聊发送成功
    '群聊消息发送成功': Colors.PURPLE, # 真正的紫色 - 群聊发送成功
}


def colorize_level(level_name: str) -> str:
    """为日志级别添加颜色"""
    color = LOG_LEVEL_COLORS.get(level_name, Colors.RESET)
    return f"{color}{level_name}{Colors.RESET}"


def colorize_message(message: str, level: str = 'INFO') -> str:
    """为消息内容添加颜色"""
    # 检查是否包含消息类型标记
    for msg_type, color in MESSAGE_TYPE_COLORS.items():
        if msg_type in message:
            # 为整条消息添加对应的颜色
            return f"{color}{message}{Colors.RESET}"
    
    # 不包含消息类型标记的消息，添加级别颜色
    color = LOG_LEVEL_COLORS.get(level, Colors.RESET)
    return f"{color}{message}{Colors.RESET}"


def supports_color() -> bool:
    """检测终端是否支持颜色"""
    import sys
    import os
    
    # 检查是否在交互式终端中
    if not sys.stdout.isatty():
        return False
    
    # 检查环境变量
    if os.environ.get('NO_COLOR'):
        return False
    
    # 检查终端类型
    term = os.environ.get('TERM', '')
    if term.lower() in ('dumb', 'unknown'):
        return False
    
    return True