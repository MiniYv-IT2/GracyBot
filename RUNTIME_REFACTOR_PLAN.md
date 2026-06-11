# GracyBot Runtime 重构 — 定稿计划

> 每个 QQ 号 = 一个 Runtime 实例。
> 全局 ROOT 日志输出终端 + 每个 Runtime 独立文件日志。
> 全局资源共享 `data/`，账号独立数据 `style/instances/<name>/data/`。
> `ROBOT_ID` / `MASTER_ID` / 全局 Pipeline 全部删除，全绑定 Runtime。

---

## 一、新增模块：`core/runtime/`

```
core/runtime/
├── __init__.py         # from .runtime import Runtime, RuntimeRegistry, RuntimeContext
├── runtime.py          # Runtime 数据类 + RuntimeRegistry + RuntimeContext
└── data.py             # get_global_path / get_instance_path / deep_merge
```

### 1.1 `runtime.py`

```python
@dataclass
class Runtime:
    instance_name: str         # style/instances/<name> 的目录名
    robot_id: str              # QQ 号
    master_id: str             # 主人 QQ
    adapter_tag: IdentityTag   # 关联适配器标签

    pipeline: Pipeline         # 独立管道
    logger: Logger             # 独立日志器（logs/instances/<name>/runtime.log）

    plugin_manager: PluginManager = None   # 全局引用
    adapter_pool: AdapterPool = None       # 全局引用

    @property
    def instance_data_dir(self) -> str:
        return f"style/instances/{self.instance_name}/data"


class RuntimeRegistry:
    """全局 Runtime 注册表"""
    _runtimes: dict[str, Runtime] = {}

    @classmethod
    def register(cls, runtime: Runtime): ...
    @classmethod
    def get_by_tag(cls, tag: IdentityTag) -> Optional[Runtime]: ...
    @classmethod
    def get_by_robot_id(cls, robot_id: str) -> Optional[Runtime]: ...


_current_runtime: ContextVar[Runtime] = ContextVar("_current_runtime")

class RuntimeContext:
    @staticmethod
    def set(runtime: Runtime) -> Token: ...
    @staticmethod
    def get() -> Runtime: ...
    @staticmethod
    def reset(token: Token): ...
```

### 1.2 `data.py`

```python
def get_global_path(plugin_name: str, *segments: str) -> str:
    """全局资源 → data/<plugin_name>/[...]"""
    return os.path.join("data", plugin_name, *segments)

def get_instance_path(runtime: Runtime, plugin_name: str, *segments: str) -> str:
    """账号独立 → style/instances/<name>/data/<plugin_name>/[...]"""
    return os.path.join("style", "instances", runtime.instance_name, "data", plugin_name, *segments)

def deep_merge(base: dict, override: dict) -> dict:
    """递归深度合并 — 缺字段自动补"""
    result = base.copy()
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = v
    return result
```

### 1.3 `__init__.py`

```python
from .runtime import Runtime, RuntimeRegistry, RuntimeContext
from .data import get_global_path, get_instance_path, deep_merge
```

---

## 二、需要修改的文件清单

### 2.1 `core/__init__.py` — 注册 Runtime 模块

在 `Core` 类加一个 LazyLoader：

```python
def _get_runtime_registry():
    from .runtime import RuntimeRegistry
    return RuntimeRegistry

class Core:
    plugin_manager = LazyLoader(_get_plugin_manager)
    security_manager = LazyLoader(_get_security_manager)
    ...
    runtime_registry = LazyLoader(_get_runtime_registry)   # ← 新增
```

### 2.2 `core/config.py` — 删除全局变量

| 操作 | 具体 |
|---|---|
| 删除 | `ROBOT_ID = ""` + `_update_robot_id()` |
| 删除 | `MASTER_ID = ""` + `_update_master_id()` |
| 删除 | `ROBOT_START_TIME = time.time()` |
| 保留改底层 | `get_current_robot_id()` → 走 `RuntimeContext.get().robot_id` |
| 保留改底层 | `get_current_master_id()` → 走 `RuntimeContext.get().master_id` |

