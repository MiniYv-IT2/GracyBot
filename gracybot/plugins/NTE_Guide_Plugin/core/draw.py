"""
异环攻略插件 - 游戏电竞风绘图模块
"""
import os
import math
from io import BytesIO
from typing import Optional

from PIL import Image, ImageDraw, ImageFont, ImageFilter

from ..config import DATA_DIR, BG_DIR
from .fetcher import fetch_image

# ── 色彩方案（深色电竞风） ──
BG_COLOR = (10, 10, 26)
CARD_BG = (18, 22, 42)
ACCENT_BLUE = (0, 180, 255)
ACCENT_PURPLE = (140, 0, 255)
ACCENT_GOLD = (255, 180, 0)
ACCENT_GREEN = (0, 220, 150)
TEXT_WHITE = (220, 220, 235)
TEXT_GRAY = (140, 140, 170)
TEXT_DIM = (90, 90, 120)
BORDER_COLOR = (40, 45, 70)

# ── 字体 ──
_FONTS = {}
_FONT_DIRS = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "res", "resource", "DouyinSansBold.otf"),
]


def _get_font(size: int, bold: bool = False):
    key = f"{'bold_' if bold else ''}{size}"
    if key not in _FONTS:
        for path in _FONT_DIRS:
            if os.path.exists(path):
                try:
                    _FONTS[key] = ImageFont.truetype(path, size, encoding='unic')
                    break
                except Exception:
                    continue
        if key not in _FONTS:
            _FONTS[key] = ImageFont.load_default()
    return _FONTS[key]


# ── 绘图工具 ──

def _draw_rounded_rect(draw, x1, y1, x2, y2, radius, fill=None, outline=None, width=1):
    """绘制圆角矩形"""
    if radius <= 0:
        draw.rectangle([x1, y1, x2, y2], fill=fill, outline=outline, width=width)
        return
    draw.rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=fill, outline=outline, width=width)


def _draw_bg_gradient(img):
    """绘制深蓝黑渐变背景"""
    w, h = img.size
    draw = ImageDraw.Draw(img)
    for y in range(h):
        r = int(10 + y / h * 12)
        g = int(10 + y / h * 8)
        b = int(26 + y / h * 18)
        draw.line([(0, y), (w, y)], fill=(r, g, b))


def _draw_header_bar(draw, w):
    """顶部标题装饰条"""
    _draw_rounded_rect(draw, 20, 16, w - 20, 66, 10, fill=CARD_BG, outline=ACCENT_BLUE, width=1)
    draw.rectangle([20, 16, w - 20, 22], fill=ACCENT_BLUE)


def _draw_footer(draw, w, h, text="数据来源: nteguide.com"):
    """底部信息栏"""
    _draw_rounded_rect(draw, 20, h - 46, w - 20, h - 16, 8, fill=CARD_BG, outline=BORDER_COLOR, width=1)
    font_s = _get_font(13)
    draw.text((30, h - 38), text, font=font_s, fill=TEXT_DIM)
    # 底部紫色条
    draw.rectangle([20, h - 16, w - 20, h - 14], fill=ACCENT_PURPLE)


def _draw_card(draw, x, y, w, h, accent_color=ACCENT_BLUE):
    """绘制卡片背景"""
    _draw_rounded_rect(draw, x, y, x + w, y + h, 12, fill=CARD_BG, outline=accent_color, width=1)
    draw.rectangle([x, y, x + w, y + 6], fill=accent_color)


