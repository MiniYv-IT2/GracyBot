"""
异环(NTE)攻略插件 — 查询角色/武器/材料/兑换码

命令:
  /异环           — 导航菜单
  /异环角色 <名字>  — 角色详情
  /异环武器 <名字>  — 弧盘详情
  /异环材料 <名字> [起始等级] [目标等级] — 升级材料计算
  /异环兑换码      — 最新兑换码
  /异环搜索 <关键词> — 跨分类搜索
  /异环清理缓存    — 清理缓存文件
"""
import os
import logging
from typing import Optional

from graci import on_command, plugin_handler, PluginContext
from graci import GracyImage, GracyText

from .config import DATA_DIR, CACHE_DIR, CACHE_MAX_DAYS
from .core.fetcher import clear_cache
from .core.parser import (
    get_character_list, get_character_detail,
    get_weapon_list, get_weapon_detail,
    get_leveling_materials,
    get_redeem_codes, search,
)
from .core.draw import (
    draw_navigation, draw_character_detail, draw_weapon_detail,
    draw_leveling_materials, draw_redeem_codes, draw_search_results,
)

_logger = logging.getLogger("Gracy.NTEGuide")

os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(os.path.join(DATA_DIR, "background"), exist_ok=True)


async def _match_slug(name: str, items: list) -> Optional[dict]:
    """模糊匹配名称，返回匹配项"""
    name = name.strip().lower()
    # 精确匹配
    for item in items:
        if item["name"].lower() == name:
            return item
    # 包含匹配
    for item in items:
        if name in item["name"].lower():
            return item
    # 拼音/部分匹配
    for item in items:
        if any(ch in item["name"] for ch in name if '\u4e00' <= ch <= '\u9fff'):
            return item
    return None


@on_command("/异环", "/异环角色", "/异环武器", "/异环材料",
            "/异环兑换码", "/异环搜索", "/异环清理缓存")
@plugin_handler
async def handle_nte(ctx: PluginContext):
    """异环攻略 — 统一入口"""
    cmd = ctx.command
    raw = ctx.raw_text.strip()

    try:
        # ── /异环 — 导航 ──
        if cmd == "/异环" and not raw.replace("/异环", "").strip():
            img_bytes = await draw_navigation()
            if img_bytes:
                await ctx.send(GracyImage(file_data=img_bytes))
            else:
                await ctx.reply("生成导航图失败")
            return

        # ── /异环角色 <名字> — 角色详情 ──
        if cmd == "/异环角色":
            args = raw[len(cmd):].strip()
            if not args:
                await ctx.reply("用法: /异环角色 <角色名>\n例: /异环角色 薄荷")
                return

            chars = await get_character_list()
            match = await _match_slug(args, chars)
            if not match:
                await ctx.reply(f"未找到角色「{args}」，试试: 薄荷/娜娜莉/白藏/零")
                return

            detail = await get_character_detail(match["slug"])
            if not detail:
                await ctx.reply(f"获取角色「{match['name']}」详情失败")
                return

            img_bytes = await draw_character_detail(detail)
            if img_bytes:
                await ctx.send(GracyImage(file_data=img_bytes))
            else:
                await ctx.reply(f"「{match['name']}」数据解析失败")
            return

        # ── /异环武器 <名字> — 弧盘详情 ──
        if cmd == "/异环武器":
            args = raw[len(cmd):].strip()
            if not args:
                await ctx.reply("用法: /异环武器 <弧盘名>\n例: /异环武器 晴空")
                return

            weaps = await get_weapon_list()
            match = await _match_slug(args, weaps)
            if not match:
                await ctx.reply(f"未找到弧盘「{args}」，试试关键词: 休息日/思考喵/茶花会")
                return

            detail = await get_weapon_detail(match["slug"])
            if not detail:
                await ctx.reply(f"获取弧盘「{match['name']}」详情失败")
                return

            img_bytes = await draw_weapon_detail(detail)
            if img_bytes:
                await ctx.send(GracyImage(file_data=img_bytes))
            else:
                await ctx.reply(f"「{match['name']}」数据解析失败")
            return

        # ── /异环材料 <角色> [起始] [目标] — 升级材料 ──
        if cmd == "/异环材料":
            args = raw[len(cmd):].strip().split()
            if not args:
                await ctx.reply("用法: /异环材料 <角色名> [起始等级] [目标等级]\n例: /异环材料 薄荷\n例: /异环材料 薄荷 1 60")
                return

            char_name = args[0]
            chars = await get_character_list()
            match = await _match_slug(char_name, chars)
            if not match:
                await ctx.reply(f"未找到角色「{char_name}」")
                return

            mats = await get_leveling_materials(match["slug"])
            if mats is None:
                await ctx.reply(f"获取材料数据失败")
                return

            detail = await get_character_detail(match["slug"])
            if detail:
                img_bytes = await draw_leveling_materials(detail, mats)
                if img_bytes:
                    await ctx.send(GracyImage(file_data=img_bytes))
                else:
                    await ctx.reply("生成材料图失败")
            else:
                await ctx.reply("获取角色信息失败")
            return

        # ── /异环兑换码 ──
        if cmd == "/异环兑换码":
            codes = await get_redeem_codes()
            if not codes:
                await ctx.reply("暂未获取到兑换码")
                return

            img_bytes = await draw_redeem_codes(codes)
            if img_bytes:
                await ctx.send(GracyImage(file_data=img_bytes))
            else:
                text = "最新兑换码:\n" + "\n".join(f"  {c['code']}" for c in codes[:10])
                await ctx.reply(text)
            return

        # ── /异环搜索 <关键词> ──
        if cmd == "/异环搜索":
            args = raw[len(cmd):].strip()
            if not args:
                await ctx.reply("用法: /异环搜索 <关键词>\n例: /异环搜索 薄荷")
                return

            results = await search(args)
            img_bytes = await draw_search_results(results)
            if img_bytes:
                await ctx.send(GracyImage(file_data=img_bytes))
            else:
                total = sum(len(v) for v in results.values())
                if total > 0:
                    text = f"找到 {total} 个结果:\n"
                    for cat, items in [("角色", results["characters"]),
                                       ("武器", results["weapons"]),
                                       ("材料", results["materials"])]:
                        if items:
                            text += f"\n[{cat}] " + ", ".join(i["name"] for i in items[:5])
                    await ctx.reply(text)
                else:
                    await ctx.reply("未找到匹配结果")
            return

        # ── /异环清理缓存 ──
        if cmd == "/异环清理缓存":
            from graci import plugin_manager
            cfg = plugin_manager.get_plugin_config("NTE_Guide_Plugin")
            max_days = cfg.get("cache_max_days", 7) if cfg else 7

            deleted, remaining = clear_cache(max_days)
            await ctx.reply(f"清理完成: 已删 {deleted} 个过期缓存, 剩余 {remaining} 个")
            return

    except Exception as e:
        _logger.error(f"命令执行异常 [{cmd}]: {e}", exc_info=True)
        await ctx.reply(f"处理命令时出错: {e}")
