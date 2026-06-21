# QQ 官方个人机器人适配器开发指南

> GracyBot v1.9.25+ 新增 `qq_official` 平台适配器
> 本文档记录适配器的实际架构、关键协议和开发约束（根据实现修订）

---

## 一、框架核心约束

### 1.1 禁止修改的文件（core 直系文件）

以下文件**严禁修改**，除非是适配器加载逻辑的必然需求：

```
core/
├── config.py                 # 框架配置项，只读
├── config_manager.py         # 配置管理器
├── security.py               # 日志脱敏工具
├── security_manager.py       # 安全管理器
├── monitor.py                # 监控管理器
├── logger_manager.py         # 日志管理器
├── utils.py                  # 通用工具函数
├── plugin_manager.py         # 插件管理器
├── handler.py                # 旧路径回调处理
└── __init__.py               # 统一导出
```

### 1.2 允许修改的文件

| 文件 | 修改原因 |
|------|---------|
| `core/main.py` | `_register_instance()` 需添加 `qq_official` 分支 |
| `core/gracy_adapter/adapters.json` | 可选，用于适配器注册信息 |

---

## 二、适配器位置

`core/gracy_adapter/qq_official/` — 非插件，直接继承 `GracyAdapter` 抽象基类。

---

## 三、文件架构（实际实现，多文件 Mixin 模式，共 11 个文件）

| 文件 | 职责 | 类/函数 |
|------|------|---------|
| `api.py` | 统一入口门面 | `QQOfficialAPI(AuthMixin, MediaMixin, MessageMixin, BotMixin)` |
| `auth.py` | OAuth2 Token + aiohttp 会话管理 | `AuthMixin` → `get_access_token()`, `_get_session()` |
| `message.py` | HTTP 消息发送（低层 API） | `MessageMixin` → `send_c2c_message()`, `send_group_message()` |
| `media.py` | 富媒体上传（图片/语音） | `MediaMixin` → `upload_rich_media()`, `upload_rich_media_group()` |
| `bot.py` | 机器人信息 + Gateway 接入点 | `BotMixin` → `get_bot_info()`, `get_gateway_url()` |
| `gateway.py` | WebSocket 连接 + 心跳管理 | `QQOfficialGateway` |
| `protocol.py` | 协议转换（官方 Payload ↔ GracyEvent/GracyMsg） | `parse_event()`, `build_send_payload()`, `_convert_segments()` |
| `sender.py` | 消息发送高层封装（上传+降级） | `send_message()` |
| `adapter.py` | 适配器入口，生命周期管理 | `QQOfficialAdapter(GracyAdapter)` |
| `bind.py` | 主从绑定管理器 | `MasterBinding` |
| `factory.py` | 工厂函数 | `create_adapter()` |

---

## 四、关键协议细节

### 4.1 WebSocket 事件格式

```python
{"op": 0, "t": "C2C_MESSAGE_CREATE", "d": {...}}
# "t"=事件类型, "d"=数据体
# 注意：字段名为 "t" 和 "d"，不是 "type" 和 "data"
```

### 4.2 Intents（WebSocket 鉴权）

- `1 << 25` = `GROUP_AND_C2C_EVENT` — 覆盖 `C2C_MESSAGE_CREATE` + `GROUP_AT_MESSAGE_CREATE`
- 错误值：`1 << 30` 和 `(1<<27)|(1<<28)` 都不对

### 4.3 富媒体上传流程

```
1. POST /v2/users/{openid}/files       (私聊)
   POST /v2/groups/{group_openid}/files (群聊)
   → 返回 file_info (有效期字符串)

2. msg_type=7 + media={"file_info": ...} 发送
```

- 图片 `file_type=1`，语音 `file_type=3`
- 上传使用 `file_data`（base64）或 `url` 字段
- `srv_send_msg=False` 只上传不发送，返回 `file_info`

### 4.4 消息发送组合

- `msg_type=7`（富媒体）支持 `content` + `media` 同时发送
- 图片上传后**保留文字**（已修复的 bug）
- 语音和文本不能同时发送（语音优先）

---

## 五、QQ 官方 API 端点

| 功能 | 端点 | 方法 |
|------|------|------|
| 获取 Token | `https://bots.qq.com/app/getAppAccessToken` | POST |
| Gateway 接入点 | `/v2/gateway` | GET |
| 上传私聊媒体 | `/v2/users/{openid}/files` | POST |
| 上传群聊媒体 | `/v2/groups/{group_openid}/files` | POST |
| 发送私聊消息 | `/v2/users/{openid}/messages` | POST |
| 发送群聊消息 | `/v2/groups/{group_openid}/messages` | POST |

---

## 六、消息转换流程

### 入站（QQ 事件 → GracyEvent）

```
WS Payload → gateway.py parse → protocol.py parse_event()
→ GracyEvent(sender_id, target_id, chat_type, segments, nickname, ...)
→ adapter.py wrapped_event → Pipeline
```

### 出站（GracyMsg → QQ 消息）

```
segments → protocol.py build_send_payload() → sender.py send_message()
→ 媒体上传（media.py）→ api.send_xxx_message() → QQ
```

---

## 七、已修复的 Bug 记录

1. **文字+图片丢文字** — `sender.py` 图片上传成功后 `content = ""` 清空文字，已删掉
2. **图片日志显示文件名** — `send.py` 预览日志 `[图片:path]` 改为 `[图片]`
3. **Easysearch 搜索报错** — `main.py` 硬编码 Linux 路径 `/usr/bin/chromium`，改为自动检测
4. **media.py 调试日志** — 去掉文件大小、重试、file_info 截断日志

---

## 八、已知平台限制（不可解决）

- 群聊语音上传返回 500（code=50015014）
- 不支持被加好友、加群、被拉入群
- 语音和文本不能同时发送

---

## 九、适配器实现注意事项

### 9.1 Mixin 组合模式

```python
class QQOfficialAPI(AuthMixin, MediaMixin, MessageMixin, BotMixin):
    def __init__(self, app_id, app_secret, is_sandbox=False):
        self._init_auth(app_id, app_secret, is_sandbox)
```

- `AuthMixin._init_auth()` 必须在 `__init__` 中调用
- Mixin 之间通过 `self` 共享 `_api_base`、`_session` 等属性

### 9.2 日志命名

所有日志 logger 统一使用 `Gracy.QQOfficial.*` 前缀：
```python
_logger = logging.getLogger("Gracy.QQOfficial.media")
```

### 9.3 文件上传

- `file_path` 模式自动读取本地文件做 base64
- 不要添加 `url=""` 空字段（会导致 QQ API 500）
- 上传失败会走降级逻辑（sender.py）

### 9.4 临时文件清理

`sender.py` 中 `file_data` → 临时文件 → 发送完成后 `finally` 块清理
