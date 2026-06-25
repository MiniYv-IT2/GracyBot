"""

原神崩铁查询插件 — 通过早柚核心(GsCore)实现



命令翻译机制：

  用户输入 /原神绑定 123456789

  ↓ 插件翻译成 GsCore 原生命令

  绑定uid 123456789

  ↓ 通过 WebSocket 发送

  GsCore 处理并返回结果

"""

import logging

import os



from core.decorators import on_command, plugin_handler, PluginContext

from core.gracy_adapter.message import GracyImage, GracyText



from .core.gscore_bridge import (

    get_client, _download_image,

    _create_qrcode, _poll_qrcode,

    _make_qr_image, _display_qr_in_terminal,

)



_logger = logging.getLogger("Gracy.Genshin")



# ── GsCore 客户端单例 ──

_gscore = get_client()



# ── 缓存目录 ──

_PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))

_CACHE_DIR = os.path.join(_PLUGIN_DIR, "data", "cache")



# ═══════════════════════════════════════════════

# 命令翻译表：将 GracyBot 指令映射为 GsCore 原生命令

# GsCore 使用无斜杠前缀的纯文本命令

# ═══════════════════════════════════════════════

_CMD_MAP = {

    # ── 原神 ──

    "/原神绑定":    "绑定uid",     # /原神绑定 123456789 → 绑定uid 123456789

    "/原神uid":     "查询",        # /原神uid 123456789  → 查询 123456789

    "/我的角色":    "角色列表",    # → 角色列表

    "/深渊":        "深渊",        # → 深渊

    "/体力":        "当前状态",    # → 当前状态



    # ── 崩铁（GsCore 根据 UID 自动识别游戏类型） ──

    "/崩铁绑定":    "绑定uid",     # → 绑定uid <UID>

    "/崩铁uid":     "查询",        # → 查询 <UID>

    "/忘却之庭":    "深渊",        # → 深渊（GsCore 自动判断游戏）

    "/开拓力":      "当前状态",    # → 当前状态



    # ── 登录 / 绑定 / 签到（GsCore 核心功能） ──

    "/扫码登陆":    "扫码登陆",    # → 扫码登陆（米游社二维码登录）

    "/签到":        "签到",        # → 签到（米游社每日签到）

    "/绑定帮助":    "绑定帮助",    # → 绑定帮助（显示绑定/CK 帮助）

    "/绑定信息":    "绑定信息",    # → 绑定信息（显示已绑定的 UID）

    "/刷新ck":      "刷新CK",      # → 刷新CK（刷新失效 Cookie）



    # ── 攻略／图鉴（需带角色/武器/材料名称） ──

    "/攻略":        "参考攻略",     # /攻略 胡桃 → 参考攻略 胡桃

    "/面板":        "参考面板",     # /面板 胡桃 → 参考面板 胡桃

    "/查角色":      "查角色",       # /查角色 胡桃 → 查角色 胡桃

    "/查武器":      "查武器",       # /查武器 和璞鸢 → 查武器 和璞鸢

    "/查圣遗物":    "查圣遗物",     # /查圣遗物 绝缘 → 查圣遗物 绝缘

    "/查天赋":      "查天赋",       # /查天赋 胡桃 → 查天赋 胡桃

    "/角色材料":    "角色材料",     # /角色材料 胡桃 → 角色材料 胡桃

    "/武器材料":    "武器材料",     # /武器材料 和璞鸢 → 武器材料 和璞鸢

    "/查命座":      "查命座",       # /查命座 胡桃 → 查命座 胡桃

    "/查原魔":      "查原魔",       # /查原魔 急冻树 → 查原魔 急冻树

    "/查食物":      "查食物",       # /查食物 仙跳墙 → 查食物 仙跳墙

    "/哪里有":      "哪里有",       # /哪里有 蒲公英 → 哪里有 蒲公英

    "/原神任务":    "原神任务",     # /原神任务 第一章 → 原神任务 第一章



    # ── 深渊／活动（无需参数） ──

    "/版本深渊":    "版本深渊",     # 深渊阵容统计

    "/活动列表":    "活动列表",     # 当前活动列表

    "/卡池列表":    "卡池列表",     # 当期卡池信息



    # ── 数据查询（无需参数） ──

    "/原神公告":    "原神公告",     # 原神公告

    "/七圣召唤":    "七圣召唤",     # 七圣召唤数据

    "/版本规划":    "版本规划",     # 原石/资源规划

    "/抽卡记录":    "抽卡记录",     # 抽卡历史记录

    "/每月统计":    "每月统计",     # 每月资源统计

    "/实时便笺":    "实时便笺",     # 体力/派遣/洞天宝钱

    "/我的背包":    "我的背包",     # 背包材料查询

    "/伤害乘区":    "伤害乘区",     # 伤害乘区表

    "/gs帮助":      "gs帮助",       # GenshinUID 完整帮助

}



