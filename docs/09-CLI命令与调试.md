# CLI 命令与调试

> 使用 `gracy` 命令行工具管理框架、调试插件。

---

## 目录

- [命令速查表](#命令速查表)
- [插件 CLI 命令注册](#插件-cli-命令注册)
- [调试技巧](#调试技巧)
- [日志解读](#日志解读)
- [平台调试建议](#平台调试建议)

---

## 命令速查表

| 命令 | 说明 | 示例 |
|---|---|---|
| `gracy run` | 启动机器人 | `gracy run --debug` |
| `gracy stop` | 停止机器人 | `gracy stop` |
| `gracy status` | 查看运行状态 | `gracy status` |
| `gracy instance list` | 列出所有实例 | `gracy instance list` |
| `gracy instance add <name>` | 添加新实例 | `gracy instance add 小号` |
| `gracy instance enable <name>` | 启用实例（下次启动生效） | `gracy instance enable 小号` |
| `gracy instance disable <name>` | 禁用实例（下次启动跳过） | `gracy instance disable 小号` |
| `gracy instance remove <name>` | 删除实例 | `gracy instance remove 小号` |
| `gracy plugin list` | 列出所有插件 | `gracy plugin list` |
| `gracy plugin install <path>` | 安装插件 | `gracy plugin install ./my-plugin` |
| `gracy plugin remove <name>` | 卸载插件 | `gracy plugin remove MyPlugin` |
| `gracy ins <pkg>` | 快速安装 Python 包/插件依赖 | `gracy ins requests` |
| `gracy autostart` | 注册开机自启 | `gracy autostart` |
| `gracy --help` | 查看全部命令 | `gracy --help` |
| `gracy instance --help` | 实例管理帮助 | `gracy instance --help` |
| `gracy plugin --help` | 插件子命令帮助 | `gracy plugin --help` |

---

## 插件 CLI 命令注册

插件可以向 `gracy` 注册自己的 CLI 子命令。

### 注册接口

```python
from graci import register_cli_command

def my_cli_handler():
    """我的插件的 CLI 命令"""
    print("插件 CLI 命令执行")

register_cli_command("my-plugin", my_cli_handler, help_text="我的插件 CLI 命令")
```

### 完整示例

```python
"""示例插件 — 带有 CLI 命令"""
import logging
from graci import on_command, plugin_handler, PluginContext, register_cli_command

_logger = logging.getLogger("Gracy.示例插件")


# ── CLI 命令 ──
def cli_hello():
    """CLI 说你好（在终端执行 gracy hello）"""
    print("👋 Hello from CLI!")


def cli_stats():
    """显示插件统计"""
    print("📊 插件运行统计：")
    print("  调用次数: 42")
    print("  平均耗时: 0.3s")


# 注册到 gracy CLI
register_cli_command("hello", cli_hello, "打印问候")
register_cli_command("stats", cli_stats, "显示统计")


# ── 消息命令 ──
@on_command("/hello")
@plugin_handler
async def handle_hello(ctx: PluginContext):
    await ctx.reply("Hello from bot!")
```

### 注册参数

| 参数 | 类型 | 说明 | 必填 |
|---|---|---|---|
| `name` | str | 子命令名 | 是 |
| `handler` | Callable | 回调函数 | 是 |
| `help_text` | str | 帮助说明 | 否（默认为函数 docstring） |

> 注册后，在终端运行 `gracy hello` 即可触发。CLI 命令支持**全局安装**（`pip install .`）后任意目录执行。

---

## 调试技巧

### 方式一：DEBUG 日志

```bash
gracy run --debug
```

关键日志标记：

| 日志标记 | 说明 | 调试什么 |
|---|---|---|
| `[SecurityFilter]` | 安全过滤阶段 | 黑名单是否拦截 |
| `[CommandMatcher]` | 命令匹配阶段 | 插件是否匹配到命令 |
| `[PluginHandler]` | 插件执行阶段 | 执行成功/失败，异常 Traceback |
| `[ResponseSender]` | 兜底处理 | 自动回复 / AI 对话 |
| `[Decorator]` | 装饰器处理 | 权限/频率/冷却拦截 |
| `[OneBotWS]` | WebSocket 连接 | 连接/断连/重连 |
| `LLM_Chat` | AI 对话插件 | API 调用情况 |

### 方式二：日志文件实时追踪

```bash
# Windows PowerShell
Get-Content logs/gracybot.log -Tail 20 -Wait

# Linux / macOS
tail -f logs/gracybot.log

# 过滤特定插件
tail -f logs/gracybot.log | Select-String "帮助插件"   # Windows
tail -f logs/gracybot.log | grep "帮助插件"              # Linux
```

### 方式三：检查插件加载状态

```bash
gracy plugin list
```

输出示例：

```
共 10 个插件:
  • 易搜助手
  • 帮助插件
  • LLM_Chat 📦       # 📦 表示有 requirements.txt
  ...
```

启动日志中也有：

```
📊 共注册成功 10 个插件：
  1. 插件名称：帮助插件 | 版本：1.1.3 | 触发指令：['/help', ...]
```

**无插件** = 肯定是 TOML 语法错误。

### 方式四：命令行传参

```python
# 新风格：从 raw_text 截取参数
args = ctx.raw_text[len(ctx.command):].strip()
# 例如 "/搜索 python教程" → args = "python教程"

# 旧风格：从 data["text"] 截取
args = data.get("text", "")[len(matched_cmd):].strip()
```

---

## 日志解读

### 正常消息流

```
[适配器回调] 收到消息 | 用户ID: ****4908 | 消息: /help
[CommandMatcher] TOML 匹配: 帮助插件 → /help    ← 匹配成功
[PluginHandler] 成功: 帮助插件 命令=/help 耗时=0.241s  ← 执行成功
[消息发送] 成功发送私聊消息 | 目标: ****4908 | 图片:temp_help.png
```

### 常见异常

| 日志内容 | 含义 | 解决 |
|---|---|---|
| `[CommandMatcher] 跳过 xxx（仅主人可用）` | 非主人使用主人命令 | - |
| `[PluginHandler] 异常: xxx 错误=...` | 插件运行时异常 | 看 Traceback 定位代码 |
| `[安全防护] 用户 xxx 消息频率超限` | 频率限制触发 | 稍后再试或调大限制 |
| `[OneBotWS] 连接断开` | WebSocket 断连 | 检查 NapCat 状态 |
| `❌ 插件 xxx 缺少 metadata.toml` | 插件没有 TOML 文件 | 检查目录结构 |
| `❌ 缺少必填字段: commands` | TOML 缺少命令列表 | 检查 metadata.toml |

---

## 平台调试建议

### Windows

```powershell
# 查看端口占用（确认 WebSocket 端口）
netstat -ano | findstr :3001

# 强制停止所有 Python 进程
taskkill /f /im python*

# 查看实时日志
Get-Content logs/gracybot.log -Tail 30 -Wait

# 以管理员身份运行（截图功能需要）
```

### Linux

```bash
# 查看 WebSocket 连接状态
ss -tlnp | grep 3001

# 查看 systemd 服务日志
journalctl --user -u gracybot -f

# 查看进程
ps aux | grep bot.py

# 内存占用
top -b -n 1 | grep python
```

### macOS

```bash
# 查看 launchctl 服务状态
launchctl list | grep gracy

# 重启服务
launchctl stop gracybot
launchctl start gracybot
```

### Termux（Android）

```bash
# 使用 tmux 保持后台会话
tmux new -s gracy
gracy run
# Ctrl+B, D 分离会话
# tmux attach -t gracy 重新连接

# 查看进程
pgrep -af python
```
