"""GracyBot 核心主模块 — 应用逻辑（Quart 异步路由、启动、关闭）"""
import asyncio
import multiprocessing
try:
    multiprocessing.set_start_method('spawn')
except RuntimeError:
    pass

from quart import Quart, request, jsonify
import json
import os
import threading
import time
import sys
import traceback
import logging

from core.config import CALLBACK_PORT, BOT_VERSION
from core.handler import callback_base
from core.plugin_manager import plugin_manager
from core.utils import logger, logger_manager  # 复用utils全局日志和消息工具
from core.gracy_adapter.send import gracy_send_msg
from core.gracy_adapter.message import GracyText
from core.config_manager import config_manager
from core.monitor import monitor_manager, register_health_check_routes
from core.gracy_adapter.pool import adapter_pool
from core.gracy_adapter.identity import IdentityTag
from core.event import event_bus
from core.runtime import Runtime, RuntimeRegistry
from core.logger_manager import setup_runtime_logger
from core.pipeline import Pipeline
from core.pipeline.stages import SecurityFilter, BuiltinCommands, CommandMatcher, PluginHandler, ResponseSender

def _resolve_plugins_dir() -> str:
    """自动确定插件目录路径

    优先级: GRACYBOT_HOME > CWD(bot.py) > site-packages > CWD
    """
    # 1. GRACYBOT_HOME
    root = os.environ.get("GRACYBOT_HOME", "").strip()
    if root:
        p = os.path.join(root, "plugins")
        if os.path.exists(p):
            return p

    # 2. CWD 有 bot.py（本地项目）
    cwd = os.getcwd()
    if os.path.exists(os.path.join(cwd, "bot.py")):
        p = os.path.join(cwd, "plugins")
        if os.path.exists(p):
            return p

    # 3. pip 安装目录的 plugins/
    try:
        import core as _core_mod
        _core_dir = os.path.dirname(os.path.abspath(_core_mod.__file__))
        _site_pkg = os.path.dirname(_core_dir)
        p = os.path.join(_site_pkg, "plugins")
        if os.path.exists(p):
            return p
    except Exception:
        pass

    # 4. 回退 CWD/plugins
    return os.path.join(cwd, "plugins")


# ========== Quart 应用初始化 ==========
app = Quart(__name__)


# ── 实例配置路径 ──

def _instances_dir() -> str:
    """返回 style/instances 目录的绝对路径"""
    base = os.environ.get("GRACYBOT_HOME", os.getcwd())
    return os.path.join(base, "style", "instances")


def _discover_instance_configs() -> list[dict]:
    """扫描 style/instances/<name>/config.json，返回所有启用的实例配置列表"""
    inst_dir = _instances_dir()
    if not os.path.isdir(inst_dir):
        logger.warning(f"⚠️ 实例目录不存在: {inst_dir}")
        return []

    results = []
    for entry in sorted(os.listdir(inst_dir)):
        cfg_path = os.path.join(inst_dir, entry, "config.json")
        if not os.path.isfile(cfg_path):
            continue
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            if not cfg.get("enabled", True):
                logger.info(f"  ⏭️ 实例 {entry} 已禁用，跳过")
                continue
            cfg["_dir_name"] = entry
            cfg["_config_path"] = cfg_path
            results.append(cfg)
        except Exception as e:
            logger.error(f"❌ 加载实例配置失败 {cfg_path}: {e}")

    return results


