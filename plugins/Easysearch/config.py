"""
插件配置
"""
from typing import Dict, Any

DEFAULT_CONFIG: Dict[str, Any] = {
    "default_engine": "bing",
    "timeout": 20,
    "engines": {
        "bing": {"name": "必应"},
        "baidu": {"name": "百度"},
        "google": {"name": "谷歌"},
        "sogou": {"name": "搜狗"},
        "yandex": {"name": "Yandex"}
    }
}
