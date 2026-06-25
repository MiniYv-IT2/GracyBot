"""
绘图渲染模块 — 搜索列表 / 歌曲详情卡片

支持：
  - 随机背景图（data/background/ 目录）
  - 无背景时使用默认渐变背景
  - 搜索歌单列表绘制
  - 单曲详情卡片绘制
"""
import io
import os
import secrets
import logging
from typing import List, Optional

import httpx
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from core.config import BOT_VERSION
from .api import SearchItem, SongPlayData

_logger = logging.getLogger("Gracy.Music")

# ── 路径 ──
PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PLUGIN_DIR, "data")
BACKGROUND_DIR = os.path.join(DATA_DIR, "background")

# 共享字体资源
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_RES = os.path.join(_ROOT, "style", "resource")
FONT_PATH = os.path.join(_RES, "DouyinSansBold.otf")
_DEFAULT_FONT = os.path.join(_RES, "DouyinSansBold.otf")

# ── 尺寸常量 ──
IMG_WIDTH = 800
PADDING = 30
CARD_RADIUS = 16
SUPPORTED_BG_FORMATS = ('.jpg', '.jpeg', '.png', '.webp', '.bmp')

# ── 配色 ──
COLOR_PRIMARY = (219, 112, 147)      # 粉玫瑰色（主色）
COLOR_ACCENT = (255, 182, 193)       # 浅粉色（高亮）
COLOR_TEXT_MAIN = (255, 255, 255)    # 白色文字
COLOR_TEXT_SECONDARY = (220, 220, 220)
COLOR_TEXT_DIM = (180, 180, 180)
COLOR_CARD_BG = (255, 255, 255)      # 卡片白色背景
COLOR_CARD_BORDER = (219, 112, 147)  # 卡片边框
COLOR_INDEX_BG = (219, 112, 147)     # 序号底色


# ── 字体工具 ──

def _load_font(size: int) -> ImageFont.FreeTypeFont:
    """加载字体，失败时回退默认"""
    try:
        if os.path.exists(FONT_PATH):
            return ImageFont.truetype(FONT_PATH, size)
    except Exception:
        pass
    return ImageFont.load_default()


# ── 背景工具 ──

def _load_random_background(target_w: int, target_h: int) -> Optional[Image.Image]:
    """从 data/background/ 随机加载一张背景图，等比居中裁剪"""
    if not os.path.isdir(BACKGROUND_DIR):
        return None
    try:
        files = [f for f in os.listdir(BACKGROUND_DIR)
                 if f.lower().endswith(SUPPORTED_BG_FORMATS)]
        if not files:
            return None
        chosen = secrets.choice(files)
        bg_path = os.path.join(BACKGROUND_DIR, chosen)
        _logger.info(f"[绘图] 随机背景图：{chosen}（共{len(files)}张可选）")

        bg = Image.open(bg_path).convert("RGB")
        bw, bh = bg.size
        scale = max(target_w / bw, target_h / bh)
        nw, nh = int(bw * scale), int(bh * scale)
        bg = bg.resize((nw, nh), Image.Resampling.LANCZOS)
        left = (nw - target_w) // 2
        top = (nh - target_h) // 2
        bg = bg.crop((left, top, left + target_w, top + target_h))
        # 高斯模糊半透明蒙层，让文字更清晰
        overlay = Image.new("RGB", (target_w, target_h), (20, 20, 30))
        bg = Image.blend(bg, overlay, 0.35)
        return bg
    except Exception as e:
        _logger.warning(f"[绘图] 背景图加载失败：{e}")
        return None


def _create_default_background(w: int, h: int) -> Image.Image:
    """创建默认渐变背景（粉紫渐变）"""
    img = Image.new("RGB", (w, h), (28, 28, 40))
    draw = ImageDraw.Draw(img)
    for y in range(h):
        ratio = y / h
        r = int(28 + (219 - 28) * ratio * 0.3)
        g = int(28 + (112 - 28) * ratio * 0.3)
        b = int(40 + (147 - 40) * ratio * 0.3)
        draw.line([(0, y), (w, y)], fill=(r, g, b))
    return img


# ── 圆角矩形工具 ──

