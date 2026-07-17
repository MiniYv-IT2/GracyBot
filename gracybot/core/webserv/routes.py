"""通用 Web 路由注册 — 不依赖具体 web 框架"""

import logging
from gracybot.core.utils import logger, logger_manager
from gracybot.core.webserv import jsonify


def register_error_handlers(app):
    """注册通用错误处理器"""
    import traceback
    from gracybot.core.webserv import request

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
            'client_ip': request.remote_addr if hasattr(request, 'remote_addr') else 'unknown',
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


def register_health_check_routes(app):
    """注册健康检查/监控面板路由"""
    try:
        from gracybot.core.monitor import monitor_manager
    except ImportError:
        return

    @app.route('/health', methods=['GET'])
    async def health_check():
        """健康检查端点"""
        health_info = monitor_manager.get_health_check()
        status_code = 200 if health_info["status"] == "healthy" else 503
        return jsonify(health_info), status_code

    @app.route('/metrics', methods=['GET'])
    async def get_metrics():
        """性能指标端点"""
        metrics = monitor_manager.get_performance_metrics()
        return jsonify(metrics)

    @app.route('/status', methods=['GET'])
    async def get_status():
        """系统状态端点"""
        status = monitor_manager.get_system_status()
        return jsonify(status)
