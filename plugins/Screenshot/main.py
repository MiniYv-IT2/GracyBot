import os
import shutil
import logging

from core.config import MASTER_ID
from core.gracy_adapter.send import gracy_send_msg
from core.gracy_adapter.message import GracyImage, GracyText

logger = logging.getLogger("Gracy")

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "image")
SAVE_DIR = os.path.join(DATA_DIR, "saved")

_latest_screenshot = None


def handle_screenshot(self_bot, bot, message, user_id, chat_type, permission, log_func):
    global _latest_screenshot
    raw_msg = message.get("raw_message", "").strip()
    target_id = str(message.get("group_id") if chat_type == "group" else user_id)

    if str(user_id) != str(MASTER_ID):
        gracy_send_msg(target_id, GracyText(text="Permission denied."), chat_type=chat_type)
        return True

    if raw_msg == "/屏幕截图":
        from .capture import capture_screen
        try:
            path = capture_screen()
            _latest_screenshot = path
            gracy_send_msg(target_id, GracyImage(file_path=path), chat_type=chat_type)
            gracy_send_msg(target_id, GracyText(text="Save this screenshot? Reply /保存截图"), chat_type=chat_type)
            logger.info("[插件执行] [Screenshot] Captured: %s", os.path.basename(path))
        except Exception as e:
            logger.error("[插件执行] [Screenshot] Capture failed: %s", str(e))
            gracy_send_msg(target_id, GracyText(text="Screenshot capture failed."), chat_type=chat_type)
        return True

    if raw_msg == "/保存截图":
        if not _latest_screenshot or not os.path.exists(_latest_screenshot):
            gracy_send_msg(target_id, GracyText(text="No screenshot to save."), chat_type=chat_type)
            return True
        try:
            os.makedirs(SAVE_DIR, exist_ok=True)
            filename = os.path.basename(_latest_screenshot)
            dest = os.path.join(SAVE_DIR, filename)
            shutil.copy2(_latest_screenshot, dest)
            logger.info("[插件执行] [Screenshot] Saved: %s", dest)
            gracy_send_msg(target_id, GracyText(text="Screenshot saved to data/image/saved/."), chat_type=chat_type)
        except Exception as e:
            logger.error("[插件执行] [Screenshot] Save failed: %s", str(e))
            gracy_send_msg(target_id, GracyText(text="Save failed."), chat_type=chat_type)
        return True

    return False
