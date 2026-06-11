"""HTTP 回调安全校验层 — 频率限制、输入验证、戳一戳事件

不再持有 ROBOT_ID 全局常量，不再硬编码 OneBot 解析器。
robot_id / master_id 由各适配器实例自行管理。
"""

from quart import jsonify
from quart import request as _quart_request

from core.utils import logger
from core.gracy_adapter.send import gracy_send_msg
from core.gracy_adapter.message import GracyText
from core.security import sanitize_log
from core.security_manager import security_manager


async def callback_base():
    try:
        # 获取客户端IP进行频率限制检查
        client_ip = _quart_request.remote_addr
        if not security_manager.check_rate_limit(client_ip):
            logger.warning(f"[安全防护] 客户端IP {client_ip} 频率超限")
            return jsonify({"retcode": 429, "msg": "请求频率过高，请稍后再试"}), 429

        data = await _quart_request.get_json()
        if not data:
            logger.error(sanitize_log(f"[回调基础] 接收消息为空"))
            return jsonify({"retcode": 1, "msg": "消息为空"}), 400

        # 输入验证
        if not security_manager.validate_input(data):
            logger.warning(f"[安全防护] 输入数据验证失败，可能包含恶意内容")
            return jsonify({"retcode": 403, "msg": "输入内容不合法"}), 403

        # 心跳/metaevent 静默处理
        if data.get("post_type") == "meta_event":
            return jsonify({"retcode": 0})

        # 通知类事件（含戳一戳）由 OneBot 适配器 parse_event 处理并发布到 EventBus，
        # 插件通过 EventBus 订阅即可，core 不硬编码任何插件。
        if data.get("post_type") == "notice":
            return jsonify({"retcode": 0})

        # 返回原始数据，由 main.py 的 _get_http_parser() 统一解析
        # （模块级不再持有全局 OneBot 解析器，避免 ROBOT_ID 硬编码）
        return {
            "chat_type": data.get("message_type", "private"),
            "sender_id": str(data.get("user_id", "")),
            "target_id": str(data.get("user_id", "") if data.get("message_type") == "private" else data.get("group_id", "")),
            "raw_msg": data.get("raw_message", ""),
            "nickname": data.get("sender", {}).get("nickname", "") if isinstance(data.get("sender"), dict) else "",
            "is_at_bot": False,
            "data": data
        }
    except Exception as e:
        logger.error(sanitize_log(f"[适配器回调] 处理异常：{type(e).__name__}，原因：{str(e)}"))
        return jsonify({"retcode": 1, "msg": f"回调处理异常：{str(e)}"}), 500
