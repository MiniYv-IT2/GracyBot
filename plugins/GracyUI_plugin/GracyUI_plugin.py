"""GracyUI 插件 — Web 管理面板
纯 Python 方案：Flask 内嵌服务，零 Node.js 依赖。
"""
import logging
import threading
import os
import socket

_logger = logging.getLogger("GracyUI")
_PANEL_PORT = 5090

# ━━━━━━━━━━ Flask 线程管理 ━━━━━━━━━

_flask_thread = None
_panel_url = None


def _start_flask():
    """在守护线程中启动 Flask（带端口冲突自动重试）"""
    global _panel_url
    import time as _time

    for attempt in range(5):
        try:
            from plugins.GracyUI_plugin.backend.app import create_app
            app = create_app()

            import logging as _flog
            _flog.getLogger("werkzeug").setLevel(_flog.WARNING)

            _panel_url = f"http://127.0.0.1:{_PANEL_PORT}"

            # 用 werkzeug 直接起，绑定 0.0.0.0 允许局域网设备访问
            from werkzeug.serving import make_server
            server = make_server("0.0.0.0", _PANEL_PORT, app, threaded=True)
            _logger.info(f"[GracyUI] Flask 正在监听 http://0.0.0.0:{_PANEL_PORT}")
            server.serve_forever()
            return
        except OSError as e:
            _logger.warning(f"[GracyUI] Flask 端口 {_PANEL_PORT} 被占用，第{attempt+1}次重试...")
            _time.sleep(2)
        except Exception as e:
            _logger.error(f"[GracyUI] Flask 启动失败: {e}")
            return
    _logger.error(f"[GracyUI] Flask 启动失败: 端口 {_PANEL_PORT} 5次重试后仍不可用")


# ━━━━━━━━━━ 模块级自启动 — 开机即启 Flask + 发地址给主人 ━━━━━━━━━

def _boot_panel_and_notify():
    """开机自动启动 Flask 面板，并把地址发给主人"""
    import time as _t
    _t.sleep(2)  # 等核心模块、适配器全部初始化完成

    # 启动 Flask
    global _flask_thread
    _flask_thread = threading.Thread(target=_start_flask, daemon=True, name="GracyUI-Flask")
    _flask_thread.start()
    _t.sleep(2)  # 等 Flask 绑定端口

    # 获取局域网 IP
    local_ip = "127.0.0.1"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass

    # 发地址给主人
    try:
        from core.gracy_adapter.send import gracy_send_msg
        from core.gracy_adapter.message import GracyText
        from core.config import MASTER_ID

        lan = f"\n🌐 局域网：http://{local_ip}:{_PANEL_PORT}"
        msg = (
            "🎛️ GracyUI 管理面板已启动\n"
            f"版本 v1.9.2\n\n"
            f"🔗 本地：http://127.0.0.1:{_PANEL_PORT}{lan}\n\n"
            "📋 输入 /管理面板 可重新获取地址"
        )
        gracy_send_msg(MASTER_ID, GracyText(text=msg), chat_type="private")
        _logger.info(f"[GracyUI] ✔ 面板已自启，地址已发送给主人")
    except Exception as e:
        _logger.error(f"[GracyUI] 启动通知失败: {e}")


_boot_thread = threading.Thread(target=_boot_panel_and_notify, daemon=True, name="GracyUI-Boot")
_boot_thread.start()


# ━━━━━━━━━━ 命令处理 ━━━━━━━━━

def handle_gracy_ui(plugin_manager, send_msg, data, sender_id, chat_type, permission, logger):
    logger.info(f"[GracyUI] 接收到命令，发送者: {sender_id}")
    try:
        _start_or_get_url(send_msg, sender_id, chat_type, logger)
    except Exception as e:
        logger.error(f"[GracyUI] 处理失败: {e}")
        try:
            send_msg(sender_id, chat_type, "⚠️ GracyUI 面板暂不可用，请检查依赖")
        except Exception:
            pass


def _start_or_get_url(send_msg, sender_id, chat_type, logger):
    global _panel_url, _flask_thread

    # 还没启动才启动（通常开机已自启，这里做兜底）
    if _flask_thread is None or not _flask_thread.is_alive():
        logger.info("[GracyUI] 首次请求，启动 Flask 面板服务...")
        _flask_thread = threading.Thread(target=_start_flask, daemon=True, name="GracyUI-Flask")
        _flask_thread.start()
        import time as _t
        _t.sleep(1.5)  # 等 Flask 绑定端口

    # 获取本机 IP
    local_ip = "127.0.0.1"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass

    if _panel_url:
        lan = f"\n🌐 局域网：http://{local_ip}:{_PANEL_PORT}" if local_ip != "127.0.0.1" else ""
        send_msg(sender_id, chat_type,
            f"🎛️ GracyUI 管理面板\n版本 v1.9.2\n\n"
            f"🔗 本地：{_panel_url}{lan}")
    else:
        send_msg(sender_id, chat_type, "⚠️ GracyUI 面板启动中，请稍后再试")