```python
# 重构后的兼容层
def get_current_robot_id() -> str:
    try:
        return RuntimeContext.get().robot_id
    except Exception:
        return ""

def get_current_master_id() -> str:
    try:
        return RuntimeContext.get().master_id
    except Exception:
        return ""
```

### 2.3 `core/logger_manager.py` — 日志系统改造

| 操作 | 具体 |
|---|---|
| 新增 | `SanitizeFormatter` 类（内置脱敏逻辑） |
| 改造 | `StructuredLogFormatter` → 继承 `SanitizeFormatter` |
| 新增 | `setup_runtime_logger(runtime)` 函数 |
| 保留 | Root Logger + Console Handler + `gracybot.log` |
| 新增 | 子日志器 `"Gracy.<instance_name>"`，`propagate=True`，独立文件 |

### 2.4 `core/main.py` — 启动流程重构

| 操作 | 具体 |
|---|---|
| 改造 | `_register_instance(cfg)` → `_register_instance(cfg, runtime)` |
| 改造 | 扫描 `style/instances/` 后，foreach 创建 Runtime |
| 新增 | 每个 Runtime 创建独立 Pipeline |
| 新增 | `_setup_runtime_logger(runtime)` 调用 |
| 新增 | `_init_instance_data_dirs(runtime)` 创建账号数据目录 |
| 改造 | `callback()` 中收到事件后，查 RuntimeRegistry → 路由到对应 Runtime 的 Pipeline |

```python
# 重构后启动伪码
def run_bot():
    instances = _discover_instance_configs()

    for cfg in instances:
        runtime = Runtime(
            instance_name=cfg["_dir_name"],
            robot_id=cfg["robot_id"],
            master_id=cfg["master_id"],
            adapter_tag=IdentityTag(cfg["platform"], cfg["bot_name"]),
        )
        # 独立 Pipeline
        runtime.pipeline = Pipeline()
        runtime.pipeline.add_stage(SecurityFilter())
        runtime.pipeline.add_stage(BuiltinCommands())
        runtime.pipeline.add_stage(CommandMatcher())
        runtime.pipeline.add_stage(PluginHandler())
        runtime.pipeline.add_stage(ResponseSender())
        # 独立日志
        _setup_runtime_logger(runtime)
        # 账号数据目录
        _init_instance_data_dirs(runtime)
        # 注册
        RuntimeRegistry.register(runtime)
        _register_instance(cfg, runtime)

    adapter_pool.start_all()
```

### 2.5 `core/pipeline/__init__.py` — 删除全局单例

| 操作 | 具体 |
|---|---|
| 删除 | `pipeline = Pipeline()` 全局单例 |
| 删除 | `_register_default_stages()` 调用 |
| 保留 | `Pipeline` 类和 `Stage` 基类不变 |
| 保留 | `__all__` 导出，去掉 `pipeline` |

### 2.6 `core/pipeline/stages.py` — 消灭全局 import

| 文件位置 | 当前 | 改为 |
|---|---|---|
| Stage 1/2/3/4/5 中 | `from core.config import MASTER_ID` | `ctx.runtime.master_id` |
| Stage 3 PluginHandler | `_is_master()` 中 `getattr(adapter, '_instance_master_id')` | `ctx.runtime.master_id` |
| Stage 2 BuiltinCommands | `from core.config import BOT_VERSION` | 保留（框架级常量） |

### 2.7 `core/event/__init__.py` — EventBus 路由改造

| 操作 | 具体 |
|---|---|
| 改造 | `publish(event)` → 查 `RuntimeRegistry.get_by_tag(event.source)` |
| 新增 | `RuntimeContext.set(runtime)` → `runtime.pipeline.process(event)` → `reset` |

```python
async def publish(self, event: GracyEvent):
    runtime = RuntimeRegistry.get_by_tag(event.source)
    if not runtime:
        return

    token = RuntimeContext.set(runtime)
    try:
        await runtime.pipeline.process(event)
    finally:
        RuntimeContext.reset(token)
```

