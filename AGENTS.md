# AGENTS.md — GracyBot 开发规范

> 此文件约束 AI 助手在本项目中的所有行为。每次会话自动加载。

---

## 重要：信息读取优先级

1. **先读本文件（AGENTS.md）** — 项目规范、分支、适配器状态
2. **再读 `docs/` 下带数字前缀的 `.md`** — 如 `docs/05-插件开发指南（新风格）.md`
3. **最后读 `graci.py` 的 `__all__`** — 了解可用 API 符号
4. **项目记忆仅作为辅助参考** — 可能过时，以实际代码和文档为准

---

## 分支说明

- **当前工作分支：`allnew`** — 唯一活跃分支
- **远程旧分支（`dev-old`, `dev2`, `devpreview-backup1`, `oldout`, `main`）** — 均为 V1.9.2 时代代码，与 `allnew` 完全不兼容，不应参考
- **`git branch -a` 看到但不在上表的** — opencode 自动分支，可忽略

---

## 适配器支持状态

| 适配器 | 状态 |
|--------|------|
| Satori | 可用但开发不够完善，需继续优化（图片 base64 发送、Gracone 桥接等） |
| OneBot | 可用 |
| QQ Official | 可用（基本功能） |

所有适配器位于 `core/gracy_adapter/`。

---

## 项目概述

GracyBot 是 IM 多平台轻量异步机器人框架，基于 asyncio + Quart。
- 框架可独立脱离，与具体平台和业务解耦
- 外观层：`graci.py`（插件统一 `from graci import ...`）
- 适配器层：`core/gracy_adapter/`（Satori / OneBot / QQ Official）
- 入口：`core/main.py`，启动命令：`gracy run`，停止命令：`gracy stop`
- 插件目录：`plugins/`，每个插件一个子目录
- 配置目录：`style/config/`

---

## Git 规则（严格执行）

1. **只用 `git add <具体文件>`**，绝不用 `git add .` 或 `git commit -a`
2. **提交前先 `git diff --name-only`** 预览变更
3. **提交消息用中文**，格式：`类型: 简述`（如 `fix: 修复xxx`、`feat: 新增xxx`、`docs: 更新文档`）
4. **不要切换分支**，除非用户明确要求
5. **不要推送到 Gitee**，只推 GitHub（Gitee 自动同步）
6. **用户说"提交GitHub"就执行 push**（关键词触发）

---

## 插件开发规范（新风格 10 层顺序）

所有新插件和迁移的旧插件必须遵循此顺序：

```
第 1 层：模块文档        """描述"""
第 2 层：标准库          import os, logging
第 3 层：第三方库        import httpx
第 4 层：框架API         from graci import on_command, PluginContext, get_logger
第 5 层：本地模块        from .core.api import xxx
第 6 层：日志器          logger = get_logger("插件名")
第 7 层：常量            DATA_DIR = ...
第 8 层：模块级状态      _cache = []
第 9 层：辅助函数        async def _helper():
第10 层：装饰器+Handler  @on_command → @plugin_handler → async def
```

### 导入规范

- **统一从 `graci` 导入**：`from graci import on_command, PluginContext, get_logger`
- **禁止**：`from core.xxx import`、`from gracy import *`
- 插件日志用 `from graci import get_logger; logger = get_logger("插件名")`，禁止 `import logging` 创建日志器

### Handler 签名

- **新风格（推荐）**：`async def handler(ctx: PluginContext)`
- **旧风格（兼容）**：`async def handler(self_bot, bot, message, user_id, chat_type, permission, log_func)`
- Pipeline 通过 `len(params)` 自动判断

### metadata.toml

- 保留完整格式（name, version, author, description, icon 等）
- TOML 管展示（给插件商店），装饰器管注册，两者共存以装饰器为准
- 详见 `docs/08-metadata.toml规范.md`

### 完整模板

见 `docs/05-插件开发指南（新风格）.md` 的"标准插件模板"章节。

## 插件开发工作流（必须按顺序执行）

拿到插件开发任务时，不要慌，按以下步骤：

