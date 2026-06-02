import threading
import time
import re
from datetime import datetime, timedelta
from .database import add_scheduled_task, get_scheduled_tasks, disable_task, get_personas, get_current_persona
from .api_handler import call_llm_api, load_config

def parse_time_expression(text):
    # 相对时间模式（需要先匹配，因为更具体）
    relative_patterns = [
        (r'(?:过|再过)?(\d+|[一二两三四五六七八九十]+)分钟(?:后|以后)?', lambda m: calculate_relative_time(parse_chinese_number(m.group(1)), 'minute')),
        (r'(?:过|再过)?(\d+|[一二两三四五六七八九十]+)小时(?:后|以后)?', lambda m: calculate_relative_time(parse_chinese_number(m.group(1)), 'hour')),
        (r'半小时(?:后|以后)?', lambda m: calculate_relative_time(30, 'minute')),
        (r'一会儿?(?:后|以后)?', lambda m: calculate_relative_time(5, 'minute')),
    ]
    
    for pattern, calculator in relative_patterns:
        match = re.search(pattern, text)
        if match:
            return calculator(match)
    
    # 绝对时间模式
    absolute_patterns = [
        (r'(\d+)点(\d+)?分?', lambda m: f"{m.group(1).zfill(2)}:{m.group(2).zfill(2) if m.group(2) else '00'}"),
        (r'早上(\d+)点', lambda m: f"{m.group(1).zfill(2)}:00"),
        (r'晚上(\d+)点', lambda m: f"{str(int(m.group(1)) + 12).zfill(2)}:00"),
        (r'中午', lambda m: "12:00"),
        (r'(\d{1,2}):(\d{2})', lambda m: f"{m.group(1).zfill(2)}:{m.group(2)}")
    ]
    
    for pattern, formatter in absolute_patterns:
        match = re.search(pattern, text)
        if match:
            return formatter(match)
    return None

def parse_chinese_number(text):
    chinese_map = {'一': 1, '二': 2, '两': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}
    if text.isdigit():
        return int(text)
    if text in chinese_map:
        return chinese_map[text]
    if text.startswith('十'):
        return 10 + parse_chinese_number(text[1:]) if len(text) > 1 else 10
    if '十' in text:
        parts = text.split('十')
        return (chinese_map.get(parts[0], 1) * 10) + (chinese_map.get(parts[1], 0) if parts[1] else 0)
    return int(text) if text.isdigit() else 0

def calculate_relative_time(amount, unit):
    now = datetime.now()
    if unit == 'minute':
        future = now + timedelta(minutes=amount)
    elif unit == 'hour':
        future = now + timedelta(hours=amount)
    else:
        future = now
    return future.strftime("%H:%M")

def extract_task_from_message(message, chat_id):
    time_str = parse_time_expression(message)
    if not time_str:
        return None
    
    keywords = ["提醒", "叫我", "告诉我", "说", "早安", "晚安"]
    has_keyword = False
    for keyword in keywords:
        if keyword in message:
            has_keyword = True
            break
    
    if not has_keyword:
        return None
    
    task_content = message
    time_patterns = [
        r'(?:过|再过)?(?:\d+|[一二两三四五六七八九十]+)分钟(?:后|以后)?',
        r'(?:过|再过)?(?:\d+|[一二两三四五六七八九十]+)小时(?:后|以后)?',
        r'半小时(?:后|以后)?',
        r'一会儿?(?:后|以后)?',
        r'(?:早上|晚上)?(?:\d+)点(?:\d+)?分?',
        r'中午',
        r'\d{1,2}:\d{2}'
    ]
    
    for pattern in time_patterns:
        task_content = re.sub(pattern, '', task_content)
    
    task_content = re.sub(r'提醒我?', '请', task_content)
    task_content = re.sub(r'叫我', '请', task_content)
    task_content = re.sub(r'告诉我', '请', task_content)
    task_content = task_content.strip()
    
    if not task_content or task_content == '请':
        task_content = "该执行之前设置的任务了"
    
    return {"time": time_str, "content": task_content, "chat_id": chat_id}

def schedule_task(chat_id, task_time, task_content, persona=None):
    add_scheduled_task(chat_id, task_time, task_content, persona)

def check_and_execute_tasks():
    import logging
    logger = logging.getLogger('GracyBot-Scheduler')
    logger.debug("⏰ 定时任务检查器已启动")
    
    executed_tasks = set()
    
    while True:
        try:
            current_time = datetime.now().strftime("%H:%M")
            tasks = get_scheduled_tasks()
            
            if tasks:
                logger.debug(f"[定时检查] 当前时间: {current_time}, 待执行任务数: {len(tasks)}")
            
            for task_id, chat_id, task_time, task_content, persona in tasks:
                if task_time == current_time and task_id not in executed_tasks:
                    logger.info(f"[定时任务] 执行任务 #{task_id}: {task_time} - {task_content}")
                    disable_task(task_id)
                    executed_tasks.add(task_id)
                    execute_task(chat_id, task_content, persona)
                    logger.info(f"[定时任务] 任务 #{task_id} 执行完成")
            
            executed_tasks = {tid for tid in executed_tasks if tid < max([t[0] for t in tasks], default=0) - 100}
            
            time.sleep(10)
        except Exception as e:
            logger.error(f"[定时任务] 检查异常: {str(e)}")
            time.sleep(30)

def execute_task(chat_id, task_content, persona):
    config = load_config()
    personas = get_personas()
    if "默认人设" not in personas:
        personas["默认人设"] = config.get("default_persona", "")
    
    if persona and persona in personas:
        persona_content = personas[persona]
    else:
        current_persona = get_current_persona(chat_id)
        persona_content = personas.get(current_persona, personas["默认人设"])
    
    system_prompt = f"{persona_content}\n\n【定时提醒任务】\n任务内容：{task_content}\n\n要求：\n1. 发送一条简洁友好的提醒消息（不超过50字）\n2. 不要分段，不要发送多条消息\n3. 可以包含emoji和温馨提示"
    
    current_time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "system", "content": f"【重要】当前准确时间是：{current_time_str}"},
        {"role": "user", "content": f"现在到了提醒时间，请提醒我：{task_content}"}
    ]
    
    reply = call_llm_api(messages, config)
    
    chat_type, target_id = chat_id.split("_", 1)
    
    try:
        from core.gracy_adapter.send import gracy_send_msg
        from core.gracy_adapter.message import GracyText
        gracy_send_msg(target_id, GracyText(text=reply), chat_type=chat_type)
    except:
        pass

def start_scheduler():
    thread = threading.Thread(target=check_and_execute_tasks, daemon=True)
    thread.start()
