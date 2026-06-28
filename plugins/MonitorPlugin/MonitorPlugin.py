"""监控面板插件核心功能
提供系统状态和性能指标查看功能
"""

from graci import logger
from graci import monitor_manager
from graci import plugin_manager
from graci import gracy_send_msg
from graci import GracyText

async def handle_monitor(*args, **kwargs):
    """监控面板处理函数"""
    try:
        logger.info(f"[MonitorPlugin] handle_monitor函数被调用，args数量: {len(args)}, kwargs: {list(kwargs.keys())}")
        
        # 从args中获取参数（完全匹配handler.py的调用方式）
        plugin_manager = args[0] if len(args) > 0 else None
        _gracy_sender = args[1] if len(args) > 1 else None  # gracy_send_msg（保留兼容，实际直接导入使用）
        parsed_data = args[2] if len(args) > 2 else {}
        sender_id = args[3] if len(args) > 3 else "unknown"
        chat_type = args[4] if len(args) > 4 else "unknown"
        permission = args[5] if len(args) > 5 else "all"
        plugin_logger = args[6] if len(args) > 6 else logger
        
        # 从parsed_data中获取raw_msg
        raw_msg = parsed_data.get('text', '')
        
        # 设置target_id（必须放在try外，防止异常时未定义）
        target_id = sender_id
        if chat_type == 'group':
            target_id = parsed_data.get('raw_data', {}).get('group_id', sender_id)
        
        # 确保raw_msg是字符串
        if not isinstance(raw_msg, str):
            raw_msg = str(raw_msg)
        
        logger.info(f"[MonitorPlugin] 调试参数 - chat_type: {chat_type}, sender_id: {sender_id}, raw_msg: {raw_msg}")
        
        # 确保raw_msg是字符串
        if not isinstance(raw_msg, str):
            raw_msg = str(raw_msg)
        
        logger.info(f"[MonitorPlugin] 收到请求: {raw_msg}")
        logger.info(f"[MonitorPlugin] 消息详情 - 类型: {chat_type}, 发送者: {sender_id}, 目标ID: {target_id}")
        
        # 消息发送通过 GracyAdapter 适配层（已全局统一）
        
        # 根据不同指令返回不同内容 - 严格匹配命令
        content = ""
        if raw_msg in ["/状态", "/status"]:
            logger.info("[MonitorPlugin] 处理'状态'指令")
            content = get_system_status()
        
        elif raw_msg in ["/健康", "/health"]:
            logger.info("[MonitorPlugin] 处理'健康'指令")
            content = get_health_check()
        
        elif raw_msg in ["/性能", "/performance"]:
            logger.info("[MonitorPlugin] 处理'性能'指令")
            content = get_performance_summary()
        
        elif raw_msg == "/插件状态":
            logger.info("[MonitorPlugin] 处理'插件状态'指令")
            content = get_plugins_status()
        
        else:
            # 默认回复
            content = """🔍 监控面板功能说明：

• /状态 或 /status - 查看详细系统状态
• /健康 或 /health - 查看服务健康状态
• /性能 或 /performance - 查看性能统计信息
• /插件状态 - 查看已加载插件信息"""
        
        logger.info(f"[MonitorPlugin] 返回内容长度: {len(str(content))} 字符")
        logger.info(f"[MonitorPlugin] 向用户 {sender_id} 发送响应，类型: {chat_type}")
        
        # 尝试直接发送消息
        if content:
            logger.info("[MonitorPlugin] 发送响应消息")
            try:
                # 根据chat_type确定正确的发送参数
                if chat_type == 'group':
                    await gracy_send_msg(target_id, GracyText(text=content), chat_type=chat_type)
                else:
                    await gracy_send_msg(sender_id, GracyText(text=content), chat_type=chat_type)
                logger.info(f"[MonitorPlugin] 消息发送成功到 {target_id}，类型: {chat_type}")
            except Exception as send_err:
                logger.error(f"[MonitorPlugin] 发送消息失败: {str(send_err)}")
        else:
            logger.error("[MonitorPlugin] 没有可用的消息发送函数")
        
        # 记录插件执行成功
        logger.info(f"[MonitorPlugin] 命令处理完成: {raw_msg}")
               
    except Exception as e:
        logger.error(f"[MonitorPlugin] 处理请求时发生异常: {str(e)}", exc_info=True)
        
        # 确保异常情况下也发送错误消息
        error_msg = "❌ 监控数据获取失败"
        
        # 尝试发送错误消息
        try:
            if chat_type == 'group':
                await gracy_send_msg(target_id, GracyText(text=error_msg), chat_type=chat_type)
            else:
                await gracy_send_msg(sender_id, GracyText(text=error_msg), chat_type=chat_type)
            logger.info(f"[MonitorPlugin] 已发送错误消息")
        except Exception as send_err:
            logger.error(f"[MonitorPlugin] 发送错误消息失败: {str(send_err)}")
        
        # 异常情况下不需要返回值，handler.py不使用返回值

