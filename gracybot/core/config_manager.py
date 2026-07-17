import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, TypeVar, Generic

from gracybot.core.tools.paths import get_config_path

CONFIG_FILE_PATH = None


# 配置类型定义
T = TypeVar('T')


def deep_merge_config(base: dict, override: dict) -> dict:
    """递归合并两个配置字典

    规则：
      - override 中已有的键，保留 override 的值（用户设置优先）
      - base 中存在但 override 中不存在的键，从 base 补入
      - 如果某个键在两个 dict 中都是 dict 类型，则递归合并

    Args:
        base: 默认配置字典
        override: 用户当前配置字典

    Returns:
        合并后的新字典
    """
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge_config(result[key], value)
        else:
            result[key] = value
    return result

class ConfigItem(Generic[T]):
    """配置项类，支持类型转换和验证"""
    def __init__(self, key: str, default: T, description: str = '', required: bool = False, 
                 env_var: Optional[str] = None, validate_func=None):
        self.key = key
        self.default = default
        self.description = description
        self.required = required
        self.env_var = env_var or f"GRACY_{key.upper()}"
        self.validate_func = validate_func
        self.value: Optional[T] = None
    
    def validate(self, value: Any) -> bool:
        """验证配置值是否合法"""
        if self.validate_func:
            return self.validate_func(value)
        return True

