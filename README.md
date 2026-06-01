<p align="center">
  <img src="plugins/GracyUI_plugin/frontend/public/gracy.png" alt="GracyBot" width="200" />
</p>

<h1 align="center">GracyBot</h1>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/Platform-Windows%20|%20Linux%20|%20macOS-lightgrey" alt="Platform" />
  <img src="https://img.shields.io/badge/Status-Active-brightgreen" alt="Status" />
  <img src="https://img.shields.io/badge/License-MIT-green" alt="License" />
  <img src="https://img.shields.io/badge/Version-v1.9.2-orange" alt="Version" />
</p>

<p align="center">
  <strong>中文</strong> | <a href="README_EN.md">English</a>
</p>

> 想给自己的 QQ 搞个智能机器人？GracyBot 就是为此而生的。基于 **Python 3.11+** & **NapCat** 的个性化定制 QQ 机器人框架，主打安全稳定、插件化扩展与便捷更新。

**作者**：小禹 | 湖南汽车工程职业大学 · 计算机网络技术专业
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
- **多协议适配（GracyAdapter）** — 统一适配层，支持 HTTP 回调、WebSocket 正向、WebSocket 反向三种连接模式
- **企业级安全防护** — 日志自动脱敏（QQ号/API Key/密码）、危险命令拦截、输入验证、频率限制、权限分级、审计日志
- **插件化生态** — 插件即目录，放入 `plugins/` 自动注册，支持版本控制、依赖管理、循环依赖检测、热重载
- **AI 对话** — 内置 LLM_Chat 插件，对接 OpenAI 兼容 API，支持多人设切换、上下文记忆、定时任务、戳一戳互动
- **监控与可观测性** — 结构化日志、CPU/内存/消息统计、健康检查端点（`/health`、`/metrics`、`/status`）
- **Web 管理面板（GracyUI）** — 基于 React + TypeScript + TailwindCSS 的可视化 Bot 管理界面
- **跨平台** — 适配 Windows 10+ / Linux（Debian 11+）/ macOS

---

## 项目结构

```
GracyBot_V1.9.2/
├── bot.py                      # 启动入口（仅调用 core/main.py）
├── config.json                 # 主配置文件
├── config.template.json        # 配置模板
├── hotreload.json              # 热重载开关
├── requirements.txt            # Python 依赖
│
├── core/                       # 核心框架
│   ├── main.py                 # Flask 应用 & 启动流程
│   ├── handler.py              # 消息处理 & 指令分发
│   ├── plugin_manager.py       # 插件扫描/加载/注册/匹配
│   ├── config.py               # 配置读取
│   ├── config_manager.py       # 集中化配置管理
│   ├── security.py             # 安全工具（脱敏/过滤/权限）
│   ├── security_manager.py     # 安全管理器
│   ├── monitor.py              # 系统监控 & 健康检查
│   ├── logger_manager.py       # 结构化日志管理
│   ├── utils.py                # 工具函数
│   └── gracy_adapter/          # 多协议适配层
│       ├── adapter.py          # 适配器抽象基类
│       ├── event.py            # 统一事件模型
│       ├── message.py          # 消息段类型（Text/Image/At/Reply/Voice/File）
│       ├── send.py             # 统一消息发送接口
│       ├── gracy_bot.py        # GracyBot 统一入口
│       └── onebot/             # OneBot 平台实现
│           ├── http.py         # HTTP 适配器
│           ├── ws.py           # WebSocket 适配器（正向+反向）
│           └── cq.py           # CQ 码解析
│
├── plugins/                    # 插件目录（即插即用，放入即注册）
│
└── style/                      # 样式资源
    ├── gracybot_logo.py        # 启动 Logo
    ├── log_colors.py           # 日志配色
    └── styling.py              # 样式工具
```

---

## 环境要求

- **Python**: 3.11+
- **NapCat**: OneBot v11 协议端（QQ 机器人必备，负责对接 QQ 协议）
- **Python 依赖**: Flask、requests、psutil、Pillow、py-cpuinfo、rarfile（详见 `requirements.txt`）
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

---

## 插件开发

插件采用「即插即用」设计，开发步骤：

1. 在 `plugins/` 下新建目录（目录名即插件名）
2. 创建 `__init__.py`，定义 `PLUGIN_META` 元信息：

```python
PLUGIN_META = {
    "name": "我的插件",
    "version": "1.0.0",
    "description": "插件描述",
    "author": "作者名称",                    # 插件作者
    "commands": ["/mycommand"],              # 触发指令列表
    "handler": "handle_my_plugin",           # 核心处理函数名
    "chat_type": ["private", "group"],       # 支持的聊天类型
    "permission": "all",                     # all / master
    "is_at_required": False,                 # 群聊是否需要 @机器人
    "dependencies": [],                      # 依赖的其他插件
}
```

3. 创建核心文件（文件名与 `PLUGIN_META["name"]` 对应），实现 handler 函数：

```python
def handle_my_plugin(plugin_manager, send_msg, data, sender_id, chat_type, target, logger):
    # 你的插件逻辑
    pass
```

4. 重启机器人或开启热重载（`hotreload.json` 中 `"enabled": true`），插件自动加载。

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

| 模式 | 说明 | 适用场景 |
|---|---|---|
| `http` | NapCat 推送消息到 Bot 的 `/callback` 端点 | 最简单，适合新手 |
| `ws_forward` | Bot 主动连接 NapCat WebSocket | Bot 与 NapCat 同机部署 |
| `ws_reverse` | NapCat 连接 Bot 的 WebSocket | Bot 与 NapCat 不在同机 |

---

## 技术栈

- **后端**: Python 3.11+ / Flask / Werkzeug
- **前端（GracyUI）**: React / TypeScript / Vite / TailwindCSS
- **协议适配层（GracyAdapter）**: 抽象通用接口，当前已实现 OneBot v11（NapCat）
- **依赖**: requests, Flask, psutil, Pillow, py-cpuinfo, rarfile

> GracyAdapter 采用平台无关设计，OneBot 只是首个实现的适配器。后续将陆续接入 Telegram Bot API、Discord、微信等更多平台，扩展至多端机器人生态。

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