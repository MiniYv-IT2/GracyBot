"""GracyUI Quart 应用工厂"""
import os
from core.webserv import Quart, send_from_directory

from .routes import dashboard_bp, logs_bp, auth_bp, bot_bp

_DIST_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
_DIST_DIR = os.path.abspath(_DIST_DIR)


def create_app() -> Quart:
    # static_url_path="/static" 避免与 SPA fallback /<path:path> 冲突
    # 否则 Quart 内置静态路由会拦截 /dashboard 等前端路由，刷新直接 404
    app = Quart(__name__, static_folder=_DIST_DIR, static_url_path="/static")

    # 注册 API 蓝图
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(logs_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(bot_bp)

    # SPA 前端托管
    @app.route("/")
    async def index():
        return await send_from_directory(_DIST_DIR, "index.html")

    @app.route("/<path:path>")
    async def spa_fallback(path):
        full = os.path.join(_DIST_DIR, path)
        if os.path.isfile(full):
            return await send_from_directory(_DIST_DIR, path)
        return await send_from_directory(_DIST_DIR, "index.html")

    return app
