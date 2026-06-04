import json
import os
import re
from datetime import datetime
from .database import (
    add_message, get_messages, clear_messages,
    add_persona, delete_persona, get_personas, get_persona,
    set_current_persona, get_current_persona,
    set_max_context, get_max_context
)
from .api_handler import call_llm_api, load_config, save_config

def is_master(user_id, master_id):
    return str(user_id) == str(master_id)

def handle_chat_help(bot, target_id, chat_type):
    help_msg = """🌟 LLM-Chat 帮助
//+内容 - AI对话（支持上下文）
群聊：@机器人 +内容 触发对话
支持发送图片给AI识别（多模态）

主人专属命令：
/设置OpenAI API_KEY 模型 地址
/设置视觉模型 模型 API_KEY 地址
/视觉模型开关 开启/关闭
/新增人设 名称 内容
/删除人设 名称
/查看人设列表
/切换人设 名称
/清除记忆
/设置上下文数量 数量
/查看配置
/戳一戳开关 开启/关闭
/戳一戳状态

英文指令：
/persona 名称 - 切换人设
/+persona 名称 内容 - 新增人设
/-persona 名称 - 删除人设
/persona= - 查看人设列表"""
    bot(target_id, help_msg, chat_type=chat_type)

def handle_set_openai(bot, target_id, chat_type, raw_msg):
    parts = raw_msg.split(maxsplit=3)
    if len(parts) == 4:
        _, api_key, model, api_base = parts
        config = load_config()
        config.update({"api_key": api_key, "model": model, "api_base": api_base})
        save_config(config)
        bot(target_id, "✅ OpenAI配置成功", chat_type=chat_type)
    else:
        bot(target_id, "❌ 格式错误：/设置OpenAI API_KEY 模型 地址", chat_type=chat_type)


def handle_set_vision_model(bot, target_id, chat_type, raw_msg):
    parts = raw_msg.split(maxsplit=3)
    if len(parts) == 4:
        _, model, api_key, api_base = parts
        config = load_config()
        config.update({"vision_model": model, "vision_api_key": api_key, "vision_api_base": api_base, "vision_enabled": True})
        save_config(config)
        bot(target_id, f"✅ 视觉模型已设置\n• 模型：{model}\n• API Key：{api_key[:10]}...\n• 地址：{api_base}", chat_type=chat_type)
    else:
        bot(target_id, "❌ 格式错误：/设置视觉模型 模型 API_KEY API地址", chat_type=chat_type)


def handle_vision_switch(bot, target_id, chat_type, raw_msg):
    """视觉模型开关"""
    parts = raw_msg.split(maxsplit=1)
    if len(parts) == 2:
        action = parts[1].strip()
        enabled = action in ["开启", "打开", "on", "enable", "true"]
        config = load_config()
        config["vision_enabled"] = enabled
        save_config(config)
        status = "已开启" if enabled else "已关闭"
        bot(target_id, f"✅ 视觉模型{status}", chat_type=chat_type)
    else:
        bot(target_id, "❌ 格式：/视觉模型开关 开启/关闭", chat_type=chat_type)

def handle_add_persona(bot, target_id, chat_type, raw_msg):
    parts = raw_msg.split(maxsplit=2)
    if len(parts) == 3:
        _, name, content = parts
        if add_persona(name, content):
            bot(target_id, f"✅ 新增人设「{name}」成功", chat_type=chat_type)
        else:
            bot(target_id, f"❌ 人设「{name}」已存在", chat_type=chat_type)
    else:
        bot(target_id, "❌ 格式错误：/新增人设 名称 内容", chat_type=chat_type)

def handle_delete_persona(bot, target_id, chat_type, raw_msg):
    parts = raw_msg.split(maxsplit=1)
    if len(parts) == 2:
        name = parts[1]
        if name == "默认人设":
            bot(target_id, "❌ 无法删除默认人设", chat_type=chat_type)
        else:
            delete_persona(name)
            bot(target_id, f"✅ 删除人设「{name}」成功", chat_type=chat_type)
    else:
        bot(target_id, "❌ 格式错误：/删除人设 名称", chat_type=chat_type)

def handle_list_personas(bot, target_id, chat_type, current_chat_id):
    personas = get_personas()
    current = get_current_persona(current_chat_id)
    
    config = load_config()
    if "默认人设" not in personas:
        personas["默认人设"] = config.get("default_persona", "")
    
    char_list = []
    for name in personas.keys():
        if name == current:
            char_list.append(f"• {name}（当前）")
        else:
            char_list.append(f"• {name}")
    bot(target_id, f"📋 人设列表：\n" + "\n".join(char_list), chat_type=chat_type)

def handle_switch_persona(bot, target_id, chat_type, raw_msg, current_chat_id):
    parts = raw_msg.split(maxsplit=1)
    if len(parts) == 2:
        name = parts[1]
        personas = get_personas()
        config = load_config()
        if "默认人设" not in personas:
            personas["默认人设"] = config.get("default_persona", "")
        
        if name in personas:
            set_current_persona(current_chat_id, name)
            clear_messages(current_chat_id)
            bot(target_id, f"✅ 已切换至人设「{name}」", chat_type=chat_type)
        else:
            bot(target_id, "❌ 人设不存在", chat_type=chat_type)
    else:
        bot(target_id, "❌ 格式错误：/切换人设 名称", chat_type=chat_type)

