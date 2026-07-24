
import asyncio
import multiprocessing
try:
    multiprocessing.set_start_method('spawn')
except RuntimeError:
    pass

from gracybot.core.webserv import create_app, request, jsonify
import importlib
import json
import os
import threading
import time
import sys
import traceback
import logging

from gracybot.core.config import BOT_VERSION
from gracybot.core.plugin_manager import plugin_manager
from gracybot.core.utils import logger, logger_manager
from gracybot.core.config_manager import config_manager
from gracybot.core.gracy_adapter.pool import adapter_pool
from gracybot.core.gracy_adapter.identity import IdentityTag
from gracybot.core.gracy_adapter.send import gracy_send_msg
from gracybot.core.gracy_adapter.message import GracyText
from gracybot.core.event import event_bus
from gracybot.core.runtime import Runtime, RuntimeRegistry
from gracybot.core.tools.log_runtime import setup_runtime_logger
from gracybot.core.pipeline import Pipeline, SecurityFilter, BuiltinCommands, CommandMatcher, PluginHandler, ResponseSender
from gracybot.core.tools.paths import get_instances_dir, get_project_root



app = create_app()




def _instances_dir() -> str:
    return get_instances_dir()


def _discover_instance_configs() -> list[dict]:

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







    platform = cfg.get("platform", "")
    bot_name = cfg.get("bot_name", cfg.get("_dir_name", "unknown"))
    robot_id = runtime.robot_id if runtime else cfg.get("robot_id", "")
    master_id = runtime.master_id if runtime else cfg.get("master_id", "")
    tag = runtime.adapter_tag if runtime else IdentityTag(platform=platform, bot_name=bot_name)


    try:
        module = importlib.import_module(f"gracybot.core.gracy_adapter.{platform}.adapter")
    except ImportError:
        try:
            module = importlib.import_module(f"core.gracy_adapter.{platform}.adapter")
        except ImportError:
            logger.warning(f"⚠️ 无法加载适配器模块: {platform}（实例 {cfg.get('_dir_name', '?')}），跳过")
            return
        except Exception as e:
            logger.error(f"❌ 创建适配器实例失败 {platform}: {e}")
            return

    try:
        create_fn = getattr(module, "create_adapter")
        adapter = create_fn(cfg)
    except AttributeError:
        logger.warning(f"⚠️ 适配器 {platform} 缺少 create_adapter 工厂函数，跳过")
        return
    except Exception as e:
        logger.error(f"❌ 创建适配器实例失败 {platform}: {e}")
        return

    adapter.tag = tag
    adapter._instance_master_id = master_id
    adapter._instance_robot_id = robot_id
    adapter._runtime = runtime

    conn_type = getattr(adapter, 'conn_type_display', '') or ''
    if conn_type:
        tag.conn_type = conn_type
    adapter_pool.register(adapter, tag, default=default)
    logger.info(f"  ➕ [{tag.log_tag}] {platform}/{bot_name} ({conn_type}) master={master_id[:4]}****")


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





def safe_shutdown(signum=None, frame=None):

    logger_manager.log_with_context(logger, logging.INFO, "🔄 正在安全关闭服务...")


    try:
        default = adapter_pool.get_default()
        master_id = getattr(default, '_instance_master_id', '') if default else ''
        if master_id:
            shutdown_msg = f"🛑 机器人正在关闭\n时间: {time.strftime('%Y-%m-%d %H:%M:%S')}"
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    gracy_send_msg(master_id, GracyText(text=shutdown_msg), chat_type="private"),
                    loop
                )
    except Exception:
        pass


    try:
        plugin_manager.shutdown()
    except Exception as e:
        logger_manager.log_with_context(logger, logging.ERROR, f"❌ 关闭插件管理器异常: {str(e)}")


    try:
        from gracybot.core.monitor import monitor_manager
        monitor_manager.shutdown()
    except (ImportError, Exception) as e:
        if not isinstance(e, ImportError):
            logger_manager.log_with_context(logger, logging.ERROR, f"❌ 关闭监控管理器异常: {str(e)}")

    logger_manager.log_with_context(logger, logging.INFO, "✅ 服务已安全关闭")
    os._exit(0)


def _init_instances() -> None:

    configs = _discover_instance_configs()
    if not configs:
        logger.warning("⚠️ 未发现任何实例配置（storage/instances/<name>/config.json）")
        return

    for idx, cfg in enumerate(configs):
        try:
            instance_name = cfg.get("_dir_name", f"instance_{idx}")
            robot_id = cfg.get("robot_id", "")
            master_id = cfg.get("master_id", "")
            platform = cfg.get("platform", "")
            bot_name = cfg.get("bot_name", instance_name)


            tag = IdentityTag(platform=platform, bot_name=bot_name)
            runtime = Runtime(
                instance_name=instance_name,
                robot_id=robot_id,
                master_id=master_id,
                adapter_tag=tag,
                plugin_manager=plugin_manager,
                adapter_pool=adapter_pool,
            )


            pipeline = Pipeline()
            pipeline.add_stage(SecurityFilter())
            pipeline.add_stage(BuiltinCommands())
            pipeline.add_stage(CommandMatcher())
            pipeline.add_stage(PluginHandler())
            pipeline.add_stage(ResponseSender())
            runtime.pipeline = pipeline


            runtime.logger = setup_runtime_logger(instance_name, bot_name=bot_name)


            RuntimeRegistry.register(runtime)


            _register_instance(cfg, default=(idx == 0), runtime=runtime)

        except Exception as e:
            logger.error(f"❌ 初始化实例失败 {cfg.get('_dir_name', '?')}: {e}")

    count = adapter_pool.count
    logger.info(f"✅ 实例池初始化完成: {count} 个适配器, {RuntimeRegistry.count()} 个 Runtime")


