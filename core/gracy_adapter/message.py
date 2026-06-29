"""GracyBot 统一消息段类型 — 插件与适配器之间的公共契约

插件只使用这些结构化类型，从不直接拼 CQ 码。
适配器负责将消息段翻译为平台原生格式。

设计原则：
- 每种消息段是一个轻量 dataclass，字段即语义
- 与平台无关，不做任何格式假设
- 未来新增消息段只需在此文件追加，无需修改适配层
"""

from dataclasses import dataclass, field
from typing import List, Union


@dataclass
class GracyText:
    """纯文本消息段"""
    text: str


@dataclass
class GracyAt:
    """@某人"""
    target_id: str


@dataclass
class GracyImage:
    """图片消息段（三选一：本地路径 / 网络URL / 二进制数据）"""
    file_path: str = ""
    url: str = ""
    file_data: bytes = field(default_factory=bytes)


@dataclass
class GracyReply:
    """回复引用某条消息"""
    message_id: str


@dataclass
class GracyVoice:
    """语音消息段"""
    file_path: str = ""


@dataclass
class GracyFile:
    """文件消息段"""
    file_path: str = ""
    url: str = ""


@dataclass
class GracyVideo:
    """视频消息段"""
    file_path: str = ""
    url: str = ""
    file_data: bytes = field(default_factory=bytes)


@dataclass
class GracyForward:
    """合并转发消息段"""
    forward_id: str = ""
    title: str = ""


# 联合类型：列表中每一元素为上述之一
GracyMsg = Union[GracyText, GracyAt, GracyImage, GracyReply, GracyVoice, GracyFile, GracyVideo, GracyForward]


def gracy_text(text: str) -> GracyText:
    """快捷构造纯文本段"""
    return GracyText(text=text)


def gracy_image(file_path: str = "", url: str = "") -> GracyImage:
    """快捷构造图片段"""
    return GracyImage(file_path=file_path, url=url)
