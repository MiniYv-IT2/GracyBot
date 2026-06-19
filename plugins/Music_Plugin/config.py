"""
插件配置
"""
from typing import Dict, Any

DEFAULT_CONFIG: Dict[str, Any] = {
    # ── API 密钥（必填，用户自行填写） ──
    "apikey": "",

    # ── 柠柚点歌 API（搜索+播放一体化，0.001元/次） ──
    "api_url": "https://api.nycnm.cn/api/v2/diange",

    # ── 搜索超时（秒） ──
    "timeout": 10,

    # ── 每页显示数量（API 播放端每页只支持 10 首） ──
    "page_size": 10,

    # ── 缓存清理：最大缓存天数（超过此天数的缓存文件将被清理） ──
    "cache_max_days": 7,
}
