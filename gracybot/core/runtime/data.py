"""数据路径工具与深度合并

提供全局资源路径、账号独立路径、配置深度合并工具。
"""

import os
import logging
from typing import Dict, Any

from .runtime import Runtime

_logger = logging.getLogger("Core.Data")


def get_global_path(plugin_name: str, *segments: str) -> str:
    """获取插件全局资源路径

    所有账号共用同一份，适合放 API 密钥、通用模板、静态图片等。
    路径: data/<plugin_name>/[...]

    Args:
        plugin_name: 插件名称（与插件目录名一致）
        *segments: 路径片段，如 "api_keys.json"

    Returns:
        绝对路径字符串
    """
    return os.path.join("data", plugin_name, *segments)


def get_instance_path(runtime: Runtime, plugin_name: str, *segments: str) -> str:
    """获取当前 Runtime 的插件独立数据路径

    每个账号独享，适合放开关配置、倍率、签到次数、对话历史等。
    路径: storage/instances/<name>/data/<plugin_name>/[...]

    Args:
        runtime: 当前 Runtime 实例
        plugin_name: 插件名称
        *segments: 路径片段，如 "config.json"

    Returns:
        相对路径字符串（基于项目根目录）
    """
    return os.path.join(
        "res", "instances",
        runtime.instance_name,
        "data",
        plugin_name,
        *segments,
    )


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """递归深度合并两个字典

    以 base 为基底，override 覆盖其上。override 中有而 base 中没有的键直接追加。
    用于插件配置合并：default_config（基底）← global_config ← instance_config。

    Args:
        base: 基底字典（默认配置）
        override: 覆盖字典（用户配置/账号配置）

    Returns:
        合并后的新字典
    """
    result = base.copy()
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = deep_merge(result[key], val)
        else:
            result[key] = val
    return result


def ensure_instance_data_dir(runtime: Runtime, plugin_name: str) -> str:
    """确保账号独立数据目录存在，返回目录路径

    在 storage/instances/<name>/data/<plugin_name>/ 下创建目录。
    """
    dir_path = get_instance_path(runtime, plugin_name)
    os.makedirs(dir_path, exist_ok=True)
    return dir_path


def ensure_global_data_dir(plugin_name: str) -> str:
    """确保全局数据目录存在，返回目录路径"""
    dir_path = get_global_path(plugin_name)
    os.makedirs(dir_path, exist_ok=True)
    return dir_path


def load_instance_config(
    runtime: Runtime,
    plugin_name: str,
    default_config: Dict[str, Any],
    filename: str = "config.json",
) -> Dict[str, Any]:
    """加载账号独立配置，缺失字段自动补默认值

    1. 读取 storage/instances/<name>/data/<plugin_name>/<filename>
    2. 如果文件不存在，创建并写入 default_config
    3. 如果文件存在但有缺失字段，deep_merge 补全后回写

    Args:
        runtime: 当前 Runtime
        plugin_name: 插件名称
        default_config: 插件定义的默认配置字典
        filename: 配置文件名，默认 "config.json"

    Returns:
        合并后的完整配置字典
    """
    import json

    cfg_dir = ensure_instance_data_dir(runtime, plugin_name)
    cfg_path = os.path.join(cfg_dir, filename)

    # 文件不存在 → 创建默认
    if not os.path.exists(cfg_path):
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(default_config, f, ensure_ascii=False, indent=2)
        _logger.info(
            f"{runtime.log_tag} 已创建默认配置: "
            f"{os.path.relpath(cfg_path)}"
        )
        return dict(default_config)

    # 文件存在 → 读取并合并
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            user_config = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        _logger.error(f"{runtime.log_tag} 配置读取失败 {cfg_path}: {e}")
        return dict(default_config)

    merged = deep_merge(default_config, user_config)

    # 如果有新增字段，回写磁盘
    if set(merged.keys()) != set(user_config.keys()):
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)
        _logger.info(
            f"{runtime.log_tag} 配置已自动合并新增字段: "
            f"{os.path.relpath(cfg_path)}"
        )

    return merged
