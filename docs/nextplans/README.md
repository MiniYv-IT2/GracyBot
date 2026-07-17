# Next Plans

## 0. 基础解耦 — graci.py 外观层 + 插件 import 统一（最高优先）

### 目标

框架内部随便重构，插件不用改代码。

### 方案

在项目根目录创建 `graci.py`（外观层），插件只 `from graci import xxx`，不再直接 `from core.xxx`。

```
插件 → graci.py（~90 行转发）→ core（内部随便改）
```

### 改动范围

**新建文件：**
- `graci.py` — 纯转发，~90 行 import

**修改文件（插件 import 替换）：**

| 插件 | 改动量 |
|------|--------|
| `plugins/Music_Plugin/Music_Plugin.py` | 换 3 行 import |
| `plugins/NTE_Guide_Plugin/NTE_Guide_Plugin.py` | 换 2 行 import |
| `plugins/Help_plugin/Help_plugin.py` | 换 3 行 import |
| `plugins/Help_plugin/core/draw.py` | 换 1 行 import |
| `plugins/Gracone_Plugin/gracone_admin.py` | 换 3 行 import |
| `plugins/Gracone_Plugin/gracone_core.py` | 换 2 行 import |
| `plugins/Gracone_Plugin/bridge.py` | 换 2 行 import |
| `plugins/Gracone_Plugin/api_bridge.py` | 换 2 行 import |
| `plugins/LLM_Chat/LLM_Chat.py` | 换 3 行 import |
| `plugins/Xiaoyu_plugin/Xiaoyu_plugin.py` | 换 4 行 import |
| `plugins/SysInfo_plugin/SysInfo_plugin.py` | 换 4 行 import |
| `plugins/Easysearch/Easysearch.py` | 换 2 行 import |
| `plugins/Update_Plugin/Update_Plugin.py` | 换 2 行 import |
| `plugins/MonitorPlugin/MonitorPlugin.py` | 换 2 行 import |
| `plugins/ExamplePlugin/ExamplePlugin.py` | 换 2 行 import |
| `plugins/GracyUI_plugin/GracyUI_plugin.py` | 换 3 行 import |
| `plugins/Screenshot/Screenshot.py` | 换 1 行 import |
| `plugins/Screenshot/main.py` | 换 1 行 import |

**不改的文件：**
- `core/` 下所有内部模块 — 不动
- `metadata.toml` — 不动
- 插件业务逻辑 — 不动

### 实施步骤

1. 创建 `graci.py`，导出所有插件用到的公共 API
2. 逐个插件替换 import（新式插件先改，旧式插件等 handler 统一时一起改）
3. 验证：运行 `python -c "from graci import GracyText, gracy_send_msg, PluginContext"` 确认导入正常
4. 验证：启动 bot，测试几个插件命令正常响应

### 效果

- 改完后框架内部随便重构，只要 `graci.py` 转发不变，插件零改动
- 插件代码更简洁：`from graci import GracyText` 代替 `from core.gracy_adapter.message import GracyText`
- 后续 handler 签名统一（旧式→新式）也在这个基础上做

---

## 1. 插件系统统一 — 旧式 handler 迁移到 PluginContext

### 背景

基础解耦完成后，下一步统一 handler 签名风格。当前两种风格并存：

- **旧式 7 参数**：`handler(self_bot, bot, message, user_id, chat_type, permission, log_func)`
- **新式 PluginContext**：`handler(ctx: PluginContext)`

### 目标

- 所有插件迁移到 `PluginContext` 新式风格
- 废弃旧式 7 参数 handler
- 框架改动时只需适配一处接口

### 涉及插件

LLM_Chat、Xiaoyu_plugin、SysInfo_plugin、Easysearch、Update_Plugin、MonitorPlugin、ExamplePlugin、GracyUI_plugin、Screenshot

### 与基础解耦的关系

基础解耦（步骤 0）先统一 import 路径，步骤 1 再统一 handler 签名。两者独立，但步骤 1 依赖步骤 0 完成。

---

## 2. Satori 适配器开发

### 背景

Satori 是通用聊天协议，已有 Python SDK（`satori-python` v1.3.5），支持 15+ 平台。

### 可行性

- 难度：中等偏低
- 与插件统一并行：可行（适配器层与插件层独立）
- 现阶段条件：满足（GracyAdapter 基类已定义）

### 开发计划

1. 实现 `GracyAdapter` 接口的 Satori 适配器
2. Satori 事件 → GracyEvent 映射
3. GracyMsg → Satori 消息元素转换
4. 注册到 AdapterPool
5. 测试验证

---

## 3. 日志系统优化

### 现状

- 全局日志：`logs/gracybot.log` + `logs/gracybot_error.log`
- 实例日志：`logs/instances/<name>/runtime.log`（仅初始化信息）

### 待办

- 暂不改动
- 后续可考虑让 runtime logger 实际记录运行时事件
