import os
import time
from core.config_manager import config_manager, ConfigItem

# ═══════════════ 框架级配置（存储在 config.json）═══════════════

# 启动路由（决定加载哪个适配器，属于框架级决策）
config_manager.register_config(ConfigItem(
    key="connection_mode",
    default="http",
    description="连接模式: http(http_reverse), ws_forward, ws_reverse",
    validate_func=lambda x: x in ["http", "http_reverse", "ws_forward", "ws_reverse"]
))

config_manager.register_config(ConfigItem(
    key="robot_id", 
    default="不要填，填根目录的config.json", 
    description="机器人ID", 
    required=True
))
config_manager.register_config(ConfigItem(
    key="callback_port", 
    default=3002, 
    description="回调服务端口",
    validate_func=lambda x: isinstance(x, int) and 1024 <= x <= 65535
))
config_manager.register_config(ConfigItem(
    key="master_id", 
    default="填写ID(默认，不用改，直接改根目录的config.json)", 
    description="主人ID", 
    required=True
))
config_manager.register_config(ConfigItem(
    key="bot_version", 
    default="v1.9.2", 
    description="机器人版本"
))
config_manager.register_config(ConfigItem(
    key="log_encoding", 
    default="utf-8", 
    description="日志编码格式"
))
config_manager.register_config(ConfigItem(
    key="auto_replies", 
    default={
        "你好": "哈喽～ 我是 GracyBot，有什么可以帮你呀？",
        "在吗": "在呢在呢～ 随时在线为你服务！",
        "谢谢": "不客气呀～ 能帮到你我也很开心！",
        "再见": "拜拜～ 下次见啦，祝你生活愉快！",
        "早上好": "早上好呀～ 新的一天也要元气满满哦！",
        "晚上好": "晚上好～ 记得早点休息，不要熬夜呀！",
        "吃了吗": "哈哈，已经吃过啦～ 你也要按时吃饭呀！",
        "天气怎么样": "抱歉呀，我暂时没法查询天气，记得关注天气预报哦～",
        "你是谁": "我是 GracyBot，一款基于 Napcat 的 QQ 机器人，很高兴认识你！",
        "加油": "谢谢鼓励～ 你也超棒的，一起加油呀！"
    },
    description="自动回复配置"
))
config_manager.register_config(ConfigItem(
    key="debug_mode", 
    default=False, 
    description="调试模式"
))
config_manager.register_config(ConfigItem(
    key="log_level", 
    default="WARNING", 
    description="日志级别",
    validate_func=lambda x: x in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
))

# ═══════════════ OneBot 适配器专属配置（存储在 onebot_config.json）═══════════════
# 这些配置项由 OneBot 适配器使用，从独立配置文件加载，
# 未来新增适配器各自维护自己的配置文件，不污染框架 config.json

config_manager.register_config(ConfigItem(
    key="napcat_http_url",
    default="http://localhost:3000",
    description="NapCat HTTP API 地址"
))
config_manager.register_config(ConfigItem(
    key="ws_host",
    default="127.0.0.1",
    description="WebSocket 地址(正向=OneBot地址, 反向=监听地址)"
))
config_manager.register_config(ConfigItem(
    key="ws_port",
    default=3001,
    description="WebSocket 端口",
    validate_func=lambda x: isinstance(x, int) and 1024 <= x <= 65535
))
config_manager.register_config(ConfigItem(
    key="access_token",
    default="",
    description="OneBot access_token（留空=不使用token连接）"
))

# ═══════════════ 加载配置 ═══════════════

_ONEBOT_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "gracy_adapter", "onebot", "onebot_config.json"
)

# 1. 加载框架配置 (config.json)
if not config_manager.load():
    raise RuntimeError("配置加载失败，请检查配置文件或环境变量")

# 2. 加载 OneBot 适配器配置 (onebot_config.json)
config_manager.load_from(_ONEBOT_CONFIG_PATH)

# 为兼容旧代码，提供直接访问方式
ROBOT_ID = config_manager.get("robot_id")
CALLBACK_PORT = config_manager.get("callback_port")
MASTER_ID = config_manager.get("master_id")
BOT_VERSION = config_manager.get("bot_version")
LOG_ENCODING = config_manager.get("log_encoding")
AUTO_REPLIES = config_manager.get("auto_replies")
DEBUG_MODE = config_manager.get("debug_mode")
LOG_LEVEL = config_manager.get("log_level")

# 非配置项常量
ROBOT_START_TIME = time.time()

# 连接模式（框架启动路由，保留为模块常量）
CONNECTION_MODE = config_manager.get("connection_mode")

# OneBot 适配器配置不再作为模块常量，
# 使用方通过 config_manager.get("ws_host") 等方式获取
