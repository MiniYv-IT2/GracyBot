"""OneBot CQ 码清理与检测工具"""

import re

_CQ_PATTERNS = [
    (r'\[CQ:image,[^\]]+\]', '[图片]'),
    (r'\[CQ:face,[^\]]+\]', '[表情]'),
    (r'\[CQ:at,qq=(\d+)[^\]]*\]', r'[@\1]'),
    (r'\[CQ:reply,[^\]]+\]', '[回复]'),
    (r'\[CQ:record,[^\]]+\]', '[语音]'),
    (r'\[CQ:video,[^\]]+\]', '[视频]'),
    (r'\[CQ:file,[^\]]+\]', '[文件]'),
    (r'\[CQ:share,[^\]]+\]', '[链接分享]'),
    (r'\[CQ:json,[^\]]+\]', '[JSON卡片]'),
    (r'\[CQ:markdown,[^\]]+\]', '[卡片消息]'),
    (r'\[CQ:forward,[^\]]+\]', '[合并转发]'),
    (r'\[CQ:poke,[^\]]+\]', '[戳一戳]'),
    (r'\[CQ:dice,[^\]]+\]', '[骰子]'),
    (r'\[CQ:rps,[^\]]+\]', '[猜拳]'),
    (r'\[CQ:contact,[^\]]+\]', '[推荐好友]'),
]


def sanitize(msg: str) -> str:
    """将 CQ 码替换为可读文本（用于日志展示）"""
    for pattern, replacement in _CQ_PATTERNS:
        msg = re.sub(pattern, replacement, msg)
    return msg


def is_cq_raw_message(msg: str) -> bool:
    """判断消息是否为纯 CQ 格式的系统消息（如心跳等）"""
    return bool(msg and msg.startswith("[CQ:"))