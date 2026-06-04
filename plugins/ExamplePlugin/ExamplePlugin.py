"""示例插件核心功能文件
演示如何使用版本控制和依赖管理功能
"""

from core.utils import logger
from core.plugin_manager import plugin_manager

def handle_example(plugin_manager, gracy_send_msg, data, sender_id, chat_type, permission, logger, **_):
    """示例插件处理函数"""
    raw_msg = data.get("text", "") if isinstance(data, dict) else str(data)
    sanitized = raw_msg[:80] + "..." if len(raw_msg) > 80 else raw_msg
    logger.debug(f"[示例插件] 收到消息: {sanitized} 来自: {sender_id} 类型: {chat_type}")
    
    # 根据不同指令返回不同内容
    if "版本" in raw_msg:
        plugins_metadata = plugin_manager.get_all_plugins_metadata()
        response = "📊 当前加载的插件信息：\n\n"
        for plugin_info in plugins_metadata:
            if plugin_info:
                response += f"🔹 {plugin_info['name']} v{plugin_info['version']}\n"
                if plugin_info['dependencies']:
                    deps_info = ", ".join([f"{dep['name']} (≥{dep.get('min_version', '0.0.0')})"] for dep in plugin_info['dependencies'])
                    response += f"   依赖: {deps_info}\n"
        return response
    
    elif "示例依赖" in raw_msg:
        response = "📋 依赖管理功能说明：\n\n"
        response += "1. 插件可以在PLUGIN_META中定义依赖\n"
        response += "2. 格式：{\"name\": \"插件名\", \"min_version\": \"1.0.0\"}\n"
        response += "3. 系统会自动检查依赖是否满足\n"
        response += "4. 支持版本范围限制和循环依赖检测"
        return response
    
    return "👋 你好！这是一个演示版本控制和依赖管理功能的示例插件。\n试试输入：\n• 版本 - 查看所有插件版本信息\n• 示例依赖 - 了解依赖管理功能"

def on_shutdown():
    """插件关闭时的清理函数"""
    logger.info("[示例插件] 执行关闭清理操作")
