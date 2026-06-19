import os
import urllib.parse
import sys
import logging
from typing import Dict, Optional
from playwright.async_api import async_playwright, TimeoutError as PwTimeout
from core.plugin_manager import plugin_manager

_logger = logging.getLogger("Gracy.Easysearch")

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(PLUGIN_DIR, "data")

IPHONE_VIEWPORT = {"width": 390, "height": 844}
IPHONE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)
MAX_PAGE_HEIGHT = 4000

COMMON_PROXIES = [
    "http://127.0.0.1:7890",
    "http://127.0.0.1:10809",
    "http://127.0.0.1:1080",
    "http://127.0.0.1:7891",
    "http://127.0.0.1:8118",
]


def _load_config() -> dict:
    """从统一配置系统加载配置"""
    return plugin_manager.get_plugin_config("Easysearch")


def _detect_proxy() -> Optional[Dict[str, str]]:
    # 1. config.json 优先
    cfg = _load_config()
    proxy_url = cfg.get("proxy", "")
    if proxy_url:
        return {"server": proxy_url}
    # 2. 环境变量
    for env_name in ("HTTPS_PROXY", "HTTP_PROXY", "https_proxy", "http_proxy", "ALL_PROXY"):
        val = os.environ.get(env_name, "")
        if val:
            return {"server": val}
    # 3. Windows 系统代理注册表
    if sys.platform == "win32":
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Internet Settings")
            enabled, _ = winreg.QueryValueEx(key, "ProxyEnable")
            if enabled:
                server, _ = winreg.QueryValueEx(key, "ProxyServer")
                winreg.CloseKey(key)
                server = server.strip()
                if "=" in server:
                    server = server.split(";")[0].split("=")[-1].strip()
                if not server.startswith("http"):
                    server = "http://" + server
                return {"server": server}
            winreg.CloseKey(key)
        except Exception:
            pass
    return None


async def _screenshot_page(url: str, wait_ms: int = 3000) -> Optional[str]:
    cfg = _load_config()
    timeout = cfg.get("timeout", 20) * 1000
    proxy = _detect_proxy()
    if proxy:
        _logger.info(f"[截图] 使用代理: {proxy['server']}")

    try:
        async with async_playwright() as pw:
            launch_args = {"headless": True}
            if proxy:
                launch_args["proxy"] = proxy

            browser = await pw.chromium.launch(**launch_args)
            context = await browser.new_context(
                viewport=IPHONE_VIEWPORT,
                user_agent=IPHONE_UA,
                device_scale_factor=2,
                is_mobile=True,
                has_touch=True,
            )
            page = await context.new_page()
            _logger.info(f"[截图] 正在导航至: {url[:60]}...")
            await page.goto(url, timeout=timeout, wait_until="domcontentloaded")
            await page.wait_for_timeout(wait_ms)

            page_height = await page.evaluate("document.body.scrollHeight")
            page_height = min(page_height, MAX_PAGE_HEIGHT)

            path = os.path.join(CACHE_DIR, "browser_screenshot.png")
            os.makedirs(CACHE_DIR, exist_ok=True)
            await page.screenshot(path=path, full_page=False, clip={
                "x": 0, "y": 0,
                "width": IPHONE_VIEWPORT["width"],
                "height": min(page_height, 3000),
            })
            _logger.info(f"[截图] 成功: {path}")
            return path

    except PwTimeout:
        _logger.warning(f"[截图] 超时: {url[:60]}...")
        return None
    except Exception as e:
        _logger.error(f"[截图] 失败: {e}", exc_info=True)
        return None


SEARCH_URLS = {
    "bing": "https://www.bing.com/search?q={query}",
    "baidu": "https://www.baidu.com/s?wd={query}",
    "google": "https://www.google.com/search?q={query}&hl=zh-CN",
    "sogou": "https://www.sogou.com/web?query={query}",
    "yandex": "https://yandex.com/search/?text={query}",
}


async def do_search(query: str, engine: str = None) -> Dict:
    cfg = _load_config()
    if not engine:
        engine = cfg["default_engine"]
    if engine not in SEARCH_URLS:
        return {"ok": False, "error": f"不支持的搜索引擎: {engine}"}

    engine_cn = cfg["engines"].get(engine, {}).get("name", engine)
    url = SEARCH_URLS[engine].format(query=urllib.parse.quote(query))
    path = await _screenshot_page(url)
    if not path:
        return {"ok": False, "error": f"截图失败（{engine_cn}）\n请检查代理配置或网络连接"}
    return {"ok": True, "image_path": path, "engine": engine, "engine_cn": engine_cn, "query": query}


async def do_browse(url: str) -> Dict:
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url
    path = await _screenshot_page(url)
    if not path:
        return {"ok": False, "error": f"无法访问或截图超时: {url}\n请检查代理配置或网络连接"}
    return {"ok": True, "image_path": path, "url": url}
