# 2026-06-30 Gracone + Satori 图片发送问题

> 第三方 NoneBot 插件（cchess 等）通过 Gracone 翻译后，Satori 适配器无法正确发送图片。

---

## 问题表现

| 场景 | 行为 |
|------|------|
| 群聊 `/象棋人机` | Cchess 完全不响应（matcher 可能未触发） |
| 私聊 `/象棋人机` | 文字成功，图片不显示 |
| 群聊 `/状态` (Gracone) | 发送失败，日志无错误信息 |
| 私聊 `/状态` | 发送失败 |

对比：`/help`（非 Gracone）图片发送成功。

## 日志分析

**SysInfo `/运行状态` 成功 (03:34:22)：**
```
[Satori.message] - 图片压缩: temp_sysinfo.png ... JPEG 99KB
[Satori] - 消息发送成功
```

**Gracone `/状态` 失败 (03:39:14)：**
```
send called: target='...' chat_type='group'
[Send] - 发送失败... [图片]
```
没有"图片压缩"或"发送异常"日志，说明 adapter 的 `elements` 为空。

## 根因

### `nb_to_gracy_segment()` 翻译问题

`plugins/Gracone_Plugin/bridge/message_translator.py:80-85`：

```python
elif seg_type == 'image':
    url = str(data.get('url', '') or '')
    file_path = str(data.get('file', '') or '')
    if url:
        return GracyImage(url=url)
    return GracyImage(file_path=file_path)  # 只有相对文件名
```

当 NoneBot 图片段只有 `data.file`（如 `"xxxxx.png"`）、没有 `data.url` 时：
- `GracyImage(file_path="xxxxx.png")` 发给 adapter
- adapter 去磁盘找 `xxxxx.png` → 找不到 → 不生成 `Image` 元素 → `elements` 为空 → 返回 False

### 私聊 `/象棋人机` 图片不显示

Cchess 返回的图片有 `data.url`（HTTP URL），所以 `GracyImage(url=url)` → adapter 用 `Image(src=url)` 发送成功。但 URL 是 Koishi 内部地址，NapCat 无法访问，用户看不到图。

## 修復方向

### 方案 A：Gracone 侧下载图片转 data URL（推荐）
`message_translator.py` 中，当只有 `file_path` 时，用 httpx 从 Koishi API 下载图片并转 base64 data URL。

### 方案 B：Satori adapter 侧下载 HTTP URL 图片
adapter 收到 HTTP URL 的图片时，用 httpx 下载并转 data URL。

### 方案 C：Gracone 侧上传文件获取 HTTP URL
用 Koishi 的文件上传 API 把本地文件上传，获取可访问的 URL。

---

## 待确认

- Gracone `/象棋人机` 群聊完全不响应：matcher 未触发还是 to_me 规则拦截？
- `import logging` 统一为 `from graci import get_logger` 后所有日志正常
- Pipeline 的 `[PluginHandler] 成功` 日志归在 `[Core] [Pipeline]` 而非 `[Gracy] [插件名]`，是否需要改
