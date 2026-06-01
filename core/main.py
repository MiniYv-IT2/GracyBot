"""GracyBot 核心主模块 — 所有应用逻辑（Flask、路由、启动、关闭）"""
import multiprocessing
try:
    multiprocessing.set_start_method('spawn')
except RuntimeError:
    pass

from flask import Flask, request, jsonify
import json
import os
import threading
import time
import sys
import traceback
import logging

from core.config import ROBOT_ID, CALLBACK_PORT, MASTER_ID, BOT_VERSION
from core.handler import callback_base, dispatch_plugin_cmd
from core.plugin_manager import plugin_manager, PLUGIN_REGISTRY
from core.utils import logger, logger_manager  # 复用utils全局日志和消息工具
from core.gracy_adapter.send import gracy_send_msg
from core.gracy_adapter.message import GracyText
from core.config_manager import config_manager
from core.monitor import monitor_manager, register_health_check_routes

# ========== Flask应用初始化 ==========
app = Flask(__name__)
# 彻底关闭Werkzeug请求日志
for _log_name in ('werkzeug', 'werkzeug.serving'):
    _wk_log = logging.getLogger(_log_name)
    _wk_log.disabled = True
    _wk_log.setLevel(logging.CRITICAL)
    _wk_log.handlers = []


# 回调接口（增强错误处理版本）
@app.route('/callback', methods=['POST'])
def callback():
    context = {
        'client_ip': request.remote_addr,
        'request_id': str(time.time())[-6:],  # 简单的请求ID生成
        'path': request.path
    }

    # 记录收到的消息
    monitor_manager.record_message_received()

    start_time = time.time()

    try:
        # 检查Content-Type
        if request.content_type != 'application/json':
            error_msg = f"不支持的Content-Type: {request.content_type}"
            logger_manager.log_with_context(logger, logging.WARNING, error_msg, context)
            monitor_manager.record_message_error()
            return jsonify({"retcode": 415, "msg": "仅支持application/json格式"}), 415

        # 获取并验证JSON数据
        try:
            json_data = request.get_json()
            if json_data is None:
                error_msg = "请求体无法解析为JSON格式"
                logger_manager.log_with_context(logger, logging.ERROR, error_msg, context)
                monitor_manager.record_message_error()
                return jsonify({"retcode": 400, "msg": "无效的JSON格式"}), 400
        except Exception as json_err:
            error_msg = f"JSON解析失败: {str(json_err)}"
            logger_manager.log_with_context(logger, logging.ERROR, error_msg, context)
            monitor_manager.record_message_error()
            return jsonify({"retcode": 400, "msg": "JSON解析错误"}), 400

        # 心跳/metaevent 静默处理，不记日志
        if json_data.get("post_type") == "meta_event":
            return jsonify({"retcode": 0})

        # 调用基础处理函数
        try:
            parsed_data = callback_base()
        except TimeoutError:
            error_msg = "处理超时"
            logger_manager.log_with_context(logger, logging.ERROR, error_msg, context, exc_info=True)
            monitor_manager.record_message_error()
            return jsonify({"retcode": 504, "msg": "请求处理超时"}), 504
        except ValueError as val_err:
            error_msg = f"数据验证失败: {str(val_err)}"
            logger_manager.log_with_context(logger, logging.ERROR, error_msg, context)
            monitor_manager.record_message_error()
            return jsonify({"retcode": 400, "msg": f"数据验证错误: {str(val_err)}"}), 400
        except PermissionError as perm_err:
            error_msg = f"权限验证失败: {str(perm_err)}"
            logger_manager.log_with_context(logger, logging.WARNING, error_msg, context)
            monitor_manager.record_message_error()
            return jsonify({"retcode": 403, "msg": "权限不足"}), 403
        except Exception as base_err:
            error_msg = f"基础处理函数异常: {str(base_err)}"
            logger_manager.log_with_context(logger, logging.ERROR, error_msg, context, exc_info=True)
            monitor_manager.record_message_error()
            return jsonify({"retcode": 500, "msg": "处理过程异常"}), 500

        # 分发命令处理
        if isinstance(parsed_data, dict):
            try:
                ret = dispatch_plugin_cmd(parsed_data)
                processing_time = time.time() - start_time
                monitor_manager.record_message_processed(processing_time)
                # 解包：dispatch 现在返回 (response, handled) 或 (response, status, handled)
                if len(ret) == 3:
                    result, status_code, handled = ret
                else:
                    result, handled = ret
                    status_code = None

                if handled:
                    logger.info('请求处理成功')
                else:
                    raw_msg = parsed_data.get("raw_msg", "")
                    # 只在消息以已注册指令开头时记录失败（白名单 + startswith，避免 CQ 码误触）
                    # 跳过 CQ 码（系统消息）和 // 前缀（AI 聊天触发器）
                    if not raw_msg.startswith("[CQ:"):
                        builtin_cmds = {"/关机", "/重启", "/开机", "/关于"}
                        all_cmds = set(builtin_cmds)
                        for p in PLUGIN_REGISTRY:
                            for cmd in p.get("commands", []):
                                if cmd != "//":  # AI 触发前缀，非传统指令
                                    all_cmds.add(cmd)
                        if any(raw_msg.startswith(cmd) for cmd in all_cmds):
                            logger.info(f'指令未匹配任何插件: {raw_msg[:30]}')

                if status_code is not None:
                    return result, status_code
                return result
            except Exception as dispatch_err:
                error_msg = f"命令分发异常: {str(dispatch_err)}"
                logger_manager.log_with_context(logger, logging.ERROR, error_msg, context, exc_info=True)
                monitor_manager.record_message_error()
                return jsonify({"retcode": 500, "msg": "服务繁忙，请稍后再试"}), 500
        else:
            processing_time = time.time() - start_time
            monitor_manager.record_message_processed(processing_time)
            return parsed_data

    except Exception as e:
        # 终极异常捕获，确保服务不崩溃
        error_msg = f"未预期的异常: {str(e)}"
        # 记录完整堆栈信息
        stack_trace = traceback.format_exc()
        logger_manager.log_with_context(logger, logging.CRITICAL, error_msg, context,
                                        extra={"stack_trace": stack_trace})

        # 向管理员发送错误通知
        try:
            error_notify = f"🚨 机器人异常警报 🚨\n"
            error_notify += f"时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            error_notify += f"错误: {str(e)}\n"
            error_notify += f"类型: {type(e).__name__}\n"
            gracy_send_msg(MASTER_ID, GracyText(text=error_notify), chat_type="private")
        except:
            # 确保通知失败不会影响响应
            pass

        # 返回安全的错误信息
        return jsonify({"retcode": 500, "msg": "系统维护中，请稍后再试"}), 500


