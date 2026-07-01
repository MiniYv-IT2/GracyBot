"""GracyBot 框架级配置 — config.json 中的全局配置项

robot_id / master_id 等实例级配置已迁移到 style/instances/<name>/config.json，
每个实例独立管理，不再全局共享。
"""

import os
import time
from core.config_manager import config_manager, ConfigItem

# ═══════════════ 框架默认值 ═══════════════

DEFAULT_CONFIG = {
    "bot_version": "v1.9.57",

    "log_encoding": "utf-8",
    "log_level": "INFO",
    "debug_mode": False,
    "auto_replies": {
        "你好": "哈喽～ 我是 GracyBot，有什么可以帮你呀？",
        "在吗": "在呢在呢～ 随时在线为你服务！",
        "谢谢": "不客气呀～ 能帮到你我也很开心！",
        "再见": "拜拜～ 下次见啦，祝你生活愉快！",
        "早上好": "早上好呀～ 新的一天也要元气满满哦！",
        "晚上好": "晚上好～ 记得早点休息，不要熬夜呀！",
        "吃了吗": "哈哈，已经吃过啦～ 你也要按时吃饭呀！",
        "天气怎么样": "抱歉呀，我暂时没法查询天气，记得关注天气预报哦～",
        "你是谁": "我是 GracyBot，很高兴认识你！",
        "加油": "谢谢鼓励～ 你也超棒的，一起加油呀！"
    }
}
"""完整默认配置字典（框架级，不含实例级字段如 robot_id/master_id）。"""

# ═══════════════ 框架级配置（存储在 config.json）═══════════════

config_manager.register_config(ConfigItem(
    key="bot_version",
    default="v1.9.57",
    description="机器人版本"
))

config_manager.register_config(ConfigItem(
    key="log_encoding",
    default="utf-8",
    description="日志编码格式"
))

config_manager.register_config(ConfigItem(
    key="debug_mode",
    default=False,
    description="调试模式"
))

config_manager.register_config(ConfigItem(
    key="auto_replies",
    default={},
    description="关键词自动回复配置"
))

config_manager.register_config(ConfigItem(
    key="log_level",
    default="WARNING",
    description="日志级别",
    validate_func=lambda x: x in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
))

# ═══════════════ 加载配置 ═══════════════

if not config_manager.load():
    pass

config_manager._auto_update_config(DEFAULT_CONFIG)
config_manager.load()

# ═══════════════ 模块常量（框架级，不包含实例级字段） ═══════════════

BOT_VERSION = config_manager.get("bot_version")
LOG_ENCODING = config_manager.get("log_encoding")
AUTO_REPLIES = config_manager.get("auto_replies")
DEBUG_MODE = config_manager.get("debug_mode")
LOG_LEVEL = config_manager.get("log_level")

# robot_id / master_id 已迁移到各实例配置文件 + RuntimeRegistry
# 旧代码通过 get_current_robot_id() / get_current_master_id() 从 RuntimeContext 获取
ROBOT_ID = ""
MASTER_ID = ""
ROBOT_START_TIME = time.time()


def get_current_robot_id() -> str:
    """获取当前消息上下文中的机器人 ID（多实例时自动适配当前账号）

    插件在消息处理中调用此函数代替直接使用 ROBOT_ID，
    多账号场景下会自动返回正确的机器人 ID。
    无上下文时回退到第一个 Runtime 的 robot_id。
    """
    try:
        from core.runtime import RuntimeContext
        runtime = RuntimeContext.get()
        if runtime and runtime.robot_id:
            return runtime.robot_id
    except Exception:
        pass
    # 无上下文时尝试第一个 Runtime（如插件 on_ready 线程）
    try:
        from core.runtime import RuntimeRegistry
        runtimes = RuntimeRegistry.get_all()
        if runtimes and runtimes[0].robot_id:
            return runtimes[0].robot_id
    except Exception:
        pass
    return ROBOT_ID


def get_current_master_id() -> str:
    """获取当前消息上下文中的主人 ID（多实例时自动适配当前账号）

    插件在消息处理中调用此函数代替直接使用 MASTER_ID，
    多账号场景下会自动返回当前消息来源实例配置的主人 ID。
    无上下文时回退到第一个 Runtime 的 master_id。
    """
    try:
        from core.runtime import RuntimeContext
        runtime = RuntimeContext.get()
        if runtime and runtime.master_id:
            return runtime.master_id
    except Exception:
        pass
    # 无上下文时尝试第一个 Runtime（如插件 on_ready 线程）
    try:
        from core.runtime import RuntimeRegistry
        runtimes = RuntimeRegistry.get_all()
        if runtimes and runtimes[0].master_id:
            return runtimes[0].master_id
    except Exception:
        pass
    return MASTER_ID
