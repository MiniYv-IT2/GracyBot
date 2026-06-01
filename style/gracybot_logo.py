import sys
import os
import re
from typing import List, Dict, Tuple, Optional

# 颜色定义 - 樱花粉系列
class Colors:
    # ANSI颜色代码
    RESET = '\033[0m'
    PINK_LIGHT = '\033[95m'  # 浅粉色
    PINK_MEDIUM = '\033[35m'  # 中粉色
    PINK_DARK = '\033[38;5;135m'  # 深粉色
    CYAN = '\033[96m'  # 青色(用于装饰)
    WHITE = '\033[97m'  # 白色
    
    # 方块字符
    BLOCK_FULL = '█'  # 全方块
    BLOCK_HALF = '▓'  # 半方块
    BLOCK_LIGHT = '▒'  # 浅方块
    BLOCK_THIN = '░'  # 最浅方块
    
    @staticmethod
    def supports_color() -> bool:
        """检查终端是否支持颜色"""
        return sys.stdout.isatty()

# GracyBot字符串识别器
class GracyBotDetector:
    @staticmethod
    def is_gracybot(text: str) -> bool:
        """检查文本是否为GracyBot(大小写不敏感)"""
        # 支持大小写和变体
        pattern = r'^gracybot$'
        return bool(re.match(pattern, text.lower()))
    
    @staticmethod
    def get_variants() -> List[str]:
        """获取GracyBot的常见变体"""
        return [
            "GracyBot",
            "gracybot",
            "GRACYBOT",
            "Gracybot",
            "GRacyBot"
        ]

# 字母构建器 - 使用方块字符构建字母
class BlockLetterBuilder:
    def __init__(self, colors: Colors):
        self.colors = colors
    
    def get_letter(self, char: str, color: str) -> List[str]:
        """获取字母的方块字符表示"""
        # 为每个字母定义7行的方块字符表示
        # 同时支持大写和小写字母
        # 字母定义（使用标准ASCII方块字符表示）
        letters = {
            # 大写字母
            'G': [
                "█████",
                "█    ",
                "█    ",
                "█ ███",
                "█   █",
                "█   █",
                "█████"
            ],
            'R': [
                "█████",
                "█   █",
                "█   █",
                "████ ",
                "█  █ ",
                "█   █",
                "█  ██"
            ],
            'A': [
                " ███ ",
                "█   █",
                "█   █",
                "█████",
                "█   █",
                "█   █",
                "█   █"
            ],
            'C': [
                "█████",
                "█    ",
                "█    ",
                "█    ",
                "█    ",
                "█    ",
                "█████"
            ],
            'Y': [
                "█   █",
                "█   █",
                " █ █ ",
                "  █  ",
                "  █  ",
                "  █  ",
                "  █  "
            ],
            'B': [
                "████ ",
                "█  █ ",
                "████ ",
                "█  █ ",
                "█  █ ",
                "████ ",
                "████ "
            ],
            'O': [
                " ███ ",
                "█   █",
                "█   █",
                "█   █",
                "█   █",
                "█   █",
                " ███ "
            ],
            'T': [
                "█████",
                "  █  ",
                "  █  ",
                "  █  ",
                "  █  ",
                "  █  ",
                "  █  "
            ],
            # 小写字母（如果需要不同样式可以添加）
            'g': [
                "█████",
                "█    ",
                "█    ",
                "█ ███",
                "█   █",
                "█   █",
                "█████"
            ],
            'r': [
                "████ ",
                "█  █ ",
                "█  █ ",
                "████ ",
                "█    ",
                "█    ",
                "█  █ "
            ],
            'a': [
                " ███ ",
                "█   █",
                "█   █",
                "█████",
                "█   █",
                "█   █",
                "█   █"
            ],
            'c': [
                "█████",
                "█    ",
                "█    ",
                "█    ",
                "█    ",
                "█    ",
                "█████"
            ],
            'y': [
                "█   █",
                "█   █",
                " █ █ ",
                "  █  ",
                "  █  ",
                "  █  ",
                "  █  "
            ],
            'b': [
                "████ ",
                "█  █ ",
                "████ ",
                "█  █ ",
                "█  █ ",
                "████ ",
                "████ "
            ],
            'o': [
                " ███ ",
                "█   █",
                "█   █",
                "█   █",
                "█   █",
                "█   █",
                " ███ "
            ],
            't': [
                "█████",
                "  █  ",
                "  █  ",
                "  █  ",
                "  █  ",
                "  █  ",
                "  █  "
            ],
            ' ': [
                "     ",
                "     ",
                "     ",
                "     ",
                "     ",
                "     ",
                "     "
            ]
        }
        
        # 返回字母的表示，如果不存在则返回空格
        return letters.get(char, letters[' '])