def get_system_status():
    """获取系统状态"""
    try:
        status = monitor_manager.get_system_status()
        
        response = "📊 **系统状态概览** 📊\n\n"
        response += f"🔹 **运行状态**: {get_status_emoji(status['status'])} {status['status']}\n"
        response += f"🔹 **运行时间**: {status['uptime_formatted']}\n"
        response += f"🔹 **更新时间**: {format_timestamp(status['timestamp'])}\n\n"
        
        response += "💻 **系统资源** 💻\n"
        response += f"🔹 CPU使用率: {status['system']['cpu_usage_percent']}%\n"
        response += f"🔹 内存使用率: {status['system']['memory']['usage_percent']}%\n"
        response += f"🔹 内存使用: {status['system']['memory']['used_mb']:.2f}MB / {status['system']['memory']['total_mb']:.2f}MB\n\n"
        
        response += "📨 **消息统计** 📨\n"
        response += f"🔹 总接收: {status['message_stats']['total_received']}\n"
        response += f"🔹 总处理: {status['message_stats']['total_processed']}\n"
        response += f"🔹 错误数: {status['message_stats']['total_errors']}\n"
        response += f"🔹 错误率: {status['message_stats']['error_rate_percent']}%\n"
        response += f"🔹 平均响应: {status['message_stats']['avg_response_time_ms']:.2f}ms"
        
        return response
        
    except Exception as e:
        logger.error(f"[MonitorPlugin] 获取系统状态失败: {str(e)}", exc_info=True)
        return "❌ 获取系统状态信息失败"

def get_health_check():
    """获取健康检查信息"""
    try:
        health = monitor_manager.get_health_check()
        
        response = "🏥 **健康检查结果** 🏥\n\n"
        response += f"🔹 **整体状态**: {get_status_emoji(health['status'])} {health['status']}\n"
        response += f"🔹 **服务名称**: {health['service']}\n"
        response += f"🔹 **服务版本**: v{health['version']}\n"
        response += f"🔹 **检查时间**: {format_timestamp(health['timestamp'])}\n"
        response += f"🔹 **运行时间**: {health['uptime']}\n\n"
        
        response += "✅ **检查项状态** ✅\n"
        response += f"🔹 CPU状态: {'正常' if health['checks']['cpu_healthy'] else '异常⚠️'}\n"
        response += f"🔹 内存状态: {'正常' if health['checks']['memory_healthy'] else '异常⚠️'}\n"
        response += f"🔹 错误率状态: {'正常' if health['checks']['error_rate_healthy'] else '异常⚠️'}"
        
        return response
        
    except Exception as e:
        logger.error(f"[MonitorPlugin] 获取健康检查失败: {str(e)}", exc_info=True)
        return "❌ 获取健康检查信息失败"

