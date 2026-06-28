# GracyPlugin 插件基类 — 实施计划

## 目标

为 GracyBot 提供统一的插件编程模型，`from graci import GracyPlugin`，三种模式归一。

## 改动范围

### 新增 1 个文件

`core/decorators/plugin_base.py` — `GracyPlugin` 基类

```python
class GracyPlugin:
    """插件基类 — 提供快捷方法和生命周期钩子"""

    # 由 loader 在调用时注入
    ctx: Optional[PluginContext] = None
    adapter_tag: Optional[IdentityTag] = None

    # 内置快捷方法
    async def reply(self, text: str) -> bool: ...
    async def send(self, *segs, ct=None) -> bool: ...

    # 可选钩子
    async def on_load(self): ...      # 插件加载
    async def on_unload(self): ...    # 插件卸载
```

### 在 plugin_manager.py 加 ~10 行扫描逻辑

`plugin_manager.init()` 扫描 `metadata.toml` 时，如果读到 `class` 字段：

1. `importlib.import_module(module_path)` 导入模块
2. `getattr(module, class_name)` 获取类
3. 验证是 `GracyPlugin` 子类
4. 扫描类中所有 `@on_command` 装饰的方法，注册到 `plugin_manager.registry`
5. `handler_func` 指向 `instance.method`（由 `@plugin_handler` 包装）

### 在 PluginHandler 加 ~5 行分支

检测到 `handler_func` 是绑定方法（bound method）时，不实例化，直接调用。

### 可选的 metadata.toml 写法

```toml
[plugin]
name = "Hello"
version = "1.0.0"
class = "HelloPlugin"        # ← 新增字段
handler = "handle_xiaoyu"     # ← 旧字段仍然可用
commands = ["/hello"]
```

### 兼容性

| 插件类型 | 写法 | 是否需要 toml |
|---------|------|-------------|
| 旧风格函数 | 7 参数签名 | 要 |
| 新风格装饰器 | `@on_command` + `@plugin_handler` | 不 |
| GracyPlugin 基类 | `class X(GracyPlugin)` | 可选 |

三种模式在 Pipeline 中无差别执行，`plugin_manager.registry` 统一存储。

## 不动的内容

- `core/decorators/` 下已有装饰器：`@on_command`、`@on_regex`、`@plugin_handler` 等全部保留
- `metadata.toml` 保留，只需加一个 `class` 字段
- Pipeline 架构不改变
- 现有插件无需迁移

## 实施顺序

1. 创建 `core/decorators/plugin_base.py`（GracyPlugin 基类）
2. 修改 `plugin_manager.py`，扫描 TOML 时处理 `class` 字段
3. 修改 `PluginHandler`，处理 bound method 的调用
4. 选一个插件改写验证