def _draw_section_divider(draw, w, y):
    """绘制分区水平分隔线（渐隐效果）"""
    for i in range(8):
        alpha = 30 + i * 20
        draw.line([(30 + i * 10, y), (w - 30 - i * 10, y)],
                  fill=(0 + i * 20, 20 + i * 10, 50 + i * 10))
    # 中心亮点
    draw.line([(w // 2 - 40, y), (w // 2 + 40, y)],
              fill=ACCENT_BLUE, width=1)


def _wrap_text(text, font, max_width, draw):
    """文字自动换行，返回行列表"""
    lines = []
    for paragraph in text.split('\n'):
        if not paragraph:
            lines.append('')
            continue
        chars = list(paragraph)
        line = ''
        for ch in chars:
            test_line = line + ch
            bbox = draw.textbbox((0, 0), test_line, font=font)
            tw = bbox[2] - bbox[0]
            if tw > max_width and line:
                lines.append(line)
                line = ch
            else:
                line = test_line
        if line:
            lines.append(line)
    return lines


# ── 渲染函数 ──

async def draw_navigation() -> Optional[bytes]:
    """绘制/异环导航菜单图"""
    w, h = 800, 520
    img = Image.new('RGB', (w, h), BG_COLOR)
    draw = ImageDraw.Draw(img)

    _draw_bg_gradient(img)

    # 标题
    _draw_header_bar(draw, w)
    title_font = _get_font(28, bold=True)
    draw.text((40, 28), "异环攻略 NTE Guide", font=title_font, fill=ACCENT_BLUE)

    # 卡片菜单
    menus = [
        (ACCENT_BLUE,   "角色图鉴",  "查询角色详情、技能、配装\n输入: /异环角色 <名字>"),
        (ACCENT_GREEN,  "弧盘大全",  "查询武器属性、被动效果\n输入: /异环武器 <名字>"),
        (ACCENT_PURPLE, "升级计算器", "查看等级提升所需材料\n输入: /异环材料 <角色> [等级]"),
        (ACCENT_GOLD,   "兑换码",    "获取最新可用兑换码\n输入: /异环兑换码"),
    ]
    card_w = 175
    card_h = 190
    gap = 20
    total_w = len(menus) * card_w + (len(menus) - 1) * gap
    start_x = (w - total_w) // 2
    card_y = 100

    for i, (accent, title, desc) in enumerate(menus):
        cx = start_x + i * (card_w + gap)
        _draw_card(draw, cx, card_y, card_w, card_h, accent)

        # 图标圆
        icon_cx, icon_cy = cx + card_w // 2, card_y + 50
        draw.ellipse([icon_cx - 28, icon_cy - 28, icon_cx + 28, icon_cy + 28],
                     fill=accent)
        tf = _get_font(22, bold=True)
        draw.text((icon_cx - 10, icon_cy - 12), str(i + 1), font=tf, fill=TEXT_WHITE)

        # 标题
        tf2 = _get_font(17, bold=True)
        draw.text((cx + (card_w - draw.textbbox((0, 0), title, font=tf2)[2]) // 2,
                   card_y + 100), title, font=tf2, fill=TEXT_WHITE)

        # 描述
        sf = _get_font(12)
        desc_lines = desc.split('\n')
        for dy, line in enumerate(desc_lines):
            draw.text((cx + 12, card_y + 128 + dy * 18), line, font=sf, fill=TEXT_GRAY)

    # 底部搜索提示
    _draw_footer(draw, w, h, "输入 /异环搜索 <关键词> 跨分类搜索")
    return _img_to_bytes(img)


async def draw_character_detail(data: dict) -> Optional[bytes]:
    """绘制角色详情图"""
    name = data.get("name", data.get("slug", "未知"))
    rarity = data.get("rarity", "?")
    attr = data.get("attr", "?")
    role = data.get("role", "?")
    faction = data.get("faction", "?")
    cn_va = data.get("cn_va", "?")
    jp_va = data.get("jp_va", "?")
    tier = data.get("tier", "")
    skills = data.get("skills", [])
    passives = data.get("passives", [])
    gear = data.get("gear", {})
    if isinstance(gear, str):
        gear = {"_raw": gear}
    materials = data.get("materials", [])
    teams = data.get("teams", [])
    introduction = data.get("introduction", "")
    rating_desc = data.get("rating_desc", "")
    role_detail = data.get("role_detail", "")

    # ── 计算图片高度 ──
    content_h = 100  # header 区域

    # 角色图片（右） + 信息（左），取较大者
    img_url = data.get("img_url", "")
    has_img = bool(img_url)
    content_h = max(content_h, 90 + 260 + 20)  # 图片区域

    # 信息: 4行 × 22px = 88
    content_h = max(content_h, 90 + 4 * 22)

    # 评级描述
    if rating_desc:
        content_h += 42  # 一行描述

    # 介绍
    if introduction:
        content_h += 54  # 两行介绍

    # 分隔线
    content_h += 20

    # 技能区: 标题 + 3个技能条
    content_h += 30
    if skills:
        for sk in skills[:3]:
            content_h += (52 if sk.get("desc") else 34) + 6

    content_h += 30  # 间距

    # 被动区
    content_h += 30
    if passives:
        content_h += 24 + len(passives[:4]) * 24

    content_h += 30  # 间距

    # 配装区
    content_h += 30  # 标题
    has_gear = gear.get("best_weapon") or gear.get("disk_set") or gear.get("main_stats")
    if has_gear:
        content_h += 24 * 4  # 最多4项
    else:
        content_h += 0

    content_h += 30  # 间距

    # 材料区
    content_h += 30
    if materials:
        content_h += 24 + len(materials[:6]) * 24

    # 配队区
    content_h += 20  # 分隔线 + 间距
    if teams:
        content_h += 34  # 标题行 + 下划线
        content_h += len(teams[:2]) * 56  # 每个队伍卡片
    content_h += 10  # footer前间距

    content_h += 80  # 底部留白 + footer

    h = max(700, content_h)
    w = 800

    # ── 开始绘制 ──
    img = Image.new('RGB', (w, h), BG_COLOR)
    draw = ImageDraw.Draw(img)
    _draw_bg_gradient(img)

    section_font = _get_font(16, bold=True)
    body_font = _get_font(14)
    small_font = _get_font(13)

    y = 20

    # ═══════════ 标题栏 ═══════════
    _draw_header_bar(draw, w)
    title_font = _get_font(26, bold=True)
    subtitle_font = _get_font(14)
    draw.text((40, 24), f"{name}", font=title_font, fill=TEXT_WHITE)

    # 稀有度+属性+定位 标签（标题右侧）
    tag_x = 40 + draw.textbbox((0, 0), name, font=title_font)[2] + 12
    tag_y = 27
    for tag, color in [(rarity, ACCENT_GOLD), (attr, ACCENT_BLUE), (role, ACCENT_GREEN)]:
        tw = draw.textbbox((0, 0), tag, font=subtitle_font)[2] + 16
        _draw_rounded_rect(draw, tag_x, tag_y, tag_x + tw, tag_y + 22, 4, fill=color)
        draw.text((tag_x + 8, tag_y + 3), tag, font=subtitle_font, fill=(255, 255, 255))
        tag_x += tw + 8

    # 评级（标题栏第二行）
    if tier:
        draw.text((40, 56), f"评级: {tier}", font=_get_font(13), fill=ACCENT_GOLD)

    y = 90

    # ═══════════ 角色图片 + 基本信息 ═══════════
    if img_url:
        img_bytes = await fetch_image(img_url)
        if img_bytes:
            try:
                char_img = Image.open(BytesIO(img_bytes)).convert("RGBA")
                max_h = 260
                ratio = min(max_h / char_img.height, 260 / char_img.width)
                new_size = (int(char_img.width * ratio), int(char_img.height * ratio))
                char_img = char_img.resize(new_size, Image.LANCZOS)
                px, py = w - new_size[0] - 30, y
                img.paste(char_img, (px, py), char_img)
                # 角色图片左边框装饰线
                draw.line([(px - 10, py), (px - 10, py + new_size[1])],
                          fill=ACCENT_BLUE, width=2)
            except Exception:
                pass

    # 基本信息（左列）
    info_x = 30
    info_items = [
        ("阵营", faction),
        ("中文配音", cn_va),
        ("日文配音", jp_va),
        ("武器类型", data.get("weapon_type", "?")),
    ]
    for k, v in info_items:
        draw.text((info_x, y), f"{k}: {v}", font=body_font, fill=TEXT_GRAY)
        y += 22

    # 对齐到图片底部 + 间距
    y = max(y, 90 + 260 + 20)

    # 评级描述
    if rating_desc:
        _draw_rounded_rect(draw, 30, y, w - 30, y + 36, 6, fill=(15, 25, 45), outline=ACCENT_GOLD, width=1)
        draw.text((45, y + 8), f"评级: {rating_desc}", font=_get_font(13), fill=ACCENT_GOLD)
        y += 44

    # 角色介绍
    if introduction:
        intro_font = _get_font(13)
        intro_lines = _wrap_text(f"「{introduction}」", intro_font, w - 80, draw)
        _draw_rounded_rect(draw, 30, y, w - 30, y + 26 + min(len(intro_lines), 3) * 18,
                           6, fill=(15, 22, 38), outline=BORDER_COLOR, width=1)
        for li, line in enumerate(intro_lines[:3]):
            draw.text((45, y + 6 + li * 18), line, font=intro_font, fill=TEXT_GRAY)
        y += 28 + min(len(intro_lines), 3) * 18

    y += 10

    # ═══════════ 分隔线 ═══════════
    _draw_section_divider(draw, w, y)
    y += 10

    # ═══════════ 技能 ═══════════
    if skills:
        draw.text((30, y), "技能", font=section_font, fill=ACCENT_BLUE)
        # 标题下装饰短横线
        draw.rectangle([30, y + 24, 80, y + 26], fill=ACCENT_BLUE)
        y += 34

        for sk in skills[:3]:
            skill_h = 52 if sk.get("desc") else 34
            _draw_rounded_rect(draw, 30, y, w - 30, y + skill_h, 6, fill=CARD_BG, outline=BORDER_COLOR, width=1)
            # 技能类型标签
            type_colors = {"普攻": ACCENT_GREEN, "战技": ACCENT_PURPLE, "终结技": ACCENT_GOLD}
            tc = type_colors.get(sk["type"], ACCENT_BLUE)
            _draw_rounded_rect(draw, 42, y + 4, 42 + 48, y + skill_h - 4, 4, fill=tc)
            f10 = _get_font(12, bold=True)
            draw.text((46, y + 8), sk["type"], font=f10, fill=(255, 255, 255))
            # 技能名称
            draw.text((100, y + 7), sk["name"], font=_get_font(14, bold=True), fill=TEXT_WHITE)
            # 技能描述
            if sk.get("desc"):
                desc_font = _get_font(12)
                desc_text = sk["desc"][:60]
                draw.text((100, y + 28), desc_text, font=desc_font, fill=TEXT_GRAY)
            y += skill_h + 6

    y += 10

    # ═══════════ 分隔线 ═══════════
    _draw_section_divider(draw, w, y)
    y += 10

    # ═══════════ 被动天赋 ═══════════
    if passives:
        draw.text((30, y), "被动天赋", font=section_font, fill=ACCENT_GREEN)
        draw.rectangle([30, y + 24, 80, y + 26], fill=ACCENT_GREEN)
        y += 34

        for p in passives[:4]:
            _draw_rounded_rect(draw, 30, y, w - 30, y + 26, 6, fill=(15, 25, 35), outline=BORDER_COLOR, width=1)
            # 小菱形图标
            cx, cy = 46, y + 13
            draw.polygon([(cx, cy - 4), (cx + 4, cy), (cx, cy + 4), (cx - 4, cy)],
                         fill=ACCENT_GREEN)
            draw.text((58, y + 4), p.replace("◆", "").strip(), font=body_font, fill=TEXT_WHITE)
            y += 30

    y += 10

    # ═══════════ 分隔线 ═══════════
    _draw_section_divider(draw, w, y)
    y += 10

    # ═══════════ 配装推荐 ═══════════
    if has_gear:
        draw.text((30, y), "推荐配装", font=section_font, fill=ACCENT_BLUE)
        draw.rectangle([30, y + 24, 80, y + 26], fill=ACCENT_BLUE)
        y += 34

        gear_items = []
        if gear.get("best_weapon"):
            gear_items.append(("最佳武器", gear["best_weapon"], ACCENT_GOLD))
        if gear.get("disk_set"):
            gear_items.append(("磁盘套装", gear["disk_set"], ACCENT_PURPLE))
        if gear.get("main_stats"):
            gear_items.append(("主词条", gear["main_stats"], ACCENT_GREEN))
        if gear.get("sub_stats"):
            gear_items.append(("副词条", gear["sub_stats"], ACCENT_BLUE))

        for g_label, g_val, g_color in gear_items:
            _draw_rounded_rect(draw, 30, y, w - 30, y + 28, 6, fill=CARD_BG, outline=BORDER_COLOR, width=1)
            # 标签
            _draw_rounded_rect(draw, 42, y + 3, 42 + 68, y + 25, 4, fill=g_color)
            draw.text((46, y + 5), g_label, font=_get_font(12, bold=True), fill=(255, 255, 255))
            # 数值
            draw.text((120, y + 5), g_val[:55], font=_get_font(13), fill=TEXT_WHITE)
            y += 32

    y += 10

    # ═══════════ 分隔线 ═══════════
    _draw_section_divider(draw, w, y)
    y += 10

    # ═══════════ 升级材料 ═══════════
    if materials:
        draw.text((30, y), "升级材料", font=section_font, fill=ACCENT_GOLD)
        draw.rectangle([30, y + 24, 80, y + 26], fill=ACCENT_GOLD)
        y += 34

        for m in materials[:6]:
            _draw_rounded_rect(draw, 30, y, w - 30, y + 28, 6, fill=CARD_BG, outline=BORDER_COLOR, width=1)
            # 等级标签
            label = m["level"].replace("等级", "")
            _draw_rounded_rect(draw, 42, y + 3, 42 + 60, y + 25, 4, fill=ACCENT_BLUE)
            draw.text((46, y + 5), label, font=_get_font(12, bold=True), fill=(255, 255, 255))
            # 材料详情
            draw.text((112, y + 5), m["materials"][:55], font=_get_font(13), fill=TEXT_WHITE)
            y += 32

    y += 10

    # ═══════════ 分隔线 ═══════════
    _draw_section_divider(draw, w, y)
    y += 10

    # ═══════════ 推荐配队 ═══════════
    if teams:
        draw.text((30, y), "推荐配队", font=section_font, fill=ACCENT_PURPLE)
        draw.rectangle([30, y + 24, 80, y + 26], fill=ACCENT_PURPLE)
        y += 34

        for team in teams[:2]:
            # 队伍卡片
            _draw_rounded_rect(draw, 30, y, w - 30, y + 52, 8, fill=CARD_BG, outline=BORDER_COLOR, width=1)
            # 队伍名
            draw.text((45, y + 4), team["name"], font=_get_font(15, bold=True), fill=TEXT_WHITE)
            # 成员列表
            members_text = " / ".join(team["members"])
            draw.text((45, y + 28), members_text, font=_get_font(13), fill=ACCENT_GOLD)
            y += 56

    y += 10

    # ═══════════ 底部 ═══════════
    _draw_footer(draw, w, h, f"输入 /异环武器 {name} 查看推荐弧盘")
    return _img_to_bytes(img)


async def draw_weapon_detail(data: dict) -> Optional[bytes]:
    """绘制武器/弧盘详情图"""
    name = data.get("name", data.get("slug", "未知"))
    rarity = data.get("rarity", "?")
    atk_val = data.get("atk", "?")
    sub_stat = data.get("sub_stat", "")
    weapon_type = data.get("type", "?")
    acquisition = data.get("acquisition", "")
    effect_name = data.get("effect_name", "")
    effect_desc = data.get("effect_desc", "")
    compatible_list = data.get("compatible_chars_list", [])
    img_url = data.get("img_url", "")

    # 动态高度
    content_h = 100
    content_h += 150  # ATK 区 + 图片
    content_h += 30
    if effect_desc:
        content_h += 70  # 效果区
    content_h += 30
    if compatible_list:
        content_h += 30 + min(len(compatible_list), 9) * 24
    if acquisition:
        content_h += 50
    content_h += 80

    h = max(550, content_h)
    w = 700

    img = Image.new('RGB', (w, h), BG_COLOR)
    draw = ImageDraw.Draw(img)
    _draw_bg_gradient(img)

    _draw_header_bar(draw, w)
    title_font = _get_font(26, bold=True)
    section_font = _get_font(16, bold=True)
    body_font = _get_font(14)
    small_font = _get_font(13)

    # 稀有度标签在标题栏
    draw.text((40, 24), f"弧盘: {name}", font=title_font, fill=TEXT_WHITE)
    if rarity:
        rt = draw.textbbox((0, 0), f"弧盘: {name}", font=title_font)
        tag_x = 40 + rt[2] - rt[0] + 10
        rw = draw.textbbox((0, 0), rarity, font=_get_font(14))[2] + 16
        _draw_rounded_rect(draw, tag_x, 27, tag_x + rw, 49, 4, fill=ACCENT_GOLD)
        draw.text((tag_x + 8, 30), rarity, font=_get_font(14), fill=(255, 255, 255))

    y = 90

    # ═══════════ ATK + 图片 + 属性 ═══════════
    # 左侧大 ATK 显示
    _draw_rounded_rect(draw, 30, y, 195, y + 130, 10, fill=CARD_BG, outline=ACCENT_BLUE, width=1)
    draw.text((50, y + 12), "ATK", font=_get_font(14), fill=TEXT_DIM)
    atk_font = _get_font(36, bold=True)
    draw.text((50, y + 36), str(atk_val), font=atk_font, fill=TEXT_WHITE)
    # 副属性
    if sub_stat:
        draw.text((50, y + 80), sub_stat, font=_get_font(13), fill=ACCENT_GREEN)

    # 中间位置：武器图片
    if img_url:
        wp_img_bytes = await fetch_image(img_url)
        if wp_img_bytes:
            try:
                wp_img = Image.open(BytesIO(wp_img_bytes)).convert("RGBA")
                wp_img = wp_img.resize((100, 100), Image.LANCZOS)
                ix = 240
                iy = y + 15
                # 图片背景卡片
                _draw_rounded_rect(draw, ix - 10, iy - 10, ix + 110, iy + 110, 8, fill=CARD_BG, outline=BORDER_COLOR, width=1)
                img.paste(wp_img, (ix, iy), wp_img)
            except Exception:
                pass

    # 右侧属性详情
    info_x = 370
    info_items = []
    if weapon_type:
        info_items.append(("类型", weapon_type))
    if sub_stat:
        pass  # 已显示

    for k, v in [("类型", weapon_type)]:
        draw.text((info_x, y + 20), f"{k}: {v}", font=body_font, fill=TEXT_GRAY)
        y += 28

    # 获取方式
    if acquisition:
        draw.text((info_x, y + 20), f"获取: {acquisition[:40]}", font=body_font, fill=TEXT_GRAY)

    y = 90 + 140

    # ═══════════ 弧盘效果 ═══════════
    if effect_name or effect_desc:
        _draw_section_divider(draw, w, y)
        y += 10

        draw.text((30, y), "弧盘效果", font=section_font, fill=ACCENT_PURPLE)
        draw.rectangle([30, y + 24, 80, y + 26], fill=ACCENT_PURPLE)
        y += 34

        # 效果名卡片
        if effect_name:
            _draw_rounded_rect(draw, 30, y, w - 30, y + 30, 6, fill=CARD_BG, outline=ACCENT_PURPLE, width=1)
            draw.text((45, y + 5), effect_name, font=_get_font(15, bold=True), fill=TEXT_WHITE)
            y += 36

        # 效果描述
        if effect_desc:
            desc_font = _get_font(13)
            desc_lines = _wrap_text(effect_desc, desc_font, w - 80, draw)
            for li, line in enumerate(desc_lines[:4]):
                draw.text((45, y + li * 20), line, font=desc_font, fill=TEXT_GRAY)
            y += max(30, len(desc_lines[:4]) * 20 + 10)

    # ═══════════ 适配角色 ═══════════
    if compatible_list:
        _draw_section_divider(draw, w, y)
        y += 10

        draw.text((30, y), "适配角色", font=section_font, fill=ACCENT_BLUE)
        draw.rectangle([30, y + 24, 80, y + 26], fill=ACCENT_BLUE)
        y += 34

        # 角色网格
        _draw_rounded_rect(draw, 30, y, w - 30, y + min(len(compatible_list), 9) * 24 + 14,
                           8, fill=CARD_BG, outline=BORDER_COLOR, width=1)
        for i, cname in enumerate(compatible_list[:9]):
            draw.text((45, y + 8 + i * 24), f"● {cname}", font=body_font, fill=TEXT_WHITE)
        y += min(len(compatible_list), 9) * 24 + 22

    y += 10
    _draw_footer(draw, w, h, "数据来源: nteguide.com")
    return _img_to_bytes(img)


async def draw_leveling_materials(data: dict, level_ranges: list) -> Optional[bytes]:
    """绘制升级材料图"""
    name = data.get("name", data.get("slug", "未知"))

    y = 90
    m_font = _get_font(14)

    if level_ranges:
        y += len(level_ranges[:8]) * 42
    else:
        y += 30

    h = max(500, y + 60)
    w = 700

    img = Image.new('RGB', (w, h), BG_COLOR)
    draw = ImageDraw.Draw(img)
    _draw_bg_gradient(img)

    _draw_header_bar(draw, w)
    title_font = _get_font(26, bold=True)
    draw.text((40, 24), f"{name} · 升级材料", font=title_font, fill=TEXT_WHITE)

    y = 90

    if level_ranges:
        for m in level_ranges[:8]:
            _draw_rounded_rect(draw, 30, y, w - 30, y + 36, 6, fill=CARD_BG, outline=BORDER_COLOR, width=1)
            label = m["level"].replace("等级", "")
            draw.text((50, y + 8), f"[{label}]", font=_get_font(15, bold=True), fill=ACCENT_BLUE)
            mt = m.get("materials", "")
            draw.text((160, y + 8), mt[:55], font=m_font, fill=TEXT_GRAY)
            y += 42
    else:
        draw.text((50, y), "暂无材料数据", font=m_font, fill=TEXT_GRAY)

    _draw_footer(draw, w, h, "数据来源: nteguide.com")
    return _img_to_bytes(img)


async def draw_redeem_codes(codes: list) -> Optional[bytes]:
    """绘制兑换码图"""

    y = 90
    if codes:
        y += len(codes[:12]) * 34
    else:
        y += 30

    h = max(400, y + 60)
    w = 650

    img = Image.new('RGB', (w, h), BG_COLOR)
    draw = ImageDraw.Draw(img)
    _draw_bg_gradient(img)

    _draw_header_bar(draw, w)
    title_font = _get_font(26, bold=True)
    draw.text((40, 24), "兑换码", font=title_font, fill=ACCENT_GOLD)

    y = 90
    code_font = _get_font(16, bold=True)

    if codes:
        for c in codes[:12]:
            _draw_rounded_rect(draw, 30, y, w - 30, y + 28, 6, fill=CARD_BG, outline=BORDER_COLOR, width=1)
            draw.text((45, y + 4), c["code"], font=code_font, fill=ACCENT_BLUE)
            y += 34
    else:
        draw.text((50, y), "暂未获取到兑换码", font=_get_font(15), fill=TEXT_GRAY)

    _draw_footer(draw, w, h, "数据来源: nteguide.com")
    return _img_to_bytes(img)


async def draw_search_results(results: dict) -> Optional[bytes]:
    """绘制搜索结果图"""

    # 先计算 y 确定高度
    y = 90
    categories = [
        ("角色", results.get("characters", []), ACCENT_BLUE),
        ("武器", results.get("weapons", []), ACCENT_GREEN),
        ("材料", results.get("materials", []), ACCENT_GOLD),
    ]
    for _, items, _ in categories:
        if items:
            y += 36 + len(items[:5]) * 22 + 6
    if not any(v for v in results.values()):
        y += 30

    h = max(450, y + 60)
    w = 700

    img = Image.new('RGB', (w, h), BG_COLOR)
    draw = ImageDraw.Draw(img)
    _draw_bg_gradient(img)

    _draw_header_bar(draw, w)
    title_font = _get_font(26, bold=True)
    draw.text((40, 24), "搜索结果", font=title_font, fill=TEXT_WHITE)

    y = 90
    s_font = _get_font(15)
    has_result = False

    for cat_name, items, color in categories:
        if items:
            has_result = True
            _draw_rounded_rect(draw, 30, y, w - 30, y + 30, 6, fill=color)
            draw.text((45, y + 5), f"[{cat_name}] {len(items)} 个结果", font=_get_font(15, bold=True), fill=TEXT_WHITE)
            y += 36
            for item in items[:5]:
                draw.text((55, y), f"  {item['name']}", font=s_font, fill=TEXT_GRAY)
                y += 22
            y += 6

    if not has_result:
        draw.text((50, y), "未找到匹配结果", font=_get_font(15), fill=TEXT_GRAY)

    _draw_footer(draw, w, h, "数据来源: nteguide.com")
    return _img_to_bytes(img)


# ── 辅助 ──

def _img_to_bytes(img: Image.Image, fmt: str = "PNG") -> bytes:
    buf = BytesIO()
    img.save(buf, format=fmt, optimize=True)
    return buf.getvalue()
