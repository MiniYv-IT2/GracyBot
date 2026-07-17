"""
异环攻略插件 - HTTP 请求 + 缓存模块
"""
import os
import json
import time
import hashlib
from typing import Optional, Any

import httpx

from graci import get_logger

from ..config import CACHE_DIR, CACHE_EXPIRE, BASE_URL

logger = get_logger("NTEGuide.fetcher")

# 缓存键前缀
_PREFIX = "nte_"


def _cache_key(url: str) -> str:
    return _PREFIX + hashlib.md5(url.encode()).hexdigest()


def _cache_path(key: str) -> str:
    return os.path.join(CACHE_DIR, f"{key}.json")


def _get_cache(key: str, max_age: int) -> Optional[Any]:
    """从缓存读取"""
    path = _cache_path(key)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        age = time.time() - data.get("ts", 0)
        if age < max_age:
            return data.get("data")
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"缓存读取失败 {key}: {e}")
    return None


def _set_cache(key: str, data: Any):
    """写入缓存"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = _cache_path(key)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"ts": time.time(), "data": data}, f, ensure_ascii=False)
    except OSError as e:
        logger.warning(f"缓存写入失败 {key}: {e}")


async def fetch_url(url: str, cache_type: Optional[str] = None) -> Optional[str]:
    """获取页面 HTML，支持缓存"""
    if cache_type and cache_type in CACHE_EXPIRE:
        key = _cache_key(url)
        max_age = CACHE_EXPIRE[cache_type]
        cached = _get_cache(key, max_age)
        if cached is not None:
            logger.debug(f"缓存命中: {url[:60]}")
            return cached

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0), follow_redirects=True) as client:
            r = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            html = r.text

        if cache_type and cache_type in CACHE_EXPIRE:
            key = _cache_key(url)
            _set_cache(key, html)

        logger.debug(f"请求成功: {url[:60]} ({len(html)} bytes)")
        return html

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP 错误 {e.response.status_code}: {url[:60]}")
    except httpx.TimeoutException:
        logger.error(f"请求超时: {url[:60]}")
    except Exception as e:
        logger.error(f"请求失败: {url[:60]} - {e}")
    return None


async def fetch_image(url: str) -> Optional[bytes]:
    """下载图片"""
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0), follow_redirects=True) as client:
            r = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            return r.content
    except Exception as e:
        logger.warning(f"图片下载失败: {url[:60]} - {e}")
    return None


def clear_cache(max_days: int = 7) -> tuple:
    """清理过期缓存，返回 (已删, 剩余)"""
    if not os.path.exists(CACHE_DIR):
        return 0, 0
    now = time.time()
    deleted = 0
    remaining = 0
    for fname in os.listdir(CACHE_DIR):
        if fname.startswith(_PREFIX) and fname.endswith(".json"):
            path = os.path.join(CACHE_DIR, fname)
            age_hours = (now - os.path.getmtime(path)) / 3600
            if age_hours > max_days * 24:
                try:
                    os.remove(path)
                    deleted += 1
                except OSError:
                    pass
            else:
                remaining += 1
    return deleted, remaining
