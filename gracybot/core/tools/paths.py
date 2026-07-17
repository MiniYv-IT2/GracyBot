"""GracyBot 统一路径解析

所有路径从 get_project_root() 派生，不散落各处读环境变量。

优先级:
  1. GRACYBOT_HOME 环境变量（Docker / systemd）
  2. CWD 有 bot.py（本地项目开发）
  3. site-packages 安装目录
  4. CWD

用法:
    from gracybot.core.tools.paths import get_plugins_dir, get_config_path
"""

import os
import functools

_ROOT_ENV_VAR = "GRACYBOT_HOME"


@functools.lru_cache(maxsize=1)
def get_project_root() -> str:
    if root := os.environ.get(_ROOT_ENV_VAR):
        return os.path.realpath(root)

    cwd = os.getcwd()
    if os.path.exists(os.path.join(cwd, "bot.py")):
        return os.path.realpath(cwd)

    return os.path.realpath(cwd)


@functools.lru_cache(maxsize=1)
def get_storage_dir() -> str:
    return os.path.join(get_project_root(), "storage")


@functools.lru_cache(maxsize=1)
def get_plugins_dir() -> str:
    return os.path.join(get_project_root(), "gracybot", "plugins")


@functools.lru_cache(maxsize=1)
def get_instances_dir() -> str:
    return os.path.join(get_storage_dir(), "instances")


@functools.lru_cache(maxsize=1)
def get_config_path() -> str:
    return os.path.join(get_storage_dir(), "config.json")


@functools.lru_cache(maxsize=1)
def get_disabled_plugins_path() -> str:
    return os.path.join(get_storage_dir(), ".gracybot_disabled.json")


@functools.lru_cache(maxsize=1)
def get_res_config_dir() -> str:
    return os.path.join(get_storage_dir(), "config")


@functools.lru_cache(maxsize=1)
def get_logs_dir() -> str:
    return os.path.join(get_storage_dir(), "logs")


def invalidate_cache() -> None:
    get_project_root.cache_clear()
    get_storage_dir.cache_clear()
    get_plugins_dir.cache_clear()
    get_instances_dir.cache_clear()
    get_config_path.cache_clear()
    get_disabled_plugins_path.cache_clear()
    get_res_config_dir.cache_clear()
    get_logs_dir.cache_clear()
