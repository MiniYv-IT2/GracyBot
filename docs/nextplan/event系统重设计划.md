# 事件系统重设计划

## 现状

- 只有一个 `GracyEvent`（`core/gracy_adapter/event.py`），本质是纯消息结构体
- 4 个适配器（OneBot HTTP/WS、Satori、QQ Official）均在入口静默丢弃非消息事件
- Pipeline 假定只处理消息事件，无事件类型路由
- EventBus 用 `chat_type`（`"private"/"group"`）做事件类型路由

## 缺陷

日常使用中缺失的功能：

- 加群/退群无感知 — 无法自动欢迎
- 好友申请无法处理 — 不能自动审批
- 消息撤回无感知 — 无法记录/防撤回
- 入群欢迎/退群通知做不了
- 群管理变更无感知
- 心跳/重连无感知 — 插件不知道连接状态
- 禁言/解禁无感知

## 事件类型

### 目录结构

```
core/event/
├── __init__.py        # EventBus + event_bus（现有，保留）
├── base.py            # GracyEvent 基类（从 adapter/event.py 移入）
├── message.py         # GracyMessageEvent
├── notice.py          # GracyNoticeEvent + NoticeType 枚举
├── request.py         # GracyRequestEvent + RequestType 枚举
├── meta.py            # GracyMetaEvent + MetaType 枚举
└── system.py          # GracySystemEvent（框架系统事件，无 source）
```

`core/gracy_adapter/event.py` 废弃或简化为 import 转发。

### GracyEvent 基类（base.py）

```
- type: EventType        # 事件类型枚举
- timestamp: float       # 事件发生时间
- raw_data: dict         # 平台原始数据
- cancelled: bool        # 是否被拦截
```

注意：基类 **不包含** `source: IdentityTag`，因为系统事件没有来源适配器。

### GracyMessageEvent（message.py）

消息事件，当前 GracyEvent 的主体内容移到这里：

```
- sender_id: str
- target_id: str
- chat_type: str          # "private" | "group"
- segments: List[GracyMsg]
- raw_text: str
- message_id: str
- nickname: str
- is_at_bot: bool
- source: Optional[IdentityTag]
```

### GracyNoticeEvent（notice.py）

通知事件，所有通知的基类，子类按类型细分：

```
- notice_type: NoticeType
- user_id: str
- target_id: str
- operator_id: Optional[str]
- source: Optional[IdentityTag]
```

NoticeType 枚举：

| 类型 | 说明 |
|------|------|
| `member_add` | 新成员加入群 |
| `member_remove` | 成员退群/被踢 |
| `recall` | 消息撤回（+ message_id） |
| `group_ban` | 群禁言/解禁（+ duration） |
| `group_admin` | 群管理变更（+ is_admin） |
| `group_card` | 群名片变更 |
| `poke` | 戳一戳 |
| `friend_add` | 好友添加 |

### GracyRequestEvent（request.py）

请求事件：

```
- request_type: RequestType
- user_id: str
- comment: str
- flag: str
- source: Optional[IdentityTag]
```

RequestType 枚举：

| 类型 | 说明 |
|------|------|
| `friend` | 好友申请 |
| `group` | 群邀请 |

### GracyMetaEvent（meta.py）

平台元事件：

```
- meta_type: MetaType
- data: dict
- source: Optional[IdentityTag]
```

MetaType 枚举：

| 类型 | 说明 |
|------|------|
| `heartbeat` | 心跳 |
| `connected` | 连接建立 |
| `disconnected` | 连接断开 |
| `lifecycle` | 生命周期（enable/disable） |

### GracySystemEvent（system.py）

框架系统事件（平台无关，无 source）：

```
- system_type: SystemType
- data: dict         # 任意附加数据
```

SystemType 枚举：

| 类型 | 说明 | 发布方 |
|------|------|--------|
| `startup` | 框架启动完成 | main.py |
| `shutdown` | 框架关闭 | main.py |
| `plugin_loaded` | 插件加载 | plugin_manager |
| `plugin_unloaded` | 插件卸载 | plugin_manager |
| `plugin_reloaded` | 插件重载 | plugin_manager |
| `adapter_connected` | 适配器连接 | adapter_pool |
| `adapter_disconnected` | 适配器断开 | adapter_pool |
| `config_changed` | 配置变更 | config_manager |

## 日志格式

日志分类为 `[Core] [Event]`，非 `[Pipeline]`。

```
timestamp - [Core] - INFO - [Event] - [消息事件] 收到消息 | 用户ID: **** | 消息类型: 群聊 | 消息: xxx
timestamp - [Core] - INFO - [Event] - [通知事件] 通知事件 [member_add] | 用户ID: **** | 目标: **** | 操作者: ****
timestamp - [Core] - INFO - [Event] - [通知事件] 通知事件 [recall] | 消息ID: **** | 发送者: **** | 目标: ****
timestamp - [Core] - INFO - [Event] - [请求事件] 请求事件 [friend] | 用户ID: **** | 备注: xxx
timestamp - [Core] - INFO - [Event] - [元事件] 元事件 [heartbeat] | 状态: 正常
timestamp - [Core] - INFO - [Event] - [系统事件] 系统事件 [startup] | 版本: v1.9.57
```

## 需改模块

| 模块 | 改动 |
|------|------|
| `core/event/__init__.py` | EventBus 按 `event.type` 路由，不再按 `chat_type` |
| `core/event/base.py` | 新建，GracyEvent 基类 + EventType 枚举 |
| `core/event/message.py` | 新建，GracyMessageEvent |
| `core/event/notice.py` | 新建，GracyNoticeEvent + NoticeType |
| `core/event/request.py` | 新建，GracyRequestEvent + RequestType |
| `core/event/meta.py` | 新建，GracyMetaEvent + MetaType |
| `core/event/system.py` | 新建，GracySystemEvent + SystemType |
| `core/gracy_adapter/event.py` | 废弃或转发到新位置 |
| `core/gracy_adapter/onebot/ws.py` | 非消息事件不再丢弃，转 | 对应事件类 |
| `core/gracy_adapter/onebot/http.py` | 同上 |
| `core/gracy_adapter/satori/event.py` | 同上 |
| `core/gracy_adapter/satori/adapter.py` | 同上 |
| `core/gracy_adapter/qq_official/gateway.py` | 同上 |
| `core/pipeline/` | 加 `EventRouter` Stage，非消息事件跳过 CommandMatcher |
| `core/plugin_manager.py` | 发出 GracySystemEvent(plugin_loaded/...) |
| `core/adapter_pool.py` | 发出 GracySystemEvent(adapter_connected/...) |
| `core/main.py` | 发出 GracySystemEvent(startup/shutdown) |
| `graci.py` + `__all__` | 导出新事件类 |
| `docs/11-基础API参考.md` | 更新事件类文档 |

## 不改的

- **插件接口**：`from graci import GracyEvent` 继续可用（内部导入路径变）
- **PluginContext**：保持只为消息事件构建，不变
- **tools/**：没有事件要发

## 分阶段实施建议

1. **阶段 1**：建事件类文件 + 基类 + 子类 + 枚举，不改适配器
2. **阶段 2**：修改 EventBus 按 `event.type` 路由 + Pipeline 加 EventRouter
3. **阶段 3**：逐个适配器把非消息事件透传进来
4. **阶段 4**：框架核心加系统事件发出
5. **阶段 5**：更新文档 + 清理旧文件
