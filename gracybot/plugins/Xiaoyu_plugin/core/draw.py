"""小禹插件 — 帮助图片绘制模块
从 PLUGIN_REGISTRY 动态读取小禹插件命令，自动跟随元数据更新
布局复用 Help_plugin 风格：渐变背景 + Logo + 卡片
"""

import io
import os
import sys
import textwrap
from typing import List, Tuple, Dict

# venv site-packages
def _get_venv_sp():
    try:
        import site
        return site.getsitepackages()[0]
    except Exception:
        for p in sys.path:
            if 'site-packages' in p:
                return p
    return None

_sp = _get_venv_sp()
if _sp and _sp not in sys.path:
    sys.path.insert(0, _sp)

import numpy as np
from PIL import Image, ImageDraw, ImageFont

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_RES = os.path.join(_ROOT, "res", "resource")

sys.path.append(_ROOT)
from graci import get_logger
from graci import BOT_VERSION

logger = get_logger("Xiaoyu.draw")


class XiaoyuHelpDrawer:
    # ═══════════════ 资源 ═══════════════
    FONT_PATH = os.path.join(_RES, "DouyinSansBold.otf")
    LOGO_PATH = os.path.join(_RES, "gracybot_logo.png")

    # ═══════════════ 主题色 ═══════════════
    C_BG_START   = (248, 250, 255)
    C_BG_END     = (255, 252, 248)
    C_HEADER_BG  = (240, 242, 248)
    C_CARD_BG    = (255, 255, 255)
    C_CARD_BORDER= (220, 225, 235)
    C_TITLE      = (255, 182, 193)
    C_SUBTITLE   = (80, 80, 80)
    C_COMMAND    = (255, 182, 193)
    C_DESC       = (70, 70, 70)
    C_FOOTER     = (100, 100, 100)
    C_ACCENT     = (0, 90, 180)
    C_LOGO_BG    = (255, 255, 255)
    LOGO_TOL     = 25

    IMG_W        = 800
    PAD          = 25
    TOP_H        = 120
    LOGO_H       = 65
    SEC_H        = 50
    MARKER_SZ    = 18
    MARKER_PAD   = (SEC_H - MARKER_SZ) // 2
    TITLE_LEFT   = MARKER_PAD * 2 + MARKER_SZ
    GAP_BELOW    = 15
    GAP_AFTER    = 25
    CARD_PX      = 15
    CARD_PT      = 10
    CARD_PB      = 10
    CARD_GAP     = 12
    CARD_R       = 10
    INNER_GAP    = 4
    NAME_DESC_GAP= 12
    FOOTER_H     = 40

    def __init__(self):
        self._load_fonts()
        self._load_logo()

    # ═══════════════ 加载 ═══════════════
    def _load_fonts(self):
        try:
            self.f_title   = ImageFont.truetype(self.FONT_PATH, 36)
            self.f_sub     = ImageFont.truetype(self.FONT_PATH, 18)
            self.f_section = ImageFont.truetype(self.FONT_PATH, 20)
            self.f_cmd     = ImageFont.truetype(self.FONT_PATH, 15)
            self.f_desc    = ImageFont.truetype(self.FONT_PATH, 13)
            self.f_footer  = ImageFont.truetype(self.FONT_PATH, 12)
        except Exception as e:
            logger.error(f"字体加载失败: {e}")
            raise

    def _load_logo(self):
        try:
            logo = Image.open(self.LOGO_PATH).convert("RGBA")
            arr = np.array(logo)
            r, g, b, a = arr.T
            white = ((r >= self.C_LOGO_BG[0] - self.LOGO_TOL)
                     & (g >= self.C_LOGO_BG[1] - self.LOGO_TOL)
                     & (b >= self.C_LOGO_BG[2] - self.LOGO_TOL)
                     & (a > 128))
            arr[..., -1][white.T] = 0
            logo = Image.fromarray(arr)
            ow, oh = logo.size
            nw = int(self.LOGO_H * ow / oh)
            self.logo = logo.resize((nw, self.LOGO_H), Image.Resampling.LANCZOS)
        except Exception as e:
            logger.warning(f"Logo 加载失败: {e}")
            self.logo = None

    # ═══════════════ 工具 ═══════════════
    @staticmethod
    def _gradient(draw, w, h, s, e):
        for y in range(h):
            r = int(s[0] + (e[0] - s[0]) * y / h)
            g = int(s[1] + (e[1] - s[1]) * y / h)
            b = int(s[2] + (e[2] - s[2]) * y / h)
            draw.line([(0, y), (w, y)], fill=(r, g, b))

    def _text_sz(self, text, font, draw):
        if not text:
            return 0, 0
        try:
            bb = draw.textbbox((0, 0), text, font=font)
            return bb[2] - bb[0], bb[3] - bb[1]
        except Exception:
            return int(len(text) * font.size * 0.6), int(font.size * 1.2)

    def _rounded_rect(self, draw, xy, r, fill=None, outline=None, width=1):
        x1, y1, x2, y2 = xy
        if x1 >= x2 or y1 >= y2:
            return
        r = min(r, (x2 - x1) // 2, (y2 - y1) // 2)
        if fill:
            draw.rectangle((x1 + r, y1, x2 - r, y2), fill=fill)
            draw.rectangle((x1, y1 + r, x2, y2 - r), fill=fill)
            draw.pieslice((x1, y1, x1 + 2 * r, y1 + 2 * r), 180, 270, fill=fill)
            draw.pieslice((x2 - 2 * r, y1, x2, y1 + 2 * r), 270, 360, fill=fill)
            draw.pieslice((x1, y2 - 2 * r, x1 + 2 * r, y2), 90, 180, fill=fill)
            draw.pieslice((x2 - 2 * r, y2 - 2 * r, x2, y2), 0, 90, fill=fill)
        if outline and width > 0:
            draw.arc((x1, y1, x1 + 2 * r, y1 + 2 * r), 180, 270, fill=outline, width=width)
            draw.arc((x2 - 2 * r, y1, x2, y1 + 2 * r), 270, 360, fill=outline, width=width)
            draw.arc((x1, y2 - 2 * r, x1 + 2 * r, y2), 90, 180, fill=outline, width=width)
            draw.arc((x2 - 2 * r, y2 - 2 * r, x2, y2), 0, 90, fill=outline, width=width)
            draw.line([(x1 + r, y1), (x2 - r, y1)], fill=outline, width=width)
            draw.line([(x1 + r, y2), (x2 - r, y2)], fill=outline, width=width)
            draw.line([(x1, y1 + r), (x1, y2 - r)], fill=outline, width=width)
            draw.line([(x2, y1 + r), (x2, y2 - r)], fill=outline, width=width)

    # ═══════════════ 动态读取 PLUGIN_REGISTRY ═══════════════
    def _get_xiaoyu_commands(self) -> Dict[str, List[str]]:
        """从 PLUGIN_REGISTRY 读取小禹插件的命令列表（每次调用都重新读，自动跟随热重载更新）"""
        result: Dict[str, List[str]] = {}
        try:
            from graci import plugin_manager
            for plugin in plugin_manager.registry:
                if plugin.get("name") == "小禹插件":
                    cmds = plugin.get("commands", [])
                    descs = plugin.get("command_descriptions", {})
                    fallback_desc = plugin.get("description", "")
                    for cmd in cmds:
                        desc = descs.get(cmd, "") or fallback_desc
                        # 构建 "命令#描述" 格式（与 Help_plugin 一致）
                        entry = f"{cmd}#{desc}" if desc else cmd
                        result.setdefault("小禹插件", []).append(entry)
                    break
        except Exception as e:
            logger.error(f"读取 PLUGIN_REGISTRY 失败: {e}")
        return result

    @staticmethod
    def _parse_cmd_list(lines: List[str]) -> List[Tuple[str, str | None]]:
        """解析 cmd#desc 格式列表 → [(cmd, desc), ...]"""
        cmds = []
        for line in lines:
            if "#" in line:
                cmd, desc = line.split("#", 1)
                cmds.append((cmd.strip(), desc.strip()))
            else:
                cmds.append((line.strip(), None))
        return cmds

    # ═══════════════ 布局 ═══════════════
    def _layout(self, draw) -> Tuple[List[Dict], int]:
        """构建卡片布局，返回 (layout_info, total_y)"""
        data = self._get_xiaoyu_commands()
        max_cols = 4
        cw = (self.IMG_W - self.PAD * 2 - self.CARD_GAP * (max_cols - 1)) // max_cols
        layout = []
        y = self.TOP_H + self.PAD

        for sec_name, raw_lines in data.items():
            cmds = self._parse_cmd_list(raw_lines)
            if not cmds:
                continue

            # 节标题
            layout.append({"type": "header", "name": sec_name, "y": y})
            y += self.SEC_H + self.GAP_BELOW

            row, col, max_h = [], 0, 0
            for cmd, desc in cmds:
                _, hc = self._text_sz(cmd, self.f_cmd, draw)
                # 描述自动换行（每行 12 字符）
                wrapped = textwrap.wrap(desc or "", width=12)
                lh = self.f_desc.getbbox("A")[3] - self.f_desc.getbbox("A")[1] + self.INNER_GAP
                hd = len(wrapped) * lh if wrapped else 0
                ch = max(self.CARD_PT + hc + self.NAME_DESC_GAP + hd + self.CARD_PB, 35)
                row.append({"type": "card", "name": cmd, "desc": desc, "height": ch})
                max_h = max(max_h, ch)
                col += 1
                if col == max_cols:
                    for i, c in enumerate(row):
                        c["x"] = self.PAD + i * (cw + self.CARD_GAP)
                        c["y"] = y
                        c["width"] = cw
                    layout.extend(row)
                    y += max_h + self.CARD_GAP
                    row, col, max_h = [], 0, 0
            if row:
                for i, c in enumerate(row):
                    c["x"] = self.PAD + i * (cw + self.CARD_GAP)
                    c["y"] = y
                    c["width"] = cw
                layout.extend(row)
                y += max_h + self.CARD_GAP
            y += self.GAP_AFTER

        return layout, y

    # ═══════════════ 绘制 ═══════════════
    def _draw_cards(self, img, layout):
        draw = ImageDraw.Draw(img)
        for item in layout:
            if item["type"] == "header":
                draw.rectangle((0, item["y"], self.IMG_W, item["y"] + self.SEC_H),
                               fill=self.C_HEADER_BG)
                draw.ellipse((self.MARKER_PAD, item["y"] + self.MARKER_PAD,
                              self.MARKER_PAD + self.MARKER_SZ,
                              item["y"] + self.MARKER_PAD + self.MARKER_SZ),
                             fill=self.C_ACCENT)
                draw.text((self.TITLE_LEFT, item["y"] + self.MARKER_PAD),
                          item["name"], font=self.f_section, fill=self.C_TITLE)
            elif item["type"] == "card":
                x0, y0 = item["x"], item["y"]
                x1, y1 = x0 + item["width"], y0 + item["height"]
                self._rounded_rect(draw, (x0, y0, x1, y1), r=self.CARD_R,
                                   fill=self.C_CARD_BG, outline=self.C_CARD_BORDER)
                draw.text((x0 + self.CARD_PX, y0 + self.CARD_PT),
                          item["name"], font=self.f_cmd, fill=self.C_COMMAND)
                if item.get("desc"):
                    wrapped = textwrap.wrap(item["desc"], width=12)
                    bb = self.f_cmd.getbbox(item["name"])
                    ys = y0 + self.INNER_GAP + (bb[3] - bb[1]) + self.NAME_DESC_GAP
                    lh = self.f_desc.getbbox("A")[3] - self.f_desc.getbbox("A")[1] + self.INNER_GAP
                    for i, line in enumerate(wrapped):
                        draw.text((x0 + self.CARD_PX, ys + i * lh),
                                  line, font=self.f_desc, fill=self.C_DESC)

    # ═══════════════ 主入口 ═══════════════
    def draw(self) -> bytes:
        # 先布局算高度
        tmp = Image.new("RGB", (self.IMG_W, 1000), color=(255, 255, 255))
        td = ImageDraw.Draw(tmp)
        layout, total_y = self._layout(td)
        total_h = total_y + self.FOOTER_H + self.PAD

        img = Image.new("RGB", (self.IMG_W, total_h), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)

        # 渐变背景
        self._gradient(draw, self.IMG_W, total_h, self.C_BG_START, self.C_BG_END)

        # Logo + 标题
        if self.logo:
            img.paste(self.logo, (self.PAD, self.PAD), self.logo)
            lw, _ = self.logo.size
            xs = self.PAD + lw + 15
            draw.text((xs, self.PAD), "小禹帮助列表", font=self.f_title, fill=self.C_TITLE)
            draw.text((xs, self.PAD + self.f_title.getbbox("小禹帮助列表")[3] + 5),
                      "官方核心控制中枢 · 命令自动跟随元数据更新", font=self.f_sub, fill=self.C_SUBTITLE)

        # 绘制卡片
        self._draw_cards(img, layout)

        # 底部版权
        ver = BOT_VERSION[1:] if BOT_VERSION.startswith('v') else BOT_VERSION
        footer = f"GracyBot v{ver} · 小禹插件"
        fb = draw.textbbox((0, 0), footer, font=self.f_footer)
        fw, fh = fb[2] - fb[0], fb[3] - fb[1]
        draw.text((self.IMG_W - fw - self.PAD, total_h - self.FOOTER_H + (self.FOOTER_H - fh) // 2),
                  footer, font=self.f_footer, fill=self.C_FOOTER)

        with io.BytesIO() as out:
            img.save(out, format="PNG", optimize=True)
            return out.getvalue()
