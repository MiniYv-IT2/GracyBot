"""
Gracone_Plugin.py — GracyBot ↔ NoneBot 兼容层（薄入口）

由三个文件组成:
  gracone_core.py    加载引擎、补丁、EventBus
  gracone_admin.py   管理命令（状态/禁用/启用/安装/搜索）
  Gracone_Plugin.py  本文件（薄入口，仅做导入+初始化）

注意: metadata.toml 的 handler.entry = "handle_gracone"，
      故须在此文件公开 handle_gracone 符号以供 GracyBot 框架发现。
"""

# ── 第 0 层：必须先于一切加载命名空间注入 ──
import sys
import os

# 将本插件目录加入 sys.path，使同目录下的 .py 可被正常导入
_gracone_dir = os.path.dirname(os.path.abspath(__file__))
if _gracone_dir not in sys.path:
    sys.path.insert(0, _gracone_dir)

# 注入 nonebot 虚拟命名空间（必须在任何 NoneBot 插件 import 之前）
import gracone_nonebot  # noqa: F401 — 执行 sys.modules 注入

# 注入外部插件虚拟命名空间（alconna, uninfo, orm 等）
import gracone_ext_plugins  # noqa: F401

# ── 第 2 层：Gracone 引擎 + 管理命令 ──
# （@on_command 装饰器在 import 时注册命令）
from gracone_admin import handle_gracone  # noqa: F401 — 框架通过此符号发现 handler
from gracone_core import initialize

# ── 第 3 层：启动 ──
initialize()