# GracyBot艺术字设计 - 使用方块字符构建
class GracyBotLogo:
    def __init__(self, compact_mode: bool = False, text: str = "GRACYBOT", force_color: bool = True):
        """初始化Logo生成器
        
        Args:
            compact_mode: 是否使用紧凑模式(适合手机显示)
            text: 要显示的文本，默认为"GRACYBOT"
            force_color: 是否强制使用颜色，默认为True
        """
        self.compact_mode = compact_mode
        self.text = text.upper()  # 强制转换为大写
        self.colors = Colors()
        self.use_color = force_color or self.colors.supports_color()
        self.letter_builder = BlockLetterBuilder(self.colors)
        self.detector = GracyBotDetector()
    
    def get_logo(self) -> List[str]:
        """获取Logo的字符行列表"""
        if self.compact_mode:
            return self._get_compact_logo()
        return self._get_full_logo()
    
    def _colorize(self, text: str, color: str) -> str:
        """为文本添加颜色"""
        # 强制使用颜色，直接返回带有ANSI颜色代码的文本
        return f"{color}{text}{self.colors.RESET}"
    
    def _get_full_logo(self) -> List[str]:
        """获取完整版本的Logo(适合PC显示)"""
        # 为GracyBot八个字母分别生成颜色 - 使用统一的粉色系
        colors = [
            self.colors.PINK_LIGHT,   # G
            self.colors.PINK_LIGHT,   # r
            self.colors.PINK_LIGHT,   # a
            self.colors.PINK_LIGHT,   # c
            self.colors.PINK_LIGHT,   # y
            self.colors.PINK_LIGHT,   # B
            self.colors.PINK_LIGHT,   # o
            self.colors.PINK_LIGHT    # t
        ]
        
        # 方块字符映射
        block_map = {'█': self.colors.BLOCK_FULL, ' ': ' '}
        
        # 为每个字母生成方块字符表示
        letter_blocks = []
        for char in self.text:
            letter_blocks.append(self.letter_builder.get_letter(char, ''))
        
        # 合并所有字母的行
        logo_lines = []
        for i in range(7):  # 每个字母有7行
            line = "  "  # 左边距
            for j, letter in enumerate(letter_blocks):
                # 为每个字母添加对应的颜色和方块字符替换
                color_index = j % len(colors)
                colored_line = ""
                for c in letter[i]:
                    colored_char = block_map.get(c, c)
                    colored_line += self._colorize(colored_char, colors[color_index])
                line += colored_line
                # 在字母之间添加两个空格以增强可读性
                if j < len(letter_blocks) - 1:
                    line += "  "
            logo_lines.append(line)
        
        # 添加装饰和标识
        is_gracybot = self.detector.is_gracybot(self.text)
        if is_gracybot:
            logo_lines.append("")
        
        # 添加樱花装饰
        if is_gracybot:
            # 使用方块字符创建装饰行，每个字母对应一个装饰元素
            decor_line = "  "
            # 创建樱花粉装饰元素
            decor_element = self._colorize(self.colors.BLOCK_FULL, self.colors.PINK_LIGHT)
            light_element = self._colorize(self.colors.BLOCK_LIGHT, self.colors.PINK_LIGHT)
            # 交替使用不同亮度的装饰元素
            for k in range(8):  # 固定8个装饰元素，对应GracyBot八个字母
                if k % 2 == 0:
                    decor_line += decor_element
                else:
                    decor_line += light_element
                if k < 7:
                    decor_line += " "
            logo_lines.append(decor_line)
        
        return logo_lines
    
    def _get_compact_logo(self) -> List[str]:
        """获取紧凑版本的Logo(适合手机显示)"""
        # 紧凑模式下使用更简单的字母表示
        compact_letters = {
            'G': [
                f"{self.colors.BLOCK_FULL*3}",
                f"{self.colors.BLOCK_FULL} {self.colors.BLOCK_FULL}",
                f"{self.colors.BLOCK_FULL} {self.colors.BLOCK_FULL}",
                f"{self.colors.BLOCK_FULL*3}",
                f"{self.colors.BLOCK_FULL}   ",
                f"{self.colors.BLOCK_FULL}   ",
                f"{self.colors.BLOCK_FULL*3}"
            ],
            'r': [
                f"{self.colors.BLOCK_FULL*3}",
                f"{self.colors.BLOCK_FULL}  ",
                f"{self.colors.BLOCK_FULL*3}",
                f"{self.colors.BLOCK_FULL}  ",
                f"{self.colors.BLOCK_FULL}  ",
                f"{self.colors.BLOCK_FULL}  ",
                f"{self.colors.BLOCK_FULL}  "
            ],
            'a': [
                f" {self.colors.BLOCK_FULL*2}",
                f"{self.colors.BLOCK_FULL*3}",
                f"{self.colors.BLOCK_FULL} {self.colors.BLOCK_FULL}",
                f"{self.colors.BLOCK_FULL} {self.colors.BLOCK_FULL}",
                f"{self.colors.BLOCK_FULL*3}",
                f"      ",
                f"      "
            ],
            'c': [
                f"{self.colors.BLOCK_FULL*3}",
                f"{self.colors.BLOCK_FULL}  ",
                f"{self.colors.BLOCK_FULL}  ",
                f"{self.colors.BLOCK_FULL}  ",
                f"{self.colors.BLOCK_FULL}  ",
                f"{self.colors.BLOCK_FULL*3}",
                f"      "
            ],
            'y': [
                f"{self.colors.BLOCK_THIN} {self.colors.BLOCK_THIN}",
                f" {self.colors.BLOCK_THIN} ",
                f"  {self.colors.BLOCK_FULL}",
                f"  {self.colors.BLOCK_FULL}",
                f"  {self.colors.BLOCK_FULL}",
                f"  {self.colors.BLOCK_FULL}",
                f"  {self.colors.BLOCK_FULL}"
            ],
            'B': [
                f"{self.colors.BLOCK_FULL*3}",
                f"{self.colors.BLOCK_FULL} {self.colors.BLOCK_FULL}",
                f"{self.colors.BLOCK_FULL*3}",
                f"{self.colors.BLOCK_FULL} {self.colors.BLOCK_FULL}",
                f"{self.colors.BLOCK_FULL} {self.colors.BLOCK_FULL}",
                f"{self.colors.BLOCK_FULL*3}",
                f"      "
            ],
            'o': [
                f" {self.colors.BLOCK_FULL*2}",
                f"{self.colors.BLOCK_FULL*3}",
                f"{self.colors.BLOCK_FULL} {self.colors.BLOCK_FULL}",
                f"{self.colors.BLOCK_FULL} {self.colors.BLOCK_FULL}",
                f"{self.colors.BLOCK_FULL*3}",
                f" {self.colors.BLOCK_FULL*2}",
                f"      "
            ],
            't': [
                f"{self.colors.BLOCK_FULL*3}",
                f" {self.colors.BLOCK_FULL} ",
                f" {self.colors.BLOCK_FULL} ",
                f" {self.colors.BLOCK_FULL} ",
                f" {self.colors.BLOCK_FULL} ",
                f" {self.colors.BLOCK_FULL} ",
                f" {self.colors.BLOCK_FULL} "
            ],
            ' ': [
                "   ",
                "   ",
                "   ",
                "   ",
                "   ",
                "   ",
                "   "
            ]
        }
        
        # 为每个字母生成方块字符表示
        letter_blocks = []
        for char in self.text:
            letter_blocks.append(compact_letters.get(char, compact_letters[' ']))
        
        # 合并所有字母的行
        logo_lines = []
        for i in range(7):  # 每个字母有7行
            line = ""
            for j, letter in enumerate(letter_blocks):
                line += letter[i]
            logo_lines.append(line)
        
        # 添加识别标识
        is_gracybot = self.detector.is_gracybot(self.text)
        if is_gracybot:
            logo_lines.append("")
            logo_lines.append("[GracyBot - 八个字母]")
        
        return logo_lines
    
    def print_logo(self) -> None:
        """打印Logo到控制台"""
        logo = self.get_logo()
        for line in logo:
            print(line)
        
        print("")
        # 猫咪颜文字，高亮粉色标记 - 使用直接的ANSI颜色代码
        cat_emoji = "(=^･ω･^=)"
        cat_text = f"喵，Gracy酱被主人召回成功了喵{cat_emoji}"
        print(f"\033[95m{cat_text}\033[0m")  # 粉色ANSI代码
        
        # 开发者信息 - 使用直接的ANSI颜色代码
        dev_info = "最好用的Bot框架 开发者QQ:192004908 小禹"
        print(f"\033[35m{dev_info}\033[0m")  # 紫色ANSI代码(作为粉色的后备)

# 适配方案 - 检测终端类型并选择合适的显示模式
class TerminalAdapter:
    @staticmethod
    def detect_terminal_width() -> int:
        """检测终端宽度"""
        try:
            # 尝试获取终端大小
            width = os.get_terminal_size().columns
            return width
        except:
            # 默认宽度
            return 80
    
    @staticmethod
    def should_use_compact_mode() -> bool:
        """判断是否应该使用紧凑模式"""
        # 宽度小于60的终端使用紧凑模式
        return TerminalAdapter.detect_terminal_width() < 60



# 命令行接口
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='GracyBot Logo 艺术字生成器')
    parser.add_argument('--compact', action='store_true', help='使用紧凑模式(适合手机)')
    parser.add_argument('--no-color', action='store_true', help='不使用颜色')

    parser.add_argument('--text', type=str, default='GracyBot', help='自定义显示文本')
    
    args = parser.parse_args()
    
    # 检测是否应该使用紧凑模式
    use_compact = args.compact or TerminalAdapter.should_use_compact_mode()
    
    # 创建并显示Logo
    logo = GracyBotLogo(compact_mode=use_compact, text=args.text)
    if args.no_color:
        logo.use_color = False
    logo.print_logo()
    
    # 显示使用提示