def _register_instance(cfg: dict, default: bool = False, runtime=None) -> None:
    """根据实例配置创建一个适配器并注册到池

    Args:
        cfg: 实例配置字典
        default: 是否设为默认适配器
        runtime: 关联的 Runtime 实例（P1 起传入，替代从 cfg 读取身份）
    """
    platform = cfg.get("platform", "onebot")
    bot_name = cfg.get("bot_name", cfg.get("_dir_name", "unknown"))
    robot_id = runtime.robot_id if runtime else cfg.get("robot_id", "")
    master_id = runtime.master_id if runtime else cfg.get("master_id", "")
    tag = runtime.adapter_tag if runtime else IdentityTag(platform=platform, bot_name=bot_name)

    conn_type = cfg.get("type", "http")

    if platform == "onebot":
        if conn_type in ("ws_forward", "ws_reverse"):
            from core.gracy_adapter.onebot.ws import GracyOneBotWS
            ws_mode = "forward" if conn_type == "ws_forward" else "reverse"
            adapter = GracyOneBotWS(
                mode=ws_mode,
                host=cfg.get("host", "127.0.0.1"),
                port=cfg.get("port", 3001),
                access_token=cfg.get("access_token", ""),
                robot_id=robot_id,
            )
        else:
            from core.gracy_adapter.onebot.http import GracyOneBot
            adapter = GracyOneBot(
                napcat_url=cfg.get("http_url", "http://127.0.0.1:3000"),
                callback_port=cfg.get("callback_port", CALLBACK_PORT),
                robot_id=robot_id,
            )
    else:
        logger.warning(f"⚠️ 不支持的平台: {platform}（实例 {cfg.get('_dir_name', '?')}），跳过")
        return

    adapter.tag = tag
    adapter._instance_master_id = master_id
    adapter._instance_robot_id = robot_id
    adapter._runtime = runtime  # 关联 Runtime 实例（P2 阶段替代 _instance_*）
    adapter_pool.register(adapter, tag, default=default)
    logger.info(f"  ➕ [{tag.log_tag}] {platform}/{bot_name} ({conn_type}) master={master_id[:4]}****")


# ── HTTP 事件解析器池（按 self_id/robot_id 索引，支持多 QQ 号路由） ──

_http_parsers: dict[str, "GracyOneBot"] = {}

def _get_parser_by_self_id(self_id: str):
    """根据 self_id 查找对应的适配器并返回事件解析器

    遍历 AdapterPool 中的适配器，匹配 _instance_robot_id == self_id，
    命中后缓存在 _http_parsers 字典中避免重复创建。
    未命中时回退到默认适配器。
    """
    # 优先从缓存取
    if self_id and self_id in _http_parsers:
        return _http_parsers[self_id]

    # 遍历池查找匹配的适配器
    target_adapter = None
    target_tag = None
    target_robot_id = self_id
    for adapter, tag in adapter_pool._adapters.values():
        rid = getattr(adapter, '_instance_robot_id', '')
        if rid and self_id and str(rid) == str(self_id):
            target_adapter = adapter
            target_tag = tag
            target_robot_id = str(rid)
            break

    # 未命中，回退到默认适配器
    if not target_adapter:
        default = adapter_pool.get_default()
        if default is None:
            return None
        target_adapter = default
        target_tag = adapter_pool.get_default_tag()
        target_robot_id = getattr(default, '_instance_robot_id', '')

    # 创建解析器并缓存
    from core.gracy_adapter.onebot.http import GracyOneBot
    parser = GracyOneBot(robot_id=target_robot_id)
    # 把适配器和 tag 挂上去方便外部访问 tag / master_id
    parser._adapter = target_adapter
    parser._source_tag = target_tag
    if target_robot_id:
        _http_parsers[target_robot_id] = parser
    return parser


# 事件去重缓存（key=用户+内容+时间窗，TTL=1秒）
_event_dedup_cache: dict = {}
_DEDUP_TTL = 1.0