# 需要参数的命令

_CMD_ARGS_REQUIRED = {

    "/原神绑定", "/崩铁绑定",

    "/攻略", "/面板", "/查角色", "/查武器", "/查圣遗物",

    "/查天赋", "/角色材料", "/武器材料", "/查命座",

    "/查原魔", "/查食物", "/哪里有", "/原神任务",

}



# 用法提示

_CMD_USAGE = {

    "/原神绑定": "❌ 用法：/原神绑定 <UID>\n示例：/原神绑定 123456789",

    "/崩铁绑定": "❌ 用法：/崩铁绑定 <UID>\n示例：/崩铁绑定 123456789",

    "/攻略":     "❌ 用法：/攻略 <角色名>\n示例：/攻略 胡桃",

    "/面板":     "❌ 用法：/面板 <角色名>\n示例：/面板 胡桃",

    "/查角色":   "❌ 用法：/查角色 <角色名>\n示例：/查角色 胡桃",

    "/查武器":   "❌ 用法：/查武器 <武器名>\n示例：/查武器 和璞鸢",

    "/查圣遗物": "❌ 用法：/查圣遗物 <圣遗物名>\n示例：/查圣遗物 绝缘",

    "/查天赋":   "❌ 用法：/查天赋 <角色名>\n示例：/查天赋 胡桃",

    "/角色材料": "❌ 用法：/角色材料 <角色名>\n示例：/角色材料 胡桃",

    "/武器材料": "❌ 用法：/武器材料 <武器名>\n示例：/武器材料 和璞鸢",

    "/查命座":   "❌ 用法：/查命座 <角色名>\n示例：/查命座 胡桃",

    "/查原魔":   "❌ 用法：/查原魔 <怪物名>\n示例：/查原魔 急冻树",

    "/查食物":   "❌ 用法：/查食物 <食物名>\n示例：/查食物 仙跳墙",

    "/哪里有":   "❌ 用法：/哪里有 <材料名>\n示例：/哪里有 蒲公英",

    "/原神任务": "❌ 用法：/原神任务 <任务名>\n示例：/原神任务 第一章",

    "/扫码登陆": "✅ 发送 /扫码登陆 后，使用米游社 APP 扫码完成登录",

    "/绑定帮助": "✅ 显示绑定 Cookie/UID 的帮助信息",

    "/绑定信息": "✅ 查看当前已绑定的 UID 列表",

    "/签到":     "✅ 米游社每日签到（需先绑定 Cookie）",

    "/刷新ck":   "✅ 刷新已绑定的失效 Cookie",

}





# ── 启动连接（插件加载时自动执行） ──

def __init_plugin():

    """插件加载时初始化 GsCore 连接"""

    if _gscore is None:

        _logger.info("[Genshin_Plugin] GsCore 已禁用，跳过连接")

        return

    try:

        import asyncio

        loop = asyncio.get_event_loop()

        if loop.is_running():

            asyncio.ensure_future(_gscore.start())

    except RuntimeError:

        pass





# ── Handler ──

@on_command(

    "/原神绑定", "/原神uid", "/我的角色", "/深渊", "/体力",

    "/崩铁绑定", "/崩铁uid", "/忘却之庭", "/开拓力",

    "/扫码登陆", "/签到", "/绑定帮助", "/绑定信息", "/刷新ck",

    # ── 攻略／图鉴（需参数） ──

    "/攻略", "/面板", "/查角色", "/查武器", "/查圣遗物",

    "/查天赋", "/角色材料", "/武器材料", "/查命座",

    "/查原魔", "/查食物", "/哪里有", "/原神任务",

    # ── 深渊／活动 ──

    "/版本深渊", "/活动列表", "/卡池列表",

    # ── 数据查询 ──

    "/原神公告", "/七圣召唤", "/版本规划",

    "/抽卡记录", "/每月统计", "/实时便笺", "/我的背包",

    "/伤害乘区", "/gs帮助",

)

@plugin_handler

