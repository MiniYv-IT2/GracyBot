"""
gracone_core.py — Gracone 加载引擎

职责:
1. 全局状态管理（loaded/disabled 插件列表）
2. NoneBot 插件扫描与加载（单文件 + 子包）
3. cchess ORM 补丁
4. EventBus 事件分发
"""

import sys
import os
import types
import logging
import importlib.util
from pathlib import Path

from graci import Stage, RuntimeRegistry
from bridge.matcher_bridge import matcher_manager, dispatch_event, inject_into_nonebot

_logger = logging.getLogger("Gracone")

# ── 版本号 ──
GRACONE_VERSION = "1.0.0"

# ── 全局状态 ──
_gracone_initialized = False
_loaded_nb_plugins: list[str] = []
_disabled_nb_plugins: set[str] = set()
_plugin_dir = Path(__file__).parent / "nonebot_plugins"


# ════════════════════════════════════════════════════
# 禁用列表持久化
# ════════════════════════════════════════════════════

def _get_disabled_file() -> str:
    """返回禁用列表 JSON 路径（项目根目录/.gracone_disabled.json）"""
    gracy_home = os.environ.get("GRACYBOT_HOME", os.getcwd())
    return os.path.join(gracy_home, ".gracone_disabled.json")


def load_disabled_plugins() -> set[str]:
    """从 JSON 加载已禁用的 NoneBot 插件名称集合"""
    path = _get_disabled_file()
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                data = __import__('json').load(f)
                return set(data.get("disabled", []))
    except Exception as e:
        _logger.warning(f"读取禁用列表失败: {e}")
    return set()


def _run_fake_driver_startup():
    """触发 Fake Driver 的 on_startup 钩子 — 同步执行"""
    try:
        from gracone_nonebot import _fake_driver
        if hasattr(_fake_driver, '_startup_hooks') and _fake_driver._startup_hooks:
            for hook in _fake_driver._startup_hooks:
                try:
                    r = hook()
                    if hasattr(r, '__await__'):
                        # 钩子虽是 async def，但实际是同步操作，用 send(None) 驱动到完成
                        try:
                            r.send(None)
                        except StopIteration:
                            pass
                        except Exception:
                            # 尝试 run_until_complete / create_task
                            import asyncio
                            try:
                                loop = asyncio.get_running_loop()
                                asyncio.ensure_future(r)
                            except RuntimeError:
                                asyncio.get_event_loop().run_until_complete(r)
                except Exception as e:
                    _logger.warning(f"FakeDriver on_startup 钩子失败: {e}")
    except ImportError:
        pass


def save_disabled_plugins() -> None:
    """保存禁用插件集合到 JSON"""
    path = _get_disabled_file()
    try:
        with open(path, 'w', encoding='utf-8') as f:
            import json
            json.dump({"disabled": sorted(_disabled_nb_plugins)}, f,
                       ensure_ascii=False, indent=2)
    except Exception as e:
        _logger.error(f"保存禁用列表失败: {e}")


# ════════════════════════════════════════════════════
# 插件加载引擎
# ════════════════════════════════════════════════════

def _patch_cchess_modules(module_name: str):
    """cchess 模块补丁 — 替换模块命名空间中的 sqlalchemy 引用为假实现"""

    class _Cond:
        def __init__(self, col, op, val):
            self._condition = (col, op, val)

    class _FakeCol:
        def __init__(self, name):
            self.name = name
        def __hash__(self):
            return hash(self.name)
        def __eq__(self, other):
            return _Cond(self.name, '==', other)
        def __ne__(self, other):
            return _Cond(self.name, '!=', other)
        def desc(self):
            return ('desc', self.name)

    class _FakeStmt:
        def __init__(self, model_cls):
            self._model_cls = model_cls
            self._where = []
            self._order_by_reverse = False
        def where(self, *conditions):
            self._where.extend(conditions)
            return self
        def order_by(self, *cols):
            for c in cols:
                if isinstance(c, tuple) and c[0] == 'desc':
                    self._order_by_reverse = True
            return self

    def _fake_select(model_cls):
        return _FakeStmt(model_cls)

    _store = {}

    class _FakeSess:
        def __init__(self):
            self._pending = {}
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def scalar(self, stmt):
            if not hasattr(stmt, '_model_cls'):
                return None
            filters = {}
            for cond in stmt._where:
                if hasattr(cond, '_condition'):
                    col, op, val = cond._condition
                    filters[col] = val
            game_id = filters.get('game_id')
            session_id = filters.get('session_id')
            recs = list(_store.values())
            if stmt._order_by_reverse:
                recs.reverse()
            for rec in recs:
                if game_id and rec.game_id == game_id:
                    return rec
                if session_id and rec.session_id == session_id:
                    if not filters.get('is_game_over') or not rec.is_game_over:
                        return rec
                has_game_over_check = any(
                    hasattr(c, '_condition') and c._condition[0] == 'is_game_over'
                    for c in stmt._where
                )
                if has_game_over_check and session_id and rec.session_id == session_id and not rec.is_game_over:
                    return rec
            return None
        def add(self, instance):
            self._pending[instance.game_id] = instance
        async def commit(self):
            for k, v in self._pending.items():
                _store[k] = v
            self._pending.clear()
        async def flush(self):
            pass
        async def close(self):
            pass

    # 替换 game 模块的引用
    game_mod = sys.modules.get(f"{module_name}.game")
    if game_mod:
        game_mod.select = _fake_select
        game_mod.get_session = lambda: _FakeSess()
        _logger.info(f"  ── patched game: select → fake")

    # 为 model 的 GameRecord 添加假列描述符
    model_mod = sys.modules.get(f"{module_name}.model")
    if model_mod and hasattr(model_mod, 'GameRecord'):
        for attr in ('game_id', 'session_id', 'id', 'is_game_over', 'update_time',
                     'start_time', 'player_red_id', 'player_red_name',
                     'player_red_is_ai', 'player_red_level',
                     'player_black_id', 'player_black_name',
                     'player_black_is_ai', 'player_black_level',
                     'start_fen', 'moves'):
            setattr(model_mod.GameRecord, attr, _FakeCol(attr))
        _logger.info(f"  ── patched model: GameRecord columns → descriptors")


