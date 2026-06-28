"""GracyUI 插件 — Web 管理面板
纯 Python 方案：Quart 内嵌服务，零 Node.js 依赖。
"""
import logging
import threading
import os
import socket

_logger = logging.getLogger("GracyUI")
_PANEL_PORT = 5090

# ━━━━━━━━━━ Quart 线程管理 ━━━━━━━━━

_quart_thread = None
_panel_url = None
_main_event_loop = None  # 由 main.py 设置


def _start_quart():
    """在守护线程中启动 Quart（hypercorn，带端口冲突自动重试）"""
    global _panel_url
    import time as _time
    import asyncio

    for attempt in range(5):
        try:
            from plugins.GracyUI_plugin.backend.app import create_app
            app = create_app()

            _panel_url = f"http://127.0.0.1:{_PANEL_PORT}"

            from graci import Config, serve

            cfg = Config()
            cfg.bind = [f"0.0.0.0:{_PANEL_PORT}"]
            cfg.loglevel = "warning"

            # ── 在主线程中才能注册信号处理器，子线程中需要禁用 ──
            _loop = asyncio.new_event_loop()
            asyncio.set_event_loop(_loop)
            # 覆盖 add_signal_handler（子线程不支持）
            _loop.add_signal_handler = lambda *args, **kwargs: None

            _logger.info(f"[GracyUI] Quart 正在监听 http://0.0.0.0:{_PANEL_PORT}")
            _loop.run_until_complete(serve(app, cfg))
            return
        except OSError as e:
            _logger.warning(f"[GracyUI] Quart 端口 {_PANEL_PORT} 被占用，第{attempt+1}次重试...")
            _time.sleep(2)
        except Exception as e:
            _logger.error(f"[GracyUI] Quart 启动失败: {e}")
            return
    _logger.error(f"[GracyUI] Quart 启动失败: 端口 {_PANEL_PORT} 5次重试后仍不可用")


# ━━━━━━━━━━ 模块级自启动 — 开机即启 Quart + 发地址给主人 ━━━━━━━━━

def _boot_panel_and_notify():
    """开机自动启动 Quart 面板，并把地址发给主人"""
    import time as _t
    _t.sleep(2)  # 等核心模块、适配器全部初始化完成

    # 启动 Quart
    global _quart_thread
    _quart_thread = threading.Thread(target=_start_quart, daemon=True, name="GracyUI-Quart")
    _quart_thread.start()
    _t.sleep(2)  # 等 Quart 绑定端口

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
        from graci import gracy_send_msg
        from graci import GracyText
        from graci import get_current_master_id
        import asyncio

        # 从 RuntimeContext 获取当前实例的主人 ID
        _master_id = get_current_master_id()

        # 检查是否首次运行（占位符值）
        _is_first_run = not _master_id
        if _is_first_run:
            _logger.info("[GracyUI] master_id 未配置，跳过发送面板地址（请先编辑 config.json 填写 master_id）")
            _logger.info(f"[GracyUI] Quart 正在监听 http://0.0.0.0:{_PANEL_PORT}")
            return

        lan = f"\n🌐 局域网：http://{local_ip}:{_PANEL_PORT}"
        from graci import BOT_VERSION
        ver = BOT_VERSION.removeprefix('v') if BOT_VERSION.startswith('v') else BOT_VERSION
        msg = (
            "🎛️ GracyUI 管理面板已启动\n"
            f"版本 v{ver}\n\n"
            f"🔗 本地：http://127.0.0.1:{_PANEL_PORT}{lan}\n\n"
            "📋 输入 /管理面板 可重新获取地址"
        )

        # 在子线程中，通过 run_coroutine_threadsafe 把任务调度到主循环
        try:
            import asyncio as _asyncio
            if _main_event_loop:
                future = _asyncio.run_coroutine_threadsafe(
                    gracy_send_msg(_master_id, GracyText(text=msg), chat_type="private"),
                    _main_event_loop
                )
                future.result(timeout=10)
            else:
                # 退而求其次
                _asyncio.run(gracy_send_msg(_master_id, GracyText(text=msg), chat_type="private"))
        except Exception as _e:
            _logger.warning(f"[GracyUI] 调度发送失败: {_e}")
        _logger.info(f"[GracyUI] ✔ 面板已自启，地址已发送给主人")
    except Exception as e:
        _logger.error(f"[GracyUI] 启动通知失败: {e}")


def start_panel_boot():
    """由框架 on_ready 钩子调用启动面板"""
    global _main_event_loop
    import asyncio
    _main_event_loop = asyncio.get_event_loop()

    if not os.environ.get("GRACY_NO_WEBUI"):
        _boot_thread = threading.Thread(target=_boot_panel_and_notify, daemon=True, name="GracyUI-Boot")
        _boot_thread.start()
    else:
        _logger.info("[GracyUI] GRACY_NO_WEBUI 已设置，跳过自启面板")


# 注册 on_ready 钩子（框架初始化完成后自动调用）
try:
    from graci import plugin_manager
    plugin_manager.register_on_ready(start_panel_boot)
except ImportError:
    pass


# ━━━━━━━━━━ 命令处理 ━━━━━━━━━

async def handle_gracy_ui(plugin_manager, send_msg, data, sender_id, chat_type, permission, logger):
    logger.info(f"[GracyUI] 接收到命令，发送者: {sender_id}")
    try:
        await _start_or_get_url(send_msg, sender_id, chat_type, logger)
    except Exception as e:
        logger.error(f"[GracyUI] 处理失败: {e}")
        try:
            await send_msg(sender_id, "⚠️ GracyUI 面板暂不可用，请检查依赖", chat_type=chat_type)
        except Exception:
            pass


async def _start_or_get_url(send_msg, sender_id, chat_type, logger):
    global _panel_url, _quart_thread

    # 还没启动才启动（通常开机已自启，这里做兜底）
    if _quart_thread is None or not _quart_thread.is_alive():
        logger.info("[GracyUI] 首次请求，启动 Quart 面板服务...")
        _quart_thread = threading.Thread(target=_start_quart, daemon=True, name="GracyUI-Quart")
        _quart_thread.start()
        import time as _t
        _t.sleep(1.5)  # 等 Quart 绑定端口

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
        from graci import BOT_VERSION
        ver = BOT_VERSION.removeprefix('v') if BOT_VERSION.startswith('v') else BOT_VERSION
        lan = f"\n🌐 局域网：http://{local_ip}:{_PANEL_PORT}" if local_ip != "127.0.0.1" else ""
        await send_msg(sender_id, chat_type,
            f"🎛️ GracyUI 管理面板\n版本 v{ver}\n\n"
            f"🔗 本地：{_panel_url}{lan}")
    else:
        await send_msg(sender_id, chat_type, "⚠️ GracyUI 面板启动中，请稍后再试")
