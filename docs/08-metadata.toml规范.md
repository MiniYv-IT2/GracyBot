# metadata.toml 规范

> GracyBot 插件元数据标准，兼容其他基于 TOML 的机器人框架。

---

## 目录

- [文件位置](#文件位置)
- [完整结构](#完整结构)
- [必填字段详解](#必填字段详解)
- [可选字段详解](#可选字段详解)
- [校验规则](#校验规则)
- [常见错误](#常见错误)

---

## 文件位置

```bash
plugins/YourPlugin/
└── metadata.toml        # 必须位于插件目录根
```

框架通过 `load_plugin_toml()`（`core/tools/validator.py`）严格校验此文件。

---

## 完整结构

```toml
[plugin]
name        = "插件名称"           # 必填：显示名（建议中文）
version     = "1.0.0"             # 必填：语义化版本
author      = "作者名"             # 必填：开发者
description = "功能描述"           # 必填：一句话说明
priority    = 50                   # 可选：优先级，越大越优先匹配，默认 50
icon        = ""                  # 可选：图标路径或 URL
dependencies = []                 # 可选：依赖插件列表

[handler]
entry       = "handle_func"       # 必填：入口函数名

[trigger]
commands       = ["/cmd1", "/cmd2"]   # 必填：触发命令（非空列表）
chat_type      = ["private", "group"] # 必填：适用场景
permission     = "all"                # 必填：权限级别
is_at_required = false               # 必填：群聊是否需 @
command_descriptions = {"/cmd1": "说明"}   # 可选：命令描述
```

---

## 必填字段详解

### [plugin] 表

| 字段 | 类型 | 说明 | 示例 |
|---|---|---|---|
| `name` | string | 插件显示名称（推荐中文） | `"帮助插件"` |
| `version` | string | 语义化版本号 | `"1.1.3"` |
| `author` | string | 开发者 | `"GracyBot开发团队"` |
| `description` | string | 功能简述 | `"查看所有命令，返回帮助图片"` |

### [handler] 表

| 字段 | 类型 | 说明 | 示例 |
|---|---|---|---|
| `entry` | string | 核心文件名中的函数名 | `"handle_help"` |

### [trigger] 表

| 字段 | 类型 | 校验规则 | 示例 |
|---|---|---|---|
| `commands` | list[string] | **非空** | `["/help", "/帮助", "/菜单"]` |
| `chat_type` | list[string] | 只能包含 `"private"` / `"group"` | `["private", "group"]` |
| `permission` | string | 只能是 `"all"` 或 `"master"` | `"all"` |
| `is_at_required` | bool | — | `false` |

---

## 可选字段详解

### priority

```toml
[plugin]
priority = 80    # 可选：优先级（正整数），越大越优先匹配，默认 50
```

`priority` 决定多插件匹配同一命令时的调度顺序。值越大优先级越高，Pipeline 按优先级降序匹配。

### icon

```toml
[plugin]
icon = "icon.png"                          # 本地相对路径
icon = "https://example.com/icon.png"      # 网络 URL
icon = ""                                  # 留空跳过
```

### dependencies

```toml
[plugin]
dependencies = [
    { name = "LLM_Chat", min_version = "1.0.0" },
    { name = "Database", min_version = "2.0.0", max_version = "3.0.0" },
]
```

| 子字段 | 类型 | 说明 | 必填 |
|---|---|---|---|
| `name` | string | 依赖插件目录名 | 是 |
| `min_version` | string | 最低版本 | 否（默认 `"0.0.0"`） |
| `max_version` | string | 最高版本 | 否 |

### command_descriptions

```toml
[trigger.command_descriptions]
"/help"   = "显示机器人帮助信息"
"/status" = "查看机器人运行状态"
```

> 用于帮助插件自动生成命令列表，每个命令可独立描述。

---

## 校验规则

框架 `validator.py` 的完整校验流程：

```
读取 TOML → 合并 [plugin]+[handler]+[trigger] → 9 字段必填检查
→ 类型检查（commands 非空列表 / chat_type 取值 / permission 范围 / is_at_bool）
→ icon 解析（本地路径/URL）→ 返回扁平化字典
```

`REQUIRED_FIELDS` 定义：

```python
REQUIRED_FIELDS = frozenset({
    "name", "version", "author", "description",
    "handler", "commands", "chat_type", "permission",
    "is_at_required",
})
```

> 注意：实际是 **9 个字段**（name、version、author、description、entry、commands、chat_type、permission、is_at_required）

---

## 常见错误

| 错误信息 | 原因 | 解决 |
|---|---|---|
| `缺少必填字段: commands` | `[trigger]` 中没有 `commands` | 添加非空命令列表 |
| `缺少必填字段: handler` | `[handler]` 中没有 `entry` | 添加入口函数名 |
| `commands 必须是非空列表` | `commands = []` | 填入至少一个命令 |
| `chat_type 必须是列表` | 写了字符串而非列表 | 改为 `["private", "group"]` |
| `permission 必须是 'all' 或 'master'` | 拼写错误 | 只需 `"all"` 或 `"master"` |
| `is_at_required 必须是布尔值` | 写了字符串或数字 | 改为 `true` / `false` |
| `plugins.xxx 中缺失核心处理函数` | TOML entry 函数名不存在 | 检查函数名是否一致 |
| `插件 xxx 缺失核心文件 xxx.py` | 核心文件名与目录名不匹配 | 文件名必须为 `{目录名}.py` |
