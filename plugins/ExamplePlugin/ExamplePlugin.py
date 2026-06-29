"""示例插件 — 10层架构模板 / 实验场

展示 GracyBot 新风格插件开发的完整模式与所有可用 API。
"""

# Layer 2: 标准库
import os
import json
import asyncio
import time
from typing import Optional

# Layer 3: 第三方库
import httpx

# Layer 4: 框架API（完整展示所有可导入符号）
from graci import (
    # 消息类型
    GracyText, GracyImage, GracyVoice, GracyAt, GracyReply, GracyMsg,
    GracyFile, GracyVideo, GracyForward,
    # 发送函数
    gracy_send_msg, gracy_call_api, gracy_get_platform_info,
    # 装饰器
    on_command, on_regex, on_keyword,
    gracy_plugin, plugin_handler, on_fallback,
    require_permission, require_master,
    rate_limit, cooldown,
    with_session, async_retry, background,
    PluginContext, DECORATOR_COMMAND_REGISTRY,
    # 配置
    BOT_VERSION, MASTER_ID, ROBOT_ID, ROBOT_START_TIME,
    get_current_master_id, get_current_robot_id,
    # 核心服务
    plugin_manager, config_manager,
    # 日志
    get_logger, with_logger, log_attrs,
    # 安全
    sanitize_log,
    # 监控
    monitor_manager,
    # CLI
    register_cli_command,
    # Pipeline / Runtime
    Stage, RuntimeRegistry, GracyEvent, IdentityTag,
)

# Layer 5: 本地模块
from .metadata import PLUGIN_NAME, PLUGIN_VERSION

# Layer 6: 日志器
logger = get_logger("Example")

# Layer 7: 常量
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CACHE_DIR = os.path.join(DATA_DIR, "cache")
EXAMPLE_API = "https://api.example.com"

# Layer 8: 模块级状态
_visit_count: int = 0
_last_search: Optional[str] = None

# Layer 9: 辅助函数
async def _fetch_joke() -> str:
    """从公共 API 获取一条冷笑话"""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get("https://v2.jokeapi.dev/joke/Any?type=single")
        resp.raise_for_status()
        data = resp.json()
        return data.get("joke", "笑话走丢了")

def _api_url(endpoint: str) -> str:
    return f"{EXAMPLE_API}/{endpoint.lstrip('/')}"

# Layer 10: 装饰器 + Handler

@on_command("/echo", "/say")
@plugin_handler
async def handle_echo(ctx: PluginContext):
    """简单 echo — 演示基础命令收发"""
    text = ctx.raw_text.removeprefix(ctx.command).strip()
    if not text:
        await ctx.reply("用法：/echo <内容>")
        return
    await ctx.reply(f"你说了：{text}")
    logger.info(f"用户 {ctx.sender_id} echo: {text}")

@on_regex(r"^[Hh]ello\b")
@plugin_handler
async def handle_hello(ctx: PluginContext):
    """正则匹配 — 匹配以 hello 开头的消息"""
    name = ctx.raw_text.split(maxsplit=1)[-1] if len(ctx.raw_text.split()) > 1 else "world"
    await ctx.reply(f"Hi {name}!")
    logger.info(f"用户 {ctx.sender_id} 打了个招呼: {ctx.raw_text}")

@on_command("/owner")
@require_master
@plugin_handler
async def handle_owner_only(ctx: PluginContext):
    """主人专属命令 — 演示 require_master"""
    global _visit_count
    info = (
        f"Bot v{BOT_VERSION}\n"
        f"主人: {get_current_master_id()}\n"
        f"运行时间: {ROBOT_START_TIME}\n"
        f"总访问次数: {_visit_count}"
    )
    await ctx.reply(info)
    logger.info(f"主人 {ctx.sender_id} 查看状态")

@on_command("/joke")
@rate_limit(calls=3, period=60)
@plugin_handler
async def handle_joke(ctx: PluginContext):
    """随机冷笑话 — 演示 rate_limit（每分钟最多 3 次）"""
    try:
        joke = await _fetch_joke()
    except Exception as e:
        logger.error(f"获取笑话失败: {e}")
        joke = "笑话服务器打盹了，晚点再来吧"
    await ctx.reply(joke)
    logger.info(f"用户 {ctx.sender_id} 获取笑话")

@on_command("/meme")
@plugin_handler
async def handle_meme(ctx: PluginContext):
    """发送图片 — 演示 GracyImage 发送"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, "demo_meme.png")
    if not os.path.exists(path):
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get("https://httpbin.org/image/png")
            resp.raise_for_status()
            with open(path, "wb") as f:
                f.write(resp.content)
    await ctx.send(GracyImage(file_path=path))
    logger.info(f"用户 {ctx.sender_id} 请求 meme 图片")

@on_command("/botinfo")
@plugin_handler
async def handle_bot_info(ctx: PluginContext):
    """平台 API — 演示 gracy_call_api"""
    result = await gracy_call_api("get_bot_info", {})
    await ctx.reply(f"平台信息：{json.dumps(result, ensure_ascii=False, indent=2)}")
    logger.info(f"用户 {ctx.sender_id} 查询平台信息")

@background(interval=3600)
async def _cleanup_cache():
    """定时任务（每小时）— 清理过期缓存文件"""
    logger.debug("开始清理缓存...")
    if not os.path.isdir(CACHE_DIR):
        return
    now = time.time()
    removed = 0
    for fname in os.listdir(CACHE_DIR):
        fpath = os.path.join(CACHE_DIR, fname)
        if os.path.isfile(fpath) and now - os.path.getmtime(fpath) > 86400:
            os.remove(fpath)
            removed += 1
    if removed:
        logger.info(f"清理了 {removed} 个过期缓存文件")

logger.info("示例插件加载完成，10 层架构演示就绪")
