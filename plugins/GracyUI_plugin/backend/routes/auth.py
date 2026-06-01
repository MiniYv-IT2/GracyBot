"""登录认证 API"""
import secrets
from flask import Blueprint, request

auth_bp = Blueprint("auth", __name__, url_prefix="/api")

# 默认密码，后续可从 config.json 读取
_DEFAULT_PASSWORD = "gracyui"

# 简易 token 池（进程内存，重启即失效）
_tokens: set[str] = set()


@auth_bp.route("/auth/login", methods=["POST"])
def api_login():
    """POST /api/auth/login  body: {username, password}"""
    data = request.get_json(silent=True) or {}
    password = data.get("password", "")

    if password == _DEFAULT_PASSWORD:
        token = secrets.token_hex(16)
        _tokens.add(token)
        return {"success": True, "token": token, "username": data.get("username", "主人")}
    return {"success": False, "message": "密码错误"}, 401


@auth_bp.route("/auth/verify")
def api_verify():
    """GET /api/auth/verify?token=xxx"""
    token = request.args.get("token", "")
    return {"valid": token in _tokens}
