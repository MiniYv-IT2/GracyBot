# 2026-06-30 Satori emoji 消息被丢弃

## 问题

接收 emoji 消息时，Satori adapter 直接丢弃，不显示任何内容。

## 根因

`satori_to_gracy()`（`core/gracy_adapter/satori/message.py:167`）中，`emoji` type 被解析到 `data`：

```python
elif type_ in ('at', 'emoji'):
    data['id'] = getattr(elem, 'id', '')
    data['name'] = getattr(elem, 'name', '')
```

但后续 `elif` 链只处理了 `at`，没有 `emoji` 分支，掉到 `else` 被忽略。

## 修复

在 `satori_to_gracy()` 的 `elif type_ == "at"` 后加：

```python
elif type_ == "emoji":
    emoji_char = data.get("id", "")
    if emoji_char:
        result.append(GracyText(text=emoji_char))
```

## 相关文件

- `core/gracy_adapter/satori/message.py:167-209`
