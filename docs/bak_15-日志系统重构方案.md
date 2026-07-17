# 日志系统重构方案

> 版本：v1 | 关联文件：`core/logger_manager.py`、`core/decorators/`、`core/tools/`

---

## 一、现状分析

### 1.1 当前结构

```
core/logger_manager.py     ← 500+ 行，职责混杂
  ├── 项目路径探测
  ├── StructuredLogFormatter    ← 格式化 + 中文翻译 + 颜色 + 映射全写在一起
  ├── _SafeRotatingFileHandler  ← 文件轮转
  ├── _ConsoleHandler           ← 控制台队列输出
  ├── LoggerManager             ← 初始化/管理/日志写入
  └── setup_runtime_logger      ← 实例独立日志

res/
  ├── log_colors.py             ← 颜色定义
  └── styling.py               ← 中文格式化

core/decorators/
  ├── handler.py                ← _logger = "Gracy.Decorators"
  ├── security.py               ← _logger = "Gracy.Decorators"
  └── async_utils.py            ← _logger = "Gracy.Decorators"
```

### 1.2 主要问题

| 问题 | 说明 |
|------|------|
| **logger_manager.py 过于臃肿** | 500+ 行，格式逻辑/Handler/管理杂糅 |
| **Logger 命名混乱** | `GracyOneBot`、`GracyBot-HTTP`、`GracyUI`、`LLM_Chat` 等 6 种不同风格 |
| **无统一日志属性机制** | 无法在日志行中附加"实例标识符"、"优先级"等上下文 |
| **装饰器体系未覆盖日志** | 插件需要手动 `_logger = logging.getLogger(...)` |
| **显示格式不统一** | 终端输出 logger 名有的带 `Gracy.` 前缀，有的没有 |
| **格式化逻辑难以扩展** | `StructuredLogFormatter.format()` 方法 100+ 行，全耦合 |

---

## 二、目标格式

### 2.1 终端输出格式

```
时间 - [分类] - 级别 - [模块] [属性1] [属性2] ... 消息内容
```

**示例：**

```
2026-06-23 10:00:00 - [Gracy] - INFO - [Help] [P50] [onebot-主号] 收到 /help 命令 返回帮助菜单
2026-06-23 10:00:00 - [Adapter] - INFO - [QQOfficial.gateway] [qq_official-官方机器人] WebSocket 连接成功
2026-06-23 10:00:00 - [Core] - INFO - [Pipeline] 消息进入安全过滤
2026-06-23 10:00:00 - [GracyUI] - INFO - [管理面板] [P50] [onebot-主号] Web面板启动完成
```

### 2.2 格式规范

```
{timestamp} - [{category}] - {level} - [{module}] [{attr1}] [{attr2}] ... {message}
```

各段含义：

| 段 | 来源 | 说明 |
|---|---|---|
| `timestamp` | 自动 | `%Y-%m-%d %H:%M:%S` |
| `[category]` | Logger 名首段 | 分类标识：`Core`/`Adapter`/`Gracy`/`Tool`/`GracyUI` |
| `level` | LogRecord | INFO/WARNING/ERROR 等 |
| `[module]` | Logger 名剩余部分 | 模块名或插件英文名 |
| `[attr]` | LogRecord extra | 属性列表，可选的，可叠加 |
| `message` | 开发者编写 | 描述做了什么+结果 |

### 2.3 文件日志格式（统一）

文件日志与终端日志格式一致，仅不启用颜色：

```
{timestamp} - [{category}] - {level} - [{module}] [{attr1}] [{attr2}] ... {message}
```

---

## 三、分类定义

### 3.1 分类表

| 分类 | 适用对象 | Logger 命名示例 |
|---|---|---|
| `Core` | 框架核心（pipeline、event、runtime、security、decorators） | `Core.Pipeline`、`Core.Runtime` |
| `Adapter` | 适配器层（QQOfficial、OneBot） | `Adapter.QQOfficial.gateway` |
| `Tool` | CLI 工具、配置、验证器 | `Tool.CLI`、`Tool.Config` |
| `Gracy` | 插件（默认分类） | `Gracy.Help`、`Gracy.Music` |
| `GracyUI` | Web 管理面板（特例） | `GracyUI`（保持不变） |

### 3.2 插件分类规则

- 插件**默认为** `Gracy.插件英文名`
- 入口文件名 = 插件名，以 `metadata.toml` 中的 `name` 字段为准的英文名
- 子模块可写：`Gracy.Music.core.draw`
- WebUI 保持 `GracyUI` 分类，不改为 `Gracy`

### 3.3 旧风格兼容

- 已存在的 `Gracy.xxx` 格式自动被识别为 `[Gracy]` 分类
- 不强制要求所有插件立即改，但推荐新插件使用规范格式
- 开发者可自定义 logger 名称，不受规范限制（兜底保留原名）

---

## 四、架构设计

