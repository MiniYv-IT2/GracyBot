<p align="center">
  <img src="res/resource/gracy.png" alt="GracyBot" width="200" />
</p>

<h1 align="center">GracyBot</h1>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/Platform-Windows%20|%20Linux%20|%20macOS-lightgrey" alt="Platform" />
  <img src="https://img.shields.io/badge/Status-Active-brightgreen" alt="Status" />
  <img src="https://img.shields.io/badge/License-MIT-green" alt="License" />
  <img src="https://img.shields.io/badge/Version-v2.0.0test-orange" alt="Version" />
</p>

<p align="center">
  <strong>中文</strong> | <a href="README_EN.md">English</a>
</p>

> 想给自己的 QQ 搞个智能机器人？GracyBot 就是为此而生的。基于 **Python 3.11+** 的个性化定制 QQ 机器人框架，支持 **NapCat (OneBot)** 与 **QQ 官方个人机器人 API** 双协议，主打安全稳定、插件化扩展与便捷更新。

**作者**：小禹 / MiniYv | 湖南汽车工程职业大学 · 计算机网络技术专业
**团队**：GracyBot 开发团队
📧 **邮箱**：bc333333@163.com | 🐧 **QQ**：192004908 | 📢 **内测群**：127531571

敲代码、做项目是真正让我感到充实和热爱的事。学历可以定义起点，但不能框住眼界和天花板——GracyBot 就是在这份坚持下从零搭建起来的，希望它能帮到更多想动手做 QQ 机器人的朋友。

如果你在使用过程中遇到困难，或者想参与开发、交流讨论，欢迎加入内测群，我们一起让 GracyBot 变得更好！

---

## 目录

