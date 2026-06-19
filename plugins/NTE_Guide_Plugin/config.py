"""
异环攻略插件 - 配置文件
"""
import os

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(PLUGIN_DIR, "data")
CACHE_DIR = os.path.join(DATA_DIR, "cache")
BG_DIR = os.path.join(DATA_DIR, "background")

# 缓存过期时间（秒）
CACHE_EXPIRE = {
    "character_list": 86400,    # 角色列表 24h
    "character_detail": 86400,  # 角色详情 24h
    "weapon_list": 86400,       # 武器列表 24h
    "weapon_detail": 86400,     # 武器详情 24h
    "material_list": 86400,     # 材料列表 24h
    "redeem_codes": 3600,       # 兑换码 1h
}

# 缓存清理默认天数
CACHE_MAX_DAYS = 7

# 数据源
BASE_URL = "https://nteguide.com/zh"

# 角色属性映射（英→中）
ATTR_MAP = {
    "anima": "生命",
    "cosmos": "宇宙",
    "incantation": "咒术",
    "psyche": "灵魂",
    "chaos": "混沌",
    "lakshana": "相",
    "anima属性": "生命",
    "cosmos属性": "宇宙",
    "incantation属性": "咒术",
    "psyche属性": "灵魂",
    "chaos属性": "混沌",
    "lakshana属性": "相",
    "生命": "生命",
    "宇宙": "宇宙",
    "咒术": "咒术",
    "灵魂": "灵魂",
    "混沌": "混沌",
    "相": "相",
}

# 稀有度映射
RARITY_MAP = {
    "S": "S",
    "A": "A",
    "B": "B",
    "S-Rank": "S",
    "A-Rank": "A",
    "B-Rank": "B",
}

# Slug → 中文名映射（用于配队显示）
SLUG_NAME_MAP = {
    "nanally": "娜娜莉",
    "sakiri": "咲里",
    "fadia": "法蒂亚",
    "lacrimosa": "安魂曲",
    "baicang": "白藏",
    "zero-male": "零(男)",
    "zero-female": "零(女)",
    "hotori": "穗鸟",
    "daffodil": "达芙迪尔",
    "jiuyuan": "九原",
    "haniel": "哈尼尔",
    "adler": "阿德勒",
    "skia": "翳",
    "edgar": "埃德加",
    "mint": "薄荷",
    "hathor": "哈索尔",
    "chiz": "赤子",
    "aurelia": "奥蕾莉亚",
    "xun": "浔",
    "chaos": "卡厄斯",
    "crow": "库洛",
    "nelly": "奈莉",
    "nanally": "娜娜莉",
    "sakiri": "纱希",
    "zero-male": "零",
    "hotori": "穗鸟",
}