### 4.1 新结构

```
core/tools/log_tool.py          ← 新增：日志工具函数
  ├── parse_logger_name()       ← 解析 logger 名为 [分类] [模块]
  ├── build_attrs()             ← 从 extra 构建属性列表
  └── format_console_line()     ← 组装最终终端显示行

core/decorators/logger.py       ← 新增：日志装饰器
  ├── @with_logger()            ← 自动创建 logger + 注入属性
  └── @log_attrs()              ← 动态添加/删除属性

core/logger_manager.py          ← 简化：只保留初始化/Handler
  ├── StructuredLogFormatter    ← 缩短，引用 log_tool
  ├── _SafeRotatingFileHandler  ← 不变
  ├── _ConsoleHandler           ← 不变
  ├── LoggerManager             ← 缩短
  └── setup_runtime_logger      ← 不变

res/
  ├── log_colors.py             ← 不变
  └── styling.py               ← 不变
```

### 4.2 文件职责

| 文件 | 职责 | 预估行数 |
|---|---|---|
| `core/tools/log_tool.py` | 纯函数工具：解析/格式化/属性构建 | ~80 行 |
| `core/decorators/logger.py` | 装饰器定义：注入 logger + 管理属性 | ~80 行 |
| `core/logger_manager.py` | Handler 创建 / 初始化 / 文件日志 | ~250 行 |

### 4.3 数据流

```
插件调用 _logger.info("消息", extra={"priority": "P50", "instance": "onebot-主号"})
  → logging.LogRecord 携带 extra
  → StructuredLogFormatter.format(record)
     → log_tool.parse_logger_name(record.name) → ("Gracy", "Help")
     → log_tool.build_attrs(record) → ["P50", "onebot-主号"]
     → log_tool.format_console_line(...) → "2026-06-23 ... - [Gracy] - INFO - [Help] [P50] [onebot-主号] 消息"
  → _ConsoleHandler → print 到终端
  → _SafeRotatingFileHandler → 写入文件（完整 logger 名）
```

---

## 五、分步实施计划

### 第 1 步：创建 `core/tools/log_tool.py`

内容：
- `parse_logger_name(name: str) -> tuple[str, str]` — 把 `Gracy.Help` 拆成 `("Gracy", "Help")`
- `build_attrs(record: LogRecord) -> list[str]` — 从 extra 构建属性列表
- `format_console(timestamp, category, level, module, attrs, message) -> str` — 组装终端行

可测试性：纯函数，不依赖任何模块，可直接 `pytest` 测试。

### 第 2 步：新增 `core/decorators/logger.py`

内容：
- `@with_logger(category="Gracy")` — 自动 `self._logger = logging.getLogger(f"{category}.{plugin_name}")`
- `@log_attrs(key=value)` — 给 LogRecord extra 添加属性

### 第 3 步：简化 `core/logger_manager.py`

内容：
- `StructuredLogFormatter.format()` 中引用 `log_tool.parse_logger_name()` 和 `log_tool.format_console()`
- 删除已迁移到 `log_tool` 的代码
- 保持 Handler 体系和初始化逻辑不变

### 第 4 步：核心理化（约 15 个文件）

| 文件 | 旧 Logger | 新 Logger |
|---|---|---|
| `core/pipeline/__init__.py` | `GracyPipeline` | `Core.Pipeline` |
| `core/pipeline/stages.py` | `GracyPipeline` | `Core.Pipeline` |
| `core/event/__init__.py` | `GracyEvent` | `Core.Event` |
| `core/runtime/runtime.py` | `Gracy.Runtime` | `Core.Runtime` |
| `core/runtime/data.py` | `Gracy.Data` | `Core.Data` |
| `core/security.py` | `GracyBot-HTTP` | `Core.Security` |
| `core/config_manager.py` | `GracyBot-Config` | `Tool.Config` |
| `core/adapter.py` | `GracyOneBot` | `Adapter.OneBot` |
| `core/gracy_adapter/onebot/adapter.py` | `GracyOneBot` | `Adapter.OneBot` |
| `core/gracy_adapter/onebot/ws.py` | `GracyOneBotWS` | `Adapter.OneBot.ws` |
| `core/gracy_adapter/onebot/http.py` | `GracyOneBot` | `Adapter.OneBot.http` |
| `core/gracy_adapter/send.py` | `Gracy.Send` | `Adapter.Send` |
| `core/gracy_adapter/pool.py` | `Gracy.Pool` | `Adapter.Pool` |
| `core/decorators/security.py` | `Gracy.Decorators` | `Core.Decorators` |
| `core/decorators/handler.py` | `Gracy.Decorators` | `Core.Decorators` |
| `core/decorators/async_utils.py` | `Gracy.Decorators` | `Core.Decorators` |
| `core/gracy_session/gracy_session_manager.py` | `GracySession` | `Core.Session` |
| `core/gracy_session/gracy_session_handler.py` | `GracySession` | `Core.Session` |