def setup_error_handlers():
    """设置全局错误处理器"""

    @app.errorhandler(404)
    def not_found(error):
        context = {
            'client_ip': request.remote_addr,
            'path': request.path,
            'method': request.method
        }
        logger_manager.log_with_context(logger, logging.WARNING, '404页面未找到', context)
        return jsonify({"retcode": 404, "msg": "接口不存在"}), 404

    @app.errorhandler(405)
    def method_not_allowed(error):
        context = {
            'client_ip': request.remote_addr,
            'path': request.path,
            'method': request.method
        }
        logger_manager.log_with_context(logger, logging.WARNING, f'方法不允许: {request.method}', context)
        return jsonify({"retcode": 405, "msg": "不支持的请求方法"}), 405

    @app.errorhandler(Exception)
    def handle_exception(error):
        """处理所有未捕获的异常"""
        context = {
            'client_ip': request.remote_addr,
            'path': request.path if hasattr(request, 'path') else 'unknown',
            'error_type': type(error).__name__
        }
        stack_trace = traceback.format_exc()
        logger_manager.log_with_context(logger,
                                        logging.CRITICAL,
                                        f'未处理的异常: {str(error)}',
                                        context,
                                        extra={"stack_trace": stack_trace})

        # 返回统一的错误响应
        return jsonify({"retcode": 500, "msg": "服务器内部错误"}), 500


