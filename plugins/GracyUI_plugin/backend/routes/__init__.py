"""GracyUI 后端路由 Blueprint 注册"""

from .dashboard import dashboard_bp
from .logs import logs_bp
from .auth import auth_bp
from .bot import bot_bp

__all__ = ["dashboard_bp", "logs_bp", "auth_bp", "bot_bp"]
