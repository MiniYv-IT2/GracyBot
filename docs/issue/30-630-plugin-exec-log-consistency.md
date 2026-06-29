# 2026-06-30 插件执行日志统一性问题

## 问题

所有插件执行应有一致的可见日志，目前三种路径各不同。

## 现状

| 路径 | 插件类型 | 示例 | 有 `[PluginHandler] 成功`？ | 有自身 `[Gracy] [插件名]`？ |
|------|----------|------|---------------------------|---------------------------|
| **A: TOML 匹配** | SysInfo、Help 等 | `/运行状态` | 有（`[Core] [Pipeline]`） | 无（除非 handler 内写 `logger.info`） |
| **B: 装饰器匹配** | ExamplePlugin 新风格 | `/echo` | 有（`[Core] [Pipeline]`） + **重复的** `[Core] [Decorators] [装饰器] 执行成功` | 无 |
| **C: Gracone 分发** | NoneBot 插件 (cchess 等) | `/状态`、`/象棋人机` | **无**（未走到 PluginHandler） | 无 |

## 用户预期

每次插件执行时看到 `[Gracy] [插件名] - INFO - 执行成功 命令=xxx 耗时=xxx`。

## 原因

- `PluginHandler` 日志器 = `logging.getLogger("Core.Pipeline")` → 类别 `[Core] [Pipeline]`
- `@plugin_handler` 日志器 = `logging.getLogger("Core.Decorators")` → 类别 `[Core] [Decorators]`
- `GraconeStage` 日志器 = `get_logger("Gracone")` → 类别 `[Gracy] [Gracone]`，但只有 `DEBUG` 级"Gracone 已处理"，无 `INFO` 级执行记录
- 各插件 handler 自身未主动 `logger.info` 记录执行

## 修復方案

### 不动框架（优先）

只改 `GraconeStage` 和/或 `dispatch_event`：
- `GraconeStage.process()` 成功时加 `logger.info(f"执行成功: 命令={raw_text} 耗时={elapsed:.3f}s 已匹配=N个NoneBot插件")`
- `dispatch_event()` 返回匹配的插件名列表（当前只返回 True/False），或 GraconeStage 从 matcher 信息提取

### 允许改框架

- **`PluginHandler`**：日志器从 `Core.Pipeline` 改为 `Gracy.Pipeline` → 类别变 `[Gracy] [Pipeline]`
- **`@plugin_handler`**：去掉重复的 `[装饰器] 执行成功` 日志（已由 PluginHandler 记录）
- 统一格式：`[Gracy] [Pipeline] - INFO - [PluginName] 执行成功 命令=xxx 耗时=xxx`

## 相关文件

- `core/pipeline/plugin_handler.py:13` — `_logger = logging.getLogger("Core.Pipeline")`
- `core/decorators/handler.py:33` — `_logger = logging.getLogger("Core.Decorators")`（第 91 行重复日志）
- `plugins/Gracone_Plugin/gracone_core.py:357-384` — `GraconeStage.process()`
- `plugins/Gracone_Plugin/bridge/matcher_bridge.py:594-686` — `dispatch_event()`