def _round_rect(draw: ImageDraw.ImageDraw, xy, radius: int, fill=None, outline=None, width=1):
    """绘制圆角矩形"""
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 公开绘图函数
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def draw_search_results(results: List[SearchItem], keyword: str) -> str:
    """绘制搜索结果列表"""
    item_h = 70
    spacing = 12
    card_start_y = 140
    footer_h = 60
    list_h = card_start_y + len(results) * (item_h + spacing) + footer_h + PADDING
    w = IMG_WIDTH
    h = max(list_h, 900)

    # 1. 背景
    bg = _load_random_background(w, h)
    if bg is None:
        bg = _create_default_background(w, h)
    draw = ImageDraw.Draw(bg)

    # 2. 字体
    font_title = _load_font(36)
    font_subtitle = _load_font(22)
    font_song = _load_font(26)
    font_singer = _load_font(20)
    font_index = _load_font(22)
    font_footer = _load_font(16)

    # 3. 标题区
    title_y = 50
    draw.text((PADDING, title_y), f"🎵 搜索: {keyword}", font=font_title, fill=COLOR_TEXT_MAIN)
    draw.text((PADDING, title_y + 50), f"共找到 {len(results)} 首", font=font_subtitle, fill=COLOR_TEXT_SECONDARY)

    # 4. 歌单卡片
    card_x = PADDING
    card_w = w - PADDING * 2

    for i, song in enumerate(results):
        cy = card_start_y + i * (item_h + spacing)

        # 卡片背景（深色半透明效果）
        _round_rect(draw, (card_x, cy, card_x + card_w, cy + item_h),
                    radius=CARD_RADIUS, fill=(50, 50, 70))

        # 序号圆圈
        circle_x = card_x + 20
        circle_y = cy + (item_h - 34) // 2
        draw.ellipse((circle_x, circle_y, circle_x + 34, circle_y + 34),
                     fill=COLOR_PRIMARY)
        idx_text = str(song.idx)
        ib = draw.textbbox((0, 0), idx_text, font=font_index)
        iw = ib[2] - ib[0]
        ih = ib[3] - ib[1]
        draw.text((circle_x + (34 - iw) // 2, circle_y + (34 - ih) // 2),
                  idx_text, font=font_index, fill=(255, 255, 255))

        # 歌名
        name_x = circle_x + 50
        draw.text((name_x, cy + 8), song.name, font=font_song, fill=COLOR_TEXT_MAIN)

        # 歌手
        draw.text((name_x, cy + 40), song.artist, font=font_singer, fill=COLOR_TEXT_SECONDARY)

        # 分隔线（最后一项不画）
        if i < len(results) - 1:
            line_y = cy + item_h - 1
            draw.line([(card_x + 20, line_y), (card_x + card_w - 20, line_y)],
                      fill=(255, 255, 255, 40))

    # 5. 底部提示
    footer_y = h - 60
    draw.text((PADDING, footer_y), "💡 发送 /选择 编号 查看歌曲详情", font=font_footer, fill=COLOR_TEXT_DIM)
    # 右下角版本信息
    ver = BOT_VERSION.removeprefix("v")
    footer_text = f"Created By GracyBot v{ver}"
    fb = draw.textbbox((0, 0), footer_text, font=font_footer)
    fw = fb[2] - fb[0]
    draw.text((w - PADDING - fw, footer_y), footer_text, font=font_footer, fill=COLOR_TEXT_DIM)

    # 6. 保存
    out_dir = os.path.join(DATA_DIR, "cache")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "search_results.png")
    bg.save(out_path, "PNG")
    _logger.info(f"[绘图] 搜索结果图已保存: {out_path}")
    return out_path


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list:
    """按像素宽度换行文本，返回行列表"""
    lines = []
    for char in text:
        if not lines:
            lines.append(char)
        else:
            test_line = lines[-1] + char
            tb = font.getbbox(test_line)
            if tb[2] - tb[0] <= max_width:
                lines[-1] = test_line
            else:
                lines.append(char)
    return lines


