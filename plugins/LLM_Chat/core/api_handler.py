import json
import os
import logging
from openai import OpenAI

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
logger = logging.getLogger("LLM_Chat")


def load_config():
    default_config = {
        "api_key": "",
        "model": "deepseek-chat",
        "api_base": "https://api.deepseek.com/v1",
        "vision_model": "deepseek-chat",
        "vision_api_key": "",
        "vision_api_base": "https://api.deepseek.com/v1",
        "vision_enabled": True,
        "max_context": 50,
        "default_persona": "你是由GracyBot开发团队开发的AI助手，名为GracyBot AI。",
        "poke_enabled": True,
        "poke_ai_reply": True,
        "poke_back": True
    }
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
            # 合并默认配置，确保所有字段存在
            for key, value in default_config.items():
                if key not in config:
                    config[key] = value
            return config
    return default_config


def save_config(config):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)


def _build_openai_messages(messages):
    seen_system_time = False
    for msg in reversed(messages):
        if msg.get("role") == "system" and msg.get("content", "").startswith("【系统时间同步】"):
            if seen_system_time:
                msg["content"] = "[已过期的时间同步，忽略]"
            seen_system_time = True


def call_llm_api(messages, config=None):
    if config is None:
        config = load_config()

    # 判断是否有图片
    has_images = _has_images(messages)
    
    # 选择模型和配置
    if has_images:
        # 检查视觉模型是否启用
        if not config.get("vision_enabled", False):
            logger.warning("[视觉模型] 视觉模型未启用，请使用 /设置视觉模型 命令配置")
            return "❌ 视觉模型未启用，请输入 /chat帮助 查看配置命令"
        
        # 检查视觉模型配置是否完整
        vision_model = config.get("vision_model")
        vision_api_key = config.get("vision_api_key")
        vision_api_base = config.get("vision_api_base")
        
        if not vision_model or not vision_api_key or not vision_api_base:
            logger.error("[视觉模型] 配置不完整，请使用 /设置视觉模型 命令配置")
            return "❌ 视觉模型配置为空，请输入 /chat帮助 查看配置命令"
        
        model = vision_model
        api_base = vision_api_base
        api_key = vision_api_key
        logger.info(f"[视觉模型] 使用模型: {model}, API地址: {api_base}")
    else:
        model = config["model"]
        api_base = config.get("api_base")
        api_key = config["api_key"]

    client = OpenAI(
        api_key=api_key,
        base_url=api_base
    )

    _build_openai_messages(messages)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.7,
            timeout=30
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        error_msg = str(e)
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            try:
                error_data = json.loads(e.response.text)
                if 'error' in error_data:
                    error_msg = f"Error code: {error_data.get('error', {}).get('code', 'unknown')} - {error_data.get('error', {}).get('message', error_msg)}"
            except Exception:
                pass
        
        # 视觉模型调用失败，记录详细错误日志
        if has_images:
            logger.error(f"[视觉模型] API调用失败: {error_msg}")
            return f"❌ 视觉模型调用失败：{error_msg}"
        else:
            return f"❌ API调用失败：{error_msg}"


def _has_images(messages):
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "image_url":
                    return True
    return False