def safe_shutdown(signum=None, frame=None):
    """安全关闭服务"""
    # 使用logger_manager直接记录，确保与gracybot.log格式一致
    logger_manager.log_with_context(logger, logging.INFO, "🔄 正在安全关闭服务...")

    # 通知管理员
    try:
        # 处理版本号格式，避免双v问题
        version = BOT_VERSION.removeprefix('v')
        shutdown_msg = f"🛑 GracyBot v{version} 正在关闭\n"
        shutdown_msg += f"时间: {time.strftime('%Y-%m-%d %H:%M:%S')}"
        gracy_send_msg(MASTER_ID, GracyText(text=shutdown_msg), chat_type="private")
    except:
        pass

    # 清理资源
    try:
        plugin_manager.shutdown()
    except Exception as e:
        logger_manager.log_with_context(logger, logging.ERROR, f"❌ 关闭插件管理器异常: {str(e)}")

    # 关闭监控管理器
    try:
        monitor_manager.shutdown()
    except Exception as e:
        logger_manager.log_with_context(logger, logging.ERROR, f"❌ 关闭监控管理器异常: {str(e)}")

    logger_manager.log_with_context(logger, logging.INFO, "✅ 服务已安全关闭")
    # 使用 os._exit 强制终止进程（sys.exit 在子线程中只退出当前线程，Flask 主线程不受影响）
    os._exit(0)


def _load_hotreload_config() -> bool:
    """读取热重载开关标记，默认开启"""
    _flag = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hotreload.json")
    try:
        if os.path.exists(_flag):
            with open(_flag, "r", encoding="utf-8") as f:
                return json.load(f).get("enabled", True)
    except Exception:
        pass
    return True