def load_single_plugin(py_file):
    """加载单个 .py 文件作为 NoneBot 插件"""
    global _loaded_nb_plugins
    module_name = f"nonebot_plugins.{py_file.stem}"
    if module_name in sys.modules:
        return
    try:
        spec = importlib.util.spec_from_file_location(module_name, str(py_file))
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = mod
            sys.modules[f'nonebot.plugins.{py_file.stem}'] = mod
            spec.loader.exec_module(mod)
            _loaded_nb_plugins.append(py_file.stem)
            _logger.info(f"已加载 NoneBot 插件: {py_file.stem}")
    except Exception as e:
        _logger.error(f"加载 NoneBot 插件 {py_file.name} 失败: {e}", exc_info=True)


def load_package_plugin(sub_dir):
    """加载子包目录作为 NoneBot 插件（目录名作为模块名）"""
    global _loaded_nb_plugins
    pkg_name = sub_dir.name
    module_name = f"nonebot_plugins.{pkg_name}"

    if module_name in sys.modules:
        return
    try:
        init_file = sub_dir / "__init__.py"

        # 先将包自身注册
        pkg_mod = types.ModuleType(module_name)
        pkg_mod.__package__ = module_name
        pkg_mod.__path__ = [str(sub_dir)]
        pkg_mod.__file__ = str(init_file)
        pkg_mod.__version__ = "0.0.0"  # 预设置版本号，避免子模块在 __init__.py 加载前引用 __version__ 出错
        sys.modules[module_name] = pkg_mod

        # 先加载所有子模块
        for py_file in sorted(sub_dir.glob("*.py")):
            if py_file.name == "__init__.py":
                continue
            sub_module_name = f"{module_name}.{py_file.stem}"
            if sub_module_name in sys.modules:
                continue
            try:
                sub_spec = importlib.util.spec_from_file_location(
                    sub_module_name, str(py_file))
                if sub_spec and sub_spec.loader:
                    sub_mod = importlib.util.module_from_spec(sub_spec)
                    sub_mod.__package__ = module_name
                    sys.modules[sub_module_name] = sub_mod
                    sub_spec.loader.exec_module(sub_mod)
            except Exception as e:
                _logger.warning(f"加载子模块 {py_file.name} 时出错: {e}")

        # cchess 专用补丁
        if pkg_name == 'cchess':
            _patch_cchess_modules(module_name)

        # 加载 __init__.py
        spec = importlib.util.spec_from_file_location(module_name, str(init_file))
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = mod
            spec.loader.exec_module(mod)

        _loaded_nb_plugins.append(pkg_name)
        _logger.info(f"已加载 NoneBot 包插件: {pkg_name}")
    except Exception as e:
        _logger.error(f"加载 NoneBot 包插件 {pkg_name} 失败: {e}", exc_info=True)


def scan_and_load_nb_plugins():
    """扫描 nonebot_plugins 目录并加载 NoneBot 插件"""
    global _loaded_nb_plugins

    # 单文件 .py
    skip_files = {"echo.py"}
    for py_file in sorted(_plugin_dir.glob("*.py")):
        if py_file.name.startswith("_") or py_file.name == "__init__.py":
            continue
        if py_file.name in skip_files:
            _logger.info(f"  ⏭️ 跳过测试插件: {py_file.name}")
            continue
        plugin_name = py_file.stem
        if plugin_name in _disabled_nb_plugins:
            _logger.info(f"  ⏭️ 已禁用: {plugin_name}")
            continue
        load_single_plugin(py_file)

    # 子包
    for sub_dir in sorted(_plugin_dir.iterdir()):
        if not sub_dir.is_dir() or sub_dir.name.startswith("_"):
            continue
        init_file = sub_dir / "__init__.py"
        if not init_file.exists():
            continue
        pkg_name = sub_dir.name
        if pkg_name in _disabled_nb_plugins:
            _logger.info(f"  ⏭️ 已禁用: {pkg_name}")
            continue
        load_package_plugin(sub_dir)


