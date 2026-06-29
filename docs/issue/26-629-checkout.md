# 2026-06-29 全插件合规审查

> 对比远程 gitee/allnew，扫描全部 14 个插件（style/ 非插件已排除）的规范符合情况。

---

## 总体概览

| 插件 | Logger | 导入 | requests | time.sleep | Handler | 日志前缀 | metadata | 10层 |
|------|--------|------|----------|------------|---------|---------|----------|------|
| **NTE_Guide_Plugin** | ✅ | ✅ | ✅ | ✅ | ✅ 新 | ✅ | ✅ | ✅ |
| **Music_Plugin** | ✅ | ✅ | ✅ | ✅ | ✅ 新 | ⚠️ 冗余 | ✅ | ⚠️ |
| **Genshin_Plugin** | ✅ | ❌ `from core` | ✅ | ✅ | ✅ 新 | ✅ | ✅ | ⚠️ |
| **Help_plugin** | ⚠️ draw.py | ✅ | ✅ | ✅ | ✅ 新 | ✅ | ✅ | ✅ |
| **Easysearch** | ⚠️ 变量名 | ✅ | ✅ | ✅ | ❌ 旧 | ✅ | ✅ | ❌ |
| **Gracone_Plugin** | ❌ 命名 | ✅ | ✅ | ✅ | ✅ 新 | ✅ | ✅ | ⚠️ |
| **GracyUI_plugin** | ❌ 命名 | ✅ | ✅ | ❌ 4处 | ❌ 旧 | ✅已修 | ✅ | ❌ |
| **LLM_Chat** | ❌ 无模块级 | ✅ | ✅ | ❌ 2处 | ❌ 旧 | ❌ 冗余 | ✅ | ❌ |
| **MonitorPlugin** | ❌ `from graci` | ❌同左 | ✅ | ✅ | ❌ 非标 | ❌ 冗余 | ✅ | ❌ |
| **Screenshot** | ⚠️ 变量名 | ✅ | ✅ | ✅ | ❌ 旧 | ❌ 冗余 | ✅ | ❌ |
| **SysInfo_plugin** | ⚠️ 变量名 | ✅ | ✅ | ✅ | ❌ 旧 | ⚠️ draw.py | ✅ | ❌ |
| **Update_Plugin** | ❌ `from graci` | ✅ | ✅ | ✅ | ❌ 旧 | ❌ 冗余 | ✅ | ❌ |
| **Xiaoyu_plugin** | ❌ `from graci` | ✅ | ✅ | ❌ 1处 | ❌ 旧 | ❌ 冗余 | ✅ | ❌ |
| **ExamplePlugin** | ❌ `from graci` | ✅ | ✅ | ✅ | ❌ 旧同步 | ⚠️ | ✅ | ❌ |

### 图例
| 符号 | 含义 |
|------|------|
| ✅ | 符合规范 |
| ⚠️ | 轻微违规 |
| ❌ | 严重违规 |

---

## 违规分类统计

| 问题类型 | 涉及插件 | 数量 |
|---------|---------|------|
| **`from graci import logger`** ❌ | ExamplePlugin, MonitorPlugin, Update_Plugin, Xiaoyu_plugin, Help_plugin/core/draw.py | 5 |
| **`from core.xxx import`** ❌ | Genshin_Plugin | 1 |
| **Logger 命名缺失 `Gracy.` 前缀** | （Gracone/GracyUI 为系统插件，允许独立分类） | 0 |
| **`time.sleep()`/`_time.sleep()`** ❌ | GracyUI (4), LLM_Chat (2), Xiaoyu (1) | 3 |
| **消息中冗余 `[模块名]` 前缀** | Music_Plugin, LLM_Chat, MonitorPlugin, Screenshot, Update_Plugin, Xiaoyu_plugin, SysInfo_plugin/draw.py | 7 |
| **旧风格 handler** | Easysearch, ExamplePlugin, GracyUI, LLM_Chat, MonitorPlugin, Screenshot, SysInfo, Update_Plugin, Xiaoyu | 9 |
| **变量名用 `logger` 非 `_logger`** | Easysearch, Screenshot, SysInfo_plugin | 3 |

---

## 各插件详情

### NTE_Guide_Plugin — 唯一完全合规 ✅

全项通过，新风格模范插件。

### Music_Plugin
- ✅ Logger: `_logger = logging.getLogger("Gracy.Music")`
- ✅ 新风格 handler: `async def handler(ctx: PluginContext)`
- ⚠️ 日志消息含 `[音频]` `[点歌]` `[搜索]` `[播放]` `[绘图]` 等功能标签（非模块名重复，但可清理）
- ⚠️ 10层：常量 `DATA_DIR` 定义在状态变量 `_last_*` 之后，应互换