async def handle_genshin(ctx: PluginContext):

    """原神崩铁查询统一入口"""



    cmd = ctx.command

    raw = ctx.raw_text.strip()

    args = raw[len(cmd):].strip()



    # ── 参数检查：必需参数的命令 → 显示用法 ──

    if cmd in _CMD_ARGS_REQUIRED and not args:

        await ctx.reply(_CMD_USAGE.get(cmd, "❌ 请提供参数"))

        return



    # ── 无参命令（如 /扫码登陆 /绑定帮助）直接显示用法 ──

    if cmd in ("/扫码登陆", "/绑定帮助", "/绑定信息", "/签到", "/刷新ck"):

        pass  # 直接转发给 GsCore



    # ── 命令翻译：GracyBot 命令 → GsCore 原生命令 ──

    gs_native_cmd = _CMD_MAP.get(cmd, cmd.lstrip("/"))  # 翻译或去斜杠

    if args:

        gs_text = f"{gs_native_cmd} {args}"

    else:

        gs_text = gs_native_cmd



    # ── 映射 user_type ──

    user_type = "direct" if ctx.chat_type == "private" else "group"



    # ── 扫码登录：走自定义流程，绕过 GsCore 的 qrcode_login ──

    if cmd == "/扫码登陆":

        await ctx.reply("📱 正在生成二维码，请稍候...")



        # 1. 创建二维码（调米游社 API）

        qr_data = await _create_qrcode()

        if not qr_data:

            await ctx.reply("❌ 二维码创建失败，可能是网络问题，请稍后重试")

            return



        # 2. 生成二维码图片

        img_bytes = _make_qr_image(qr_data["url"])



        # 3. 保存到缓存目录

        os.makedirs(_CACHE_DIR, exist_ok=True)

        qr_path = os.path.join(_CACHE_DIR, "qrcode_latest.png")

        with open(qr_path, "wb") as f:

            f.write(img_bytes)



        # 4. 终端渲染显示

        _display_qr_in_terminal(img_bytes)



        # 5. 发送到 QQ

        await ctx.reply("请使用米游社 APP 扫描下方二维码登录：")

        await ctx.send(GracyImage(file_path=qr_path))

        await ctx.reply(

            "免责声明:您将通过扫码完成获取米游社sk以及ck。\n"

            "我方仅提供米游社查询及相关游戏内容服务,\n"

            "若您的账号封禁、被盗等处罚与我方无关。\n"

            "害怕风险请勿扫码~"

        )



        # 6. 轮询等待扫码（最长 120 秒）

        _logger.info("[扫码] 等待用户扫码结果（最长 120s）...")

        poll_result = await _poll_qrcode(

            qr_data["ticket"], qr_data["device_id"], timeout=120,

        )

        if not poll_result:

            await ctx.reply("⏳ 二维码已过期或扫码超时，请重新 /扫码登陆")

            _logger.info(f"用户{ctx.sender_id} 查询: /扫码登陆 结果=超时/过期")

            return



        # 7. 从 passport API 获取的 Set-Cookie 中提取完整 cookie

        _logger.info("[扫码] 扫码成功，提取 Cookie...")

        cookie_raw = poll_result.get("cookie_raw", "")

        if not cookie_raw:

            _logger.warning(f"[扫码] 无 Set-Cookie")

            await ctx.reply("❌ Cookie 获取失败，请重试 /扫码登陆")

            return



        # 解析 Set-Cookie，组装 GsCore 需要的格式

        # 每个 Set-Cookie 格式: "key=value; Path=/; Domain=..."

        # 只取每个 cookie 的第一段 (name=value)

        cookiejar = {}

        for sc in poll_result.get("raw_cookies", []):

            first_part = sc.split(";")[0].strip()

            if "=" in first_part:

                k, v = first_part.split("=", 1)

                cookiejar[k.strip()] = v.strip()



        _logger.info(f"[扫码] 解析到 cookie 字段: {list(cookiejar.keys())}")



        # GsCore 添加CK 通过 SimpleCookie 解析，寻找逻辑（add_ck.py _deal_ck）:

        #   1) sk_list=['stoken','stoken_v2'] → 如果有 stoken，用它换 cookie_token

        #   2) lt_list=['login_ticket','login_ticket_v2'] → 用 login_ticket 换 stoken → 再换 cookie_token ✅ 走这条

        #   3) ck_list=['cookie_token','cookie_token_v2'] → 直接用 cookie_token（无 stoken 的保底方案）

        # 注意：login_ticket 需要跟 account_id 一起提交，GsCore 内部会调 API 换成 stoken

        cookie_parts = []

        # cookie_token 必须

        if "cookie_token" in cookiejar:

            cookie_parts.append(f"cookie_token={cookiejar['cookie_token']}")

        elif "cookie_token_v2" in cookiejar:

            cookie_parts.append(f"cookie_token_v2={cookiejar['cookie_token_v2']}")

        # account_id 必须（GsCore 的 get_account_id 从 id_list 中找）

        if "account_id" in cookiejar:

            cookie_parts.append(f"account_id={cookiejar['account_id']}")

        elif "ltuid" in cookiejar:

            cookie_parts.append(f"ltuid={cookiejar['ltuid']}")

        # login_ticket → GsCore 会用它换 stoken，这样就有完整权限了！

        if "login_ticket" in cookiejar:

            cookie_parts.append(f"login_ticket={cookiejar['login_ticket']}")

            _logger.info("[扫码] 发现 login_ticket，GsCore 将用它换取 stoken")

        elif "login_ticket_v2" in cookiejar:

            cookie_parts.append(f"login_ticket_v2={cookiejar['login_ticket_v2']}")

            _logger.info("[扫码] 发现 login_ticket_v2，GsCore 将用它换取 stoken")



        if not cookie_parts:

            _logger.warning(f"[扫码] Cookie 缺少必要字段: {list(cookiejar.keys())}")

            await ctx.reply("❌ Cookie 字段不完整，请重试 /扫码登陆")

            return

        cookie_str = ";".join(cookie_parts)



        # 8. 通过 GsCore 存储 Cookie

        _logger.info("[扫码] Cookie 获取成功，正在绑定到 GsCore...")

        await ctx.reply("✅ 扫码成功！正在绑定 Cookie...")

        try:

            add_result = await _gscore.send_command(

                user_id=ctx.sender_id,

                user_type=user_type,

                text=f"添加 {cookie_str}",

                group_id=ctx.target_id if ctx.chat_type == "group" else "",

            )

            _logger.info(f"[扫码] GsCore 添加CK 返回 {len(add_result)} 条: {[t for t,d in add_result]}")

            has_text = False

            for msg_type, msg_data in add_result:

                if msg_type == "text":

                    await ctx.reply(msg_data)

                    has_text = True

                elif msg_type == "image":

                    _logger.info(f"[扫码] GsCore 返回图片(跳过图片显示)：{msg_data[:60]}")

            if not has_text:

                await ctx.reply("✅ Cookie 绑定至 GsCore 完成！可以试试发 /签到 验证")

        except Exception as e:

            _logger.error(f"[扫码] 添加CK异常: {e}")

            await ctx.reply(f"❌ Cookie 绑定失败: {e}")



        _logger.info(f"用户{ctx.sender_id} 查询: /扫码登陆 (自定义流程→成功)")

        return



    # ═══════════════════════════════════════════════

    # 非扫码登录：走原有 GsCore 流程

    # ═══════════════════════════════════════════════

    # ── 检查 GsCore 连接状态 ──

    if not _gscore.connected:

        await ctx.reply("🔄 正在连接早柚核心(GsCore)，请稍后重试...")

        return



    # ── 发送到 GsCore ──

    await ctx.reply("⏳ 正在查询，请稍候...")

    _logger.info(f"→ 发送至 GsCore: [{gs_text}]")



    try:

        kwargs = dict(

            user_id=ctx.sender_id,

            user_type=user_type,

            text=gs_text,

            group_id=ctx.target_id if ctx.chat_type == "group" else "",

        )

        results = await _gscore.send_command(**kwargs)

    except Exception as e:

        _logger.error(f"GsCore 查询异常: {e}", exc_info=True)

        await ctx.reply(f"❌ 查询失败：{e}")

        return



    # ── 调试: 查看返回值（隐去 base64 正文） ──

    _logger.info(f"[GsCore结果] 共 {len(results)} 条消息, 类型: {[t for t, d in results]}")



    # ── 处理返回结果 ──

    if not results:

        await ctx.reply("⏳ GsCore 暂无响应，请稍后重试")

        return



    text_parts = []

    image_tasks = []



    for msg_type, msg_data in results:

        if msg_type == "image":

            _logger.info(f"[GsCore结果] 条目: type=image, len={len(msg_data) if msg_data else 0}")

        else:

            _logger.info(f"[GsCore结果] 条目: type={msg_type}, data_preview={str(msg_data)[:100]}")

        if msg_type == "text":

            text_parts.append(msg_data)

        elif msg_type == "image":

            local_path = await _download_image(msg_data)

            if local_path:

                image_tasks.append(local_path)



    # 先发文字

    if text_parts:

        await ctx.reply("\n".join(text_parts))



    # 再发图片

    for img_path in image_tasks:

        try:

            await ctx.send(GracyImage(file_path=img_path))

        except Exception as e:

            _logger.warning(f"图片发送失败: {e}")



    _logger.info(f"用户{ctx.sender_id} 查询: {cmd} {'(' + args + ')' if args else ''}")





# ── 执行初始化 ──

__init_plugin()

