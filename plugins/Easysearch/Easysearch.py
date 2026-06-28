import logging
from graci import gracy_send_msg
from graci import GracyImage, GracyText

from .main import do_search, do_browse
from .core.draw import draw_error

logger = logging.getLogger("Gracy.Easysearch")

ENGINE_ALIASES = {
    "/搜索": None, "搜索": None,
    "/必应搜索": "bing",
    "/百度搜索": "baidu",
    "/谷歌搜索": "google",
    "/搜狗搜索": "sogou",
    "/Yandex搜索": "yandex",
}


def _extract_search(raw_msg: str):
    for cmd, engine in ENGINE_ALIASES.items():
        if raw_msg == cmd:
            return engine, ""
        if raw_msg.startswith(cmd + " "):
            kw = raw_msg[len(cmd):].strip()
            if kw:
                return engine, kw
            return engine, ""
    return None, None


def _extract_browse(raw_msg: str):
    if raw_msg == "/浏览":
        return ""
    if raw_msg.startswith("/浏览 "):
        return raw_msg[4:].strip()
    return None


async def handle_easysearch(self_bot, bot, message, user_id, chat_type, permission, log_func):
    raw_msg = message.get("text", "").strip()
    target_id = str(message.get("raw_data", {}).get("group_id") if chat_type == "group" else user_id)

    engine, query = _extract_search(raw_msg)
    if query is not None:
        if not query:
            await bot(target_id, GracyText(text="❌ 用法：/搜索 关键词\n或：/百度搜索 关键词 /必应搜索 关键词 /谷歌搜索 关键词 /搜狗搜索 关键词 /Yandex搜索 关键词"), chat_type=chat_type)
            return True
        await bot(target_id, GracyText(text=f"🔍 正在搜索: {query}"), chat_type=chat_type)
        result = await do_search(query, engine)
        if result["ok"]:
            await bot(target_id, GracyImage(file_path=result["image_path"]), chat_type=chat_type)
        else:
            img_path = draw_error(result["error"])
            await bot(target_id, GracyImage(file_path=img_path), chat_type=chat_type)
        log_func.info(f"用户{user_id} 搜索: {query} (引擎:{engine or '默认'})")
        return True

    browse_url = _extract_browse(raw_msg)
    if browse_url is not None:
        if not browse_url:
            await bot(target_id, GracyText(text="❌ 用法：/浏览 https://example.com"), chat_type=chat_type)
            return True
        await bot(target_id, GracyText(text=f"🌐 正在浏览..."), chat_type=chat_type)
        result = await do_browse(browse_url)
        if result["ok"]:
            await bot(target_id, GracyImage(file_path=result["image_path"]), chat_type=chat_type)
        else:
            img_path = draw_error(result["error"])
            await bot(target_id, GracyImage(file_path=img_path), chat_type=chat_type)
        log_func.info(f"用户{user_id} 浏览: {browse_url}")
        return True

    return False
