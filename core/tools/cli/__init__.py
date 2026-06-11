"""GracyBot CLI 工具 — 跨平台命令行入口

插件接入:
    from core.tools.cli import register_cli_command

    def my_handler():
        \"\"\"我的插件命令说明\"\"\"
        ...

    register_cli_command("mycmd", my_handler, "我的插件功能说明")
"""

from .app import gracy_cli, register_cli_command

__all__ = ["gracy_cli", "register_cli_command"]
