import sys
import re
import urllib.request
import json
from typing import List


class Colors:
    RESET = '\033[0m'
    RED = '\033[91m'
    ORANGE = '\033[38;5;208m'
    YELLOW = '\033[93m'
    GREEN = '\033[92m'
    CYAN = '\033[96m'
    BLUE = '\033[94m'
    PURPLE = '\033[95m'
    BLOCK_FULL = '█'


class BlockLetterBuilder:
    def get_letter(self, char: str) -> List[str]:
        letters = {
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
                "█   █"
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
                "█████",
                "█   █",
                "█   █",
                "█████",
                "█   █",
                "█   █",
                "█████"
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
        }
        return letters.get(char, ["     "] * 7)


class GracyBotLogo:
    def __init__(self):
        self.colors = Colors()
        self.text = "GRACYBOT"
        self.letter_builder = BlockLetterBuilder()

    def _colorize(self, text: str, color: str) -> str:
        return f"{color}{text}{self.colors.RESET}"

    def _get_logo(self) -> List[str]:
        colors = [
            self.colors.RED, self.colors.ORANGE, self.colors.YELLOW,
            self.colors.GREEN, self.colors.CYAN, self.colors.BLUE,
            self.colors.PURPLE, self.colors.RED,
        ]
        block_map = {'█': self.colors.BLOCK_FULL, ' ': ' '}

        letter_blocks = []
        for char in self.text:
            letter_blocks.append(self.letter_builder.get_letter(char))

        logo_lines = []
        for i in range(7):
            line = "  "
            for j, letter in enumerate(letter_blocks):
                color_index = j % len(colors)
                colored_line = ""
                for c in letter[i]:
                    colored_line += self._colorize(block_map.get(c, c), colors[color_index])
                line += colored_line
                if j < len(letter_blocks) - 1:
                    line += "  "
            logo_lines.append(line)

        logo_lines.append("")
        return logo_lines

    @staticmethod
    def _strip_ansi(text: str) -> str:
        return re.sub(r'\033\[[0-9;]*m', '', text)

    def print_logo(self) -> None:
        logo = self._get_logo()
        is_tty = sys.stdout.isatty()
        for line in logo:
            print(self._strip_ansi(line) if not is_tty else line)

        print("")
        cat_text = "喵，Gracy酱被主人召回成功了喵(=^･ω･^=)"
        dev_info = "最好用的Bot框架 开发者QQ:192004908 小禹"
        if is_tty:
            print(f"\033[95m{cat_text}\033[0m")
            print(f"\033[35m{dev_info}\033[0m")
        else:
            print(cat_text)
            print(dev_info)

        hitokoto = None
        try:
            req = urllib.request.Request(
                "https://v1.hitokoto.cn/?c=j",
                headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=2) as resp:
                data = json.loads(resp.read())
                hitokoto = data.get("hitokoto", "")
        except Exception:
            pass

        if hitokoto:
            pink = "\033[38;5;213m"
            reset = "\033[0m"
            if is_tty:
                print(f"{pink}{hitokoto}{reset}")
            else:
                print(hitokoto)
