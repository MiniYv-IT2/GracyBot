"""GracyBot 插件管理器 — 负责扫描、加载、注册、匹配、重载"""

import os
import json
import shutil
import importlib.util
from typing import Dict, List, Callable, Optional, Set, Tuple
import re
from gracybot.core.utils import logger
from gracybot.core.tools.validator import load_plugin_toml, TOMLPluginError
from gracybot.core.tools.paths import get_disabled_plugins_path, get_res_config_dir, get_project_root
from gracybot.core.decorators.registration import (
    DECORATOR_COMMAND_REGISTRY,
    FALLBACK_HANDLERS,
    _register_decorated_function,
    _register_fallback_function,
    clear_registry,
)


class PluginManager:
    """插件管理器单例 — 扫描、加载、注册、匹配、重载、禁用"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self._initialized = False
        self._plugin_configs: Dict[str, dict] = {}
        self._registry: List[Dict] = []
        self._versions: Dict[str, str] = {}
        self._dep_graph: Dict[str, List[str]] = {}
        self._ready_hooks: List[Callable] = []
        self._visited: Set[str] = set()

    # ── 属性访问器（供外部只读访问） ──

    @property
    def registry(self) -> List[Dict]:
        """已注册插件的完整列表"""
        return self._registry

    @property
    def versions(self) -> Dict[str, str]:
        """已加载插件的版本号映射"""
        return self._versions

    # ── 版本工具 ──

    def parse_version(self, version: str) -> List[int]:
        """解析版本号字符串为整数列表"""
        try:
            parts = re.findall(r'\d+', version)
            return [int(part) for part in parts]
        except Exception:
            return [0]

    def compare_versions(self, version1: str, version2: str) -> int:
        """版本号比较：1=v1>v2, 0=相等, -1=v1<v2"""
        v1 = self.parse_version(version1)
        v2 = self.parse_version(version2)
        max_len = max(len(v1), len(v2))
        v1 += [0] * (max_len - len(v1))
        v2 += [0] * (max_len - len(v2))
        for i in range(max_len):
            if v1[i] > v2[i]:
                return 1
            elif v1[i] < v2[i]:
                return -1
        return 0

    # ── 禁用列表 ──

    @staticmethod
    def _get_disabled_file() -> str:
        return get_disabled_plugins_path()

    def load_disabled_plugins(self) -> Set[str]:
        """从 JSON 加载已禁用插件名称集合"""
        path = self._get_disabled_file()
        try:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return set(data.get("disabled", []))
        except Exception:
            pass
        return set()

    def save_disabled_plugins(self, disabled: Set[str]) -> None:
        """保存禁用插件集合到 JSON"""
        path = self._get_disabled_file()
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump({"disabled": sorted(disabled)}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"❌ 保存禁用列表失败: {e}")

    # ── on_ready 钩子 ──

    def register_on_ready(self, hook: Callable) -> None:
        """注册 on_ready 钩子，框架初始化后统一调用"""
        self._ready_hooks.append(hook)

    def trigger_on_ready(self) -> None:
        """触发所有 on_ready 钩子"""
        for hook in self._ready_hooks:
            try:
                hook()
            except Exception as e:
                logger.error(f"❌ on_ready 钩子执行失败: {e}")

    # ── 循环依赖检测 ──

    def check_circular_dependency(self, plugin_name: str, visited: Set[str], path: List[str]) -> bool:
        """DFS 检测循环依赖"""
        visited.add(plugin_name)
        path.append(plugin_name)
        if plugin_name in self._dep_graph:
            for dep in self._dep_graph[plugin_name]:
                if dep not in visited:
                    if self.check_circular_dependency(dep, visited, path):
                        return True
                elif dep in path:
                    cycle_start = path.index(dep)
                    cycle = " -> ".join(path[cycle_start:]) + " -> " + dep
                    logger.error(f"❌ 检测到循环依赖: {cycle}")
                    return True
        path.pop()
        return False

    def check_plugin_dependencies(self, plugin_name: str, dependencies: List[Dict]) -> Tuple[bool, str]:
        """检查插件依赖是否满足版本要求"""
        if not dependencies:
            return True, ""
        for dep in dependencies:
            dep_name = dep.get('name')
            min_ver = dep.get('min_version', '0.0.0')
            max_ver = dep.get('max_version')
            if dep_name not in self._versions:
                return False, f"依赖插件 '{dep_name}' 未加载"
            loaded_ver = self._versions[dep_name]
            if self.compare_versions(loaded_ver, min_ver) < 0:
                return False, f"依赖插件 '{dep_name}' 版本过低，需要 >= {min_ver}，当前 {loaded_ver}"
            if max_ver and self.compare_versions(loaded_ver, max_ver) > 0:
                return False, f"依赖插件 '{dep_name}' 版本过高，需要 <= {max_ver}，当前 {loaded_ver}"
        return True, ""

    # ── 初始化入口 ──

    def init(self, plugin_dir: str = "./plugins") -> None:
        """初始化：扫描 → 加载 → 合并装饰器
        元数据来自 metadata.toml（主通道）+ @on_command 装饰器（副通道）
        """
        if self._initialized:
            logger.warning("⚠️ 插件管理器已初始化，无需重复调用")
            return
        self._registry.clear()
        self._versions.clear()
        self._dep_graph.clear()
        self._ready_hooks.clear()
        clear_registry()

        abs_plugin_dir = os.path.abspath(plugin_dir)
        logger.info(f"📌 开始扫描插件目录（绝对路径）：{abs_plugin_dir}")

        # 第一阶段：扫描 metadata
        plugins_meta = self._scan_plugins_metadata(plugin_dir)

        # 循环依赖检测
        self._visited.clear()
        for pname in self._dep_graph:
            if pname not in self._visited:
                if self.check_circular_dependency(pname, set(), []):
                    logger.error("❌ 检测到循环依赖，初始化失败！")
                    return

        # 第二阶段：按依赖顺序加载
        self._load_plugins_by_dependency(plugins_meta, plugin_dir)

        # 第三阶段：合并装饰器注册 + 按 priority 排序
        self._merge_decorator_registry()
        self._registry.sort(key=lambda p: p.get("priority", 50), reverse=True)

        self._initialized = True
        from gracybot.core.logger_manager import logger_manager
        import logging
        logger_manager.log_with_context(logger, logging.INFO, f"\n✅ 插件管理器初始化完成！")
        logger_manager.log_with_context(logger, logging.INFO, f"📊 共注册成功 {len(self._registry)} 个插件：")
        for idx, plugin in enumerate(self._registry, 1):
            show_cmds = plugin['commands'][:3] + ["..."] if len(plugin['commands']) > 3 else plugin['commands']
            ver_info = f" | 版本：{plugin.get('version', '未指定')}"
            pri_info = f" | 优先级：{plugin.get('priority', 50)}"
            logger_manager.log_with_context(logger, logging.INFO, f"   {idx}. {plugin['name']}{ver_info}{pri_info} | 指令：{show_cmds}")

    # ── 第一阶段：扫描元信息 ──

    def _scan_plugins_metadata(self, plugin_dir: str) -> Dict[str, Dict]:
        """扫描所有插件的 metadata.toml，返回 {name: meta}"""
        plugins_meta = {}
        if not os.path.exists(plugin_dir):
            logger.error(f"❌ 插件目录 {plugin_dir} 不存在，跳过插件加载")
            return plugins_meta

        disabled_set = self.load_disabled_plugins()
        if disabled_set:
            logger.info(f"🚫 已禁用插件: {', '.join(sorted(disabled_set))}")

        for plugin_name in os.listdir(plugin_dir):
            if plugin_name in disabled_set:
                logger.debug(f"🚫 插件 {plugin_name} 已被禁用，跳过加载")
                continue
            plugin_path = os.path.join(plugin_dir, plugin_name)
            if not os.path.isdir(plugin_path):
                continue
            toml_path = os.path.join(plugin_path, "metadata.toml")
            if not os.path.exists(toml_path):
                logger.warning(f"❌ 插件 {plugin_name} 缺少 metadata.toml，跳过加载")
                continue
            try:
                meta = load_plugin_toml(toml_path, plugin_path)
                meta["plugin_path"] = plugin_path
                deps = meta.get("dependencies", [])
                self._dep_graph[plugin_name] = [d["name"] for d in deps] if deps else []
                plugins_meta[plugin_name] = meta
                logger.debug(f"🔍 [TOML] 成功读取插件 {plugin_name} v{meta['version']} priority={meta['priority']}")
            except TOMLPluginError as e:
                logger.error(f"❌ {e}")
            except Exception as e:
                logger.error(f"❌ 插件 {plugin_name} metadata.toml 加载异常: {e}", exc_info=True)
        return plugins_meta

    # ── 第二阶段：按依赖顺序加载 ──

    def _load_plugins_by_dependency(self, plugins_meta: Dict[str, Dict], plugin_dir: str) -> None:
        """按依赖顺序加载每个插件的核心模块"""
        loaded = set()

        def load_plugin(plugin_name: str) -> bool:
            if plugin_name in loaded:
                return True
            if plugin_name not in plugins_meta:
                logger.error(f"❌ 依赖插件 '{plugin_name}' 不存在")
                return False
            meta = plugins_meta[plugin_name]
            for dep in meta.get("dependencies", []):
                if dep["name"] not in loaded:
                    if not load_plugin(dep["name"]):
                        return False
            ok, err = self.check_plugin_dependencies(plugin_name, meta.get("dependencies", []))
            if not ok:
                logger.error(f"❌ 插件 '{plugin_name}' 依赖检查失败: {err}")
                return False
            try:
                plugin_path = meta["plugin_path"]
                core_file = f"{plugin_name}.py"
                core_path = os.path.join(plugin_path, core_file)
                if not os.path.exists(core_path):
                    logger.error(f"❌ 插件 {plugin_name} 缺失核心文件 {core_file}，跳过加载")
                    return False
                mod_name = f"gracybot.plugins.{plugin_name}.{core_file[:-3]}"
                spec = importlib.util.spec_from_file_location(name=mod_name, location=core_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                handler_name = meta["handler"]
                if not hasattr(module, handler_name):
                    logger.error(f"❌ 插件 {plugin_name} 中缺失处理函数 {handler_name}，跳过加载")
                    return False
                handler_func = getattr(module, handler_name)
                if not callable(handler_func):
                    logger.error(f"❌ 插件 {plugin_name} 中 {handler_name} 不可调用，跳过加载")
                    return False

                # 扫描装饰器
                pname = meta.get("name", plugin_name)
                for attr_name in dir(module):
                    attr_val = getattr(module, attr_name)
                    if callable(attr_val) and hasattr(attr_val, "_gracy_on_command"):
                        _register_decorated_function(
                            attr_val,
                            plugin_name=pname,
                            permission=meta.get("permission", "all"),
                            chat_type=meta.get("chat_type", ["private", "group"]),
                            is_at_required=meta.get("is_at_required", False),
                        )
                        logger.debug(f"🔍 [装饰器] 插件 {pname} 注册命令: {attr_val._gracy_on_command}")
                    if callable(attr_val) and hasattr(attr_val, "_gracy_fallback"):
                        _register_fallback_function(
                            attr_val,
                            plugin_name=pname,
                            chat_type=meta.get("chat_type", ["private", "group"]),
                        )
                        logger.debug(f"🔍 [装饰器] 插件 {pname} 注册兜底处理器")

                self._registry.append({
                    **meta,
                    "handler_func": handler_func,
                    "core_module": module,
                })
                self._versions[plugin_name] = meta["version"]
                loaded.add(plugin_name)
                self._init_plugin_config(plugin_name, plugin_path)
                logger.debug(f"✅ 插件 {plugin_name} (v{meta['version']}) 注册成功！")
                if meta.get("dependencies"):
                    dep_info = ", ".join(f"{d['name']} (>= {d.get('min_version', '0.0.0')})" for d in meta["dependencies"])
                    logger.debug(f"   依赖: {dep_info}")
                return True
            except Exception as e:
                logger.error(f"❌ 加载插件 {plugin_name} 异常: {e}", exc_info=True)
                return False

        for pname in plugins_meta:
            if pname not in loaded:
                load_plugin(pname)

    # ── 第三阶段：合并装饰器注册 ──

    def _merge_decorator_registry(self) -> None:
        """将 DECORATOR_COMMAND_REGISTRY 合并到 self._registry"""
        existing_names = {p["name"] for p in self._registry}
        for entry in DECORATOR_COMMAND_REGISTRY:
            pname = entry.get("plugin_name", "unknown")
            if pname in existing_names:
                for p in self._registry:
                    if p["name"] == pname:
                        for cmd in entry.get("commands", []):
                            if cmd not in p["commands"]:
                                p["commands"].append(cmd)
                            p.setdefault("command_handlers", {})[cmd] = entry["handler_func"]
                        break
            else:
                merged = {
                    "name": pname,
                    "version": "0.0.0",
                    "author": "",
                    "description": "",
                    "priority": 50,
                    "commands": entry.get("commands", []),
                    "handler_func": entry["handler_func"],
                    "chat_type": entry.get("chat_type", ["private", "group"]),
                    "permission": entry.get("permission", "all"),
                    "is_at_required": entry.get("is_at_required", False),
                    "plugin_path": "",
                    "from_decorator": True,
                }
                self._registry.append(merged)
                self._versions[pname] = merged["version"]
                existing_names.add(pname)
                logger.debug(f"🔍 [装饰器] 纯装饰器插件: {pname} 命令: {merged['commands']}")

    # ── 指令匹配（供 Pipeline 调用） ──

    def get_matched_plugin(self, raw_msg: str, chat_type: str, sender_id: str, is_at_bot: bool,
                           master_id: str = "") -> Optional[Dict]:
        """串行匹配（备用/兼容路径，新 Pipeline 用并行匹配）"""
        master_check = str(master_id) if master_id else ""
        for plugin in self._registry:
            if chat_type not in plugin["chat_type"]:
                continue
            if plugin["permission"] == "master":
                if not master_check or str(sender_id) != master_check:
                    continue
            if chat_type == "group" and plugin.get("is_at_required", False) and not is_at_bot:
                continue
            matched_cmd = None
            for cmd in plugin["commands"]:
                if cmd == "//":
                    if re.search(r'(?:^|\s)//', raw_msg):
                        matched_cmd = cmd
                        break
                elif cmd in raw_msg:
                    matched_cmd = cmd
                    break
            if matched_cmd:
                return plugin
        return None

    # ── 查询 ──

    def get_plugin_metadata(self, plugin_name: str) -> Optional[Dict]:
        """获取指定插件的元信息"""
        for p in self._registry:
            if p.get('name') == plugin_name:
                return {
                    "name": p.get("name"),
                    "version": p.get("version"),
                    "author": p.get("author"),
                    "description": p.get("description"),
                    "priority": p.get("priority", 50),
                    "commands": p.get("commands"),
                    "chat_type": p.get("chat_type"),
                    "permission": p.get("permission"),
                    "is_at_required": p.get("is_at_required", False),
                    "icon_path": p.get("icon_path"),
                    "dependencies": p.get("dependencies", []),
                    "plugin_path": p.get("plugin_path", ""),
                }
        return None

    def get_all_plugins_metadata(self) -> List[Dict]:
        """获取所有已加载插件的元信息列表"""
        return [self.get_plugin_metadata(p['name']) for p in self._registry]

    def find_plugin_by_command(self, command: str) -> Optional[Dict]:
        """根据指令查找所属插件"""
        for p in self._registry:
            if command in p.get("commands", []):
                return p
        return None

    def get_plugin_count(self) -> int:
        """获取已注册插件总数"""
        return len(self._registry)

    def is_plugin_loaded(self, plugin_name: str) -> bool:
        """检查插件是否已加载"""
        return plugin_name in self._versions

    # ── 重载 ──

    def reload_plugin(self, plugin_name: str) -> bool:
        """重载指定插件（全量重扫）"""
        plugin_path = None
        for p in self._registry:
            if p.get('name') == plugin_name:
                plugin_path = p.get('plugin_path')
                break
        if not plugin_path:
            logger.error(f"❌ 未找到插件 {plugin_name}")
            return False
        try:
            self._registry[:] = [p for p in self._registry if p.get('name') != plugin_name]
            self._versions.pop(plugin_name, None)
            logger.info(f"🔄 开始重载插件 {plugin_name}")
            self._initialized = False
            self.init(os.path.dirname(plugin_path))
            logger.info(f"✅ 插件 {plugin_name} 重载完成")
            return True
        except Exception as e:
            logger.error(f"❌ 重载插件 {plugin_name} 异常: {e}", exc_info=True)
            return False

    # ── 配置初始化 ──

    def _init_plugin_config(self, plugin_name: str, plugin_path: str) -> dict:
        """初始化插件配置（config.py + config.json）

        配置优先级（后加载覆盖前）：
            1. DEFAULT_CONFIG（插件内默认值）
            2. storage/config/<plugin>_config.json（全局用户配置）
        使用 deep_merge 递归合并，新增字段自动补默认值。
        """
        config_py_path = os.path.join(plugin_path, "config.py")
        if not os.path.exists(config_py_path):
            self._plugin_configs[plugin_name] = {}
            return {}
        try:
            mod_name = f"gracybot.plugins.{plugin_name}.config"
            spec = importlib.util.spec_from_file_location(name=mod_name, location=config_py_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            default = getattr(mod, "DEFAULT_CONFIG", None)
            if default is None or not isinstance(default, dict):
                self._plugin_configs[plugin_name] = {}
                return {}
            from gracybot.core.runtime import deep_merge

            plugin_cfg_json = os.path.join(plugin_path, "config.json")
            if not os.path.exists(plugin_cfg_json):
                with open(plugin_cfg_json, "w", encoding="utf-8") as f:
                    json.dump(default, f, ensure_ascii=False, indent=2)

            # 全局用户配置（storage/config/）
            res_dir = self._get_res_config_dir()
            if res_dir:
                res_cfg = os.path.join(res_dir, f"{plugin_name}_config.json")
                if os.path.exists(res_cfg):
                    with open(res_cfg, "r", encoding="utf-8") as f:
                        user_cfg = json.load(f)
                else:
                    # 迁移：从旧路径 res/config/ 复制
                    old_cfg = os.path.join(get_project_root(), "res", "config", f"{plugin_name}_config.json")
                    if os.path.exists(old_cfg):
                        os.makedirs(res_dir, exist_ok=True)
                        shutil.copy2(old_cfg, res_cfg)
                        with open(res_cfg, "r", encoding="utf-8") as f:
                            user_cfg = json.load(f)
                    else:
                        user_cfg = None

                if user_cfg is not None:
                    # deep_merge: default 做基底，user_cfg 覆盖其上，新增字段自动补默认值
                    merged = deep_merge(default, user_cfg)
                    # 写回磁盘，补齐新增字段
                    with open(res_cfg, "w", encoding="utf-8") as f:
                        json.dump(merged, f, ensure_ascii=False, indent=2)
                    self._plugin_configs[plugin_name] = merged
                else:
                    os.makedirs(res_dir, exist_ok=True)
                    with open(res_cfg, "w", encoding="utf-8") as f:
                        json.dump(default, f, ensure_ascii=False, indent=2)
                    self._plugin_configs[plugin_name] = dict(default)
            else:
                self._plugin_configs[plugin_name] = dict(default)
            return self._plugin_configs[plugin_name]
        except Exception as e:
            logger.error(f"❌ 插件 {plugin_name} 配置初始化失败: {e}")
            self._plugin_configs[plugin_name] = {}
            return {}

    def shutdown(self):
        """关闭插件管理器，清理资源"""
        logger.info("🔒 开始关闭插件管理器")
        for plugin in self._registry:
            core_module = plugin.get('core_module')
            if core_module and hasattr(core_module, 'on_shutdown'):
                func = getattr(core_module, 'on_shutdown')
                if callable(func):
                    try:
                        func()
                    except Exception as e:
                        logger.error(f"调用插件 {plugin.get('name', '?')} on_shutdown 时出错: {e}")
        self._registry.clear()
        self._versions.clear()
        self._dep_graph.clear()
        self._ready_hooks.clear()
        self._plugin_configs.clear()
        self._initialized = False
        logger.info("✅ 插件管理器已关闭")

    def get_plugin_config(self, plugin_name: str) -> dict:
        """获取插件配置"""
        return self._plugin_configs.get(plugin_name, {})

    def _get_res_config_dir(self) -> Optional[str]:
        return get_res_config_dir()


# ── 全局单例 ──
plugin_manager = PluginManager()
