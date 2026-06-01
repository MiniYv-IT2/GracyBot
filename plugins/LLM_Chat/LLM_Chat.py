from core.config import MASTER_ID
from core.config_manager import config_manager
from .core.event_handler import (
    is_master, handle_chat_help, handle_set_openai, handle_set_vision_model,
    handle_add_persona, handle_delete_persona, handle_list_personas,
    handle_switch_persona, handle_clear_memory, handle_set_context,
    handle_view_config, handle_ai_chat
)
from .core.poke_handler import set_poke_enabled, get_poke_status
from .core.scheduler import extract_task_from_message, schedule_task, start_scheduler

scheduler_started = False

def handle_llm_chat(self_bot, bot, message, user_id, chat_type, permission, log_func):
    global scheduler_started
    if not scheduler_started:
        start_scheduler(config_manager.get("napcat_http_url", "http://localhost:3000"))
        scheduler_started = True
    
    raw_msg = message.get("raw_message", "").strip()
    nickname = message.get("sender", {}).get("card", "") or message.get("sender", {}).get("nickname", "") or user_id
    target_id = str(message.get("group_id") if chat_type == "group" else user_id)
    chat_id = f"{chat_type}_{target_id}"
    
    # 去除群聊中的 @机器人 CQ码，提取纯文本命令
    import re
    clean_msg = re.sub(r'\[CQ:at,qq=\d+\]\s*', '', raw_msg).strip()
    
    if raw_msg == "/chat帮助":
        handle_chat_help(bot, target_id, chat_type)
        log_func.info(f"用户{user_id}查询帮助")
        return True
    
    chat_content = ""
    if clean_msg.startswith("//"):
        chat_content = clean_msg[2:].strip()
    
    if chat_content:
        task_info = extract_task_from_message(chat_content, chat_id)
        if task_info:
            schedule_task(chat_id, task_info["time"], task_info["content"])
            bot(target_id, f"⏰ 定时提醒已设置\n⏱️ 时间：{task_info['time']}\n📝 内容：{task_info['content']}", chat_type=chat_type)
            return True
        else:
            handle_ai_chat(bot, target_id, chat_type, chat_content, user_id, nickname, chat_id, message)
            return True
    
    if is_master(user_id, MASTER_ID):
        if chat_type == "group" and clean_msg.startswith("/设置OpenAI"):
            bot(target_id, "❌ 配置命令仅支持私聊", chat_type=chat_type)
            return True
        
        if clean_msg.startswith("/设置OpenAI"):
            handle_set_openai(bot, target_id, chat_type, clean_msg)
            return True
        elif clean_msg.startswith("/设置视觉模型"):
            handle_set_vision_model(bot, target_id, chat_type, clean_msg)
            return True
        elif clean_msg.startswith("/新增人设") or clean_msg.startswith("/+persona"):
            handle_add_persona(bot, target_id, chat_type, clean_msg)
            return True
        elif clean_msg.startswith("/删除人设") or clean_msg.startswith("/-persona"):
            handle_delete_persona(bot, target_id, chat_type, clean_msg)
            return True
        elif clean_msg in ["/查看人设列表", "/persona="]:
            handle_list_personas(bot, target_id, chat_type, chat_id)
            return True
        elif clean_msg.startswith("/切换人设") or clean_msg.startswith("/persona "):
            handle_switch_persona(bot, target_id, chat_type, clean_msg, chat_id)
            return True
        elif clean_msg == "/清除记忆":
            handle_clear_memory(bot, target_id, chat_type, chat_id)
            return True
        elif clean_msg.startswith("/设置上下文数量"):
            handle_set_context(bot, target_id, chat_type, clean_msg, chat_id)
            return True
        elif clean_msg == "/查看配置":
            handle_view_config(bot, target_id, chat_type, chat_id)
            return True
        elif clean_msg.startswith("/戳一戳开关"):
            parts = clean_msg.split(maxsplit=1)
            if len(parts) == 2:
                action = parts[1].strip()
                enabled = action in ["开启", "打开", "on", "enable"]
                result = set_poke_enabled(enabled)
                bot(target_id, result, chat_type=chat_type)
            else:
                bot(target_id, "❌ 格式：/戳一戳开关 开启/关闭", chat_type=chat_type)
            return True
        elif clean_msg == "/戳一戳状态":
            result = get_poke_status()
            bot(target_id, result, chat_type=chat_type)
            return True
    
    if chat_type == "private" and clean_msg and not clean_msg.startswith("/"):
        task_info = extract_task_from_message(clean_msg, chat_id)
        if task_info:
            schedule_task(chat_id, task_info["time"], task_info["content"])
            log_func.info(f"[定时任务] 已创建任务：{task_info['time']} - {task_info['content']}")
            bot(target_id, f"⏰ 定时提醒已设置\n⏱️ 时间：{task_info['time']}\n📝 内容：{task_info['content']}", chat_type=chat_type)
            return True
        else:
            log_func.info(f"[私聊对话] 未检测到定时任务，调用AI处理")
            handle_ai_chat(bot, target_id, chat_type, raw_msg, user_id, nickname, chat_id, message)
            return True

    if chat_type == "group" and clean_msg and not clean_msg.startswith("/"):
        bot_id = str(message.get("self_id", ""))
        if bot_id and f"[CQ:at,qq={bot_id}]" in raw_msg:
            log_func.info(f"[群聊对话] @机器人触发AI处理")
            handle_ai_chat(bot, target_id, chat_type, raw_msg, user_id, nickname, chat_id, message)
            return True
    
    return False
