"""Quart + Hypercorn 封装 — 唯一 import Quart/Hypercorn 的文件"""

Quart = None
request = None
jsonify = None
Blueprint = None
send_from_directory = None

Config = None  # hypercorn.config.Config
serve = None   # hypercorn.asyncio.serve


def create_app(import_name: str = __name__):
    """创建 Quart 应用，未安装时返回 None"""
    if Quart is None:
        return None
    return Quart(import_name)


async def run_server(app, port: int, host: str = "0.0.0.0"):
    """启动 Hypercorn 服务器"""
    if Quart is None:
        raise RuntimeError("Quart/Hypercorn 未安装，无法启动 HTTP 服务")

    from hypercorn.config import Config as _Config
    from hypercorn.asyncio import serve as _serve

    cfg = _Config()
    cfg.bind = [f"{host}:{port}"]
    cfg.loglevel = "warning"
    await _serve(app, cfg)


try:
    from quart import (
        Quart as _Quart,
        request as _request,
        jsonify as _jsonify,
        Blueprint as _Blueprint,
        send_from_directory as _send_from_directory,
    )
    Quart = _Quart
    request = _request
    jsonify = _jsonify
    Blueprint = _Blueprint
    send_from_directory = _send_from_directory
except ImportError:
    pass

try:
    from hypercorn.config import Config as _Config
    from hypercorn.asyncio import serve as _serve
    Config = _Config
    serve = _serve
except ImportError:
    pass
