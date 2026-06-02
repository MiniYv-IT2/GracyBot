import random
from datetime import datetime
from .api_handler import load_config, save_config, call_llm_api
from .database import get_current_persona, get_personas

POKE_REPLIES = [
    "哎呀,别戳我啦~",
    "戳我干嘛呀?",
    "再戳我就要生气了!",
    "嘿嘿,被你发现了~",
    "戳戳戳,就知道戳我!",
    "我戳回去!",
    "别闹了,我在工作呢~"
]

def handle_poke_event(data, robot_id):
    if data.get("post_type") != "notice" or data.get("notice_type") != "notify" or data.get("sub_type") != "poke":
        return False
    
    if str(data.get("target_id", "")) != str(robot_id):
        return False
    
    config = load_config()
    if not config.get("poke_enabled", True):
        return True
    
    user_id = str(data.get("user_id", ""))
    group_id = str(data.get("group_id", ""))
    nickname = data.get("sender", {}).get("nickname", "用户")
    
    chat_type = "group" if group_id else "private"
    target_id = group_id if group_id else user_id
    chat_id = f"{chat_type}_{target_id}"
    
    reply_content = ""
    if config.get("poke_ai_reply", True):
        reply_content = generate_poke_reply(chat_id, nickname, chat_type, config)
    
    if not reply_content:
        reply_content = random.choice(POKE_REPLIES)
    
    send_message(target_id, reply_content, chat_type)
    
    if config.get("poke_back", True) and random.random() < 0.7:
        send_poke(user_id)
    
    return True

def generate_poke_reply(chat_id, nickname, chat_type, config):
    try:
        current_persona = get_current_persona(chat_id)
        personas = get_personas()
        if "默认人设" not in personas:
            personas["默认人设"] = config.get("default_persona", "")
        
        if current_persona not in personas:
            current_persona = "默认人设"
        
        persona_content = personas[current_persona]
        prompt = f"{persona_content}\n\n用户{nickname}在{chat_type}中戳了你,请用简短幽默的话回应(不超过15字)。"
        
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "戳一戳"}
        ]
        
        reply = call_llm_api(messages, config)
        return reply[:30] if len(reply) > 30 else reply
    except:
        return ""

def send_message(target_id, message, chat_type):
    try:
        from core.gracy_adapter.send import gracy_send_msg
        from core.gracy_adapter.message import GracyText
        gracy_send_msg(target_id, GracyText(text=message), chat_type=chat_type)
    except:
        pass

def send_poke(target_id):
    try:
        from core.gracy_adapter.send import gracy_call_api
        gracy_call_api("send_poke", {"user_id": int(target_id)})
    except:
        pass

def set_poke_enabled(enabled):
    config = load_config()
    config["poke_enabled"] = enabled
    save_config(config)
    return f"✅ 戳一戳功能已{'开启' if enabled else '关闭'}"

def get_poke_status():
    config = load_config()
    return f"""📊 戳一戳状态:
• 总开关:{'开启' if config.get('poke_enabled', True) else '关闭'}
• AI回复:{'开启' if config.get('poke_ai_reply', True) else '关闭'}
• 回戳功能:{'开启' if config.get('poke_back', True) else '关闭'}"""
