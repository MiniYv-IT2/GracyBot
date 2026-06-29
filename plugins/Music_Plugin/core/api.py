"""
音乐 API 层 — 柠柚点歌 API（搜索 + 播放一体）

API:
  GET https://api.nycnm.cn/api/v2/diange?msg=<关键词>&apikey=<key>
    搜索：返回 data[] = {id, music_name, artist}
    翻页：加 &page=N

  GET https://api.nycnm.cn/api/v2/diange?msg=<关键词>&id=<搜到的id>&apikey=<key>
    播放：返回 data = {music_name, artist, music_link, cover_link, lrc_content}

费用：0.001元/次
"""
import urllib.parse
from typing import Dict, List, Optional

import httpx

from graci import get_logger, plugin_manager

logger = get_logger("Music.api")


def _load_cfg() -> dict:
    return plugin_manager.get_plugin_config("Music_Plugin")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 搜索结果
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class SearchItem:
    """搜索结果中的单曲"""
    __slots__ = ("idx", "name", "artist")

    def __init__(self, idx: int, name: str, artist: str):
        self.idx = idx
        self.name = name
        self.artist = artist


class SongPlayData:
    """播放数据"""
    __slots__ = ("name", "artist", "music_url", "cover_url", "lyric")

    def __init__(self, data: dict):
        self.name = data.get("music_name", "未知歌曲")
        self.artist = data.get("artist", "未知歌手")
        self.music_url = data.get("music_link", "")
        self.cover_url = data.get("cover_link", "")
        self.lyric = data.get("lrc_content", "")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 核心函数
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _api_url() -> str:
    cfg = _load_cfg()
    return cfg.get("api_url", "https://api.nycnm.cn/api/v2/diange")


async def search_songs(keyword: str, page: int = 1) -> (List[SearchItem], dict):
    """搜索歌曲，返回 (列表, 分页信息)"""
    cfg = _load_cfg()
    apikey = cfg.get("apikey", "")
    base = _api_url()
    timeout = cfg.get("timeout", 10)

    params = {"msg": keyword, "apikey": apikey, "page": page}
    url = f"{base}?{urllib.parse.urlencode(params)}"

    logger.info(f"[搜索] 关键词: {keyword}, page={page}")

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        body = resp.json()

    if body.get("code") != 200:
        logger.error(f"[搜索] API返回失败: {body.get('message', 'unknown')}")
        return [], {}

    results = []
    for item in body.get("data", []):
        results.append(SearchItem(
            idx=item.get("id", 0),
            name=item.get("music_name", "未知歌曲"),
            artist=item.get("artist", "未知歌手"),
        ))

    pagination = body.get("pagination", {})
    logger.info(f"[搜索] 找到 {len(results)} 条结果 (共{pagination.get('total_pages', '?')}页)")
    return results, pagination


async def play_song(keyword: str, song_id: int) -> Optional[SongPlayData]:
    """根据搜索关键词 + 歌曲 id 获取播放链接"""
    cfg = _load_cfg()
    apikey = cfg.get("apikey", "")
    base = _api_url()
    timeout = cfg.get("timeout", 10)

    params = {"msg": keyword, "id": song_id, "apikey": apikey}
    url = f"{base}?{urllib.parse.urlencode(params)}"

    logger.info(f"[播放] keyword={keyword}, id={song_id}")

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        body = resp.json()

    if body.get("code") != 200:
        logger.error(f"[播放] API返回失败: {body.get('message', 'unknown')}")
        return None

    return SongPlayData(body.get("data", {}))