async def run_bot():
    import gracybot.graci as _graci_pkg
    sys.modules.setdefault('graci', _graci_pkg)

    try:
        from gracybot.res.gracybot_logo import GracyBotLogo
        GracyBotLogo().print_logo()
    except Exception:
        pass


    try:
        import signal
        signal.signal(signal.SIGINT, safe_shutdown)
        signal.signal(signal.SIGTERM, safe_shutdown)
    except (ImportError, AttributeError):
        logger.warning("⚠️ 信号处理在当前环境可能不可用")


    try:
        config_manager.load()
        logger.info("✅ 配置加载完成")
    except Exception as e:
        logger.error(f"❌ 配置加载失败: {str(e)}")
        logger.warning("⚠️ 尝试使用默认配置继续启动")


    try:
        plugin_manager.init()
        logger.info("✅ 插件管理器初始化完成")
    except Exception as e:
        logger.error(f"❌ 插件管理器初始化失败: {str(e)}")
        logger.warning("⚠️ 部分插件可能无法正常工作")


    _init_instances()


    try:
        setup_error_handlers()
        logger.info("✅ 错误处理器设置完成")
    except Exception as e:
        logger.error(f"❌ 设置错误处理器失败: {str(e)}")


    try:
        from gracybot.core.webserv.routes import register_health_check_routes
        register_health_check_routes(app)
        logger.info("✅ 健康检查路由注册完成")
    except ImportError:
        pass
    except Exception as e:
        logger.error(f"❌ 注册健康检查路由失败: {str(e)}")


    version_display = BOT_VERSION.removeprefix('v')
    logger.info(f"====== GracyBot v{version_display} 启动 ======")
    instance_count = adapter_pool.count

    default = adapter_pool.get_default()
    show_master = ""
    if default and hasattr(default, '_instance_master_id'):
        mid = default._instance_master_id
        if mid:
            show_master = f"{mid[:4]}****" if len(mid) > 4 else mid
    logger.info(f"📌 已注册 {instance_count} 个实例 | 管理员 ID:{show_master}")
    logger.info(f"✅ 所有初始化完成\n")



    try:
        adapter_pool.start_all(lambda e: asyncio.create_task(event_bus.publish(e)))
        logger.info("✅ 实例池已启动")
    except Exception as e:
        logger.warning(f"⚠️ 实例池启动异常: {e}")


    try:
        for adapter, _ in adapter_pool._adapters.values():
            adapter.register_routes(app)
    except Exception as e:
        logger.warning(f"⚠️ 路由注册异常: {e}")


    try:
        plugin_manager.trigger_on_ready()
    except Exception as e:
        logger.warning(f"⚠️ on_ready 钩子触发失败: {e}")


    if adapter_pool.count == 0:
        logger.warning("⚠️ 未配置任何实例，框架退出（使用 gracy instance add <name> 创建实例）")
        return


    welcome_msg = f"🎉 GracyBot v{version_display} 启动成功！\n"
    welcome_msg += f"📌 已加载 {plugin_manager.get_plugin_count()} 个插件"
    for tag in adapter_pool.all_tags:
        try:
            adapter = adapter_pool.get(tag)
            if not adapter:
                continue
            master_id = getattr(adapter, '_instance_master_id', '')
            if master_id:
                asyncio.create_task(
                    gracy_send_msg(master_id, GracyText(text=welcome_msg), chat_type="private", tag=tag)
                )
        except Exception:
            continue


    http_port = config_manager.get("http_port", 0)
    if http_port:
        try:
            from gracybot.core.webserv import run_server
            await run_server(app, http_port)
        except Exception as e:
            logger.critical(f"❌ HTTP 服务启动失败: {str(e)}", exc_info=True)

            try:
                default = adapter_pool.get_default()
                master_id = getattr(default, '_instance_master_id', '') if default else ''
                if master_id:
                    asyncio.create_task(
                        gracy_send_msg(master_id, GracyText(text=f"❌ 机器人启动失败\n错误: {str(e)}"), chat_type="private")
                    )
            except Exception:
                pass
            sys.exit(1)
    else:

        logger.info("✅ 适配器运行中，等待消息...")
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            adapter_pool.stop_all()
            logger.info("🛑 适配器池已停止")

    sys.exit(0)