def list_plugin_dir() -> list[dict]:
    """列出 nonebot_plugins 目录下所有可识别的插件"""
    result = []
    for py_file in sorted(_plugin_dir.glob("*.py")):
        if py_file.name.startswith("_") or py_file.name in ("__init__.py", "echo.py"):
            continue
        name = py_file.stem
        result.append({
            "name": name, "type": "file",
            "loaded": name in _loaded_nb_plugins,
            "disabled": name in _disabled_nb_plugins,
        })
    for sub_dir in sorted(_plugin_dir.iterdir()):
        if not sub_dir.is_dir() or sub_dir.name.startswith("_"):
            continue
        if not (sub_dir / "__init__.py").exists():
            continue
        name = sub_dir.name
        result.append({
            "name": name, "type": "package",
            "loaded": name in _loaded_nb_plugins,
            "disabled": name in _disabled_nb_plugins,
        })
    return result


async def full_reload():
    """全量重载所有 NoneBot 插件"""
    global _loaded_nb_plugins
    matcher_manager.clear()
    keys_to_del = [k for k in sys.modules if k.startswith("nonebot_plugins.")]
    for k in keys_to_del:
        del sys.modules[k]
    _loaded_nb_plugins = []
    scan_and_load_nb_plugins()
    return len(_loaded_nb_plugins)


# ════════════════════════════════════════════════════
# Pipeline Stage — 在 ResponseSender 之前拦截消息
# ════════════════════════════════════════════════════

class GraconeStage(Stage):
    """Pipeline Stage：在 ResponseSender 前拦截消息分发给 NoneBot 插件

    返回 None → 短路 Pipeline，ResponseSender 不再执行（LLMChat 不触发）
    返回 ctx → 继续到 ResponseSender
    """

    async def process(self, ctx) :
        """处理消息上下文"""
        raw_text = ctx.raw_text.strip()
        if not raw_text:
            return ctx

        # 从 PluginContext 构造 GracyEvent 给 dispatch_event
        from graci import GracyEvent

        event = GracyEvent(
            sender_id=ctx.sender_id,
            target_id=ctx.target_id,
            chat_type=ctx.chat_type,
            raw_text=raw_text,
            is_at_bot=ctx.is_at_bot,
            raw_data=ctx.raw_data,
            nickname=ctx.nickname,
            source=None,
        )

        try:
            handled = await dispatch_event(event, ctx.adapter_tag)
            if handled:
                _logger.debug(
                    f"Gracone 已处理: {raw_text[:50]}")
                return None  # 短路，不触发 ResponseSender
        except Exception as e:
            _logger.error(f"Gracone 分发异常: {e}", exc_info=True)

        return ctx  # 未处理，继续到 ResponseSender


def _inject_stage_into_runtimes():
    """为所有 Runtime 的 Pipeline 插入 GraconeStage（在 ResponseSender 前）"""
    count = 0
    for runtime in RuntimeRegistry.get_all():
        pipeline = getattr(runtime, 'pipeline', None)
        if pipeline is None:
            continue
        stages = pipeline._stages
        # 在 ResponseSender 前插入
        for i, stage in enumerate(stages):
            if stage.__class__.__name__ == 'ResponseSender':
                # 避免重复注入
                already_injected = any(
                    s.__class__.__name__ == 'GraconeStage' for s in stages)
                if already_injected:
                    break
                stages.insert(i, GraconeStage())
                count += 1
                _logger.debug(
                    f"  ── 注入 GraconeStage 到 runtime: {runtime.instance_name}")
                break
    if count:
        _logger.info(f"  已注入到 {count} 个 Runtime Pipeline")


# ════════════════════════════════════════════════════
# 初始化
# ════════════════════════════════════════════════════

def initialize():
    """初始化 Gracone 兼容层"""
    global _gracone_initialized, _disabled_nb_plugins

    if _gracone_initialized:
        _logger.warning("Gracone 已初始化，跳过")
        return

    inject_into_nonebot()

    _disabled_nb_plugins = load_disabled_plugins()
    if _disabled_nb_plugins:
        _logger.info(f"  已加载禁用列表: {', '.join(sorted(_disabled_nb_plugins))}")

    _plugin_dir.mkdir(exist_ok=True)
    init_file = _plugin_dir / "__init__.py"
    if not init_file.exists():
        init_file.write_text("# Gracone NoneBot 插件目录\n")

    scan_and_load_nb_plugins()

    # 触发 Fake Driver 的 on_startup 钩子（供 data_source 等插件注册启动任务）
    _run_fake_driver_startup()

    # 注入 Pipeline Stage — 在 on_ready 时执行（确保 Runtime 已就绪）
    from graci import plugin_manager
    plugin_manager.register_on_ready(_inject_stage_into_runtimes)

    _gracone_initialized = True
    _logger.info(
        f"Gracone v{GRACONE_VERSION} 初始化完成 — "
        f"已加载 {len(_loaded_nb_plugins)} 个 NoneBot 插件")
    _logger.info(f"NoneBot 插件: {_loaded_nb_plugins}")
