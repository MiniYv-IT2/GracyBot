"""Bot 信息 API — QQ 头像 / 昵称"""
from graci import Blueprint

bot_bp = Blueprint("bot", __name__, url_prefix="/api")


@bot_bp.route("/bot-info")
async def api_bot_info():
    """返回 Bot QQ 号和头像 URL"""
    robot_id = ""
    nickname = "GracyBot"
    try:
        from graci import ROBOT_ID
        robot_id = str(ROBOT_ID)
    except Exception:
        pass

    try:
        from graci import gracy_get_platform_info
        info = await gracy_get_platform_info()
        nickname = info.get("nickname", "GracyBot")
    except Exception:
        pass

    avatar_url = ""
    if robot_id:
        avatar_url = f"https://q1.qlogo.cn/g?b=qq&nk={robot_id}&s=640"

    return {
        "robot_id": robot_id,
        "nickname": nickname,
        "avatar_url": avatar_url,
    }
