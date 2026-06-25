"""
音乐点歌插件 — 柠柚点歌 API（搜索 + 播放一体化）

命令：
  /点歌 <关键词>  — 搜索歌曲
  /qq音乐 <关键词> — 同上
  /选择 <编号>    — 选中并下载 MP3 发送语音
  /歌曲详情       — 查看上次选中歌曲的详情图
"""
import os
import time
import logging
from typing import Optional

import httpx

from core.decorators import on_command, plugin_handler, PluginContext
from core.gracy_adapter.message import GracyImage, GracyText, GracyVoice
from core.plugin_manager import plugin_manager

from .core.api import search_songs, play_song, SearchItem, SongPlayData
from .core.draw import draw_search_results, draw_song_detail

_logger = logging.getLogger("Gracy.Music")

# ── 会话缓存（内存级，重启即失） ──
_last_search_keyword: str = ""
_last_search_results: list = []
_last_selected_song: Optional[SongPlayData] = None

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


async def _download_mp3(url: str, song_name: str) -> Optional[str]:
    """下载 MP3 到 data/cache/，返回本地路径"""
    try:
        cache_dir = os.path.join(DATA_DIR, "cache")
        os.makedirs(cache_dir, exist_ok=True)

        safe_name = "".join(c if c.isalnum() or c in ('-','_') else '_' for c in song_name)
        local_path = os.path.join(cache_dir, f"{safe_name}.mp3")

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            with open(local_path, "wb") as f:
                f.write(resp.content)

        _logger.info(f"[音频] 下载完成: {local_path} ({len(resp.content)} bytes)")
        return local_path
    except Exception as e:
        _logger.error(f"[音频] 下载失败: {e}", exc_info=True)
        return None


# ── 统一入口，内部按命令分发 ──
@on_command("/点歌", "/qq音乐", "/选择", "/歌曲详情", "/清理缓存")
@plugin_handler
async def handle_music(ctx: PluginContext):
    """音乐点歌 — 搜索 / 播放 / 详情 / 清理缓存"""
    global _last_search_keyword, _last_search_results, _last_selected_song

    cmd = ctx.command

    # ── /点歌 /qq音乐 — 搜索 ──
    if cmd in ("/点歌", "/qq音乐"):
        args = ctx.raw_text[len(cmd):].strip()
        if not args:
            await ctx.reply("❌ 用法：/点歌 <歌曲名>\n示例：/点歌 周深")
            return

        await ctx.reply(f"🔍 正在搜索: {args}")
        try:
            results, pagination = await search_songs(args)
        except Exception as e:
            _logger.error(f"[点歌] 搜索异常: {e}", exc_info=True)
            await ctx.reply(f"❌ 搜索失败：{e}")
            return

        if not results:
            await ctx.reply(f"😅 没有找到「{args}」的相关歌曲")
            return

        _last_search_keyword = args
        _last_search_results = results[:10]

        try:
            img_path = draw_search_results(_last_search_results, args)
        except Exception as e:
            _logger.error(f"[点歌] 绘图异常: {e}", exc_info=True)
            lines = [f"🎵 搜索: {args}\n"]
            for i, s in enumerate(_last_search_results):
                lines.append(f"  {i+1}. {s.name} — {s.artist}")
            lines.append(f"\n💡 发送 /选择 编号 查看详情 (共{len(_last_search_results)}首)")
            await ctx.reply("\n".join(lines))
            return

        await ctx.send(GracyImage(file_path=img_path))
        _logger.info(f"用户{ctx.sender_id} 点歌搜索: {args} ({len(_last_search_results)}首)")
        return

    # ── /选择 N — 选取播放 ──
    if cmd == "/选择":
        if not _last_search_results:
            await ctx.reply("⚠️ 没有搜索记录，请先使用 /点歌 搜索")
            return

        args = ctx.raw_text[len(cmd):].strip()
        if not args or not args.isdigit():
            await ctx.reply("❌ 用法：/选择 <编号>\n示例：/选择 1")
            return

        idx = int(args)
        if idx < 1 or idx > len(_last_search_results):
            await ctx.reply(f"❌ 编号超出范围（1-{len(_last_search_results)}）")
            return

        selected = _last_search_results[idx - 1]
        await ctx.reply(f"📥 正在获取: {selected.name} — {selected.artist}")

        try:
            detail = await play_song(_last_search_keyword, selected.idx)
        except Exception as e:
            _logger.error(f"[选择] 解析异常: {e}", exc_info=True)
            await ctx.reply(f"❌ 获取失败：{e}")
            return

        if detail is None:
            await ctx.reply("❌ 获取失败，请检查 API 密钥是否已配置")
            return

        _last_selected_song = detail

        if detail.music_url:
            await ctx.reply(f"🎵 {detail.name} — {detail.artist}\n⏬ 正在下载 MP3...")
            local_path = await _download_mp3(detail.music_url, detail.name)
            if local_path:
                await ctx.send(GracyVoice(file_path=local_path))
                _logger.info(f"用户{ctx.sender_id} 播放第{idx}首: {selected.name}")
                return

        _logger.warning(f"[选择] 下载失败，降级发详情图")
        try:
            img_path = draw_song_detail(detail)
        except Exception as e:
            _logger.error(f"[选择] 绘图异常: {e}", exc_info=True)
            await ctx.reply(f"🎵 {detail.name}\n歌手: {detail.artist}")
            return

        await ctx.send(GracyImage(file_path=img_path))
        _logger.info(f"用户{ctx.sender_id} 选择了第{idx}首: {selected.name} (无音频)")
        return

    # ── /清理缓存 — 清理过期缓存文件 ──
    if cmd == "/清理缓存":
        cfg = plugin_manager.get_plugin_config("Music_Plugin")
        max_days = cfg.get("cache_max_days", 7)
        cache_dir = os.path.join(DATA_DIR, "cache")
        if not os.path.isdir(cache_dir):
            await ctx.reply("📂 缓存目录不存在，无需清理")
            return

        now = time.time()
        deleted = 0
        kept = 0
        for fname in os.listdir(cache_dir):
            fpath = os.path.join(cache_dir, fname)
            if os.path.isfile(fpath):
                file_age_secs = now - os.path.getmtime(fpath)
                if file_age_secs > max_days * 86400:
                    os.remove(fpath)
                    deleted += 1
                else:
                    kept += 1

        await ctx.reply(
            f"🧹 缓存清理完成\n"
            f"  • 删除过期文件（>{max_days}天）: {deleted} 个\n"
            f"  • 保留有效文件: {kept} 个"
        )
        _logger.info(f"用户{ctx.sender_id} 清理缓存: 删除{deleted}, 保留{kept}")
        return

    # ── /歌曲详情 — 查看详情 ──
    if cmd == "/歌曲详情":
        if _last_selected_song is None:
            await ctx.reply("⚠️ 还没有选过歌曲，请先 /点歌 搜索后再 /选择")
            return

        try:
            img_path = draw_song_detail(_last_selected_song)
        except Exception as e:
            _logger.error(f"[详情] 绘图异常: {e}", exc_info=True)
            d = _last_selected_song
            await ctx.reply(f"🎵 {d.name}\n歌手: {d.artist}")
            return

        await ctx.send(GracyImage(file_path=img_path))
        return