def handle_clear_memory(bot, target_id, chat_type, current_chat_id):
    clear_messages(current_chat_id)
    bot(target_id, "✅ 已清除对话记忆", chat_type=chat_type)

def handle_set_context(bot, target_id, chat_type, raw_msg, current_chat_id):
    parts = raw_msg.split(maxsplit=1)
    if len(parts) == 2:
        try:
            count = int(parts[1])
            if count > 0:
                set_max_context(current_chat_id, count)
                bot(target_id, f"✅ 上下文数量已设置为 {count}", chat_type=chat_type)
            else:
                bot(target_id, "❌ 数量必须大于0", chat_type=chat_type)
        except ValueError:
            bot(target_id, "❌ 请输入有效数字", chat_type=chat_type)
    else:
        bot(target_id, "❌ 格式错误：/设置上下文数量 数量", chat_type=chat_type)

def handle_view_config(bot, target_id, chat_type, current_chat_id):
    config = load_config()
    current_persona = get_current_persona(current_chat_id)
    max_context = get_max_context(current_chat_id)
    
    msg = f"""⚙️ 当前配置：
• 模型：{config['model']}
• 视觉模型：{config.get('vision_model', config['model'])} {'(已启用)' if config.get('vision_enabled', False) else '(已禁用)'}
• 当前人设：{current_persona}
• 上下文数量：{max_context}
• 戳一戳：{'开启' if config.get('poke_enabled', True) else '关闭'}"""
    bot(target_id, msg, chat_type=chat_type)

def handle_ai_chat(bot, target_id, chat_type, message, user_id, nickname, current_chat_id, raw_event=None):
    config = load_config()
    max_context = get_max_context(current_chat_id)
    current_persona = get_current_persona(current_chat_id)
    
    personas = get_personas()
    if "默认人设" not in personas:
        personas["默认人设"] = config.get("default_persona", "")
    
    if current_persona not in personas:
        current_persona = "默认人设"
        set_current_persona(current_chat_id, current_persona)
    
    persona_content = personas[current_persona]
    system_prompt = f"{persona_content}\n\n用户昵称：{nickname}"
    
    history = get_messages(current_chat_id, max_context)
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    
    current_time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    messages.append({"role": "system", "content": f"【系统时间同步】现在的准确时间是 {current_time_str}。这是从系统实时获取的时间，请务必以此为准。对话历史中的任何时间信息都已过时，不要基于历史时间推算，必须使用这个最新时间。"})
    
    image_urls = _extract_image_urls(raw_event) if raw_event else []
    image_urls = [u for u in image_urls if u]
    
    if image_urls and config.get("vision_enabled", True):
        content_parts = []
        for url in image_urls:
            content_parts.append({"type": "image_url", "image_url": {"url": url}})
        content_parts.append({"type": "text", "text": message if message else "请描述这张图片"})
        messages.append({"role": "user", "content": content_parts})
    else:
        messages.append({"role": "user", "content": message})
    
    reply = call_llm_api(messages, config)

    db_user_msg = "[图片]" if image_urls else message
    add_message(current_chat_id, "user", db_user_msg)
    add_message(current_chat_id, "assistant", reply)

    bot(target_id, reply, chat_type=chat_type)


def _extract_image_urls(raw_event) -> list:
    if raw_event is None:
        return []
    files = []
    
    if isinstance(raw_event, dict) and raw_event.get("images"):
        raw_imgs = raw_event["images"]
        if isinstance(raw_imgs, list):
            files = [f for f in raw_imgs if f]
    
    # 兼容旧路径：从 raw_data["message"] 数组取图片
    if not files and isinstance(raw_event, dict):
        msg_array = raw_event.get("message", [])
        if isinstance(msg_array, list):
            for seg in msg_array:
                if isinstance(seg, dict) and seg.get("type") == "image":
                    data = seg.get("data", {})
                    fid = data.get("file", "")
                    if fid and fid not in files:
                        files.append(fid)
    
    return [_fetch_via_napcat(f) for f in files if f]


def _fetch_via_napcat(file_id: str) -> str:
    import logging
    import base64
    import os as _os
    log = logging.getLogger("LLM_Chat")
    try:
        from core.gracy_adapter.send import gracy_call_api
        log.info(f"[图片] 通过NapCat获取本地路径: file={file_id[:30]}...")
        result = gracy_call_api("get_image", {"file": file_id})
        if isinstance(result, dict):
            file_path = result.get("data") or result.get("file") or ""
            if file_path and _os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                ext = _os.path.splitext(file_path)[1].lower()
                mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp"}
                ct = mime_map.get(ext, "image/jpeg")
                log.info(f"[图片] 本地文件读取成功: {file_path}")
                return f"data:{ct};base64,{b64}"
            log.warning(f"[图片] 返回的路径不存在或为空: {file_path}")
        if isinstance(result, str) and result.strip():
            file_path = result.strip()
            if _os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                ext = _os.path.splitext(file_path)[1].lower()
                mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp"}
                ct = mime_map.get(ext, "image/jpeg")
                log.info(f"[图片] 本地文件读取成功: {file_path}")
                return f"data:{ct};base64,{b64}"
            log.warning(f"[图片] 返回的路径不存在: {file_path}")
        log.warning(f"[图片] NapCat get_image 返回格式异常: {type(result).__name__}, 值: {str(result)[:100]}")
    except Exception as e:
        log.warning(f"[图片] NapCat get_image 失败: {type(e).__name__}: {str(e)[:100]}")
    return ""
