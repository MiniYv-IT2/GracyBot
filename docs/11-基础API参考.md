# 基础 API 参考

> 框架核心模块的函数、类和常量速查手册。
> 插件开发者请使用 `from graci import xxx`（外观层），本文档部分内部 API 仅供框架/适配器开发者参考。

---

## 目录

- [框架核心（`core/`）](#框架核心core)
- [适配器（`gracy_adapter/`）](#适配器gracy_adapter)
- [装饰器（`decorators/`）](#装饰器decorators)
- [工具模块（`tools/`）](#工具模块tools)
- [内置事件（`event/`）](#内置事件event)
- [会话管理（`gracy_session/`）](#会话管理gracy_session)

---

## 框架核心（`core/`）

### `plugin_manager.py`

| 符号 | 类型 | 说明 |
|---|---|---|
| `PLUGIN_REGISTRY` | list[dict] | 全局插件注册池（所有已注册插件的元数据） |
| `LOADED_PLUGIN_VERSIONS` | dict[str, str] | 已加载插件版本字典 |
| `plugin_manager` | PluginManager | 全局单例 |
| `pm.init(plugin_dir)` | method | 初始化/扫描插件目录 |
| `pm.get_matched_plugin(raw_msg, chat_type, sender_id, is_at_bot)` | method | 按消息匹配插件 |
| `pm.get_all_plugins_metadata()` | method | 获取所有插件元数据 |
| `pm.reload_plugin(name)` | method | 热重载指定插件 |

### `config.py`

| 符号 | 类型 | 说明 |
|---|---|---|
| `MASTER_ID` | str | 主人 QQ 号（全局兜底，多账号优先用 `get_current_master_id()`） |
| `ROBOT_ID` | str | 机器人 QQ 号（全局兜底，多账号优先用 `get_current_robot_id()`） |
| `get_current_robot_id()` | → str | 获取当前消息上下文的机器人 QQ（多账号自动适配） |
| `get_current_master_id()` | → str | 获取当前消息上下文的主人 QQ（多账号自动适配） |
| `BOT_VERSION` | str | 框架版本号（eg: `"v1.9.54"`） |
| `ROBOT_START_TIME` | float | 机器人启动时间戳 |
| `AUTO_REPLIES` | dict | 自动回复配置 |

### `security_manager.py`

| 符号 | 类型 | 说明 |
|---|---|---|
| `security_manager` | SecurityManager | 全局单例 |
| `sm.check_permission(user_id, permission)` | method | 返回 `(bool, msg)` |
| `sm.check_master_permission(user_id)` | method | 检查主人权限 |
| `sm.log_audit_event(user_id, action, resource, success, event_type, details)` | method | 记录审计日志 |
| `sm.check_rate_limit(key)` | method | 检查频率限制 |
| `sm.validate_input(data)` | method | 输入安全性校验 |
| `sm.get_user_role(user_id)` | method | 获取用户角色 |

---

## 适配器（`gracy_adapter/`）

### 消息段 `message.py`

```python
from graci import (
    GracyMsg,         # Union 类型别名（消息段联合类型）
    GracyText,        # GracyText(text: str)
    GracyImage,       # GracyImage(file_path=""/url=""/file_data=b"")
    GracyAt,          # GracyAt(target_id: str)
    GracyReply,       # GracyReply(message_id: str)
    GracyVoice,       # GracyVoice(file_path=""/url="")
)
```

### 事件 `event.py`

```python
@dataclass
class GracyEvent:
    sender_id: str          # 发送者
    target_id: str          # 目标
    chat_type: str          # "private" | "group"
    segments: list          # 消息段列表
    raw_text: str           # 原始文本
    message_id: str         # 消息 ID
    nickname: str           # 昵称
    is_at_bot: bool         # 是否 @机器人
    raw_data: dict          # 平台原始数据
    source: Optional[IdentityTag]  # 消息来源适配器标签（多实例路由用）
```

### 发送 `send.py`

> 所有发送函数均为 `async def`，需在异步环境中使用 `await` 调用。

```python
async def gracy_send_msg(
    target: str,            # 目标 ID
    *segments: GracyMsg,    # 消息段（不定参数）
    chat_type: str = "private",  # 聊天类型
    tag: IdentityTag = None      # 适配器标签（None=自动匹配当前上下文）
) -> bool
```

```python
async def gracy_call_api(
    action: str,            # API 动作名
    params: dict = None,    # 请求参数
    tag: IdentityTag = None # 适配器标签（None=自动匹配当前上下文）
) -> Optional[dict]         # 返回 API 响应
```

```python
async def gracy_get_platform_info(
    tag: IdentityTag = None # 适配器标签（None=自动匹配当前上下文）
) -> dict:
    """获取平台信息（登录信息、好友列表、群列表等）"""
```

---

## 装饰器（`decorators/`）

### 命令注册

```python
from graci import (
    on_command,             # @on_command("/cmd1", "/cmd2")
    on_regex,               # @on_regex(r"pattern")
    on_keyword,             # @on_keyword("关键词")
    on_fallback,            # @on_fallback() 兜底处理
    plugin_handler,         # @plugin_handler 核心包装器
    require_permission,     # @require_permission("master")
    require_master,         # @require_master 快捷主人权限
    rate_limit,             # @rate_limit(max_calls=5, period=60)
    cooldown,               # @cooldown(seconds=3)
    with_session,           # @with_session 自动注入 session
    PluginContext,          # handler 上下文类型
)
```

### PluginContext 属性

```python
ctx.sender_id       # str: 发送者
ctx.target_id       # str: 目标
ctx.chat_type       # str: 聊天类型
ctx.nickname        # str: 昵称
ctx.raw_text        # str: 原始文本
ctx.text            # str: 净化文本
ctx.images          # list: 图片 ID
ctx.ats             # list: @的 ID
ctx.is_at_bot       # bool
ctx.command         # str: 匹配命令
ctx.plugin_name     # str: 插件名
ctx.send(*segs)     # method: 发送（async）
ctx.reply(text)     # method: 快捷回复（async）
```

---

## 工具模块（`tools/`）

### `validator.py`

```python
from core.tools.validator import (
    load_plugin_toml,       # 解析 TOML → dict
    TOMLPluginError,        # 校验异常类
    REQUIRED_FIELDS,        # 必填字段集合
)
```

### CLI 注册

```python
from core.tools.cli.plugins import (
    register_cli_command,   # 注册 CLI 子命令
    list_plugins,           # 列出插件
    install_plugin,         # 安装插件
    remove_plugin,          # 卸载插件
)
```

---

## 内置事件（`event/`）

```python
from core.event import event_bus, GracyEvent

event_bus.subscribe("private", handler)   # 订阅私聊事件
event_bus.subscribe("group", handler)     # 订阅群聊事件
event_bus.subscribe("*", handler)         # 通配符订阅
await event_bus.publish(event)            # 发布事件
```

---

## 会话管理（`gracy_session/`）

```python
from core.gracy_session import (
    gracy_get_session,              # 获取会话
    gracy_get_or_create_session,    # 获取或创建
    gracy_destroy_session,          # 销毁会话
    gracy_clear_context,            # 清空上下文
    gracy_get_context,              # 获取上下文
)
```