@app.route('/callback', methods=['POST'])
async def callback():
    context = {
        'client_ip': request.remote_addr,
        'request_id': str(time.time())[-6:],
        'path': request.path
    }

    monitor_manager.record_message_received()

    start_time = time.time()

    try:
        # 检查Content-Type（兼容 charset 参数，如 application/json; charset=utf-8）
        if 'application/json' not in (request.content_type or ''):
            error_msg = f"不支持的Content-Type: {request.content_type}"
            logger_manager.log_with_context(logger, logging.WARNING, error_msg, context)
            monitor_manager.record_message_error()
            return jsonify({"retcode": 415, "msg": "仅支持application/json格式"}), 415

        # 获取并验证JSON数据
        try:
            json_data = await request.get_json()
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

        # ── 事件去重：同机器人+同用户+同内容在1秒内只处理一次 ──
        dedup_key = (
            str(json_data.get("self_id", "")),
            str(json_data.get("user_id", "")),
            str(json_data.get("raw_message", "")),
            str(json_data.get("notice_type", "")),
            int(time.time() / _DEDUP_TTL),
        )
        now = time.time()
        # 清理过期缓存
        stale = [k for k, v in list(_event_dedup_cache.items()) if now - v > _DEDUP_TTL * 2]
        for k in stale:
            _event_dedup_cache.pop(k, None)
        if dedup_key in _event_dedup_cache:
            # 重复事件，静默丢弃
            return jsonify({"retcode": 0})
        _event_dedup_cache[dedup_key] = now

        # ── 根据 self_id 路由到对应适配器实例 ──
        self_id = str(json_data.get("self_id", ""))
        parser = _get_parser_by_self_id(self_id)
        http_event = parser.parse_event(json_data) if parser else None

        if http_event:
            # 标记事件来源适配器（供 Pipeline 权限、多实例路由使用）
            if parser and hasattr(parser, '_source_tag') and parser._source_tag:
                http_event.source = parser._source_tag

            # 过滤机器人自身消息（使用该适配器实例的 robot_id）
            parser_robot_id = getattr(parser, '_robot_id', '') if parser else ''
            if http_event.sender_id and parser_robot_id and str(http_event.sender_id) == str(parser_robot_id):
                return jsonify({"retcode": 0})
            # ── EventBus 发布（异步，不阻塞 HTTP 响应） ──
            try:
                await event_bus.publish(http_event)
            except Exception as e:
                logger_manager.log_with_context(
                    logger, logging.WARNING, f"EventBus 发布失败: {e}", context
                )
        else:
            # parse_event 返回 None（非消息事件、自回显等），直接响应
            return jsonify({"retcode": 0})

        # 调用基础处理函数（验证 + 过滤）
        try:
            parsed_data = await callback_base()
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

        # callback_base 验证通过 → 返回成功（Pipeline 已异步处理）
        if isinstance(parsed_data, dict):
            processing_time = time.time() - start_time
            monitor_manager.record_message_processed(processing_time)
            logger.info('请求处理成功（Pipeline 异步）')
            return jsonify({"retcode": 0})
        else:
            # callback_base 返回了错误响应（如频率超限、验证失败等）
            processing_time = time.time() - start_time
            monitor_manager.record_message_processed(processing_time)
            return parsed_data

    except Exception as e:
        error_msg = f"未预期的异常: {str(e)}"
        stack_trace = traceback.format_exc()
        logger_manager.log_with_context(logger, logging.CRITICAL, error_msg, context,
                                        extra={"stack_trace": stack_trace})

        try:
            error_notify = f"🚨 机器人异常警报 🚨\n"
            error_notify += f"时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            error_notify += f"错误: {str(e)}\n"
            error_notify += f"类型: {type(e).__name__}\n"
            from core.config import MASTER_ID as _m
            if _m:
                await gracy_send_msg(_m, GracyText(text=error_notify), chat_type="private")
        except:
            pass

        return jsonify({"retcode": 500, "msg": "系统维护中，请稍后再试"}), 500


def setup_error_handlers():

    @app.errorhandler(404)
    async def not_found(error):
        context = {
            'client_ip': request.remote_addr,
            'path': request.path,
            'method': request.method
        }
        logger_manager.log_with_context(logger, logging.WARNING, '404页面未找到', context)
        return jsonify({"retcode": 404, "msg": "接口不存在"}), 404

    @app.errorhandler(405)
    async def method_not_allowed(error):
        context = {
            'client_ip': request.remote_addr,
            'path': request.path,
            'method': request.method
        }
        logger_manager.log_with_context(logger, logging.WARNING, f'方法不允许: {request.method}', context)
        return jsonify({"retcode": 405, "msg": "不支持的请求方法"}), 405

    @app.errorhandler(Exception)
    async def handle_exception(error):
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
        return jsonify({"retcode": 500, "msg": "服务器内部错误"}), 500


async def _send_welcome_msg(welcome_msg: str, target: str = ""):
    """异步发送启动欢迎消息"""
    try:
        if not target:
            # 兜底：从池获取
            default = adapter_pool.get_default()
            if default and hasattr(default, '_instance_master_id'):
                target = str(default._instance_master_id)
        if not target or not target.isdigit():
            logger.warning("⏭️ master_id 未配置，跳过发送启动消息")
            return
        await asyncio.sleep(1)
        await gracy_send_msg(target, GracyText(text=welcome_msg), chat_type="private")
    except Exception as e:
        logger.error(f"❌ 发送启动消息失败: {str(e)}")


def safe_shutdown(signum=None, frame=None):
    """安全关闭服务"""
    logger_manager.log_with_context(logger, logging.INFO, "🔄 正在安全关闭服务...")

    try:
        version = BOT_VERSION.removeprefix('v')
        shutdown_msg = f"🛑 GracyBot v{version} 正在关闭\n"
        shutdown_msg += f"时间: {time.strftime('%Y-%m-%d %H:%M:%S')}"
        # 从实例获取 master_id
        _shutdown_target = ""
        try:
            default = adapter_pool.get_default()
            if default and hasattr(default, '_instance_master_id'):
                _shutdown_target = str(default._instance_master_id)
        except Exception:
            pass
        if _shutdown_target:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.run_coroutine_threadsafe(
                        gracy_send_msg(_shutdown_target, GracyText(text=shutdown_msg), chat_type="private"),
                        loop
                    )
            except Exception:
                pass
    except Exception:
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
    os._exit(0)


