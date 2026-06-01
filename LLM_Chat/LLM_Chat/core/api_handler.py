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

def call_llm_api(messages, config=None):
    if config is None:
        config = load_config()
    
    client = OpenAI(
        api_key=config["api_key"],
        base_url=config["api_base"]
    )
    
    try:
        response = client.chat.completions.create(
            model=config["model"],
            messages=messages,
            temperature=0.7,
            timeout=30
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        # 获取完整的错误信息
        error_msg = str(e)
        # 如果是OpenAI错误，尝试获取更多细节
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            try:
                error_data = json.loads(e.response.text)
                if 'error' in error_data:
                    error_msg = f"Error code: {error_data.get('error', {}).get('code', 'unknown')} - {error_data.get('error', {}).get('message', error_msg)}"
            except:
                pass
        return f"❌ API调用失败：{error_msg}"