### 2.8 `core/gracy_adapter/send.py` — 删除 contextvars

| 操作 | 具体 |
|---|---|
| 删除 | `current_adapter_tag` contextvar |
| 删除 | `current_robot_id` contextvar |
| 删除 | `current_master_id` contextvar |
| 改造 | `gracy_send_msg()` 中 `tag` 参数逻辑走 `RuntimeContext.get().adapter_tag` |

### 2.9 `core/decorators/context.py` — PluginContext 新增 runtime

```python
@dataclass
class PluginContext:
    runtime: Runtime = None      # ← 新增

    @property
    def adapter_tag(self):
        return self.runtime.adapter_tag if self.runtime else None

    @property
    def pool(self):
        return self.runtime.adapter_pool if self.runtime else None

    @property
    def plugin_manager(self):
        return self.runtime.plugin_manager if self.runtime else None
```

### 2.10 `core/decorators/handler.py` — PluginContext 注入 runtime

当前 Pipeline 创建 ctx 的地方，新增 `runtime=runtime` 传参。

### 2.11 `core/plugin_manager.py` — 配置加载深合并

| 操作 | 具体 |
|---|---|
| 改造 | `_init_plugin_config()` → 读取 `data/<插件名>/` + `style/instances/<name>/data/<插件名>/config.json` |
| 新增 | `deep_merge` 合并 default → global → instance |

---

## 三、需要新建的目录

| 目录 | 用途 |
|---|---|
| `core/runtime/` | 模块目录 |
| `data/` | 全局资源共享根目录 |
| `style/instances/<name>/data/` | 各实例独立数据（由框架自动创建） |
| `logs/instances/<name>/` | 各实例独立日志文件（由日志系统自动创建） |

---

## 四、改动汇总表

| # | 文件 | 操作 | 阶段 |
|---|---|---|---|
| 1 | `core/runtime/__init__.py` | 🆕 新建 | P0 |
| 2 | `core/runtime/runtime.py` | 🆕 新建 | P0 |
| 3 | `core/runtime/data.py` | 🆕 新建 | P0 |
| 4 | `core/__init__.py` | ✏️ 新增 LazyLoader | P0 |
| 5 | `core/config.py` | ✏️ 删除全局变量，改兼容层 | P1 |
| 6 | `core/logger_manager.py` | ✏️ 新增 SanitizeFormatter + runtime 日志 | P1 |
| 7 | `core/main.py` | ✏️ 启动流程重构 | P1 |
| 8 | `core/pipeline/__init__.py` | ✏️ 删除全局 pipeline 单例 | P2 |
| 9 | `core/pipeline/stages.py` | ✏️ 替换全局变量为 ctx.runtime | P2 |
| 10 | `core/event/__init__.py` | ✏️ EventBus 路由改造 | P2 |
| 11 | `core/gracy_adapter/send.py` | ✏️ 删除 3 个 contextvar | P2 |
| 12 | `core/decorators/context.py` | ✏️ PluginContext 新增 runtime | P2 |
| 13 | `core/decorators/handler.py` | ✏️ 注入 runtime 到 ctx | P2 |
| 14 | `core/plugin_manager.py` | ✏️ 配置加载深合并 | P3 |

---

## 五、实施顺序

**P0（独立可上线）：** 新建 `core/runtime/`、注册到 `core/__initify__` — 新增纯文件，零影响现有功能。

**P1（独立可上线）：** 日志改造 + 启动流程重构 — 引入 Runtime 但保留全局变量兜底，新旧并存。

**P2（需 P0+P1）：** 删除全局 Pipeline/ROBOT_ID/MASTER_ID/contextvars — 全部切到 Runtime。

**P3（需 P2）：** 插件配置深合并 — 改造 `_init_plugin_config`。

---

这就是最终定稿。如果没问题，你说了算——从 **P0** 开始写代码，还是再聊一聊？