def _load_hotreload_config() -> bool:
    """读取热重载开关标记，默认开启"""
    _project_root = os.environ.get("GRACYBOT_HOME", "")
    if not _project_root:
        _project_root = os.getcwd()
    _flag = os.path.join(_project_root, "hotreload.json")
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

        _project_root = os.environ.get("GRACYBOT_HOME", "")
        if not _project_root:
            _project_root = os.getcwd()

        # 框架配置写入 config.json（connection_mode 属于启动路由）
        config_path = os.path.join(_project_root, "config.json")
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
                _project_root,
                "core", "gracy_adapter", "onebot", "onebot_config.json"
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


def _init_instances() -> None:
    """扫描 style/instances/ 目录，为每个实例创建 Runtime + 独立 Pipeline"""
    configs = _discover_instance_configs()
    if not configs:
        logger.warning("⚠️ 未发现任何实例配置（style/instances/<name>/config.json）")
        logger.warning("💡 使用 gracy instance add <name> 创建实例")
        return

    for idx, cfg in enumerate(configs):
        try:
            instance_name = cfg.get("_dir_name", f"instance_{idx}")
            robot_id = cfg.get("robot_id", "")
            master_id = cfg.get("master_id", "")
            platform = cfg.get("platform", "onebot")
            bot_name = cfg.get("bot_name", instance_name)

            # 1. 创建 Runtime 实例
            tag = IdentityTag(platform=platform, bot_name=bot_name)
            runtime = Runtime(
                instance_name=instance_name,
                robot_id=robot_id,
                master_id=master_id,
                adapter_tag=tag,
                plugin_manager=plugin_manager,
                adapter_pool=adapter_pool,
            )

            # 2. 创建独立 Pipeline
            pipeline = Pipeline()
            pipeline.add_stage(SecurityFilter())
            pipeline.add_stage(BuiltinCommands())
            pipeline.add_stage(CommandMatcher())
            pipeline.add_stage(PluginHandler())
            pipeline.add_stage(ResponseSender())
            runtime.pipeline = pipeline

            # 3. 创建 Runtime 独立日志器
            runtime.logger = setup_runtime_logger(instance_name, bot_name=bot_name)

            # 4. 注册到 RuntimeRegistry
            RuntimeRegistry.register(runtime)

            # 5. 注册适配器到 AdapterPool
            _register_instance(cfg, default=(idx == 0), runtime=runtime)

        except Exception as e:
            logger.error(f"❌ 初始化实例失败 {cfg.get('_dir_name', '?')}: {e}")

    count = adapter_pool.count
    logger.info(f"✅ 实例池初始化完成: {count} 个适配器, {RuntimeRegistry.count()} 个 Runtime")


def _parse_cli_args() -> None:
    """解析命令行参数，通过环境变量传递给 config_manager"""
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