def get_performance_summary():
    """获取性能指标摘要"""
    try:
        metrics = monitor_manager.get_performance_metrics()
        
        # 计算CPU和内存的平均值
        cpu_avg = sum(h['value'] for h in metrics['cpu_history']) / len(metrics['cpu_history']) \
            if metrics['cpu_history'] else 0
        memory_avg = sum(h['value'] for h in metrics['memory_history']) / len(metrics['memory_history']) \
            if metrics['memory_history'] else 0
        
        response = "📈 **性能指标摘要** 📈\n\n"
        response += "💻 **资源使用趋势** 💻\n"
        response += f"🔹 CPU平均使用率: {cpu_avg:.2f}%\n"
        response += f"🔹 内存平均使用率: {memory_avg:.2f}%\n\n"
        
        response += "📨 **消息处理性能** 📨\n"
        if metrics['message_stats']['response_times']:
            avg_response = sum(metrics['message_stats']['response_times']) / len(metrics['message_stats']['response_times'])
            max_response = max(metrics['message_stats']['response_times'])
            min_response = min(metrics['message_stats']['response_times'])
            
            response += f"🔹 平均响应时间: {avg_response:.2f}ms\n"
            response += f"🔹 最大响应时间: {max_response:.2f}ms\n"
            response += f"🔹 最小响应时间: {min_response:.2f}ms\n"
        else:
            response += "🔹 暂无响应时间数据\n"
        
        if metrics['plugin_stats']:
            response += "\n🧩 **插件执行统计** 🧩\n"
            # 只显示前5个插件
            sorted_plugins = sorted(metrics['plugin_stats'].items(), 
                                   key=lambda x: x[1]['total_executions'], 
                                   reverse=True)[:5]
            
            for plugin_name, stats in sorted_plugins:
                success_rate = (stats['successful_executions'] / stats['total_executions']) * 100
                response += f"🔹 {plugin_name}:\n"
                response += f"   - 执行次数: {stats['total_executions']}\n"
                response += f"   - 成功率: {success_rate:.1f}%\n"
                response += f"   - 平均执行时间: {stats['avg_execution_time']*1000:.2f}ms\n"
        
        return response
        
    except Exception as e:
        logger.error(f"[MonitorPlugin] 获取性能指标失败: {str(e)}", exc_info=True)
        return "❌ 获取性能指标信息失败"

def get_plugins_status():
    """获取插件状态信息"""
    try:
        plugins_metadata = plugin_manager.get_all_plugins_metadata()
        
        response = "🧩 **已加载插件列表** 🧩\n\n"
        response += f"总加载插件数: {len(plugins_metadata)}\n\n"
        
        for plugin_info in plugins_metadata:
            if plugin_info:
                status_emoji = "✅"
                response += f"{status_emoji} **{plugin_info['name']}**\n"
                response += f"   版本: v{plugin_info['version']}\n"
                response += f"   描述: {plugin_info['description']}\n"
                response += f"   命令: {', '.join(plugin_info['commands'])}\n"
                response += f"   权限: {plugin_info['permission']}\n"
                
                # 显示依赖信息
                if plugin_info['dependencies']:
                    deps_info = ", ".join([f"{dep['name']} (≥{dep.get('min_version', '0.0.0')})"] for dep in plugin_info['dependencies'])
                    response += f"   依赖: {deps_info}\n"
                
                response += "\n"
        
        return response
        
    except Exception as e:
        logger.error(f"[MonitorPlugin] 获取插件状态失败: {str(e)}", exc_info=True)
        return "❌ 获取插件状态信息失败"

def get_status_emoji(status):
    """根据状态返回对应的表情符号"""
    if status == "healthy":
        return "✅"
    elif status == "degraded":
        return "⚠️"
    elif status == "unhealthy":
        return "❌"
    return "❓"

def format_timestamp(timestamp):
    """格式化时间戳"""
    try:
        from datetime import datetime
        # 处理ISO格式的时间戳
        if isinstance(timestamp, str):
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        # 处理datetime对象
        elif hasattr(timestamp, 'strftime'):
            return timestamp.strftime("%Y-%m-%d %H:%M:%S")
    except:
        pass
    return str(timestamp)