def _interactive_connection_setup():
    """首次运行：小白友好的连接模式选择菜单"""
    from core.config_manager import config_manager

    # 只在 config.json 缺失 connection_mode 且未通过命令行/环境变量指定时触发
    if os.environ.get("GRACY_CONNECTION_MODE"):
        return
    missing = config_manager.missing_in_file("connection_mode")
    if not missing:
        return

    print()
    print("=" * 42)
    print("  🎉 欢迎使用 GracyBot！检测到首次运行 🎉")
    print("=" * 42)
    print()
    print("  请选择连接模式（输入数字回车）:")
    print()
    print("   [1] HTTP 回调 — 最简单，NapCat 推送消息到 Bot")
    print("       适合: 新手 / 不想折腾")
    print()
    print("   [2] WS 正向   — Bot 主动连接 NapCat WebSocket")
    print("       适合: Bot 和 NapCat 在同一台机器")
    print()
    print("   [3] WS 反向   — NapCat 连接 Bot WebSocket")
    print("       适合: Bot 和 NapCat 不在同一台机器")
    print()

    try:
        choice = input("  请输入 [1/2/3]（默认 1）: ").strip()
    except (EOFError, KeyboardInterrupt):
        choice = ""

    modes = {"1": "http", "2": "ws_forward", "3": "ws_reverse"}
    mode = modes.get(choice, "http")
    mode_names = {"http": "HTTP 回调", "ws_forward": "正向 WS", "ws_reverse": "反向 WS"}

    # WS 模式额外配置
    ws_host = "127.0.0.1"
    ws_port = 3001
    token = ""

    if mode in ("ws_forward", "ws_reverse"):
        print()
        try:
            host_in = input(f"  WS 地址（默认 {ws_host}）: ").strip()
            if host_in:
                ws_host = host_in
            port_in = input(f"  WS 端口（默认 {ws_port}）: ").strip()
            if port_in:
                try:
                    ws_port = int(port_in)
                except ValueError:
                    print(f"  ⚠️ 无效端口，使用默认 {ws_port}")
            token_in = input("  Access Token（无需则直接回车）: ").strip()
            token = token_in
        except (EOFError, KeyboardInterrupt):
            pass

    # 写入配置文件
    try:
        import json as _json

        # 框架配置写入 config.json（connection_mode 属于启动路由）
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = _json.load(f)
        else:
            cfg = {}

        cfg["connection_mode"] = mode

        with open(config_path, "w", encoding="utf-8") as f:
            _json.dump(cfg, f, ensure_ascii=False, indent=2)

        # OneBot 适配器配置写入 onebot_config.json
        if mode in ("ws_forward", "ws_reverse"):
            onebot_config_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "gracy_adapter", "onebot", "onebot_config.json"
            )
            if os.path.exists(onebot_config_path):
                with open(onebot_config_path, "r", encoding="utf-8") as f:
                    onebot_cfg = _json.load(f)
            else:
                onebot_cfg = {}

            onebot_cfg["ws_host"] = ws_host
            onebot_cfg["ws_port"] = ws_port
            onebot_cfg["access_token"] = token

            with open(onebot_config_path, "w", encoding="utf-8") as f:
                _json.dump(onebot_cfg, f, ensure_ascii=False, indent=2)

        print()
        print(f"  ✅ 已保存: 连接模式 = {mode_names[mode]}")
        if mode in ("ws_forward", "ws_reverse"):
            print(f"     WS 地址: {ws_host}:{ws_port}")
            print(f"     Token: {'已设置' if token else '无'}")
        print(f"     配置已写入，下次启动将自动使用此模式")
        print()
    except Exception as e:
        print(f"  ⚠️ 保存配置失败: {e}，将使用默认模式启动")
        os.environ["GRACY_CONNECTION_MODE"] = mode


def _parse_cli_args():
    """解析命令行参数，通过环境变量传递给 config_manager

    支持:
        -m / --mode  连接模式 (http, http_reverse, ws_forward, ws_reverse)
        -t / --token OneBot access_token（仅 WS 模式有效）
        -h / --help  帮助
    """
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("-m", "--mode") and i + 1 < len(args):
            mode = args[i + 1]
            if mode in ("http", "http_reverse", "ws_forward", "ws_reverse"):
                os.environ["GRACY_CONNECTION_MODE"] = mode
            else:
                print(f"❌ 无效模式: {mode}（可选: http,http_reverse,ws_forward,ws_reverse）")
                sys.exit(1)
            i += 1
        elif arg in ("-t", "--token") and i + 1 < len(args):
            os.environ["GRACY_ACCESS_TOKEN"] = args[i + 1]
            i += 1
        elif arg in ("-h", "--help"):
            print("GracyBot 启动\n"
                  "  python bot.py                        默认（config.json）\n"
                  "  python bot.py -m ws_forward           正向 WS\n"
                  "  python bot.py -m ws_reverse           反向 WS\n"
                  "  python bot.py -m ws_forward -t mytok  正向 WS + token\n"
                  "  python bot.py -m http                 HTTP 回调")
            sys.exit(0)
        i += 1


