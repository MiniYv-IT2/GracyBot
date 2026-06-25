import os
import sys
import subprocess
import logging

logger = logging.getLogger("Gracy.Screenshot")
PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(PLUGIN_DIR, ".dep_checked")

def _check_deps():
    if os.path.exists(STATE_FILE):
        return
    missing = []
    try:
        import mss
    except ImportError:
        missing.append("mss")
    try:
        from PIL import Image
    except ImportError:
        missing.append("Pillow")
    if missing:
        logger.info("[插件执行] [Screenshot] Installing dependencies: %s", ", ".join(missing))
        for pkg in missing:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", pkg],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=60
            )
        logger.info("[插件执行] [Screenshot] Dependencies installed successfully")
    with open(STATE_FILE, "w") as f:
        f.write("1")

_check_deps()

from .main import handle_screenshot