1. **先看文档**：读 `docs/05-插件开发指南（新风格）.md` 和 `docs/08-metadata.toml规范.md`
2. **看项目结构**：读 `plugins/` 下已有的新风格插件（如 Help_plugin、Music_Plugin）作为参考
3. **了解 API**：读 `graci.py` 的 `__all__` 列表，知道有哪些可用符号，不用全部看
4. **写代码**：按 10 层顺序写，参考模板
5. **写完检验**：
   - 检查语法错误（import 是否正确、缩进是否对）
   - 检查是否符合 10 层书写顺序
   - 检查是否用 `from graci import` 而非 `from core.xxx import`
   - 检查 metadata.toml 字段是否完整
6. **汇报结果**：告诉用户写了什么、改了什么

### 边界规则

- **插件开发一般不准涉及框架和适配器的修改**
- 如果发现框架设计缺陷导致插件难以实现，**主动给用户建议**，用户要求改才可以改
- 未经用户允许，不要查看无关内容（框架内部实现、适配器源码等）
- **GracyBot-GUI 是独立项目**，可以查看但不要修改，不要纳入本项目管理

---

## 文件操作规则

1. **编辑前必须先 `Read` 文件**，不要凭记忆修改
2. **优先编辑现有文件**，不要随意创建新文件
3. **不要删除用户文件**，除非用户明确要求
4. **不要覆盖本地文件或改变时间戳**（git 操作时尤其注意）

---

## 沟通规则

1. **简洁回答**，不超过 4 行，除非用户要求详细
2. **不要加多余解释**，直接给答案
3. **不要用 emoji**，除非用户要求
4. **不确定就问**，不要猜

---

## 禁止事项

- 禁止 `git add .` / `git commit -a`
- 禁止 `git push` 到 Gitee
- 禁止切换分支（除非用户要求）
- 禁止删除 `.gracybot_disabled.json`（用户自己管理插件启用状态）
- 禁止在插件中 `from core.xxx import`（统一用 `from graci import`）
- **禁止 `import logging` 创建日志器**（统一用 `from graci import get_logger`，仅 `logging.exception()` 例外）
- 禁止强杀进程（用 `gracy stop`）
- **禁止 `import requests`**，必须用异步库：`httpx`、`asyncio`、`aiohttp`

---

## 异步规范

100% 异步优先。整个框架基于 asyncio，所有网络调用必须用异步库。

| 禁止 | 替代 |
|------|------|
| `import requests` | `import httpx`（推荐）或 `import aiohttp` |
| `requests.get()` | `async with httpx.AsyncClient() as c: await c.get()` |
| `time.sleep()` | `await asyncio.sleep()` |
| 同步阻塞调用 | `await loop.run_in_executor(None, func)` |

---

## 改 Bug 规范

改 bug 时必须遵守以下原则：

### 必做

1. **修完校验语法**：`python -c "import plugins.XxxPlugin.XxxPlugin"` 或逐文件检查
2. **跑一下看日志**：`gracy run`，确认无报错、功能正常
3. **修 bug 本身**：定位根因，精确修复，不要扩大改动范围

### 严禁

- **不准为了图轻松搞耦合**：bug 在框架就改框架，bug 在插件就改插件，不能为了让两边都能跑而互相迁就
- **不准随便删变量或改变量名**：可能有其他地方引用，除非确认无影响
- **不准随意移动代码位置**：在原位置改，不重构
- **不准随意改动框架结构**：框架结构改动需谨慎，必须和用户确认

### 允许

- 添加新功能、新变量、新方法
- 修改现有逻辑（在原位置）
- 框架结构改动（需用户确认）

---

## AI 行为约束

- **改代码前必须等用户说"开始改"**，或者小幅度修改（如 typo、明显 bug）可以直接改
- 不确定改动范围时，先问用户

---

## 文档同步规则

框架变动时，必须同步更新文档：

| 框架变动 | 需同步的文档 |
|----------|-------------|
| 新增/删除/重命名 `graci.py` 符号 | `docs/11-API参考.md`、`docs/05-插件开发指南.md` 中的示例 |
| 装饰器签名变化 | `docs/05-插件开发指南.md`、`docs/14-最佳实践.md` |
| 新增适配器或适配器改名 | `docs/04-项目架构.md`、`README.md` |
| 插件目录结构变化 | `docs/04-项目架构.md` |
| Pipeline/Stage 变化 | `docs/04-项目架构.md` |
| **框架版本号更新** | `README.md`（项目概述中的版本号）、`docs/11-API参考.md` |

### 规则

1. **改框架代码后**，检查上述文档是否需要同步更新
2. **版本号变化时**，更新 `README.md` 中的版本号
3. **不确定要不要改**，问用户
