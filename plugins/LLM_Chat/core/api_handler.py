import json
import os
import logging
from openai import AsyncOpenAI
from graci import plugin_manager

logger = logging.getLogger("Gracy.LLMChat")


def load_config():
    """从统一配置系统加载配置"""
    return plugin_manager.get_plugin_config("LLM_Chat")


def save_config(config):
    """保存完整配置到 style/config/ 文件"""
    # 直接写入 style/config/llm_chat_config.json
    style_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "style", "config", "llm_chat_config.json"
    )
    os.makedirs(os.path.dirname(style_path), exist_ok=True)
    try:
        with open(style_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存配置到 {style_path} 失败: {str(e)}")
        return
    # 同步更新内存缓存
    plugin_manager._plugin_configs["LLM_Chat"] = dict(config)


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

    client = AsyncOpenAI(
        api_key=api_key,
        base_url=api_base
    )

    _build_openai_messages(messages)

    try:
        response = await client.chat.completions.create(
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