- [更新变化](#更新变化)
- [核心特性](#核心特性)
- [项目结构](#项目结构)
- [环境要求](#环境要求)
- [内置指令](#内置指令)
- [插件列表](#插件列表)
- [插件开发](#插件开发)
- [安全防护](#安全防护)
- [连接模式](#连接模式)
- [技术栈](#技术栈)
- [开发计划（Roadmap）](#开发计划roadmap)
- [调试命令参考](#调试命令参考)
- [声明](#声明)
- [许可证](#许可证)

---

## 更新变化

### v1.9.54 (2026-06-21)

#### 🚀 QQ 官方个人机器人适配器（重大更新）
新增 `qq_official` 适配器，支持 QQ 官方个人机器人 API v2（WebSocket Gateway），无需 NapCat 即可运行。

**架构变更**：从单文件拆分为 11 文件 Mixin 多模块架构：

`api.py` + `auth.py` + `message.py` + `media.py` + `bot.py` + `gateway.py` + `protocol.py` + `sender.py` + `adapter.py` + `bind.py` + `factory.py`

| 模块 | 说明 |
|------|------|
| **Gateway 长连接** | WebSocket 连接与会话保持，支持自动重连与心跳 |
| **OAuth2 鉴权** | 自动获取与续期 Access Token |
| **富媒体上传** | 图片、语音的本地文件/base64 上传链路 |
| **消息转换** | QQ 官方 Payload ↔ GracyEvent 双向转换 |

#### 🎯 新增 Gracone 兼容层插件
`Gracone_Plugin` — 让 NoneBot 插件可直接运行在 GracyBot 上。

目前已适配的 NoneBot 插件：
- **中国象棋**（cchess）— 人机对战，含 Stockfish 引擎
- **Kawaii 状态图**（nonebot_plugin_kawaii_status）— 系统状态图生成

#### 🧹 适配器代码优化
- **统一日志命名**：`Gracy.QQPersonal` → `Gracy.QQOfficial`
- **裁剪调试日志**：移除 media.py 冗余重试逻辑和文件大小日志
- **删除硬编码**：Easysearch 等插件不再写死 Linux 路径 `/usr/bin/chromium`
- **修复文字+图片组合发送**：`sender.py` 中 `content = ""` bug 导致图片上传后文字丢失

### v1.9.25 (2026-06-12)

#### 🚀 多实例多账号支持（重大更新）
**问题背景**：v1.9.2 只支持单 QQ 号运行。插件硬编码全局 `ROBOT_ID` 和 `MASTER_ID`，无法区分是哪个账号收到的消息，也无法按账号回复。

**变更内容**：从架构层面引入多实例支持，一个 GracyBot 进程可同时登录多个 QQ 号，各账号独立运行。

| 模块 | 变更 |
|------|------|
| **AdapterPool** | 适配器池，支持注册多个适配器实例，按 `IdentityTag`（platform + bot_name）索引 |
| **实例配置文件** | 每个实例独立配置于 `res/instances/<name>/config.json`，含 `robot_id`、`master_id`、`http_url`、`callback_port` |
| **消息路由** | 根据 NapCat 回调的 `self_id` 自动匹配对应适配器实例，消息来源与回复一一对应 |
| **Pipeline 上下文** | 自动为每个消息绑定来源适配器实例，所有消息发送自动走对账号 |
| **CLI 实例管理** | `gracy instance add` / `gracy instance list` / `gracy instance remove` |

#### 📦 插件开发兼容性
- 新增 `get_current_robot_id()` — 替代 `from core.config import ROBOT_ID`，自动返回当前消息来源的 QQ 号
- 新增 `get_current_master_id()` — 替代 `from core.config import MASTER_ID`，自动返回当前消息来源实例的主人 QQ
- 旧风格插件无需修改代码，Pipeline 自动按来源适配器路由消息发送
- `gracy_send_msg()` / `gracy_call_api()` / `gracy_get_platform_info()` 无 tag 时自动适配当前消息来源

#### 🐛 问题修复
- **自回显过滤**：HTTP 适配器 `parse_event()` 增加自回显过滤（`sub_type=self`、`sender_id==self_id`），避免 NapCat 回显消息进入 Pipeline 二次处理
- **回调早返**：`parse_event()` 返回 None 时（非消息事件、自回显等）直接返回，不再执行 `callback_base()`，消除多余的"请求处理成功"日志
- **日志性能**：恢复使用 `io.TextIOWrapper(sys.stdout.buffer)` 作为日志控制台处理器，避免 Hypercorn 接管 stdout 后日志丢失

### v1.9.2 (2026-05-31)

#### 🔧 Linux 跨平台兼容性修复
**问题描述**：在 Linux 系统（Debian/Ubuntu/CentOS 等）下运行 Bot 时，SysInfo 等插件在执行 `/运行状态` 命令时偶发 `NameError: name 'time' is not defined` 或 `NameError: name 'ThreadPoolExecutor' is not defined`，而 Windows 完全正常。  
**根因分析**：Linux 默认使用 `fork` 机制创建子进程，该机制直接复制父进程内存，不会重新执行模块级 `import` 语句。在热重载（Werkzeug reloader）或多线程并发场景下，部分标准库（如 `time`、`concurrent.futures`）的命名空间在 fork 后的子进程中丢失或未被正确继承，导致运行时 `NameError`。Windows 默认使用 `spawn` 模式，每次重新初始化解释器，因此不会出现此问题。  
**修复方案**：在 `core/main.py` 入口统一设置 `multiprocessing.set_start_method('spawn')`，强制 Linux 使用与 Windows 一致的进程启动方式，从根源上消除 fork 带来的命名空间不一致问题。启动耗时增加约 0.5s（仅一次），日常消息响应速度无影响。此修复为框架级底层修复，对插件开发者完全透明。

#### 📄 配置文件（config.json）逻辑统一维护
**变更说明**：`config.json` 原为仅针对 OneBot（NapCat）登录方案的单协议配置文件，v1.9.2 升级为 **全平台统一配置中心**。  
**变更前**：包含 `napcat_http_url`、`ws_host`、`ws_port`、`access_token` 等 NapCat 协议专用字段，功能局限于 HTTP 回调与 WS 连接配置，维护分散。  
**变更后**：移除 NapCat 专用冗余字段，统一使用 `connection_mode`（`http` / `ws_forward` / `ws_reverse`）选择连接模式，保留基础身份配置（`robot_id`、`master_id`、`callback_port`）的同时，新增以下模块，实现单一文件全局管控：

| 模块 | 字段 | 说明 |
|------|------|------|
| **日志系统** | `log_encoding`、`log_level`、`debug_mode` | 编码、级别、调试模式开关 |
| **AI 模型** | `openai_api_key`、`openai_model`、`openai_api_base`、`openai_default_character` | 对接 OpenAI 兼容 API，支持自定义模型与基地址 |
| **自动回复** | `auto_replies` | 关键词 → 回复语字典，免插件实现快捷自动应答 |

**优势**：一处配置、全局生效；不再需要额外维护多个配置文件或硬编码参数。后续扩展多协议适配器（Telegram/Discord 等）时，只需在同一文件中追加对应平台配置块即可。

---

## 核心特性

- **模块化架构** — 配置管理 / 日志系统 / 安全模块 / 监控面板 / 插件管理器分离，职责清晰
- **多协议适配（GracyAdapter）** — 统一适配层，支持 OneBot (NapCat) HTTP/WebSocket 与 QQ 官方个人机器人 WebSocket Gateway 双协议
- **多实例多账号** — 单进程支持多个 QQ 号同时在线，各账号独立配置、独立路由、独立处理，`gracy instance` CLI 命令管理实例
- **企业级安全防护** — 日志自动脱敏（QQ号/API Key/密码）、危险命令拦截、输入验证、频率限制、权限分级、审计日志
- **插件化生态** — 插件即目录，放入 `plugins/` 自动注册，支持版本控制、依赖管理、循环依赖检测、热重载
- **AI 对话** — 内置 LLM_Chat 插件，对接 OpenAI 兼容 API，支持多人设切换、上下文记忆、定时任务、戳一戳互动
- **监控与可观测性** — 结构化日志、CPU/内存/消息统计、健康检查端点（`/health`、`/metrics`、`/status`）
- **Web 管理面板（GracyUI）** — 基于 React + TypeScript + TailwindCSS 的可视化 Bot 管理界面
- **跨平台** — 适配 Windows 10+ / Linux（Debian 11+）/ macOS

---

## 项目结构

```
gracybot/
├── bot.py                       # 程序入口
├── graci.py                     # 兼容层：转发到 gracybot.graci（旧插件兼容）
├── config.json                  # 全局机器人配置
├── requirements.txt             # 依赖清单
│
├── gracybot/                    # 顶级包（命名空间）
│   ├── __init__.py              # 包初始化
│   ├── graci/                   # 插件公共 API 包
│   │   ├── __init__.py          # 统一导出
│   │   ├── messages.py          # GracyText, GracyImage 等
│   │   ├── decorators.py        # on_command, plugin_handler 等
│   │   ├── context.py           # PluginContext
│   │   └── core_api.py          # 发送函数、配置、服务等
│   │
│   ├── core/                    # 核心框架
│   │   ├── __init__.py          # Core 类（延迟加载）
│   │   ├── main.py              # 启动/关闭/心跳
│   │   ├── plugin_manager.py    # 插件扫描/加载/注册
│   │   ├── config.py            # 框架级配置常量
│   │   ├── config_manager.py    # 集中化配置管理
│   │   ├── security.py          # 安全工具
│   │   ├── security_manager.py  # 安全管理器
│   │   ├── monitor.py           # 系统监控
│   │   ├── logger_manager.py    # 结构化日志管理
│   │   ├── utils.py             # 工具函数
│   │   ├── event/               # 事件总线
│   │   ├── pipeline/            # 消息处理管道
│   │   ├── runtime/             # Runtime（实例上下文）
│   │   ├── decorators/          # 装饰器
│   │   ├── webserv/             # Quart Web 服务
│   │   ├── gracy_adapter/       # 多协议适配层
│   │   │   ├── adapter.py       # 适配器抽象基类
│   │   │   ├── event.py         # 统一事件模型
│   │   │   ├── message.py       # 消息段类型
│   │   │   ├── send.py          # 统一消息发送
│   │   │   ├── onebot/          # OneBot 平台实现
│   │   │   ├── qq_official/     # QQ 官方机器人
│   │   │   └── satori/          # Satori 协议适配器
│   │   └── tools/               # CLI、日志工具等
│   │
│   └── plugins/                 # 插件目录
│
├── res/                         # 样式/资源
│   ├── gracybot_logo.py         # 启动 Logo
    ├── log_colors.py           # 日志配色
    ├── styling.py              # 样式工具
    └── instances/               # 多实例配置文件（每个 QQ 号一个目录）
        ├── 主号/
        │   └── config.json     # 实例配置：robot_id、master_id、http_url、callback_port
        └── 小号/
            └── config.json
```

---

## 环境要求

- **Python**: 3.11+
- **NapCat（可选）**: OneBot v11 协议端，使用 OneBot 适配器时必备
- **QQ 官方机器人（可选）**: 使用 QQ 官方个人机器人适配器时无需 NapCat，需前往 QQ 开放平台注册
- **Python 依赖**: Quart、aiohttp、psutil、Pillow、py-cpuinfo（详见 `requirements.txt`）
- **Node.js / npm**: 18+
- **前端依赖**: React、TypeScript、Vite、TailwindCSS（GracyUI 插件内置，`npm install` 即可）
- **操作系统**: Windows 10+ / Linux（Debian 11+）/ macOS
- **AI 对话（可选）**: 任意 OpenAI 兼容 API（默认对接 DeepSeek）

---

## 内置指令

| 指令 | 说明 | 权限 |
|---|---|---|
| `/关机` | 关闭机器人服务 | 仅主人 |
| `/重启` | 重启机器人服务 | 仅主人 |
| `/开机` | 启动机器人服务 | 仅主人 |
| `/关于` | 查看机器人框架信息 | 所有人 |

---

## 插件列表

| 插件 | 说明 |
|---|---|
| **LLM_Chat** | AI 对话，多人设切换、上下文记忆、定时任务、戳一戳互动 |
| **帮助插件** | 生成帮助图片，展示所有可用命令 |
| **SysInfo_plugin** | 查看系统资源占用与运行详情 |
| **小禹插件** | 核心控制中枢：时间查询、QQ 变更、黑名单、热重载开关、依赖安装 |
| **GracyUI** | Web 可视化 Bot 管理面板 |
| **MonitorPlugin** | 查看系统状态与性能指标 |
| **Gracone** | NoneBot 插件兼容层（象棋、状态图等） |

---

## 插件开发

插件采用「即插即用」设计，主推 `metadata.toml` + `@plugin_handler` 新风格（建议新插件使用），同时向下兼容旧风格 7 参数签名。

### 新风格（推荐）

在 `plugins/<插件名>/` 下创建 `metadata.toml` 和插件文件：

```toml
[plugin]
name        = "我的插件"
version     = "1.0.0"
author      = "作者"

[handler]
entry       = "handle_my_plugin"

[trigger]
commands       = ["/mycommand"]
chat_type      = ["private", "group"]
permission     = "all"           # "all" 或 "master"
is_at_required = false
```

```python
from core.decorators.handler import plugin_handler

@plugin_handler
async def handle_my_plugin(ctx):
    await ctx.reply("Hello from GracyBot!")
```

### 多账号适配

插件内需要获取当前 QQ 号或主人 QQ 时，使用以下 API 代替全局 `import`：

```python
from graci import get_current_robot_id, get_current_master_id

# 获取当前消息来源的机器人 QQ（多账号时自动适配）
qq = get_current_robot_id()

# 获取当前消息来源实例的主人 QQ
master = get_current_master_id()
```

### 旧风格（兼容）

```python
def handle_my_plugin(plugin_manager, send_msg, data, sender_id, chat_type, target, logger):
    # 你的插件逻辑
    pass
```

---

## 安全防护

- **日志脱敏** — 自动隐藏 QQ 号、群 ID、API Key、密码等敏感信息
- **危险命令拦截** — 正则匹配 `rm -rf`、`shutdown`、`reboot` 等危险命令
- **输入验证** — XSS 防护、敏感字符过滤、长度限制
- **频率限制** — 基于 IP 和用户 ID 的请求频率控制
- **权限分级** — `master`（仅主人）/ `all`（所有人）两级权限
- **审计日志** — 记录用户操作、插件执行、权限校验等关键事件

---

## 连接模式

### OneBot（NapCat）模式

| 模式 | 说明 | 适用场景 |
|---|---|---|
| `http` | NapCat 推送消息到 Bot 的 `/callback` 端点 | 最简单，适合新手 |
| `ws_forward` | Bot 主动连接 NapCat WebSocket | Bot 与 NapCat 同机部署 |
| `ws_reverse` | NapCat 连接 Bot 的 WebSocket | Bot 与 NapCat 不在同机 |

### QQ 官方机器人模式

`qq_official` 适配器使用 QQ 官方 API v2 **WebSocket Gateway** 长连接，无需 NapCat，无需配置 `connection_mode`。连接由适配器自动管理（鉴权 → 连接 → 心跳 → 重连）。

---

## 技术栈

- **后端**: Python 3.11+ / Quart / Hypercorn
- **前端（GracyUI）**: React / TypeScript / Vite / TailwindCSS
- **协议适配层（GracyAdapter）**: 抽象通用接口，已实现 OneBot v11（NapCat）+ QQ 官方个人机器人 API v2
- **依赖**: Quart、aiohttp、psutil、Pillow、py-cpuinfo、rarfile

> GracyAdapter 采用平台无关设计，OneBot 和 QQ 官方 API 是已实现的适配器。后续将陆续接入 Telegram Bot API、Discord、微信等更多平台，扩展至多端机器人生态。

---

## 开发计划（Roadmap）

| 状态 | 功能模块 | 说明 |
|---|---|---|
| 已完成 | 核心框架 & 插件系统 | 模块化架构、插件热重载、依赖管理、版本控制 |
| 已完成 | GracyAdapter（OneBot） | HTTP 回调 + WS 正向/反向三种连接模式 |
| 已完成 | 安全防护体系 | 日志脱敏、危险命令拦截、频率限制、权限分级、审计日志 |
| 已完成 | LLM_Chat 插件 | 多人设切换、上下文记忆、定时任务、戳一戳互动 |
| 已完成 | 监控与健康检查 | CPU/内存统计、响应时间追踪、`/health` 端点 |
| 开发中 | GracyUI 管理面板完善 | 补充插件管理、日志中心、权限配置、实时消息流等模块 |
| 开发中 | 插件商店（Plugin Store） | 在线浏览、搜索、一键安装/卸载第三方插件 |
| 开发中 | GracyAdapter（多平台） | 接入 Telegram Bot API、Discord 等更多 IM 平台 |
| 规划中 | 工作流引擎 | 可视化拖拽编排自动化消息处理流程 |
| 规划中 | Docker 一键部署 | 提供官方镜像，`docker-compose up` 即可启动全套服务 |

---

## 调试命令参考

项目根目录下的 `debug_commands.txt` 整理了一份分平台（Linux/macOS 和 Windows）的调试命令示例，涵盖启动管理、日志查看、进程排查、消息模拟测试、健康检查等常用操作，希望能帮大家在遇到问题时快速定位。

---

## 声明

本项目为个人学习研究项目，不参与任何商业合作，仅供学习交流参考。请勿将本项目用于任何商业目的。

---

## 许可证

本项目采用 [MIT License](LICENSE) 开源协议，允许自由使用、复制、修改、合并、出版发行、再许可及出售软件的副本。详细信息请查看项目根目录下的 `LICENSE` 文件。