"""Satori 消息转换 — GracyMsg ↔ Satori 消息元素"""

import base64
import io
import json
import logging
import os
from typing import List, Optional, Union

from gracybot.core.gracy_adapter.message import (
    GracyMsg,
    GracyText,
    GracyImage,
    GracyVoice,
    GracyAt,
    GracyReply,
    GracyFile,
    GracyVideo,
    GracyForward,
)

_logger = logging.getLogger("Adapter.Satori.message")

_MIME_MAP = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
    ".mp4": "video/mp4",
}


def _compress_image(file_path: str) -> tuple:
    try:
        from PIL import Image
        img = Image.open(file_path)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        w, h = img.size
        if w > 800:
            ratio = 800 / w
            img = img.resize((800, int(h * ratio)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=60, optimize=True)
        data = buf.getvalue()
        _logger.info(f"图片压缩: {os.path.basename(file_path)} {w}x{h} -> JPEG {len(data)//1024}KB")
        return data, "image/jpeg"
    except Exception as e:
        _logger.warning(f"图片压缩失败: {e}")
        return None, None


def _file_to_data_url(file_path: str) -> Optional[str]:
    if not os.path.isfile(file_path):
        _logger.warning(f"媒体文件不存在: {file_path}")
        return None
    ext = os.path.splitext(file_path)[1].lower()
    mime = _MIME_MAP.get(ext, "application/octet-stream")
    try:
        with open(file_path, "rb") as f:
            data = f.read()
        if ext in (".png", ".bmp", ".tiff") and len(data) > 200_000:
            compressed, new_mime = _compress_image(file_path)
            if compressed is not None:
                data, mime = compressed, new_mime
        b64 = base64.b64encode(data).decode("ascii")
        return f"data:{mime};base64,{b64}"
    except Exception as e:
        _logger.error(f"读取媒体文件失败: {file_path} -> {e}")
        return None


def gracy_to_satori(segments: List[GracyMsg], uploaded_urls: dict = None) -> List[dict]:
    uploaded_urls = uploaded_urls or {}
    result = []
    for seg in segments:
        if isinstance(seg, GracyText):
            result.append({"type": "text", "data": {"content": seg.text}})
        elif isinstance(seg, GracyImage):
            url = seg.url or seg.file_path
            if url:
                upload_url = uploaded_urls.get(seg.file_path) if seg.file_path else None
                if upload_url:
                    result.append({"type": "image", "data": {"url": upload_url}})
                elif url.startswith(("http://", "https://", "data:")):
                    result.append({"type": "image", "data": {"url": url}})
                else:
                    data_url = _file_to_data_url(url)
                    if data_url:
                        result.append({"type": "image", "data": {"url": data_url}})
        elif isinstance(seg, GracyVoice):
            if seg.file_path:
                upload_url = uploaded_urls.get(seg.file_path)
                if upload_url:
                    result.append({"type": "voice", "data": {"url": upload_url}})
                elif seg.file_path.startswith(("http://", "https://", "data:")):
                    result.append({"type": "voice", "data": {"url": seg.file_path}})
                else:
                    data_url = _file_to_data_url(seg.file_path)
                    if data_url:
                        result.append({"type": "voice", "data": {"url": data_url}})
        elif isinstance(seg, GracyAt):
            result.append({"type": "at", "data": {"id": seg.target_id}})
        elif isinstance(seg, GracyReply):
            result.append({"type": "reply", "data": {"id": seg.message_id}})
        elif isinstance(seg, GracyFile):
            url = seg.url or seg.file_path
            if url:
                upload_url = uploaded_urls.get(seg.file_path) if seg.file_path else None
                if upload_url:
                    result.append({"type": "file", "data": {"url": upload_url}})
                elif url.startswith(("http://", "https://", "data:")):
                    result.append({"type": "file", "data": {"url": url}})
                else:
                    data_url = _file_to_data_url(url)
                    if data_url:
                        result.append({"type": "file", "data": {"url": data_url}})
        elif isinstance(seg, GracyVideo):
            url = seg.url or seg.file_path
            if url:
                upload_url = uploaded_urls.get(seg.file_path) if seg.file_path else None
                if upload_url:
                    result.append({"type": "video", "data": {"url": upload_url}})
                elif url.startswith(("http://", "https://", "data:")):
                    result.append({"type": "video", "data": {"url": url}})
                else:
                    data_url = _file_to_data_url(url)
                    if data_url:
                        result.append({"type": "video", "data": {"url": data_url}})
        elif isinstance(seg, GracyForward):
            result.append({"type": "forward", "data": {"id": seg.forward_id, "title": seg.title}})
        else:
            _logger.warning(f"不支持的消息段类型: {type(seg).__name__}")
    return result


def satori_to_gracy(content: Union[str, list]) -> List[GracyMsg]:
    if isinstance(content, str):
        try:
            elements = json.loads(content)
        except json.JSONDecodeError:
            _logger.debug(f"解析 Satori 消息内容失败: {content[:100]}")
            return [GracyText(text=content)]
    elif isinstance(content, list):
        elements = content
    else:
        _logger.warning(f"未知的 Satori 消息内容类型: {type(content)}")
        return []

    result = []
    for elem in elements:
        if hasattr(elem, 'tag'):
            tag = elem.tag
            if tag == 'img':
                type_ = 'image'
            elif tag == 'audio':
                type_ = 'voice'
            else:
                type_ = tag
            data = {}
            if type_ == 'text':
                data['content'] = getattr(elem, 'text', '')
            elif type_ in ('at', 'emoji'):
                data['id'] = getattr(elem, 'id', '')
                data['name'] = getattr(elem, 'name', '')
            elif type_ in ('image', 'voice', 'file', 'video'):
                data['url'] = getattr(elem, 'src', '')
        else:
            type_ = elem.get("type", "")
            data = elem.get("data", {})

        if type_ == "text":
            text = data.get("content", "")
            if text:
                result.append(GracyText(text=text))
        elif type_ == "image":
            url = data.get("url", "")
            if url:
                result.append(GracyImage(url=url))
        elif type_ == "voice":
            url = data.get("url", "")
            if url:
                result.append(GracyVoice(file_path=url))
        elif type_ == "at":
            target_id = data.get("id", "")
            if target_id:
                result.append(GracyAt(target_id=target_id))
        elif type_ == "reply":
            message_id = data.get("id", "")
            if message_id:
                result.append(GracyReply(message_id=message_id))
        elif type_ == "file":
            url = data.get("url", "")
            if url:
                result.append(GracyFile(url=url))
        elif type_ == "video":
            url = data.get("url", "")
            if url:
                result.append(GracyVideo(url=url))
        elif type_ == "forward":
            forward_id = data.get("id", "")
            title = data.get("title", "")
            if forward_id:
                result.append(GracyForward(forward_id=forward_id, title=title))
        else:
            _logger.debug(f"忽略未知 Satori 消息段类型: {type_}")

    return result


def extract_plain_text(segments: List[GracyMsg]) -> str:
    parts = []
    for seg in segments:
        if isinstance(seg, GracyText):
            parts.append(seg.text)
    return "".join(parts)