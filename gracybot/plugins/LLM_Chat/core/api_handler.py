import json
import os
from openai import AsyncOpenAI
from graci import config_manager, get_logger

logger = get_logger("LLMChat")

config_manager.register_plugin_config("LLM_Chat")


def load_config():
    """从配置管理器加载配置"""
    return config_manager.get_plugin("LLM_Chat")


def save_config(config):
    """保存配置到配置管理器"""
    config_manager.update_plugin("LLM_Chat", config)


def _build_openai_messages(messages):
    seen_system_time = False
    for msg in reversed(messages):
        if msg.get("role") == "system" and msg.get("content", "").startswith("【系统时间同步】"):
            if seen_system_time:
                msg["content"] = "[已过期的时间同步，忽略]"
            seen_system_time = True


async def call_llm_api(messages, config=None):
    if config is None:
        config = load_config()

    has_images = _has_images(messages)

    if has_images:
        if not config.get("vision_enabled", False):
            logger.warning("[视觉模型] 视觉模型未启用")
            return "❌ 视觉模型未启用，请输入 /chat帮助 查看配置命令"

        vision_model = config.get("vision_model")
        vision_api_key = config.get("vision_api_key")
        vision_api_base = config.get("vision_api_base")

        if not vision_model or not vision_api_key or not vision_api_base:
            logger.error("[视觉模型] 配置不完整")
            return "❌ 视觉模型配置为空，请输入 /chat帮助 查看配置命令"

        model = vision_model
        api_base = vision_api_base
        api_key = vision_api_key
    else:
        model = config["model"]
        api_base = config.get("api_base")
        api_key = config["api_key"]

    client = AsyncOpenAI(api_key=api_key, base_url=api_base)
    _build_openai_messages(messages)

    try:
        response = await client.chat.completions.create(
            model=model, messages=messages, temperature=0.7, timeout=30
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        error_msg = str(e)
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            try:
                error_data = json.loads(e.response.text)
                error_msg = f"Error code: {error_data.get('error', {}).get('code', 'unknown')} - {error_data.get('error', {}).get('message', error_msg)}"
            except Exception:
                pass
        return f"❌ API调用失败：{error_msg}"


def _has_images(messages):
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "image_url":
                    return True
    return False