def draw_song_detail(song: SongPlayData) -> str:
    """绘制单曲详情卡片（自适应高度）"""
    # ── 准备工作：计算每个区域的高度 ──
    font_title = _load_font(38)
    font_singer_tag = _load_font(24)
    font_url_label = _load_font(18)
    font_url = _load_font(16)
    font_footer = _load_font(16)
    font_lrc = _load_font(16)

    cover_size = 180
    cover_area_h = 60 + cover_size + 30  # cover_y + cover_size + margin

    # URL 区域
    card_pad_x = PADDING
    card_w = IMG_WIDTH - PADDING * 2
    url_content_w = card_w - 50  # 25px padding each side
    url_y_offset = 40
    url_area_h = 20 + url_y_offset + 20  # title + spacing + bottom pad

    if song.music_url:
        url_lines = _wrap_text(song.music_url, font_url, url_content_w)
        url_area_h += len(url_lines) * 22 + 24  # lines + "(复制到浏览器打开)" hint
    else:
        url_area_h += 22  # "暂无可用链接"

    # 歌词区域
    lrc_area_h = 0
    if song.lyric:
        lrc_lines_all = [l for l in song.lyric.split("\n") if l.strip()]
        lrc_area_h = 30  # title
        for line in lrc_lines_all:
            clean = line.split("]", 1)[-1].strip() if "]" in line else line.strip()
            if clean:
                # 检查是否需要换行
                tb = font_lrc.getbbox(clean)
                if tb[2] - tb[0] > url_content_w - 5:
                    # 需要换行
                    sub_lines = _wrap_text(clean, font_lrc, url_content_w - 5)
                    lrc_area_h += len(sub_lines) * 24
                else:
                    lrc_area_h += 24

    # 底部提示
    footer_h = 50

    total_h = cover_area_h + 20 + url_area_h + 20 + lrc_area_h + 30 + footer_h
    total_h = max(total_h, 600)

    w = IMG_WIDTH
    h = total_h

    # ── 1. 背景 ──
    bg = _load_random_background(w, h)
    if bg is None:
        bg = _create_default_background(w, h)
    draw = ImageDraw.Draw(bg)

    # ── 2. 封面图 ──
    cover_img = None
    if song.cover_url:
        try:
            resp = httpx.get(song.cover_url.replace("R800x800", "R300x300"), timeout=5)
            if resp.status_code == 200:
                cover_img = Image.open(io.BytesIO(resp.content)).convert("RGB")
        except Exception:
            pass

    cover_x = PADDING + 20
    cover_y = 60

    if cover_img:
        cover_img = cover_img.resize((cover_size, cover_size), Image.Resampling.LANCZOS)
        mask = Image.new("L", (cover_size, cover_size), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle((0, 0, cover_size, cover_size), radius=12, fill=255)
        rounded = Image.new("RGBA", (cover_size, cover_size))
        rounded.paste(cover_img, (0, 0), mask)
        bg.paste(rounded, (cover_x, cover_y), rounded)
    else:
        _round_rect(draw, (cover_x, cover_y, cover_x + cover_size, cover_y + cover_size),
                    radius=12, fill=COLOR_PRIMARY)
        placeholder_text = "🎵"
        pt_font = _load_font(60)
        pb = draw.textbbox((0, 0), placeholder_text, font=pt_font)
        pw = pb[2] - pb[0]
        ph = pb[3] - pb[1]
        draw.text((cover_x + (cover_size - pw) // 2, cover_y + (cover_size - ph) // 2),
                  placeholder_text, font=pt_font, fill=(255, 255, 255))

    # 右侧歌曲信息
    info_x = cover_x + cover_size + 30
    info_y = cover_y + 10
    draw.text((info_x, info_y), song.name, font=font_title, fill=COLOR_TEXT_MAIN)
    draw.text((info_x, info_y + 50), f"歌手: {song.artist}", font=font_singer_tag, fill=COLOR_ACCENT)

    # ── 3. 播放链接卡片 ──
    url_card_y = cover_y + cover_size + 40
    url_card_x = PADDING
    url_card_w = w - PADDING * 2
    # 计算 URL 卡片实际高度
    url_card_h = 20 + url_y_offset + 20  # title + spacing + bottom pad
    if song.music_url:
        url_lines = _wrap_text(song.music_url, font_url, url_content_w)
        url_card_h += len(url_lines) * 22 + 24
    else:
        url_card_h += 22

    _round_rect(draw, (url_card_x, url_card_y, url_card_x + url_card_w, url_card_y + url_card_h),
                radius=CARD_RADIUS, fill=(50, 50, 70))

    url_title_y = url_card_y + 20
    draw.text((url_card_x + 25, url_title_y), "📥 MP3 播放链接", font=font_url_label, fill=COLOR_ACCENT)

    cur_y = url_title_y + url_y_offset
    if song.music_url:
        url_wrap = _wrap_text(song.music_url, font_url, url_content_w)
        for line in url_wrap:
            draw.text((url_card_x + 25, cur_y), line, font=font_url, fill=COLOR_TEXT_SECONDARY)
            cur_y += 22
        draw.text((url_card_x + 25, cur_y), "(复制到浏览器打开)", font=font_footer, fill=COLOR_TEXT_DIM)
        cur_y += 24
    else:
        draw.text((url_card_x + 25, cur_y), "暂无可用链接", font=font_url, fill=COLOR_TEXT_DIM)
        cur_y += 22

    # ── 4. 全部歌词 ──
    if song.lyric:
        lrc_title_y = cur_y + 15
        draw.text((url_card_x + 25, lrc_title_y), "📝 歌词", font=font_url_label, fill=COLOR_ACCENT)

        lrc_lines = [l for l in song.lyric.split("\n") if l.strip()]
        lrc_y = lrc_title_y + 30
        for line in lrc_lines:
            clean = line.split("]", 1)[-1].strip() if "]" in line else line.strip()
            if not clean:
                continue
            # 检查是否需要换行
            tb = font_lrc.getbbox(clean)
            if tb[2] - tb[0] > url_content_w - 5:
                sub_lines = _wrap_text(clean, font_lrc, url_content_w - 5)
                for sl in sub_lines:
                    draw.text((url_card_x + 30, lrc_y), sl, font=font_lrc, fill=COLOR_TEXT_DIM)
                    lrc_y += 24
            else:
                draw.text((url_card_x + 30, lrc_y), clean, font=font_lrc, fill=COLOR_TEXT_DIM)
                lrc_y += 24

    # ── 5. 底部提示 ──
    footer_y = h - 45
    draw.text((PADDING, footer_y), "💡 MP3 链接复制到浏览器即可播放或下载", font=font_footer, fill=COLOR_TEXT_DIM)

    # ── 6. 保存 ──
    out_dir = os.path.join(DATA_DIR, "cache")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "song_detail.png")
    bg.save(out_path, "PNG")
    _logger.info(f"[绘图] 歌曲详情图已保存: {out_path} ({w}x{h})")
    return out_path
