import json
import os
from openai import OpenAI

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


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

    model = config.get("vision_model") if _has_images(messages) and config.get("vision_enabled") else config["model"]
    api_base = config.get("vision_api_base") if _has_images(messages) and config.get("vision_enabled") else config.get("api_base")

    client = OpenAI(
        api_key=config["api_key"],
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
        return f"❌ API调用失败：{error_msg}"


def _has_images(messages):
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "image_url":
                    return True
    return False