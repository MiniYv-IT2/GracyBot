import io
import os
import textwrap
from typing import Dict, List, Tuple, Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from graci import logger
from core.config import *


class GracyBotHelpDrawer:
    # ---------------- 常量区 ----------------
    # 共享资源路径（gracybot/style/resource/）
    _ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    _RES = os.path.join(_ROOT, "style", "resource")
    FONT_PATH_REGULAR = os.path.join(_RES, "DouyinSansBold.otf")
    FONT_PATH_BOLD = FONT_PATH_REGULAR
    LOGO_PATH = os.path.join(_RES, "gracybot_logo.png")

    # 主题色
    COLOR_BACKGROUND_START = (248, 250, 255)
    COLOR_BACKGROUND_END = (255, 252, 248)
    COLOR_SECTION_HEADER_BG = (240, 242, 248)
    COLOR_CARD_BACKGROUND = (255, 255, 255)
    COLOR_CARD_OUTLINE = (220, 225, 235)
    COLOR_TEXT_HEADER = (255, 182, 193)
    COLOR_TEXT_SUBTITLE = (80, 80, 80)
    COLOR_TEXT_PLUGIN = (255, 182, 193)
    COLOR_TEXT_COMMAND = (255, 182, 193)
    COLOR_TEXT_DESC = (70, 70, 70)  # 保持描述文字为黑色
    COLOR_TEXT_FOOTER = (100, 100, 100)
    COLOR_ACCENT = (0, 90, 180)
    COLOR_LOGO_BG_REMOVE = (255, 255, 255)
    LOGO_BG_TOLERANCE = 25

    # 布局尺寸
    IMG_WIDTH = 800
    PADDING = 25
    TOP_AREA_HEIGHT = 120
    LOGO_TARGET_HEIGHT = 65
    SECTION_HEADER_HEIGHT = 50
    SECTION_MARKER_SIZE = 18
    SECTION_MARKER_PADDING = (SECTION_HEADER_HEIGHT - SECTION_MARKER_SIZE) // 2
    SECTION_TITLE_LEFT_MARGIN = SECTION_MARKER_PADDING * 2 + SECTION_MARKER_SIZE
    SECTION_SPACING_BELOW_HEADER = 15
    SECTION_SPACING_AFTER_CARDS = 25
    CARD_PADDING_X = 15
    CARD_PADDING_Y = 12
    CARD_SPACING = 12
    CARD_CORNER_RADIUS = 10
    CARD_INTERNAL_SPACE = 4
    FOOTER_HEIGHT = 40
    TALL_CARD_DESC_LENGTH_THRESHOLD = 100

    # 内边距常量
    CARD_PADDING_TOP = 10
    CARD_PADDING_BOTTOM = 10
    NAME_DESC_SPACING = 12

    # 内置指令文本
    BUILT_IN_COMMANDS_TEXT = textwrap.dedent("""
        [System]
        /关于 : 查看关于GracyBot的开发信息
        /系统更新 : 检测可用的最新框架版本
        /确认更新 : 选择开始系统更新
        /取消更新 : 取消系统更新操作
        /状态 : 获取基本的运行状态信息
        /重启 : 重启您的Bot
        /关机 : 让您的Bot得到充分休息
        /开机 : 执行开机命令
        /运行状态 : 查看框架运行信息及系统资源详情

        [AI对话]
        /+persona : 创建新的AI对话人设
        /-persona : 删除指定人设
        /persona : 切换到指定人设
    """).strip()

    # ---------------- 构造函数 ----------------
    def __init__(self, config) -> None:
        self.config = config
        self._load_fonts()
        self._load_logo()

    # ---------------- 字体 & Logo ----------------
    def _load_fonts(self) -> None:
        try:
            self.font_title = ImageFont.truetype(self.FONT_PATH_BOLD, 36)
            self.font_subtitle = ImageFont.truetype(self.FONT_PATH_REGULAR, 18)
            self.font_plugin_header = ImageFont.truetype(self.FONT_PATH_BOLD, 20)
            self.font_command = ImageFont.truetype(self.FONT_PATH_BOLD, 15)
            self.font_desc = ImageFont.truetype(self.FONT_PATH_REGULAR, 13)
            self.font_footer = ImageFont.truetype(self.FONT_PATH_REGULAR, 12)
        except Exception as e:
            logger.error(f"加载字体时出错: {e}")
            exit()

    def _load_logo(self) -> None:
        try:
            logo_img = Image.open(self.LOGO_PATH).convert("RGBA")
            img_data = np.array(logo_img)
            r, g, b, a = img_data.T
            white_areas = (
                (r >= self.COLOR_LOGO_BG_REMOVE[0] - self.LOGO_BG_TOLERANCE)
                & (g >= self.COLOR_LOGO_BG_REMOVE[1] - self.LOGO_BG_TOLERANCE)
                & (b >= self.COLOR_LOGO_BG_REMOVE[2] - self.LOGO_BG_TOLERANCE)
                & (a > 128)
            )
            img_data[..., -1][white_areas.T] = 0
            logo_transparent = Image.fromarray(img_data)
            ow, oh = logo_transparent.size
            new_w = int(self.LOGO_TARGET_HEIGHT * ow / oh)
            self.resized_logo = logo_transparent.resize(
                (new_w, self.LOGO_TARGET_HEIGHT), Image.Resampling.LANCZOS
            )
        except Exception as e:
            logger.warning(f"加载或处理 Logo 时出错: {e}")
            self.resized_logo = None

    # ---------------- 文本解析 ----------------
    @staticmethod
    def _parse_single_command_list(text_list) -> List[Tuple[str, str | None]]:
        commands = []
        lines = (
            text_list.strip().splitlines()
            if isinstance(text_list, str)
            else [ln for ln in text_list if ln.strip()]
        )

        for line in lines:
            raw = line
            stripped = line.strip()
            if not stripped or (stripped.startswith("[") and stripped.endswith("]")):
                continue
            if (raw.startswith("  ") or raw.startswith("\t")) and commands:
                cmd, desc = commands[-1]
                commands[-1] = (cmd, (desc or "") + stripped)
                continue

            # 新命令解析
            parts = None
            for sep in (" : ", " # ", "#", ":"):
                if sep in stripped:
                    parts = stripped.split(sep, 1)
                    break
            if parts and len(parts) == 2:
                cmd = (
                    parts[0][2:].strip()
                    if parts[0].startswith("- ")
                    else parts[0].strip()
                )
                desc = parts[1].strip()
            else:
                cmd = stripped[2:].strip() if stripped.startswith("- ") else stripped
                desc = None
            commands.append((cmd, desc))

        # 只保留描述第一行
        return [(c, (d.splitlines()[0].strip() if d else None)) for c, d in commands]

    def _parse_plugin_commands_sorted_grouped(
        self, plugin_dict: Dict[str, Any]
    ) -> List[Tuple[str, List[Tuple[str, str | None]]]]:
        # 是否显示内置指令（从配置读取）
        show_builtin_cmds = self.config.get("show_builtin_cmds", {}).get("default", False) if isinstance(self.config.get("show_builtin_cmds"), dict) else self.config.get("show_builtin_cmds", False)
        if show_builtin_cmds:
            built_in_list = self._parse_single_command_list(self.BUILT_IN_COMMANDS_TEXT)
            built_in_plugin = ("内置指令", built_in_list) if built_in_list else None
        else:
            built_in_plugin = None

        large_plugins, small_plugins = [], []
        for name, cmds_raw in plugin_dict.items():
            if name == "内置指令" or not cmds_raw:
                continue
             # 如果在黑名单里，跳过（从配置读取）
            plugin_blacklist = self.config.get("plugin_blacklist", {}).get("default", []) if isinstance(self.config.get("plugin_blacklist"), dict) else self.config.get("plugin_blacklist", [])
            if name in plugin_blacklist:
                continue
            cmds = self._parse_single_command_list(cmds_raw)
            if not cmds:
                continue
            (small_plugins if len(cmds) == 1 else large_plugins).append((name, cmds))

        large_plugins.sort(key=lambda x: len(x[1]), reverse=True)

        grouped_small_plugin = None
        if small_plugins:
            all_small = [c for _, cmds in small_plugins for c in cmds]
            if all_small:
                grouped_small_plugin = ("简易指令", all_small)
                logger.info(f"-> 创建 '简易指令' ({len(all_small)} 条)")

        result = []
        if built_in_plugin:
            result.append(built_in_plugin)
        result.extend(large_plugins)
        if grouped_small_plugin:
            result.append(grouped_small_plugin)

        # 添加自定义命令
        custom_list = []
        # 暂时禁用自定义命令功能
        # if getattr(self.config, "custom_cmds", None):
        #     custom_list = self._parse_single_command_list(self.config.custom_cmds)
        
        if custom_list:
            result.append(("自定义命令", custom_list))
            logger.info(f"-> 创建 '自定义命令' ({len(custom_list)} 条)")

        return result

    # ---------------- 绘图辅助 ----------------
    @staticmethod
    def _draw_gradient(
        draw,
        width: int,
        height: int,
        start: Tuple[int, int, int],
        end: Tuple[int, int, int],
    ):
        for y in range(height):
            r = int(start[0] + (end[0] - start[0]) * y / height)
            g = int(start[1] + (end[1] - start[1]) * y / height)
            b = int(start[2] + (end[2] - start[2]) * y / height)
            draw.line([(0, y), (width, y)], fill=(r, g, b))

    def _get_text_metrics(
        self, text: str, font: ImageFont.FreeTypeFont, draw
    ) -> Tuple[Tuple[int, int, int, int], Tuple[int, int]]:
        if not text:
            return (0, 0, 0, 0), (0, 0)
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            return bbox, (w, h)
        except AttributeError:
            w = draw.textlength(text, font=font)
            h = (
                sum(font.getmetrics())
                if sum(font.getmetrics()) > 0
                else font.size * 1.2
            )
            return (0, 0, int(w), int(h)), (int(w), int(h))
        except Exception:
            est_w = len(text) * font.size * 0.6
            est_h = font.size * 1.2
            return (0, 0, max(1, int(est_w)), max(1, int(est_h))), (
                max(1, int(est_w)),
                max(1, int(est_h)),
            )

    def _draw_rounded_rectangle(
        self, draw, xy, radius, fill=None, outline=None, width=1
    ):
        x1, y1, x2, y2 = xy
        if x1 >= x2 or y1 >= y2:
            return
        radius = min(radius, (x2 - x1) // 2, (y2 - y1) // 2)
        if fill:
            draw.rectangle((x1 + radius, y1, x2 - radius, y2), fill=fill)
            draw.rectangle((x1, y1 + radius, x2, y2 - radius), fill=fill)
            draw.pieslice(
                (x1, y1, x1 + 2 * radius, y1 + 2 * radius), 180, 270, fill=fill
            )
            draw.pieslice(
                (x2 - 2 * radius, y1, x2, y1 + 2 * radius), 270, 360, fill=fill
            )
            draw.pieslice(
                (x1, y2 - 2 * radius, x1 + 2 * radius, y2), 90, 180, fill=fill
            )
            draw.pieslice((x2 - 2 * radius, y2 - 2 * radius, x2, y2), 0, 90, fill=fill)
        if outline and width > 0:
            draw.arc(
                (x1, y1, x1 + 2 * radius, y1 + 2 * radius),
                180,
                270,
                fill=outline,
                width=width,
            )
            draw.arc(
                (x2 - 2 * radius, y1, x2, y1 + 2 * radius),
                270,
                360,
                fill=outline,
                width=width,
            )
            draw.arc(
                (x1, y2 - 2 * radius, x1 + 2 * radius, y2),
                90,
                180,
                fill=outline,
                width=width,
            )
            draw.arc(
                (x2 - 2 * radius, y2 - 2 * radius, x2, y2),
                0,
                90,
                fill=outline,
                width=width,
            )
            draw.line([(x1 + radius, y1), (x2 - radius, y1)], fill=outline, width=width)
            draw.line([(x1 + radius, y2), (x2 - radius, y2)], fill=outline, width=width)
            draw.line([(x1, y1 + radius), (x1, y2 - radius)], fill=outline, width=width)
            draw.line([(x2, y1 + radius), (x2, y2 - radius)], fill=outline, width=width)

    # ---------------- 卡片布局（每行最多 4 张） ----------------
    def _layout_cards(
        self,
        sections: List[Tuple[str, List[Tuple[str, str | None]]]],
        draw,
    ) -> List[Dict]:
        layout_info = []
        y_offset = self.TOP_AREA_HEIGHT + self.PADDING
        max_cols = 4
        card_spacing = self.CARD_SPACING
        card_width = (
            self.IMG_WIDTH - self.PADDING * 2 - card_spacing * (max_cols - 1)
        ) // max_cols

        for section_name, cmds in sections:
            # Section Header
            layout_info.append({"type": "header", "name": section_name, "y": y_offset})
            y_offset += self.SECTION_HEADER_HEIGHT + self.SECTION_SPACING_BELOW_HEADER

            row_cards = []
            col_idx = 0
            max_row_height = 0

            for cmd, desc in cmds:
                # 命令文本高度
                _, (w_cmd, h_cmd) = self._get_text_metrics(cmd, self.font_command, draw)

                # 自动换行 desc，每行 12 字符
                wrapped_desc = textwrap.wrap(desc or "", width=12)
                bbox = self.font_desc.getbbox("A")
                line_height = bbox[3] - bbox[1] + self.CARD_INTERNAL_SPACE

                # 卡片总高度
                h_desc_total = len(wrapped_desc) * line_height if wrapped_desc else 0
                card_h = max(
                    self.CARD_PADDING_TOP
                    + h_cmd
                    + self.NAME_DESC_SPACING
                    + h_desc_total
                    + self.CARD_PADDING_BOTTOM,
                    35,
                )

                row_cards.append(
                    {
                        "type": "card",
                        "name": cmd,
                        "desc": desc,
                        "height": card_h,
                    }
                )
                max_row_height = max(max_row_height, card_h)
                col_idx += 1

                # 达到一行或最后一张
                if col_idx == max_cols:
                    for i, card in enumerate(row_cards):
                        card["x"] = self.PADDING + i * (card_width + card_spacing)
                        card["y"] = y_offset
                        card["width"] = card_width
                    layout_info.extend(row_cards)
                    y_offset += max_row_height + card_spacing
                    row_cards = []
                    col_idx = 0
                    max_row_height = 0

            # 剩余不足一行的卡片
            if row_cards:
                for i, card in enumerate(row_cards):
                    card["x"] = self.PADDING + i * (card_width + card_spacing)
                    card["y"] = y_offset
                    card["width"] = card_width
                layout_info.extend(row_cards)
                y_offset += max_row_height + card_spacing

            y_offset += self.SECTION_SPACING_AFTER_CARDS
        return layout_info

    # ---------------- 绘制卡片（每行多张支持） ----------------
    def _draw_cards(self, img: Image.Image, layout_info: List[Dict]) -> None:
        draw = ImageDraw.Draw(img)
        for item in layout_info:
            if item["type"] == "header":
                draw.rectangle(
                    (
                        0,
                        item["y"],
                        self.IMG_WIDTH,
                        item["y"] + self.SECTION_HEADER_HEIGHT,
                    ),
                    fill=self.COLOR_SECTION_HEADER_BG,
                )
                draw.ellipse(
                    (
                        self.SECTION_MARKER_PADDING,
                        item["y"] + self.SECTION_MARKER_PADDING,
                        self.SECTION_MARKER_PADDING + self.SECTION_MARKER_SIZE,
                        item["y"]
                        + self.SECTION_MARKER_PADDING
                        + self.SECTION_MARKER_SIZE,
                    ),
                    fill=self.COLOR_ACCENT,
                )
                draw.text(
                    (
                        self.SECTION_TITLE_LEFT_MARGIN,
                        item["y"] + self.SECTION_MARKER_PADDING,
                    ),
                    item["name"],
                    font=self.font_plugin_header,
                    fill=self.COLOR_TEXT_HEADER,
                )
            elif item["type"] == "card":
                x0, y0 = item["x"], item["y"]
                x1, y1 = x0 + item["width"], y0 + item["height"]
                self._draw_rounded_rectangle(
                    draw,
                    (x0, y0, x1, y1),
                    radius=self.CARD_CORNER_RADIUS,
                    fill=self.COLOR_CARD_BACKGROUND,
                    outline=self.COLOR_CARD_OUTLINE,
                    width=1,
                )
                # name
                draw.text(
                    (x0 + self.CARD_PADDING_X, y0 + self.CARD_PADDING_TOP),
                    item["name"],
                    font=self.font_command,
                    fill=self.COLOR_TEXT_COMMAND,
                )
                if item.get("desc"):
                    wrapped_desc = textwrap.wrap(item["desc"], width=12)
                    bbox_cmd = self.font_command.getbbox(item["name"])
                    y_start = (
                        y0
                        + self.CARD_INTERNAL_SPACE
                        + (bbox_cmd[3] - bbox_cmd[1])
                        + self.NAME_DESC_SPACING
                    )
                    line_height = (
                        self.font_desc.getbbox("A")[3]
                        - self.font_desc.getbbox("A")[1]
                        + self.CARD_INTERNAL_SPACE
                    )
                    for i, line in enumerate(wrapped_desc):
                        draw.text(
                            (x0 + self.CARD_PADDING_X, y_start + i * line_height),
                            line,
                            font=self.font_desc,
                            fill=self.COLOR_TEXT_DESC,
                        )

    # ---------------- 主函数 ----------------
    def draw_help_image(self, plugin_commands_dict: Dict[str, Any]) -> bytes:
        # 解析插件命令
        sections = self._parse_plugin_commands_sorted_grouped(plugin_commands_dict)

        # 初步计算总高度
        temp_img = Image.new("RGB", (self.IMG_WIDTH, 1000), color=(255, 255, 255))
        draw = ImageDraw.Draw(temp_img)
        layout_info = self._layout_cards(sections, draw)
        total_height = (
            layout_info[-1]["y"]
            + (layout_info[-1]["height"] if "height" in layout_info[-1] else 0)
            + self.FOOTER_HEIGHT
            + self.PADDING
        )

        # 创建最终图片
        img = Image.new("RGB", (self.IMG_WIDTH, total_height), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        # 渐变背景
        self._draw_gradient(
            draw,
            self.IMG_WIDTH,
            total_height,
            self.COLOR_BACKGROUND_START,
            self.COLOR_BACKGROUND_END,
        )

        # 绘制logo
        if self.resized_logo:
            img.paste(
                self.resized_logo, (self.PADDING, self.PADDING), self.resized_logo
            )
            title_text = "GracyBot 帮助指南"
            subtitle_text = "可用插件及指令列表"
            logo_w, logo_h = self.resized_logo.size
            x_start = self.PADDING + logo_w + 15
            y_start_title = self.PADDING
            y_start_subtitle = (
                self.PADDING
                + self.font_title.getbbox(title_text)[3]
                - self.font_title.getbbox(title_text)[1]
                + 5
            )
            draw.text(
                (x_start, y_start_title),
                title_text,
                font=self.font_title,
                fill=self.COLOR_TEXT_HEADER,
            )
            draw.text(
                (x_start, y_start_subtitle),
                subtitle_text,
                font=self.font_subtitle,
                fill=self.COLOR_TEXT_SUBTITLE,
            )

        # 绘制卡片
        self._draw_cards(img, layout_info)

        # 底部版权
        footer_text = f"GracyBot --致力于简洁体验的QQ框架"
        bbox = draw.textbbox((0, 0), footer_text, font=self.font_footer)
        fw = bbox[2] - bbox[0]
        fh = bbox[3] - bbox[1]
        draw.text(
            (
                self.IMG_WIDTH - fw - self.PADDING,
                total_height - self.FOOTER_HEIGHT + (self.FOOTER_HEIGHT - fh) // 2,
            ),
            footer_text,
            font=self.font_footer,
            fill=self.COLOR_TEXT_FOOTER,
        )
        # 转成 bytes
        with io.BytesIO() as output:
            img.save(output, format="PNG", optimize=True)
            return output.getvalue()
