import io
import os
import sys
import platform
import subprocess
import requests
import secrets
import logging
from typing import Dict, Tuple, Optional
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np
import psutil
import time

logger = logging.getLogger("Gracy")

# 路径配置
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
try:
    from core.config import BOT_VERSION, ROBOT_ID  # 导入框架版本和配置
    from core.config_manager import config_manager
    NAPCAT_HTTP_URL = config_manager.get("napcat_http_url", "http://localhost:3000")
except ImportError:
    BOT_VERSION = "v2.0.0"  # 默认版本
    NAPCAT_HTTP_URL = "http://localhost:3000"
    ROBOT_ID = "未知"

# 导入napcat API
try:
    from .napcat_api import NapcatAPI
except ImportError:
    NapcatAPI = None

# 常量配置
IMG_WIDTH = 800
IMG_HEIGHT = 1300  # 增加高度以容纳多磁盘信息
BG_COLOR = (248, 249, 250)  # 更柔和的背景色
TITLE_COLOR = (219, 112, 147)  # 粉玫瑰色
TEXT_COLOR = (73, 80, 87)  # 更柔和的文字色
PROGRESS_COLOR = (255, 140, 170)  # 粉色进度条
CARD_BG_COLOR = (255, 255, 255)  # 卡片背景色，比背景更白
CARD_BORDER_COLOR = (219, 112, 147)  # 卡片边框粉玫瑰色
CIRCLE_RADIUS = 65
CIRCLE_SPACING = 120  # 增加间距
TOP_PADDING = 80
LOGO_TARGET_HEIGHT = 50
CARD_HEIGHT = 100  # 卡片高度
CARD_WIDTH = 700  # 卡片宽度
CARD_TOP_PADDING = 20  # 卡片顶部内边距

# 字体路径（使用SysInfo插件的字体）
# 共享资源路径（gracybot/style/resource/）
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_RES = os.path.join(_ROOT, "style", "resource")
FONT_PATH = os.path.join(_RES, "DouyinSansBold.otf")
ROBOT_LOGO_PATH = os.path.join(_RES, "gracybot_logo.png")

OUTPUT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "temp_sysinfo.png")
OS_LOGO_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "OS_LOGO")
BACKGROUND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "background")
SUPPORTED_BG_FORMATS = ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif')

