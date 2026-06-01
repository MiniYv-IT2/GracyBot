from core.config import MASTER_ID, NAPCAT_HTTP_URL
from .core.event_handler import (
    is_master, handle_chat_help, handle_set_openai,
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
        start_scheduler(NAPCAT_HTTP_URL)
        scheduler_started = True
    
    raw_msg = message.get("raw_message", "").strip()
    nickname = message.get("sender", {}).get("card", "") or message.get("sender", {}).get("nickname", "") or user_id
    target_id = str(message.get("group_id") if chat_type == "group" else user_id)
    chat_id = f"{chat_type}_{target_id}"
    
    if raw_msg == "/chat帮助":
        handle_chat_help(bot, target_id, chat_type)
        log_func.info(f"用户{user_id}查询帮助")
        return True
    
    chat_content = ""
    if raw_msg.startswith("//"):
        chat_content = raw_msg[2:].strip()
    
    if chat_content:
        task_info = extract_task_from_message(chat_content, chat_id)
        if task_info:
            schedule_task(chat_id, task_info["time"], task_info["content"])
            bot(target_id, f"⏰ 定时提醒已设置\n⏱️ 时间：{task_info['time']}\n📝 内容：{task_info['content']}", chat_type=chat_type)
            return True
        else:
            handle_ai_chat(bot, target_id, chat_type, chat_content, user_id, nickname, chat_id)
            return True
    
    if is_master(user_id, MASTER_ID):
        if chat_type == "group" and raw_msg.startswith("/设置OpenAI"):
            bot(target_id, "❌ 配置命令仅支持私聊", chat_type=chat_type)
            return True
        
        if raw_msg.startswith("/设置OpenAI"):
            handle_set_openai(bot, target_id, chat_type, raw_msg)
            return True
        elif raw_msg.startswith("/新增人设") or raw_msg.startswith("/+persona"):
            handle_add_persona(bot, target_id, chat_type, raw_msg)
            return True
        elif raw_msg.startswith("/删除人设") or raw_msg.startswith("/-persona"):
            handle_delete_persona(bot, target_id, chat_type, raw_msg)
            return True
        elif raw_msg in ["/查看人设列表", "/persona="]:
            handle_list_personas(bot, target_id, chat_type, chat_id)
            return True
        elif raw_msg.startswith("/切换人设") or raw_msg.startswith("/persona "):
            handle_switch_persona(bot, target_id, chat_type, raw_msg, chat_id)
            return True
        elif raw_msg == "/清除记忆":
            handle_clear_memory(bot, target_id, chat_type, chat_id)
            return True
        elif raw_msg.startswith("/设置上下文数量"):
            handle_set_context(bot, target_id, chat_type, raw_msg, chat_id)
            return True
        elif raw_msg == "/查看配置":
            handle_view_config(bot, target_id, chat_type, chat_id)
            return True
        elif raw_msg.startswith("/戳一戳开关"):
            parts = raw_msg.split(maxsplit=1)
            if len(parts) == 2:
                action = parts[1].strip()
                enabled = action in ["开启", "打开", "on", "enable"]
                result = set_poke_enabled(enabled)
                bot(target_id, result, chat_type=chat_type)
            else:
                bot(target_id, "❌ 格式：/戳一戳开关 开启/关闭", chat_type=chat_type)
            return True
        elif raw_msg == "/戳一戳状态":
            result = get_poke_status()
            bot(target_id, result, chat_type=chat_type)
            return True
    
    if chat_type == "private" and raw_msg and not raw_msg.startswith("/"):
        task_info = extract_task_from_message(raw_msg, chat_id)
        if task_info:
            schedule_task(chat_id, task_info["time"], task_info["content"])
            log_func.info(f"[定时任务] 已创建任务：{task_info['time']} - {task_info['content']}")
            bot(target_id, f"⏰ 定时提醒已设置\n⏱️ 时间：{task_info['time']}\n📝 内容：{task_info['content']}", chat_type=chat_type)
            return True
        else:
            log_func.info(f"[私聊对话] 未检测到定时任务，调用AI处理")
            handle_ai_chat(bot, target_id, chat_type, raw_msg, user_id, nickname, chat_id)
            return True
    
    return False