### Genshin_Plugin
- ✅ Logger: `_logger = logging.getLogger("Gracy.Genshin")`
- ✅ 新风格 handler
- ❌ **`from core.decorators import on_command, plugin_handler, PluginContext`** (L27)
- ❌ **`from core.gracy_adapter.message import GracyImage, GracyText`** (L29)
  - 应改为 `from graci import on_command, plugin_handler, PluginContext, GracyImage, GracyText`

### Help_plugin
- ✅ 主文件干净，新风格
- ❌ **`core/draw.py:9`**: `from graci import logger` → 应改为 `logging.getLogger("Gracy.Help.draw")`

### Easysearch
- ⚠️ Logger 变量名用 `logger`，建议改为 `_logger`
- ❌ 旧风格 handler
- ❌ 缺模块文档（Layer 1）

### Gracone_Plugin
- ✅ 新风格 handler
- ✅ Logger: 系统插件，使用独立 `"Gracone"` 分类（允许）

### GracyUI_plugin
- ✅ 日志前缀已修（本日修复）
- ✅ Logger: 系统插件，使用独立 `"GracyUI"` 分类（允许）
- ❌ **`_time.sleep()` 4 处**（L49,61,67,169）
- ❌ 旧风格 handler 无装饰器

### LLM_Chat
- ❌ 无模块级 logger（依赖 `log_func` 参数）
- ❌ **`time.sleep(10)` `time.sleep(30)`** in `core/scheduler.py:126,129`
- ❌ 日志冗余前缀 `[视觉模型]` `[定时任务]` `[私聊对话]` `[群聊对话]`
- ❌ 缺模块文档和模块级 logger

### MonitorPlugin
- ❌ **`from graci import logger`** (L5)
- ❌ Handler 非标准 `handle_monitor(*args, **kwargs)`
- ❌ 所有日志 `[MonitorPlugin]` 前缀冗余
- ❌ 10层大面积缺失

### Screenshot
- ⚠️ Logger 变量名 `logger` 应 `_logger`
- ❌ 旧风格 7 参数 handler
- ❌ 日志 `[插件执行] [Screenshot]` 前缀冗余
- ❌ 缺模块文档

### SysInfo_plugin
- ⚠️ Logger 变量名 `logger` 应 `_logger`
- ❌ 旧风格 handler
- ❌ `draw.py` 日志 `[SysInfo⏱]` 前缀（本日已修主文件，draw.py 尚未修）
- ❌ `sys.path.append()` 模块级执行
- ❌ 10层顺序：`.core.draw` import 在 logger 和 constants 之后

### Update_Plugin
- ❌ **`from graci import logger`** (L20)
- ❌ 旧风格 handler
- ❌ 所有日志 `[Update_Plugin]` 前缀冗余
- ❌ 多处内联 import（如 `from graci import BOT_VERSION`）

### Xiaoyu_plugin
- ❌ **`from graci import logger`** (L16)
- ❌ **`time.sleep(2)`** in `_restart_bot` (L496)
- ❌ 旧风格 handler
- ❌ 所有日志 `[小禹插件]` 前缀冗余
- ❌ `import logging` (L11) 导入未使用
- ❌ `import asyncio` (L21) 与 stdlib import 分离

### ExamplePlugin
- ❌ **`from graci import logger`** (L5)
- ❌ 旧风格同步 handler `def handle_example(...)`
- ⚠️ `[示例插件]` 前缀（非模块名重复，但可清理）
- ❌ 完全旧风格，无 10 层结构

---

## 已在本日修复的违规

| 文件 | 修复内容 |
|------|---------|
| `plugins/SysInfo_plugin/SysInfo_plugin.py` | 5 处 `[SysInfo]`/`[SysInfo⏱]` 前缀移除 |
| `plugins/GracyUI_plugin/GracyUI_plugin.py` | 13 处 `[GracyUI]` 前缀移除 |
| `core/security_manager.py` | 2 处 `[SecurityManager]` 前缀移除 |

---

## 建议修复优先级

| 优先级 | 问题 | 涉及插件 |
|--------|------|---------|
| P0 | `from graci import logger` → `logging.getLogger()` | 5 个插件 |
| P0 | `from core.xxx import` → `from graci import` | Genshin_Plugin |

| P1 | `time.sleep()` → `asyncio.sleep()` | GracyUI, LLM_Chat, Xiaoyu |
| P2 | 日志消息冗余前缀清理 | Music_Plugin, LLM_Chat, MonitorPlugin, Screenshot, Update_Plugin, Xiaoyu, SysInfo/draw.py |
| P3 | 旧风格 → 新风格迁移 | 9 个插件 |
| P4 | 变量名 `logger` → `_logger` | Easysearch, Screenshot, SysInfo |
