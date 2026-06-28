# Runtime 日志改进计划

## 现状

- `runtime.logger` 被创建但从未使用，仅写了一条初始化信息
- Pipeline/Adapter 组件用模块级 logger（`Core.Pipeline`、`Adapter.OneBot` 等）
- 所有实例日志混在 `gracybot.log`，无法按实例排查

## 目标

1. 每个实例的 `runtime.log` 记录该实例的完整运行时事件
2. 全局 `gracybot.log` 保留混合日志（兼容现有行为）
3. 不修改插件代码（插件仍用 `logging.getLogger()` 即可）

## 改动范围

### 仅改框架内部（不影响插件）

- `core/pipeline/__init__.py` — Pipeline 主流程获取当前 runtime logger 并写入
- `core/pipeline/plugin_handler.py` — 插件调用前后记录实例日志
- `core/pipeline/command_matcher.py` — 命令匹配记录实例日志
- `core/pipeline/response_sender.py` — 回复发送记录实例日志
- `core/gracy_adapter/send.py` — 消息发送记录实例日志
- `core/gracy_adapter/pool.py` — 适配器事件分发时绑定实例 logger

### 不改的

- 插件代码（零改动）
- `core/decorators/`（零改动）
- `core/logger_manager.py`（保持全局日志不变）

## 实现方案

### 方案 A：通过 RuntimeContext 获取当前实例 logger

在 Pipeline 处理链路中，通过 `RuntimeContext.get()` 获取当前 `runtime.logger`，在关键节点写入日志。

```
消息进入 Pipeline
  → RuntimeContext 已绑定当前 runtime
  → Pipeline.__call__ 用 runtime.logger 记录
  → 各 Stage 用 runtime.logger 记录
  → 回复发送用 runtime.logger 记录
```

**优点**：改动最小，只改 Pipeline 和 Adapter 的调用点
**缺点**：需要在每个调用点加 `runtime.logger.xxx()`

### 方案 B：日志 Filter 自动路由

创建一个 logging.Filter，检查当前 RuntimeContext，自动把日志路由到对应实例文件。

```
所有 logger → root logger
  → Filter 检查 RuntimeContext
  → 如果有当前 runtime → 同时写入 runtime.logger
  → 保留全局日志
```

**优点**：插件和框架代码无需任何改动，自动生效
**缺点**：Filter 实现复杂，需要正确处理 contextvars

### 推荐方案：A + B 结合

- **Pipeline/Adapter 核心路径**：用方案 A，显式写入实例日志（精确控制）
- **插件 logger**：用方案 B，Filter 自动路由（零改动）

## 具体改动点

### 1. Pipeline 主流程（`core/pipeline/__init__.py`）

```python
# 当前：_logger.debug(...)
# 改为：用 runtime.logger 记录实例级日志
runtime = RuntimeContext.get()
if runtime and runtime.logger:
    runtime.logger.debug(f"[Pipeline] 处理消息 {ctx.message_id}")
```

### 2. 插件调用（`core/pipeline/plugin_handler.py`）

```python
# 插件调用前后记录
runtime = RuntimeContext.get()
if runtime and runtime.logger:
    runtime.logger.info(f"[Plugin] 调用 {plugin_name}")
```

### 3. 消息发送（`core/gracy_adapter/send.py`）

```python
# 发送成功/失败记录到实例日志
runtime = RuntimeContext.get()
if runtime and runtime.logger:
    runtime.logger.info(f"[Send] → {target} 成功")
```

### 4. 日志 Filter（可选，方案 B）

```python
class RuntimeLogFilter(logging.Filter):
    def filter(self, record):
        runtime = RuntimeContext.get()
        if runtime and runtime.logger:
            # 创建一个带有实例 logger handler 的临时 handler
            # 把日志同时写入实例文件
            pass
        return True  # 不阻止全局日志
```

## 验证标准

- `logs/instances/<name>/runtime.log` 包含该实例的完整运行事件
- `logs/gracybot.log` 仍包含所有实例的混合日志（向后兼容）
- 插件代码零改动
- 多实例环境下能按实例名过滤日志

## 优先级

- **高**：Pipeline 核心路径写入实例日志（方案 A）
- **中**：Adapter 事件写入实例日志
- **低**：Filter 自动路由（方案 B，可后续做）
