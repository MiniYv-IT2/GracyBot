# 日志系统重构 — 变更记录

## 已完成的修改

### 新增文件（3 个）

| 文件 | 说明 | 行数 |
|---|---|---|
| `core/tools/log_tool.py` | 日志工具纯函数：解析 logger 名、构建属性、组装终端显示行 | 134 |
| `core/tools/log_runtime.py` | Runtime 实例独立日志器（从 logger_manager.py 拆出） | 62 |
| `core/decorators/logger.py` | 日志装饰器：`@with_logger()` / `@log_attrs()` | ~100 |

### 修改的文件（2 个）

| 文件 | 变更 |
|---|---|
| `core/logger_manager.py` | **精简 508 → 299 行**。移除 `_RUNTIME_LOGGER_NAMES`、`setup_runtime_logger`（移到 log_runtime.py）。`format()` 调用 `log_tool` 格式化控制台输出。 |
| `core/main.py` | `import setup_runtime_logger` 改为 `from core.tools.log_runtime` |

### 已改 logger 名的文件（15 个）

#### 适配层 — QQ Official（9 个）

| 文件 | 旧 Logger | 新 Logger |
|---|---|---|
| `core/gracy_adapter/qq_official/adapter.py` | `Gracy.QQOfficial` | `Adapter.QQOfficial` |
| `core/gracy_adapter/qq_official/auth.py` | `Gracy.QQOfficial.auth` | `Adapter.QQOfficial.auth` |
| `core/gracy_adapter/qq_official/bind.py` | `Gracy.QQOfficial.bind` | `Adapter.QQOfficial.bind` |
| `core/gracy_adapter/qq_official/bot.py` | `Gracy.QQOfficial.bot` | `Adapter.QQOfficial.bot` |
| `core/gracy_adapter/qq_official/gateway.py` | `Gracy.QQOfficial.gateway` | `Adapter.QQOfficial.gateway` |
| `core/gracy_adapter/qq_official/media.py` | `Gracy.QQOfficial.media` | `Adapter.QQOfficial.media` |
| `core/gracy_adapter/qq_official/message.py` | `Gracy.QQOfficial.message` | `Adapter.QQOfficial.message` |
| `core/gracy_adapter/qq_official/protocol.py` | `Gracy.QQOfficial.protocol` | `Adapter.QQOfficial.protocol` |
| `core/gracy_adapter/qq_official/sender.py` | `Gracy.QQOfficial.sender` | `Adapter.QQOfficial.sender` |

#### 适配层 — 公共（2 个）

| 文件 | 旧 Logger | 新 Logger |
|---|---|---|
| `core/gracy_adapter/pool.py` | `Gracy.Pool` | `Adapter.Pool` |
| `core/gracy_adapter/send.py` | `Gracy.Send` | `Adapter.Send` |

#### 消息流转核心（4 个）

| 文件 | 旧 Logger | 新 Logger |
|---|---|---|
| `core/pipeline/__init__.py` | `GracyPipeline` | `Core.Pipeline` |
| `core/pipeline/stages.py` | `GracyPipeline` | `Core.Pipeline` |
| `core/event/__init__.py` | `GracyEvent` | `Core.Event` |
| `core/security.py` | `GracyBot-HTTP`（7 处） | `Core.Security` |
| `core/security_manager.py` | `security` | `Core.Security` |

#### 插件（1 个）

| 文件 | 旧 Logger | 新 Logger |
|---|---|---|
| `plugins/Help_plugin/Help_plugin.py` | `Gracy.帮助插件` | `Gracy.Help` |

### 消息内容清理

QQ Official 适配器所有日志消息中多余的 `[QQOfficial]` 前缀已移除（40 处，9 个文件），终端不再显示重复：

```
改前: [Adapter] - INFO - [QQOfficial.gateway] - [QQOfficial] WebSocket 连接成功
改后: [Adapter] - INFO - [QQOfficial.gateway] - WebSocket 连接成功
```

### 终端格式

```
{时间} - [{分类}] - {级别} - [{模块}] [{属性1}] ... - {消息}
```

**示例：**
```
15:05:10 - [Core] - INFO - [Security] - 审计日志 | 用户:xxx
15:05:10 - [Core] - INFO - [Pipeline] - [适配器回调] 收到消息
15:05:10 - [Adapter] - INFO - [QQOfficial.gateway] - WebSocket 连接成功
15:05:10 - [Adapter] - INFO - [Send] - 消息发送成功
15:05:10 - [Gracy] - INFO - [Help] - 收到 /help 命令
```

### 分类前缀映射

| 前缀 | 分类 |
|---|---|
| `Core.` | Core |
| `Adapter.` | Adapter |
| `Tool.` | Tool |
| `Gracy.` | Gracy |
| `GracyUI` | GracyUI |
| `Gracone.` | Gracy |

无前缀或未知 → 取第一个 `.` 前作为分类，兜底保留原名。

### 属性机制

```python
# 方式1：手动传 extra
_logger.info("消息", extra={"log_attrs": {"priority": "P50", "instance": "onebot-主号"}})

# 方式2：装饰器
@log_attrs(priority="P50")
async def handler(ctx):
    _logger.info("消息已处理")
```

**当前还未有代码使用属性机制。**

---

## 第二批待改（运行管理 + 工具类 — 8 个文件）

| # | 文件 | 旧 logger | 新 logger |
|---|---|---|---|
| 1 | `core/runtime/runtime.py` | `Gracy.Runtime` | `Core.Runtime` |
| 2 | `core/runtime/data.py` | `Gracy.Data` | `Core.Data` |
| 3 | `core/config_manager.py` | `GracyBot-Config` | `Tool.Config` |
| 4 | `core/decorators/handler.py` | `Gracy.Decorators` | `Core.Decorators` |
| 5 | `core/decorators/security.py` | `Gracy.Decorators` | `Core.Decorators` |
| 6 | `core/decorators/async_utils.py` | `Gracy.Decorators` | `Core.Decorators` |
| 7 | `core/gracy_session/manager.py` | `GracySession` | `Core.Session` |
| 8 | `core/gracy_session/handler.py` | `GracySession` | `Core.Session` |

## 后续待改

### OneBot 适配器（不动，等核心+插件改完最后改）

| 文件 | 旧 logger | 新 logger |
|---|---|---|
| `core/adapter.py` | `GracyOneBot` | `Adapter` |
| `core/gracy_adapter/onebot/adapter.py` | `GracyOneBot` | `Adapter.OneBot` |
| `core/gracy_adapter/onebot/http.py` | `GracyOneBot` | `Adapter.OneBot.http` |
| `core/gracy_adapter/onebot/ws.py` | `GracyOneBotWS` | `Adapter.OneBot.ws` |

### 插件改名

| 文件 | 旧 logger | 新 logger |
|---|---|---|
| 各插件 | `Gracy.中文名`/`裸Gracy` | `Gracy.英文名` |
| GracyUI | `GracyUI` | 不变 |
