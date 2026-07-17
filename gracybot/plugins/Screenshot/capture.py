import os
import time
import mss
from PIL import Image

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "image")

def capture_screen():
    os.makedirs(DATA_DIR, exist_ok=True)
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        img = sct.grab(monitor)
        pil_img = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")
    filename = "screenshot_{}.png".format(int(time.time() * 1000))
    path = os.path.join(DATA_DIR, filename)
    pil_img.save(path, format="PNG", optimize=True)
    return path
