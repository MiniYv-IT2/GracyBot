"""
插件配置模板
"""
from typing import Dict, Any

DEFAULT_CONFIG: Dict[str, Any] = {
    "api_key": "",
    "model": "glm-4.7-flash",
    "api_base": "https://open.bigmodel.cn/api/paas/v4/",
    "vision_model": "qwen-vl-plus",
    "vision_api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "vision_enabled": True,
    "max_context": 100000,
    "default_persona": "",
    "poke_enabled": True,
    "poke_ai_reply": True,
    "poke_back": True,
    "vision_api_key": "",
    "tavily_api_key": "",
}