class SysInfoDrawer:
    def __init__(self, sys_info: Dict):
        self.sys_info = sys_info
        self._load_fonts()
        self._load_logos()
        # 从sys_info获取所有数据
        self.cpu_usage = sys_info.get("cpu_usage", 0.0)
        self.robot_info = sys_info.get("robot_info", {})
        self.gpu_info = sys_info.get("gpu_info", {"model": "未检测到GPU", "memory": "N/A"})
        self.io_stats = sys_info.get("io_stats", {"read_mb_s": "0.0MB/s", "write_mb_s": "0.0MB/s", "read_iops_str": "0 IOPS", "write_iops_str": "0 IOPS"})
        self.network_info = sys_info.get("network_info", {"type": "未知", "upload": 0, "download": 0})
        self.all_disks = sys_info.get("所有磁盘", [])
        self.shell_terminal = sys_info.get("shell_terminal", {"shell": "未知", "terminal": "未知"})

    def _load_fonts(self):
        """加载字体"""
        try:
            self.font_title = ImageFont.truetype(FONT_PATH, 28)
            self.font_subtitle = ImageFont.truetype(FONT_PATH, 16)
            self.font_progress = ImageFont.truetype(FONT_PATH, 20)
            self.font_text = ImageFont.truetype(FONT_PATH, 14)
            self.font_footer = ImageFont.truetype(FONT_PATH, 12)
        except Exception as e:
            raise Exception(f"字体加载失败: {e}")

    def _load_logos(self):
        """加载机器人LOGO和系统LOGO"""
        # 机器人LOGO
        try:
            logo_img = Image.open(ROBOT_LOGO_PATH).convert("RGBA")
            ow, oh = logo_img.size
            new_w = int(LOGO_TARGET_HEIGHT * ow / oh)
            self.robot_logo = logo_img.resize((new_w, LOGO_TARGET_HEIGHT), Image.Resampling.LANCZOS)
        except Exception as e:
            self.robot_logo = None

        # 系统LOGO（根据系统名称匹配）
        self.os_logo = None
        os_name = self._get_os_short_name()
        os_logo_path = os.path.join(OS_LOGO_DIR, f"{os_name.lower()}.png")
        if os.path.exists(os_logo_path):
            try:
                img = Image.open(os_logo_path).convert("RGBA")
                # 圆形裁剪
                mask = Image.new("L", (CIRCLE_RADIUS*2, CIRCLE_RADIUS*2), 0)
                draw_mask = ImageDraw.Draw(mask)
                draw_mask.ellipse((0, 0, CIRCLE_RADIUS*2, CIRCLE_RADIUS*2), fill=255)
                img = img.resize((CIRCLE_RADIUS*2, CIRCLE_RADIUS*2), Image.Resampling.LANCZOS)
                self.os_logo = Image.new("RGBA", img.size)
                self.os_logo.paste(img, (0, 0), mask)
            except Exception as e:
                pass

    def _load_random_background(self) -> Optional[Image.Image]:
        """从background目录随机加载一张背景图，支持多种格式"""
        if not os.path.isdir(BACKGROUND_DIR):
            return None
        try:
            files = [f for f in os.listdir(BACKGROUND_DIR) 
                     if f.lower().endswith(SUPPORTED_BG_FORMATS)]
            if not files:
                return None
            chosen = secrets.choice(files)
            bg_path = os.path.join(BACKGROUND_DIR, chosen)
            logger.info(f"🎲 随机背景图：{chosen}（共{len(files)}张可选）")
            bg_img = Image.open(bg_path).convert("RGB")
            # 缩放到画布大小（保持比例，居中裁剪）
            bg_img = self._fit_background(bg_img)
            return bg_img
        except Exception as e:
            logger.warning(f"背景图加载失败：{e}")
            return None

    def _fit_background(self, bg_img: Image.Image) -> Image.Image:
        """缩放背景图至画布大小，保持比例并居中裁剪"""
        bg_w, bg_h = bg_img.size
        target_w, target_h = IMG_WIDTH, IMG_HEIGHT
        # 等比缩放至至少覆盖画布
        scale = max(target_w / bg_w, target_h / bg_h)
        new_w, new_h = int(bg_w * scale), int(bg_h * scale)
        bg_img = bg_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        # 居中裁剪
        left = (new_w - target_w) // 2
        top = (new_h - target_h) // 2
        bg_img = bg_img.crop((left, top, left + target_w, top + target_h))
        return bg_img

    def _get_os_short_name(self) -> str:
        """获取系统简称（跨平台）"""
        try:
            os_full = self.sys_info.get("系统版本", "")
            if "Windows" in os_full:
                return "Windows"
            elif "Darwin" in os_full or "macOS" in os_full:
                return "macOS"
            elif "Debian" in os_full:
                return "Debian"
            elif "Ubuntu" in os_full:
                return "Ubuntu"
            elif "CentOS" in os_full:
                return "CentOS"
            elif "Arch" in os_full:
                return "Arch"
            elif "Linux" in os_full:
                return "Linux"
            else:
                return platform.system()
        except Exception:
            return platform.system()
    
    def _download_avatar(self, url: str, save_path: str) -> Optional[Image.Image]:
        """下载头像并返回Image对象"""
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                img = Image.open(io.BytesIO(response.content)).convert("RGBA")
                return img
        except Exception as e:
            pass
        return None
    
    def _draw_robot_info_card(self, draw: ImageDraw.ImageDraw, img: Image.Image) -> None:
        """绘制机器人信息卡片"""
        # 计算卡片位置
        card_x = (IMG_WIDTH - CARD_WIDTH) // 2
        card_y = TOP_PADDING + 20
        
        # 绘制毛玻璃背景卡片
        card_rect = [card_x, card_y, card_x + CARD_WIDTH, card_y + CARD_HEIGHT]
        self._draw_frosted_panel(card_x, card_y, card_x + CARD_WIDTH, card_y + CARD_HEIGHT,
                                 radius=15, alpha=180)
        # 绘制卡片边框
        draw.rounded_rectangle(card_rect, radius=15, fill=None, outline=CARD_BORDER_COLOR, width=4)
        
        # 绘制头像
        avatar_size = 70
        avatar_x = card_x + 20
        avatar_y = card_y + (CARD_HEIGHT - avatar_size) // 2
        
        if self.robot_info["avatar_url"]:
            avatar_img = self._download_avatar(self.robot_info["avatar_url"], "")
            if avatar_img:
                # 圆形裁剪头像
                mask = Image.new("L", (avatar_size, avatar_size), 0)
                mask_draw = ImageDraw.Draw(mask)
                mask_draw.ellipse((0, 0, avatar_size, avatar_size), fill=255)
                avatar_img = avatar_img.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)
                # 创建圆形头像
                circular_avatar = Image.new("RGBA", (avatar_size, avatar_size))
                circular_avatar.paste(avatar_img, (0, 0), mask)
                img.paste(circular_avatar, (avatar_x, avatar_y), circular_avatar)
            else:
                # 下载失败，绘制默认头像
                draw.ellipse((avatar_x, avatar_y, avatar_x + avatar_size, avatar_y + avatar_size), 
                           fill=(200, 200, 200), outline=CARD_BORDER_COLOR, width=2)
        else:
            # 无头像URL，绘制默认头像
            draw.ellipse((avatar_x, avatar_y, avatar_x + avatar_size, avatar_y + avatar_size), 
                       fill=(200, 200, 200), outline=CARD_BORDER_COLOR, width=2)
        
        # 绘制文字信息
        text_x = avatar_x + avatar_size + 20
        text_y = card_y + 20
        line_height = 22
        
        # 第一行：QQ昵称
        nickname_text = f"昵称：{self.robot_info['nickname']}"
        draw.text((text_x, text_y), nickname_text, font=self.font_subtitle, fill=TITLE_COLOR)
        
        # 第二行：好友数量和群聊数量
        info_text = f"好友：{self.robot_info['friend_count']} | 群聊：{self.robot_info['group_count']}"
        draw.text((text_x, text_y + line_height), info_text, font=self.font_text, fill=TEXT_COLOR)
        
        # 第三行：napcat版本
        version_text = f"协议：{self.robot_info['napcat_version']}"
        draw.text((text_x, text_y + line_height * 2), version_text, font=self.font_text, fill=TEXT_COLOR)

    def _parse_progress_data(self) -> Tuple[Dict, Dict]:
        """解析进度数据（CPU、内存、磁盘）"""
        # 内存数据
        mem_info = self.sys_info.get("内存信息", "")
        mem_used = 0.0
        mem_total = 0.0
        if "总内存：" in mem_info and "已用：" in mem_info:
            try:
                mem_total = float(mem_info.split("总内存：")[1].split("GB")[0])
                mem_used = float(mem_info.split("已用：")[1].split("GB")[0])
            except:
                pass
        mem_progress = (mem_used / mem_total * 100) if mem_total > 0 else 0.0

        # 磁盘数据
        disk_info = self.sys_info.get("磁盘信息", "")
        disk_used = 0.0
        disk_total = 0.0
        if "总容量：" in disk_info and "已用：" in disk_info:
            try:
                # 处理GB/MB单位 - 更灵活的解析
                parts = disk_info.split("，")
                for part in parts:
                    if "总容量：" in part:
                        total_str = part.replace("总容量：", "").strip()
                        if "G" in total_str:
                            disk_total = float(total_str.replace("G", "").replace("B", ""))
                        elif "M" in total_str:
                            disk_total = float(total_str.replace("M", "").replace("B", "")) / 1024
                    elif "已用：" in part:
                        used_str = part.replace("已用：", "").strip()
                        if "G" in used_str:
                            disk_used = float(used_str.replace("G", "").replace("B", ""))
                        elif "M" in used_str:
                            disk_used = float(used_str.replace("M", "").replace("B", "")) / 1024
                # 如果从使用率解析
                if "使用率：" in disk_info and disk_total == 0:
                    rate_str = disk_info.split("使用率：")[1].replace("%", "").strip()
                    disk_progress = float(rate_str)
            except:
                # 尝试从使用率直接获取
                try:
                    if "使用率：" in disk_info:
                        rate_str = disk_info.split("使用率：")[1].replace("%", "").strip()
                        disk_progress = float(rate_str)
                        # 估算总容量和已用
                        disk_total = 100.0  # 临时值
                        disk_used = disk_progress
                except:
                    pass
        disk_progress = (disk_used / disk_total * 100) if disk_total > 0 else 0.0

        # 进度数据
        progress_data = {
            "cpu": {"value": self.cpu_usage, "label": "CPU占用"},
            "mem": {"value": mem_progress, "label": "内存占用"},
            "disk": {"value": disk_progress, "label": "磁盘占用"},
            "os": {"value": 0, "label": self._get_os_short_name()}  # 系统LOGO无进度
        }

        # 详细数值（X/X）
        value_data = {
            "cpu": f"{self.cpu_usage}%",
            "mem": f"{mem_used:.1f}GB/{mem_total:.1f}GB",
            "disk": f"{disk_used:.1f}GB/{disk_total:.1f}GB",
            "os": self._get_os_short_name()
        }

        return progress_data, value_data

    def _draw_frosted_circle(self, x: int, y: int, radius: int, alpha: int = 120) -> None:
        """在指定位置绘制毛玻璃圆圈（从原背景裁剪并模糊）"""
        r = radius
        if self.original_bg:
            # 从原始清晰背景裁剪圆圈区域，高斯模糊 + 白色半透明叠加
            region = self.original_bg.crop((x - r, y - r, x + r, y + r))
            blurred = region.filter(ImageFilter.GaussianBlur(radius=12))
            white_tint = Image.new('RGBA', (r * 2, r * 2), (255, 255, 255, alpha))
            frosted = blurred.convert('RGBA')
            frosted = Image.alpha_composite(frosted, white_tint)
        else:
            frosted = Image.new('RGBA', (r * 2, r * 2), (255, 255, 255, alpha))
        mask = Image.new('L', (r * 2, r * 2), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, r * 2, r * 2), fill=255)
        self.img.paste(frosted, (x - r, y - r), mask)

    def _draw_frosted_panel(self, x1: int, y1: int, x2: int, y2: int, 
                            radius: int = 20, alpha: int = 170) -> None:
        """在指定区域绘制毛玻璃面板（从原背景裁剪并模糊）"""
        w, h = x2 - x1, y2 - y1
        if self.original_bg:
            # 从原始清晰背景裁剪面板区域，高斯模糊 + 白色半透明叠加
            region = self.original_bg.crop((x1, y1, x2, y2))
            blurred = region.filter(ImageFilter.GaussianBlur(radius=15))
            white_tint = Image.new('RGBA', (w, h), (255, 255, 255, alpha))
            frosted = blurred.convert('RGBA')
            frosted = Image.alpha_composite(frosted, white_tint)
        else:
            frosted = Image.new('RGBA', (w, h), (255, 255, 255, alpha))
        mask = Image.new('L', (w, h), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, w, h), radius=radius, fill=255)
        self.img.paste(frosted, (x1, y1), mask)

    def _draw_circle_base(self, draw: ImageDraw.ImageDraw, x: int, y: int, label: str, 
                      progress: float = None, logo_img: Image.Image = None, 
                      border_color: tuple = (200, 200, 200)) -> None:
        """通用圆形绘制方法（进度条或LOGO）"""
        # 绘制毛玻璃背景圆（替代原来的纯色填充）
        self._draw_frosted_circle(x, y, CIRCLE_RADIUS)
        
        # 绘制圆形边框
        draw.ellipse((x-CIRCLE_RADIUS, y-CIRCLE_RADIUS, x+CIRCLE_RADIUS, y+CIRCLE_RADIUS), 
                     outline=border_color, width=2)
        
        if progress is not None:
            # 绘制进度弧
            if progress > 0:
                start_angle = -90
                end_angle = start_angle + (progress / 100) * 360
                draw.arc((x-CIRCLE_RADIUS+5, y-CIRCLE_RADIUS+5, x+CIRCLE_RADIUS-5, y+CIRCLE_RADIUS-5),
                         start=start_angle, end=end_angle, fill=PROGRESS_COLOR, width=8)
            
            # 绘制进度文本
            text = f"{progress:.1f}%"
            bbox = draw.textbbox((0, 0), text, font=self.font_progress)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            draw.text((x - text_w/2, y - text_h/2), text, font=self.font_progress, fill=TITLE_COLOR)
        
        elif logo_img is not None:
            # 绘制LOGO
            img_x = x - CIRCLE_RADIUS
            img_y = y - CIRCLE_RADIUS
            if hasattr(self, 'img'):
                self.img.paste(logo_img, (img_x, img_y), logo_img)
        
        # 绘制下方标签
        try:
            label_bbox = draw.textbbox((0, 0), label, font=self.font_subtitle)
            label_w = label_bbox[2] - label_bbox[0]
            draw.text((x - label_w/2, y + CIRCLE_RADIUS + 20), label, font=self.font_subtitle, fill=TEXT_COLOR)
        except Exception:
            draw.text((x - 20, y + CIRCLE_RADIUS + 20), label, font=self.font_subtitle, fill=TEXT_COLOR)

    def _draw_circle_progress(self, draw: ImageDraw.ImageDraw, x: int, y: int, progress: float, label: str):
        """绘制圆形进度条"""
        self._draw_circle_base(draw, x, y, label, progress=progress)

    def _draw_os_logo_circle(self, draw: ImageDraw.ImageDraw, x: int, y: int, label: str):
        """绘制系统LOGO圆形"""
        self._draw_circle_base(draw, x, y, label, logo_img=self.os_logo, border_color=(220, 220, 220))

    def draw(self) -> str:
        """生成图片并返回路径"""
        # 尝试加载随机背景图
        background = self._load_random_background()
        
        # 创建图片（背景保持清晰，毛玻璃效果由面板/圆圈局部实现）
        if background:
            img = background.convert("RGBA")
            self.original_bg = background  # 保存原始背景供毛玻璃裁剪用
        else:
            img = Image.new("RGBA", (IMG_WIDTH, IMG_HEIGHT), (*BG_COLOR, 255))
            self.original_bg = None
        draw = ImageDraw.Draw(img)
        self.img = img

        # 绘制顶部标题和机器人LOGO
        title_text = "GracyBot 系统状态监控"
        if self.robot_logo:
            # 机器人LOGO放在左上角
            img.paste(self.robot_logo, (30, 20), self.robot_logo)
        
        # 标题居中显示
        title_bbox = draw.textbbox((0, 0), title_text, font=self.font_title)
        title_w = title_bbox[2] - title_bbox[0]
        title_x = (IMG_WIDTH - title_w) // 2  # 居中计算
        title_y = 30
        draw.text((title_x, title_y), title_text, font=self.font_title, fill=TITLE_COLOR)

        # 绘制机器人信息卡片
        self._draw_robot_info_card(draw, img)

        # 解析进度数据
        progress_data, value_data = self._parse_progress_data()

        # 计算四个圆圈位置（2x2排列），向下移动以容纳卡片
        circle_start_x = (IMG_WIDTH - 2*CIRCLE_RADIUS*2 - CIRCLE_SPACING) // 2
        circle_start_y = TOP_PADDING + CARD_HEIGHT + 60  # 增加间距

        # 第一行：CPU、内存
        self._draw_circle_progress(draw, circle_start_x + CIRCLE_RADIUS, circle_start_y + CIRCLE_RADIUS,
                                  progress_data["cpu"]["value"], progress_data["cpu"]["label"])
        # CPU数值显示 - 标签和数值分行显示，增加间距
        cpu_bbox = draw.textbbox((0, 0), value_data["cpu"], font=self.font_text)
        cpu_w = cpu_bbox[2] - cpu_bbox[0]
        draw.text((circle_start_x + CIRCLE_RADIUS - cpu_w/2, circle_start_y + CIRCLE_RADIUS*2 + 40),
                  value_data["cpu"], font=self.font_text, fill=TEXT_COLOR)

        self._draw_circle_progress(draw, circle_start_x + CIRCLE_RADIUS*3 + CIRCLE_SPACING, circle_start_y + CIRCLE_RADIUS,
                                  progress_data["mem"]["value"], progress_data["mem"]["label"])
        # 内存数值显示 - 标签和数值分行显示，增加间距
        mem_bbox = draw.textbbox((0, 0), value_data["mem"], font=self.font_text)
        mem_w = mem_bbox[2] - mem_bbox[0]
        draw.text((circle_start_x + CIRCLE_RADIUS*3 + CIRCLE_SPACING - mem_w/2, circle_start_y + CIRCLE_RADIUS*2 + 40),
                  value_data["mem"], font=self.font_text, fill=TEXT_COLOR)

        # 第二行：磁盘、系统LOGO
        self._draw_circle_progress(draw, circle_start_x + CIRCLE_RADIUS, circle_start_y + CIRCLE_RADIUS*3 + CIRCLE_SPACING,
                                  progress_data["disk"]["value"], progress_data["disk"]["label"])
        # 磁盘数值显示 - 标签和数值分行显示，增加间距
        disk_bbox = draw.textbbox((0, 0), value_data["disk"], font=self.font_text)
        disk_w = disk_bbox[2] - disk_bbox[0]
        draw.text((circle_start_x + CIRCLE_RADIUS - disk_w/2, circle_start_y + CIRCLE_RADIUS*4 + CIRCLE_SPACING + 40),
                  value_data["disk"], font=self.font_text, fill=TEXT_COLOR)

        self._draw_os_logo_circle(draw, circle_start_x + CIRCLE_RADIUS*3 + CIRCLE_SPACING, circle_start_y + CIRCLE_RADIUS*3 + CIRCLE_SPACING,
                                 progress_data["os"]["label"])
        # 系统标签不再重复显示，圆圈内的标签已经足够

        # 绘制详细文字信息（圆圈下方）
        text_start_y = circle_start_y + CIRCLE_RADIUS*4 + CIRCLE_SPACING + 85  # 进一步增加留白
        text_x = 50
        line_height = 30  # 增加行距
        
        # 计算文字区域总高度，绘制毛玻璃背景面板
        text_line_count = 14  # OS → 框架版本 共约14行
        text_area_height = text_line_count * line_height + 30
        self._draw_frosted_panel(
            text_x - 15, text_start_y - 15,
            text_x + CARD_WIDTH + 15, text_start_y + text_area_height,
            radius=18, alpha=165
        )

        # 系统完整信息
        os_full = self.sys_info.get("系统版本", "未知系统")
        draw.text((text_x, text_start_y), f"操作系统：{os_full}", font=self.font_text, fill=TEXT_COLOR)

        # CPU型号
        cpu_info = self.sys_info.get("CPU信息", "未知CPU")
        draw.text((text_x, text_start_y + line_height), f"CPU型号：{cpu_info}", font=self.font_text, fill=TEXT_COLOR)

        # GPU型号
        gpu_model = self.gpu_info.get("model", "未检测到GPU")
        gpu_memory = self.gpu_info.get("memory", "")
        if gpu_memory and gpu_memory != "N/A":
            gpu_text = f"GPU型号：{gpu_model} ({gpu_memory})"
        else:
            gpu_text = f"GPU型号：{gpu_model}"
        draw.text((text_x, text_start_y + line_height*2), gpu_text, font=self.font_text, fill=TEXT_COLOR)

        # Shell和Terminal环境
        line_idx = 3
        shell_term_text = f"Shell: {self.shell_terminal['shell']} | Terminal: {self.shell_terminal['terminal']}"
        draw.text((text_x, text_start_y + line_height*line_idx), shell_term_text, font=self.font_text, fill=TEXT_COLOR)

        # 所有磁盘信息（游戏血条样式）
        line_idx += 1
        draw.text((text_x, text_start_y + line_height * line_idx), "—— 磁盘分区 ——",
                  font=self.font_subtitle, fill=TITLE_COLOR)

        import re
        bar_w = 320
        bar_h = 16
        bar_x = text_x + 55
        bar_radius = bar_h // 2

        for disk_info in self.all_disks:
            line_idx += 1
            y = text_start_y + line_height * line_idx
            bar_y = y + (line_height - bar_h) // 2

            m = re.match(r'(.+?)\s+总([\d.]+)GB/已用([\d.]+)GB\(([\d.]+)%\)', disk_info)
            if m:
                mount, total_gb, used_gb, percent = m.group(1), m.group(2), m.group(3), m.group(4)
                pct = float(percent)
            else:
                mount, total_gb, used_gb, pct = "?", "0", "0", 0.0

            draw.text((text_x, y), mount, font=self.font_text, fill=TEXT_COLOR)

            draw.rounded_rectangle(
                (bar_x, bar_y, bar_x + bar_w, bar_y + bar_h),
                radius=bar_radius, fill=(210, 210, 210)
            )
            fill_w = int(bar_w * pct / 100)
            if fill_w > bar_radius * 2:
                draw.rounded_rectangle(
                    (bar_x, bar_y, bar_x + fill_w, bar_y + bar_h),
                    radius=bar_radius, fill=TITLE_COLOR
                )
            elif fill_w > 0:
                draw.rounded_rectangle(
                    (bar_x, bar_y, bar_x + max(fill_w, bar_radius * 2), bar_y + bar_h),
                    radius=bar_radius, fill=TITLE_COLOR
                )

            pct_text = f"{used_gb} / {total_gb} GB ({pct:.1f}%)"
            draw.text((bar_x + bar_w + 10, y), pct_text, font=self.font_text, fill=TEXT_COLOR)

        # IO读写速度
        line_idx += 1
        io_text = f"IO: Read: {self.io_stats['read_mb_s']} ({self.io_stats['read_iops_str']}) | Write: {self.io_stats['write_mb_s']} ({self.io_stats['write_iops_str']})"
        draw.text((text_x, text_start_y + line_height*line_idx), io_text, font=self.font_text, fill=TEXT_COLOR)

        # 网络信息
        line_idx += 1
        network_text = f"网络: {self.network_info['type']} | 上传: {self.network_info['upload']}MB | 下载: {self.network_info['download']}MB"
        draw.text((text_x, text_start_y + line_height*line_idx), network_text, font=self.font_text, fill=TEXT_COLOR)

        # 主机名称
        line_idx += 1
        host_name = self.sys_info.get("主机名称", "未知主机")
        draw.text((text_x, text_start_y + line_height*line_idx), f"主机名称：{host_name}", font=self.font_text, fill=TEXT_COLOR)

        # 系统运行时长
        line_idx += 1
        sys_uptime = self.sys_info.get("系统运行时长", "未知")
        draw.text((text_x, text_start_y + line_height*line_idx), f"系统运行时长：{sys_uptime}", font=self.font_text, fill=TEXT_COLOR)

        # 机器人启动时长
        line_idx += 1
        bot_uptime = self.sys_info.get("机器人启动时长", "未知")
        draw.text((text_x, text_start_y + line_height*line_idx), f"机器人启动时长：{bot_uptime}", font=self.font_text, fill=TEXT_COLOR)

        # 插件信息
        line_idx += 1
        plugin_info = f"已加载插件数: {self.robot_info['plugin_count']} | python包: {self.robot_info['python_package_count']} | 触发指令: {self.robot_info['command_count']}条"
        draw.text((text_x, text_start_y + line_height*line_idx), plugin_info, font=self.font_text, fill=TEXT_COLOR)

        # GracyBot版本
        line_idx += 1
        bot_version = self.sys_info.get("机器人版本", BOT_VERSION)
        draw.text((text_x, text_start_y + line_height*line_idx), f"框架版本：{bot_version}", font=self.font_text, fill=TEXT_COLOR)

        # 右下角版权信息 - 增加底部留白
        footer_text = f"Created By GracyBot v{bot_version[1:] if bot_version.startswith('v') else bot_version}"
        footer_bbox = draw.textbbox((0, 0), footer_text, font=self.font_footer)
        footer_x = IMG_WIDTH - footer_bbox[2] - 30
        footer_y = IMG_HEIGHT - footer_bbox[3] - 30  # 增加底部留白
        draw.text((footer_x, footer_y), footer_text, font=self.font_footer, fill=(0, 0, 0))

        # 保存图片（固定路径覆盖旧图，不累积历史文件）
        img_rgb = img.convert("RGB")
        img_rgb.save(OUTPUT_PATH, format="PNG", optimize=True)
        return OUTPUT_PATH
