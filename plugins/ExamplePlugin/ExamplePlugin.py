"""示例插件核心功能文件
演示如何使用版本控制和依赖管理功能
"""

from core.utils import logger
from core.plugin_manager import plugin_manager

# CQ 码脱敏（避免日志中打印超长原始 JSON/卡片内容）
_CQ_SANITIZE = [
    (r'\[CQ:image,[^\]]+\]', '[图片]'),
    (r'\[CQ:face,[^\]]+\]', '[表情]'),
    (r'\[CQ:at,qq=(\d+)[^\]]*\]', r'[@\1]'),
    (r'\[CQ:reply,[^\]]+\]', '[回复]'),
    (r'\[CQ:record,[^\]]+\]', '[语音]'),
    (r'\[CQ:video,[^\]]+\]', '[视频]'),
    (r'\[CQ:file,[^\]]+\]', '[文件]'),
    (r'\[CQ:share,[^\]]+\]', '[链接分享]'),
    (r'\[CQ:json,[^\]]+\]', '[JSON卡片]'),
    (r'\[CQ:markdown,[^\]]+\]', '[卡片消息]'),
    (r'\[CQ:forward,[^\]]+\]', '[合并转发]'),
    (r'\[CQ:poke,[^\]]+\]', '[戳一戳]'),
    (r'\[CQ:dice,[^\]]+\]', '[骰子]'),
    (r'\[CQ:rps,[^\]]+\]', '[猜拳]'),
    (r'\[CQ:contact,[^\]]+\]', '[推荐好友]'),
]

def handle_example(plugin_manager, gracy_send_msg, data, sender_id, chat_type, permission, logger, **_):
    """示例插件处理函数"""
    raw_msg = data.get("raw_message", "") if isinstance(data, dict) else str(data)
    try:
        import re
        sanitized = raw_msg
        for pattern, replacement in _CQ_SANITIZE:
            sanitized = re.sub(pattern, replacement, sanitized)
        if len(sanitized) > 80:
            sanitized = sanitized[:77] + "..."
        logger.debug(f"[示例插件] 收到消息: {sanitized} 来自: {sender_id} 类型: {chat_type}")
        
        # 根据不同指令返回不同内容
        if "版本" in raw_msg:
            # 获取所有插件的元信息
            plugins_metadata = plugin_manager.get_all_plugins_metadata()
            response = "📊 当前加载的插件信息：\n\n"
            for plugin_info in plugins_metadata:
                if plugin_info:
                    response += f"🔹 {plugin_info['name']} v{plugin_info['version']}\n"
                    # 显示依赖信息
                    if plugin_info['dependencies']:
                        deps_info = ", ".join([f"{dep['name']} (≥{dep.get('min_version', '0.0.0')})"] for dep in plugin_info['dependencies'])
                        response += f"   依赖: {deps_info}\n"
            return response
        
        elif "示例依赖" in raw_msg:
            # 演示依赖管理功能
            response = "📋 依赖管理功能说明：\n\n"
            response += "1. 插件可以在PLUGIN_META中定义依赖\n"
            response += "2. 格式：{\"name\": \"插件名\", \"min_version\": \"1.0.0\"}\n"
            response += "3. 系统会自动检查依赖是否满足\n"
            response += "4. 支持版本范围限制和循环依赖检测"
            return response
        
        # 默认回复
        return "👋 你好！这是一个演示版本控制和依赖管理功能的示例插件。\n"
        "试试输入：\n"
        "• 版本 - 查看所有插件版本信息\n"
        "• 依赖 - 了解依赖管理功能"
        "• 示例 - 查看基本功能"
               
    except Exception as e:
        logger.error(f"[示例插件] 处理消息时发生异常: {str(e)}", exc_info=True)
        return "❌ 插件处理过程中发生错误"

def on_shutdown():
    """插件关闭时的清理函数（可选）
    当机器人关闭时，插件管理器会自动调用此函数
    """
    logger.info("[示例插件] 执行关闭清理操作")
    # 在这里可以进行资源清理、连接关闭等操作
    # 例如关闭数据库连接、清理临时文件等