### 第 5 步：插件合理化（约 10 个文件）

| 文件 | 旧 Logger | 新 Logger |
|---|---|---|
| `plugins/LLM_Chat/` | `LLM_Chat` | `Gracy.LLM_Chat` |
| `plugins/GracyUI_plugin/` | `GracyUI` | `GracyUI`（不变） |
| `plugins/Gracone_Plugin/` | `Gracone` | `Gracy.Gracone` |
| `plugins/SysInfo_plugin/` | `Gracy`(裸) | `Gracy.SysInfo` |
| `plugins/Screenshot/` | `Gracy`(裸) | `Gracy.Screenshot` |
| `plugins/Easysearch/` | `Gracy`(裸) | `Gracy.Easysearch` |
| 其他插件 | 已有 `Gracy.中文名` | 统一改为英文 `Gracy.英文名` |

---

## 六、属性机制

### 6.1 内置属性

| 属性 | 来源 | 说明 |
|---|---|---|
| `P50` | `metadata.toml` 的 `priority` | 插件优先级 |
| `onebot-主号` | Runtime | 实例标识：适配器类型-bot_name |
| `qq_official-官方机器人` | Runtime | 实例标识 |

### 6.2 属性的使用

**方式一：手动传 extra（旧风格，不用装饰器）**
```python
_logger.info("消息已发送", extra={"log_attrs": {"priority": "P50", "instance": "onebot-主号"}})
```

**方式二：装饰器自动挂载（新风格）**
```python
@on_command("/search")
@log_attrs(priority="P50")
@plugin_handler
async def handler(ctx):
    _logger.info("搜索请求", extra={"keyword": "python"})
```

**直接手动设置**（无装饰器）：
```python
_logger.info(
    "消息已处理",
    extra={"priority": "P50", "instance": "onebot-主号"}
)
```

**动态管理：** `@log_attrs()` 可叠加、覆盖、清除属性。

---

## 七、使用规范

### 7.1 两种写法等价

装饰器只是语法糖，**最终都统一为 `logging.getLogger("分类.模块")`**，格式器只看 logger 名，不看是否用过装饰器。

```python
# ── 方式 A：不用装饰器（旧风格，推荐）──
_logger = logging.getLogger("Gracy.Help")

# ── 方式 B：用装饰器（新风格）──
@with_logger(category="Gracy")
class HelpPlugin:
    # 自动生成 self._logger = logging.getLogger("Gracy.Help")
    pass
```

**两条路最终一样。** 装饰器只是帮开发者省写一行，开发者爱用不用，终端显示统一。

### 7.2 Logger 命名规则

```
{分类}.{模块名}[.{子模块}]
```

| 分类 | 命名示例 | 终端显示 |
|---|---|---|
| Core | `Core.Pipeline`、`Core.Runtime` | `[Core] [Pipeline]` |
| Adapter | `Adapter.QQOfficial.gateway` | `[Adapter] [QQOfficial.gateway]` |
| Gracy | `Gracy.Help`、`Gracy.SysInfo` | `[Gracy] [Help]` |
| Tool | `Tool.Config` | `[Tool] [Config]` |
| GracyUI | `GracyUI` | `[GracyUI]` |

### 7.3 消息内容不要重复模块名

logger 名已经在 `[模块]` 位置显示了，消息内容里**不需要**再写一遍：

```python
# ❌ 错误：重复
_logger.info("[QQOfficial] WebSocket 连接成功")
# 终端显示: [Adapter] - INFO - [QQOfficial.gateway] - [QQOfficial] WebSocket 连接成功

# ✅ 正确：消息只写功能
_logger.info("WebSocket 连接成功")
# 终端显示: [Adapter] - INFO - [QQOfficial.gateway] - WebSocket 连接成功
```

### 7.4 自定义日志

开发者可以自由定义 logger 名和消息格式，不受限制：

- 不用装饰器 → 裸 `logging.getLogger()`，不做特殊兼容
- 用旧名 → 格式器兜底保留原名
- 随意写消息 → 格式器不干涉消息内容

---

## 八、兼容性保障

| 旧写法 | 新系统行为 |
|---|---|
| `_logger = logging.getLogger("Gracy.帮助插件")` | 自动识别为 `[Gracy] 帮助插件` |
| `_logger = logging.getLogger("LLM_Chat")` | 无前缀，保留原名显示 `LLM_Chat` |
| `_logger.info("消息")` | 无 extra 属性时正常显示 |
| `logger_manager.log_with_context(...)` | 保持兼容 |

---

## 九、测试验证

每步完成后验证：

1. `gracy run` 启动无报错
2. 终端输出格式符合 `[分类] - 级别 - [模块] [属性] 消息`
3. 发送 `/help` 命令，查看插件日志显示是否正确
4. 检查 `logs/gracybot.log` 保留完整 logger 名