def run_bot():
    """完整的启动流程 — 由 bot.py 入口调用"""
    _parse_cli_args()  # 先解析命令行参数（设置环境变量）
    _interactive_connection_setup()  # 首次运行引导（小白友好）
    _hotreload_enabled = _load_hotreload_config()
    _is_worker = os.environ.get("WERKZEUG_RUN_MAIN") == "true"

    # 热重载关闭时无父子进程之分，本进程即是 worker，必须走完整初始化
    if not _hotreload_enabled:
        _is_worker = True
    # WS 模式没有 Werkzeug 父子进程，热重载标记不适用，直接走完整初始化
    elif config_manager.get("connection_mode", "http") not in ("http", "http_reverse"):
        _is_worker = True

    # ═══════════════ 子进程：完整初始化（父进程跳过）═══════════════
    if _is_worker:
        # 打印彩色 Logo（仅此一处决策，不再散落在 logger_manager 中）
        try:
            sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "style"))
            from style.gracybot_logo import GracyBotLogo
            GracyBotLogo(force_color=True).print_logo()
        except Exception:
            pass

        # 注册信号处理
        try:
            import signal
            signal.signal(signal.SIGINT, safe_shutdown)
            signal.signal(signal.SIGTERM, safe_shutdown)
        except (ImportError, AttributeError):
            logger.warning("⚠️ 信号处理在当前环境可能不可用")

        # 1. 初始化配置
        try:
            config_manager.load()
            logger.info("✅ 配置加载完成")
        except Exception as e:
            logger.error(f"❌ 配置加载失败: {str(e)}")
            logger.warning("⚠️ 尝试使用默认配置继续启动")

        # 1.1 刷新安全配置
        try:
            from core.security_manager import security_manager
            security_manager.refresh_config()
            logger.info("✅ 安全配置已刷新")
        except Exception as e:
            logger.error(f"❌ 安全配置刷新失败: {str(e)}")

        # 2. 初始化插件管理器
        try:
            plugin_manager.init()
            logger.info("✅ 插件管理器初始化完成")
        except Exception as e:
            logger.error(f"❌ 插件管理器初始化失败: {str(e)}")
            logger.warning("⚠️ 部分插件可能无法正常工作")

        # 3. 设置错误处理器
        try:
            setup_error_handlers()
            logger.info("✅ 错误处理器设置完成")
        except Exception as e:
            logger.error(f"❌ 设置错误处理器失败: {str(e)}")

        # 4. 注册健康检查路由
        try:
            register_health_check_routes(app)
            logger.info("✅ 健康检查路由注册完成")
        except Exception as e:
            logger.error(f"❌ 注册健康检查路由失败: {str(e)}")

        # 5. 显示启动信息
        version_display = BOT_VERSION.removeprefix('v')
        conn_mode = config_manager.get("connection_mode", "http")
        logger.info(f"\n====== GracyBot v{version_display} 启动 ======")
        logger.info(f"📌 Bot ID：{ROBOT_ID} | 管理员 ID:{MASTER_ID}")
        if conn_mode in ("http", "http_reverse"):
            logger.info(f"📡 连接模式：HTTP 回调 → http://localhost:{CALLBACK_PORT}/callback")
        elif conn_mode == "ws_forward":
            logger.info(f"🔗 连接模式：WS 正向 → ws://{config_manager.get('ws_host','127.0.0.1')}:{config_manager.get('ws_port',3001)}")
        elif conn_mode == "ws_reverse":
            logger.info(f"🔗 连接模式：WS 反向 → 监听 {config_manager.get('ws_host','0.0.0.0')}:{config_manager.get('ws_port',8080)}")
        logger.info(f"✅ 所有初始化完成，等待消息...\n")

        # 6. 启动提醒消息
        try:
            welcome_msg = f"🎉 GracyBot v{version_display} 启动成功！\n"
            welcome_msg += f"📌 功能说明：\n"
            welcome_msg += f"  • 私聊//+内容触发AI聊天\n"
            welcome_msg += f"  • 群聊@机器人+内容 或 //+内容触发回复\n"
            welcome_msg += f"  • 输入对应指令使用插件功能（如/运行状态）"
            threading.Timer(1, lambda w=welcome_msg: gracy_send_msg(MASTER_ID, GracyText(text=w), chat_type="private")).start()
        except Exception as e:
            logger.error(f"❌ 发送启动消息失败: {str(e)}")

    # ═══════════════ 根据连接模式启动 ═══════════════
    conn_mode = config_manager.get("connection_mode", "http")

    if conn_mode in ("http", "http_reverse"):
        # ── HTTP 回调模式（现有 Flask 路径）──
        from werkzeug.serving import run_simple, WSGIRequestHandler
        import glob as _glob
        WSGIRequestHandler.log = lambda self, type, msg, *args: None
        app.config['PROPAGATE_EXCEPTIONS'] = True

        _extra_files = []
        _plugins_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "plugins")
        if os.path.isdir(_plugins_dir):
            _extra_files = _glob.glob(os.path.join(_plugins_dir, "**", "*.py"), recursive=True)

        if not _is_worker:
            logger.info(f"🔄 热重载已启用 — 修改代码后自动重启（监听 {len(_extra_files)} 个插件文件）")
        elif not _hotreload_enabled:
            logger.info("⚪ 热重载已关闭 — 代码修改需手动重启生效")

        try:
            run_simple('0.0.0.0', CALLBACK_PORT, app, use_reloader=_hotreload_enabled, use_debugger=False,
                       extra_files=_extra_files if _hotreload_enabled else [])
        except Exception as e:
            logger.critical(f"❌ 服务启动失败: {str(e)}", exc_info=True)
            if _is_worker:
                try:
                    gracy_send_msg(MASTER_ID, GracyText(text=f"❌ GracyBot 启动失败\n错误: {str(e)}"), chat_type="private")
                except:
                    pass
            sys.exit(1)

    else:
        # ── WebSocket 模式 ──
        from core.gracy_adapter.onebot.ws import GracyOneBotWS
        from core.gracy_adapter.send import set_adapter
        from core.handler import dispatch_plugin_cmd, process_event_from_adapter

        ws_mode = "forward" if conn_mode == "ws_forward" else "reverse"
        ws_host = config_manager.get("ws_host", "127.0.0.1")
        ws_port = config_manager.get("ws_port", 3001)
        token = config_manager.get("access_token", "")

        ws_adapter = GracyOneBotWS(
            mode=ws_mode,
            host=ws_host,
            port=ws_port,
            access_token=token,
            robot_id=ROBOT_ID,
        )
        # 注入到 send.py，使 gracy_send_msg() 走 WS 通道
        set_adapter(ws_adapter)

        def on_ws_event(event):
            with app.app_context():
                try:
                    start_time = time.time()
                    monitor_manager.record_message_received()
                    parsed = process_event_from_adapter(event)
                    if parsed:
                        ret = dispatch_plugin_cmd(parsed)
                        processing_time = time.time() - start_time
                        monitor_manager.record_message_processed(processing_time)
                        if isinstance(ret, tuple) and len(ret) >= 2:
                            if len(ret) == 3:
                                _, _, handled = ret
                            else:
                                _, handled = ret
                            if handled:
                                logger.info('请求处理成功')
                            else:
                                raw_msg = parsed.get("raw_msg", "")
                                if not raw_msg.startswith("[CQ:"):
                                    builtin_cmds = {"/关机", "/重启", "/开机", "/关于"}
                                    all_cmds = set(builtin_cmds)
                                    for p in PLUGIN_REGISTRY:
                                        for cmd in p.get("commands", []):
                                            if cmd != "//":
                                                all_cmds.add(cmd)
                                    if any(raw_msg.startswith(cmd) for cmd in all_cmds):
                                        logger.info(f'指令未匹配任何插件: {raw_msg[:30]}')
                except Exception as e:
                    logger.error(f"[WS 事件处理] 异常: {e}", exc_info=True)

        ws_adapter.start(on_ws_event)
        logger.info(f"✅ WebSocket {'正向连接' if ws_mode == 'forward' else '反向监听'}已启动")

        # 保持主线程存活
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            ws_adapter.stop()
            logger.info("🛑 WebSocket 已断开")

    sys.exit(0)