async def run_bot():
    """完整的启动流程 — 由 bot.py 入口调用（100% 原生异步）"""
    _parse_cli_args()  # 先解析命令行参数（设置环境变量）
    _interactive_connection_setup()  # 首次运行引导（小白友好）

    # ═══════════════ 初始化（无 werkzeug 父子进程，直接执行）═══════════════
    # 打印彩色 Logo
    try:
        _project_root = os.environ.get("GRACYBOT_HOME", "")
        if not _project_root:
            _project_root = os.getcwd()
        sys.path.insert(0, os.path.join(_project_root, "style"))
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
        _plugin_dir = _resolve_plugins_dir()
        plugin_manager.init(plugin_dir=_plugin_dir)
        logger.info(f"✅ 插件管理器初始化完成（{_plugin_dir}）")
    except Exception as e:
        logger.error(f"❌ 插件管理器初始化失败: {str(e)}")
        logger.warning("⚠️ 部分插件可能无法正常工作")

    # 2.1 扫描所有实例配置并注册到适配器池
    _init_instances()

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
    logger.info(f"====== GracyBot v{version_display} 启动 ======")
    instance_count = adapter_pool.count
    # 显示第一个实例的 master_id 作为管理员信息
    default = adapter_pool.get_default()
    show_master = ""
    if default and hasattr(default, '_instance_master_id'):
        mid = default._instance_master_id
        if mid:
            show_master = f"{mid[:4]}****" if len(mid) > 4 else mid
    logger.info(f"📌 已注册 {instance_count} 个实例 | 管理员 ID:{show_master}")
    if conn_mode in ("http", "http_reverse"):
        logger.info(f"📡 连接模式：HTTP 回调 → http://localhost:{CALLBACK_PORT}/callback")
    elif conn_mode == "ws_forward":
        logger.info(f"🔗 连接模式：WS 正向 → ws://{config_manager.get('ws_host','127.0.0.1')}:{config_manager.get('ws_port',3001)}")
    elif conn_mode == "ws_reverse":
        logger.info(f"🔗 连接模式：WS 反向 → 监听 {config_manager.get('ws_host','0.0.0.0')}:{config_manager.get('ws_port',8080)}")
    logger.info(f"✅ 所有初始化完成，等待消息...\n")

    # ═══════════════ 根据连接模式启动 ═══════════════
    conn_mode = config_manager.get("connection_mode", "http")

    if conn_mode in ("http", "http_reverse"):
        # ── HTTP 回调模式（Quart + hypercorn）──
        # 启动所有已注册的适配器（由 _init_instances 注册到池）
        try:
            adapter_pool.start_all(lambda e: asyncio.create_task(event_bus.publish(e)))
            logger.info("✅ 实例池已启动")
        except Exception as e:
            logger.warning(f"⚠️ 实例池启动异常: {e}")

        # 触发 on_ready 钩子（插件通过 plugin_manager.register_on_ready 注册）
        try:
            plugin_manager.trigger_on_ready()
        except Exception as e:
            logger.warning(f"⚠️ on_ready 钩子触发失败: {e}")

        # 发送启动消息（适配器已就绪）
        # 检查是否首次运行（占位符值），跳过发送避免无效报错
        _master_to_check = ""
        if default and hasattr(default, '_instance_master_id'):
            _master_to_check = str(default._instance_master_id)
        _is_first_run = not _master_to_check.isdigit()
        if _is_first_run:
            logger.warning("⏭️ 首次运行，跳过发送启动消息（请先编辑 config.json 填写 QQ 号）")
        else:
            try:
                welcome_msg = f"🎉 GracyBot v{version_display} 启动成功！\n"
                welcome_msg += f"📌 功能说明：\n"
                welcome_msg += f"  • 私聊//+内容触发AI聊天\n"
                welcome_msg += f"  • 群聊@机器人+内容 或 //+内容触发回复\n"
                welcome_msg += f"  • 输入对应指令使用插件功能（如/运行状态）"
                asyncio.create_task(_send_welcome_msg(welcome_msg, target=_master_to_check))
            except Exception as e:
                logger.error(f"❌ 发送启动消息失败: {str(e)}")

        # 发送失败通知也用实例 master_id
        _fail_target = _master_to_check

        try:
            from hypercorn.config import Config
            from hypercorn.asyncio import serve

            cfg = Config()
            cfg.bind = [f"0.0.0.0:{CALLBACK_PORT}"]
            cfg.loglevel = "warning"
            cfg.accesslog = None
            cfg.errorlog = None

            await serve(app, cfg)
        except Exception as e:
            logger.critical(f"❌ 服务启动失败: {str(e)}", exc_info=True)
            try:
                if _fail_target:
                    await gracy_send_msg(_fail_target, GracyText(text=f"❌ GracyBot 启动失败\n错误: {str(e)}"), chat_type="private")
            except:
                pass
            sys.exit(1)

    else:
        # ── WebSocket 模式 ──
        # 启动所有已注册的适配器（由 _init_instances 注册到池）
        try:
            adapter_pool.start_all(lambda e: asyncio.create_task(event_bus.publish(e)))
            logger.info("✅ 实例池已启动")
        except Exception as e:
            logger.warning(f"⚠️ 实例池启动异常: {e}")

        # 触发 on_ready 钩子
        try:
            plugin_manager.trigger_on_ready()
        except Exception as e:
            logger.warning(f"⚠️ on_ready 钩子触发失败: {e}")

        logger.info("✅ 适配器池运行中，等待消息...")

        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            adapter_pool.stop_all()
            logger.info("🛑 适配器池已停止")

    sys.exit(0)