class ConfigManager:
    """企业级配置管理器，支持环境变量、配置文件和默认值"""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
            cls._instance._config_items = {}
            cls._instance._file_config = {}
            cls._instance._logger = logging.getLogger("Tool.Config")
        return cls._instance
    
    def register_config(self, config_item: ConfigItem) -> None:
        """注册配置项"""
        self._config_items[config_item.key] = config_item
    
    def load(self) -> bool:
        """加载配置，优先级：环境变量 > 配置文件 > 默认值"""
        # 延迟解析路径，确保使用当前 CWD
        global CONFIG_FILE_PATH
        if CONFIG_FILE_PATH is None:
            CONFIG_FILE_PATH = get_config_path()
        try:
            # 加载配置文件
            if os.path.exists(CONFIG_FILE_PATH):
                try:
                    with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
                        self._file_config = json.load(f)
                    self._logger.info(f"✅ 配置文件加载成功: {CONFIG_FILE_PATH}")
                except json.JSONDecodeError as e:
                    self._logger.error(f"❌ 配置文件格式错误: {str(e)}")
                    return False
            else:
                self._logger.warning(f"⚠️ 配置文件不存在: {CONFIG_FILE_PATH}，将使用默认值和环境变量")
            
            # 处理每个配置项
            for key, item in self._config_items.items():
                # 1. 尝试从环境变量获取
                env_value = os.environ.get(item.env_var)
                if env_value is not None:
                    # 根据默认值类型进行转换
                    if isinstance(item.default, bool):
                        item.value = env_value.lower() in ('true', '1', 'yes', 'y')
                    elif isinstance(item.default, int):
                        try:
                            item.value = int(env_value)
                        except ValueError:
                            self._logger.error(f"❌ 环境变量 {item.env_var} 不是有效的整数")
                            item.value = item.default
                    else:
                        item.value = env_value
                    self._logger.debug(f"🔧 从环境变量加载配置 {key}: {item.env_var}")
                # 2. 尝试从配置文件获取
                elif key in self._file_config:
                    item.value = self._file_config[key]
                    self._logger.debug(f"📄 从配置文件加载配置 {key}")
                # 3. 使用默认值
                else:
                    item.value = item.default
                    self._logger.debug(f"📌 使用默认配置 {key}: {item.default}")
                
                # 验证配置
                if not item.validate(item.value):
                    self._logger.error(f"❌ 配置 {key} 的值 {item.value} 无效")
                    if item.required:
                        return False
                    # 无效时回退到默认值
                    item.value = item.default
                
                # 检查必填项
                if item.required and item.value is None:
                    self._logger.error(f"❌ 缺少必填配置 {key}")
                    return False
            
            self._initialized = True
            self._logger.info("✅ 所有配置加载完成")
            return True
        except Exception as e:
            self._logger.error(f"❌ 配置加载异常: {str(e)}", exc_info=True)
            return False
    
    def load_from(self, filepath: str) -> bool:
        """从指定路径加载配置文件，将值合并到已注册的配置项中

        用于适配器独立配置文件，
        只更新已注册的 ConfigItem，不会自动注册新项。

        Args:
            filepath: 配置文件的绝对路径

        Returns:
            加载成功返回 True
        """
        try:
            if not os.path.exists(filepath):
                self._logger.warning(f"⚠️ 配置文件不存在: {filepath}，将使用默认值")
                return False

            with open(filepath, 'r', encoding='utf-8') as f:
                file_data = json.load(f)

            loaded_keys = []
            for key, value in file_data.items():
                item = self._config_items.get(key)
                if item:
                    # 环境变量优先级仍高于文件
                    if item.env_var in os.environ:
                        continue
                    item.value = value
                    loaded_keys.append(key)
                else:
                    self._logger.debug(f"⏭️ 忽略未注册的配置项: {key}（来自 {os.path.basename(filepath)}）")

            self._logger.info(f"✅ 适配器配置加载成功: {filepath}（{len(loaded_keys)} 项）")
            return True
        except json.JSONDecodeError as e:
            self._logger.error(f"❌ 配置文件格式错误: {filepath}: {str(e)}")
            return False
        except Exception as e:
            self._logger.error(f"❌ 配置文件加载异常: {filepath}: {str(e)}", exc_info=True)
            return False

    def save_to_file_at(self, filepath: str, keys: list = None) -> bool:
        """将指定配置项保存到指定文件路径

        Args:
            filepath: 目标文件路径
            keys: 要保存的配置项键列表，None 表示全部

        Returns:
            保存成功返回 True
        """
        try:
            data = {}
            target_keys = keys or list(self._config_items.keys())
            for key in target_keys:
                item = self._config_items.get(key)
                if item and item.value is not None:
                    data[key] = item.value

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            self._logger.info(f"✅ 配置已保存到: {filepath}")
            return True
        except Exception as e:
            self._logger.error(f"❌ 保存配置文件失败: {filepath}: {str(e)}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        if not self._initialized:
            if not self.load():
                return default
        
        item = self._config_items.get(key)
        if item:
            return item.value
        return default
    
    def set(self, key: str, value: Any) -> bool:
        """动态设置配置值"""
        item = self._config_items.get(key)
        if item:
            if item.validate(value):
                item.value = value
                self._logger.info(f"🔄 动态更新配置 {key}: {value}")
                return True
            else:
                self._logger.error(f"❌ 无法设置配置 {key}: 无效值 {value}")
        return False
    
    def missing_in_file(self, *keys) -> list:
        "检查哪些配置项在 config.json 中缺失（用于首次运行引导）"
        if not self._file_config:
            return list(keys)
        return [k for k in keys if k not in self._file_config]

    def save_to_file(self) -> bool:
        """保存当前配置到文件（不包含环境变量覆盖的值）"""
        try:
            # 只保存非环境变量覆盖的配置
            config_to_save = self._file_config.copy()
            for key, item in self._config_items.items():
                if item.env_var not in os.environ and key not in os.environ:
                    config_to_save[key] = item.value
            
            with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as f:
                json.dump(config_to_save, f, ensure_ascii=False, indent=2)
            
            self._logger.info(f"✅ 配置已保存到: {CONFIG_FILE_PATH}")
            return True
        except Exception as e:
            self._logger.error(f"❌ 保存配置文件失败: {str(e)}")
            return False
    
    def generate_default_config(self) -> Dict[str, Any]:
        """生成默认配置字典"""
        default_config = {}
        for key, item in self._config_items.items():
            default_config[key] = {
                'value': item.default,
                'description': item.description,
                'env_var': item.env_var,
                'required': item.required
            }
        return default_config

    def _auto_update_config(self, default_config: dict) -> None:
        """自动同步配置文件：首次创建、补新字段、保留用户值

        每次启动都检查，但只在有变化时写回文件：
          - 首次运行 → 创建默认 config.json
          - 已有文件 → 比对 DEFAULT_CONFIG 结构，补新字段、同步 bot_version

        在打印 Logo/版本号之前完成（由 core.config 导入时触发）。

        Args:
            default_config: 完整默认配置字典（来自 core/config.py 的 DEFAULT_CONFIG）
        """
        # 确保路径已解析
        global CONFIG_FILE_PATH
        if CONFIG_FILE_PATH is None:
            CONFIG_FILE_PATH = get_config_path()

        # ── 1. 首次运行：配置文件不存在 ──
        if not os.path.exists(CONFIG_FILE_PATH):
            self._logger.info("🆕 首次运行，正在创建默认配置文件...")
            first_config = default_config.copy()
            try:
                config_dir = os.path.dirname(CONFIG_FILE_PATH)
                if config_dir:
                    os.makedirs(config_dir, exist_ok=True)
                with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as f:
                    json.dump(first_config, f, ensure_ascii=False, indent=2)
                self._file_config = first_config
                # 立即用新文件内容刷新 ConfigItem 值
                for key, item in self._config_items.items():
                    if key in self._file_config:
                        item.value = self._file_config[key]
                self._logger.warning(f"⚠️ 首次运行！已创建默认配置文件: {CONFIG_FILE_PATH}")
                self._logger.warning("💡 使用 gracy instance add <name> 创建机器人实例")
            except Exception as e:
                self._logger.error(f"❌ 创建默认配置文件失败: {str(e)}", exc_info=True)
            return

        # ── 2. 已有配置文件：加载并比对 ──
        try:
            with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
                current_config = json.load(f)
        except Exception as e:
            self._logger.error(f"❌ 读取配置文件失败: {str(e)}")
            return

        # 合并：默认配置为 base，当前配置为 override（保留用户值）
        merged = deep_merge_config(default_config, current_config)

        # 只保留 default_config 中定义的字段，不写回未知键（防止 config.json 污染）
        merged = {k: v for k, v in merged.items() if k in default_config}

        # bot_version 始终从 DEFAULT_CONFIG 同步
        if "bot_version" in default_config:
            merged["bot_version"] = default_config["bot_version"]

        # 检查是否有实际变化
        if merged == current_config:
            self._file_config = current_config
            return  # 完全一致，无需更新

        # 找出变化（用于日志）
        added = [k for k in merged if k not in current_config]
        changed = [k for k in merged if k in current_config and merged[k] != current_config[k] and k not in added]

        if added:
            self._logger.info(f"🔄 配置更新，新增字段: {added}")
        if changed:
            self._logger.info(f"🔄 配置同步字段: {changed}")

        # 写回文件
        try:
            with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as f:
                json.dump(merged, f, ensure_ascii=False, indent=2)
            self._file_config = merged
            self._logger.info("✅ 配置文件已同步")
        except Exception as e:
            self._logger.error(f"❌ 保存配置文件失败: {str(e)}", exc_info=True)
            self._file_config = current_config  # 回退到原配置

# 创建全局配置管理器实例
config_manager = ConfigManager()
