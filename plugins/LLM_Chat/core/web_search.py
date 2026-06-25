import logging
from typing import Optional

from .api_handler import load_config

_logger = logging.getLogger("Gracy.LLMChat.web_search")

_client = None


def _get_client():
    global _client
    if _client is None:
        from tavily import TavilyClient
        cfg = load_config()
        key = cfg.get("tavily_api_key", "")
        if not key:
            raise ValueError("Tavily API Key 未配置，请在配置文件中设置 tavily_api_key")
        _client = TavilyClient(key)
    return _client


def search_web(query: str, max_results: int = 5) -> Optional[str]:
    try:
        client = _get_client()
        _logger.info(f"[联网] 搜索: {query}")
        result = client.search(query, max_results=max_results)
        results = result.get("results", [])
        if not results:
            return None

        lines = [f"📡 联网搜索结果 ({len(results)}条):\n"]
        for i, r in enumerate(results, 1):
            title = r.get("title", "无标题")
            content = r.get("content", "")
            url = r.get("url", "")
            lines.append(f"{i}. {title}")
            if content:
                lines.append(f"   {content[:200]}")
            lines.append(f"   来源: {url}")
            lines.append("")
        return "\n".join(lines)
    except Exception as e:
        _logger.error(f"[联网] 搜索失败: {e}", exc_info=True)
        return f"❌ 联网搜索失败: {e}"


def extract_urls(urls: list[str]) -> Optional[str]:
    try:
        client = _get_client()
        _logger.info(f"[联网] 提取页面: {urls}")
        extracted = client.extract(urls=urls)
        results = extracted.get("results", [])
        if not results:
            return None

        lines = ["📄 页面内容提取:\n"]
        for r in results:
            title = r.get("title", "无标题")
            content = r.get("raw_content", "") or r.get("content", "")
            url = r.get("url", "")
            lines.append(f"## {title}")
            lines.append(f"来源: {url}")
            if content:
                lines.append(content[:2000])
            lines.append("")
        return "\n".join(lines)
    except Exception as e:
        _logger.error(f"[联网] 提取失败: {e}", exc_info=True)
        return f"❌ 页面提取失败: {e}"
