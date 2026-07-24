import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, TypeVar, Generic

from gracybot.core.tools.paths import get_config_path, get_plugin_config_global_dir, get_plugin_config_instance_dir, get_plugins_dir, get_user_plugins_dir

CONFIG_FILE_PATH = None



T = TypeVar('T')


def deep_merge_config(base: dict, override: dict) -> dict:














    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge_config(result[key], value)
        else:
            result[key] = value
    return result

class ConfigItem(Generic[T]):

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

        if self.validate_func:
            return self.validate_func(value)
        return True

class ConfigManager:

    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
            cls._instance._config_items = {}
            cls._instance._file_config = {}
            cls._instance._plugin_schemas: dict[str, dict] = {}
            cls._instance._plugin_config_cache: dict[str, tuple[dict, float]] = {}
            cls._instance._logger = logging.getLogger("Tool.Config")
        return cls._instance
    
    def register_config(self, config_item: ConfigItem) -> None:

        self._config_items[config_item.key] = config_item
    
    def load(self) -> bool:


        global CONFIG_FILE_PATH
        if CONFIG_FILE_PATH is None:
            CONFIG_FILE_PATH = get_config_path()
        try:

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
            

            for key, item in self._config_items.items():

                env_value = os.environ.get(item.env_var)
                if env_value is not None:

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

                elif key in self._file_config:
                    item.value = self._file_config[key]
                    self._logger.debug(f"📄 从配置文件加载配置 {key}")

                else:
                    item.value = item.default
                    self._logger.debug(f"📌 使用默认配置 {key}: {item.default}")
                

                if not item.validate(item.value):
                    self._logger.error(f"❌ 配置 {key} 的值 {item.value} 无效")
                    if item.required:
                        return False

                    item.value = item.default
                

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

        if not self._initialized:
            if not self.load():
                return default
        
        item = self._config_items.get(key)
        if item:
            return item.value
        return default
    
    def set(self, key: str, value: Any) -> bool:

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

        try:

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












        global CONFIG_FILE_PATH
        if CONFIG_FILE_PATH is None:
            CONFIG_FILE_PATH = get_config_path()


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

                for key, item in self._config_items.items():
                    if key in self._file_config:
                        item.value = self._file_config[key]
                self._logger.warning(f"⚠️ 首次运行！已创建默认配置文件: {CONFIG_FILE_PATH}")
                self._logger.warning("💡 使用 gracy instance add <name> 创建机器人实例")
            except Exception as e:
                self._logger.error(f"❌ 创建默认配置文件失败: {str(e)}", exc_info=True)
            return


        try:
            with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
                current_config = json.load(f)
        except Exception as e:
            self._logger.error(f"❌ 读取配置文件失败: {str(e)}")
            return


        merged = deep_merge_config(default_config, current_config)


        merged = {k: v for k, v in merged.items() if k in default_config}


        if "bot_version" in default_config:
            merged["bot_version"] = default_config["bot_version"]


        if merged == current_config:
            self._file_config = current_config
            return


        added = [k for k in merged if k not in current_config]
        changed = [k for k in merged if k in current_config and merged[k] != current_config[k] and k not in added]

        if added:
            self._logger.info(f"🔄 配置更新，新增字段: {added}")
        if changed:
            self._logger.info(f"🔄 配置同步字段: {changed}")


        try:
            with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as f:
                json.dump(merged, f, ensure_ascii=False, indent=2)
            self._file_config = merged
            self._logger.info("✅ 配置文件已同步")
        except Exception as e:
            self._logger.error(f"❌ 保存配置文件失败: {str(e)}", exc_info=True)
            self._file_config = current_config


    # ── 插件配置管理 ──────────────────────────────────────────

    def register_plugin_config(self, plugin_name: str, schema: dict | None = None) -> dict:
        """注册插件配置，返回配置字典

        Args:
            plugin_name: 插件名
            schema: 可选。不传时自动查找 {plugin_dir}/plugin_conf.json 作为 schema
        """
        if schema is None:
            schema = self._try_load_schema_file(plugin_name)
        self._plugin_schemas[plugin_name] = schema
        config = self._load_plugin_config(plugin_name)
        self._plugin_config_cache[plugin_name] = (config, 0)
        return config

    def _try_load_schema_file(self, plugin_name: str) -> dict:
        for base in (get_plugins_dir(), get_user_plugins_dir()):
            path = os.path.join(base, plugin_name, "plugin_conf.json")
            if os.path.exists(path):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except Exception:
                    pass
        return {}

    def _get_plugin_global_file(self, plugin_name: str) -> str:
        return os.path.join(get_plugin_config_global_dir(), plugin_name, "config.json")

    def _get_plugin_instance_file(self, plugin_name: str, instance_name: str) -> str:
        return os.path.join(get_plugin_config_instance_dir(instance_name), plugin_name, "config.json")

    def _schema_defaults(self, schema: dict) -> dict:
        result = {}
        for key, info in schema.items():
            if info.get("type") == "object" and "items" in info:
                result[key] = self._schema_defaults(info["items"])
            else:
                result[key] = info.get("default", None)
        return result

    def _load_json_file(self, filepath: str) -> dict:
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _get_runtime_instance_name(self) -> Optional[str]:
        try:
            from gracybot.core.runtime import RuntimeContext
            runtime = RuntimeContext.get()
            if runtime:
                return runtime.instance_name
        except Exception:
            pass
        return None

    def _load_plugin_config(self, plugin_name: str, instance_name: Optional[str] = None) -> dict:
        schema = self._plugin_schemas.get(plugin_name, {})
        config = self._schema_defaults(schema)

        global_file = self._get_plugin_global_file(plugin_name)
        global_data = self._load_json_file(global_file)
        merged_global = deep_merge_config(self._schema_defaults(schema), global_data)
        if merged_global != global_data:
            os.makedirs(os.path.dirname(global_file), exist_ok=True)
            try:
                with open(global_file, 'w', encoding='utf-8') as f:
                    json.dump(merged_global, f, ensure_ascii=False, indent=2)
                added = [k for k in merged_global if k not in global_data]
                if added:
                    self._logger.info(f"🔁 插件 {plugin_name} 配置自动迁移，新增字段: {added}")
            except Exception:
                pass
            global_data = merged_global

        config = deep_merge_config(config, merged_global)

        inst_name = instance_name or self._get_runtime_instance_name()
        if inst_name:
            instance_file = self._get_plugin_instance_file(plugin_name, inst_name)
            instance_data = self._load_json_file(instance_file)
            if instance_data:
                merged_inst = deep_merge_config(self._schema_defaults(schema), instance_data)
                if merged_inst != instance_data:
                    os.makedirs(os.path.dirname(instance_file), exist_ok=True)
                    try:
                        with open(instance_file, 'w', encoding='utf-8') as f:
                            json.dump(merged_inst, f, ensure_ascii=False, indent=2)
                    except Exception:
                        pass
                    instance_data = merged_inst
                config = deep_merge_config(config, instance_data)

        return config

    def get_plugin(self, plugin_name: str, key: Optional[str] = None, default: Any = None) -> Any:
        """获取插件配置

        Args:
            plugin_name: 插件名
            key: 配置键名（None 时返回整个配置字典）
            default: key 不存在时的默认值
        """
        schema = self._plugin_schemas.get(plugin_name)
        if schema is None:
            return default if key else {}

        cached = self._plugin_config_cache.get(plugin_name)
        config = cached[0] if cached else self._load_plugin_config(plugin_name)
        if not cached:
            self._plugin_config_cache[plugin_name] = (config, 0)

        if key is None:
            return config
        return config.get(key, default)

    def update_plugin(self, plugin_name: str, updates: dict, instance_name: Optional[str] = None) -> bool:
        """更新插件配置（写入对应层级文件）

        有 instance_name（或当前运行时上下文）→ 写入实例级
        无 → 写入全局
        """
        inst_name = instance_name or self._get_runtime_instance_name()
        if inst_name:
            filepath = self._get_plugin_instance_file(plugin_name, inst_name)
        else:
            filepath = self._get_plugin_global_file(plugin_name)

        existing = self._load_json_file(filepath)
        merged = deep_merge_config(existing, updates)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(merged, f, ensure_ascii=False, indent=2)
            self._logger.info(f"✅ 插件配置已更新: {filepath}")
            if plugin_name in self._plugin_config_cache:
                del self._plugin_config_cache[plugin_name]
            return True
        except Exception as e:
            self._logger.error(f"❌ 保存插件配置失败: {filepath}: {e}")
            return False


config_manager = ConfigManager()
