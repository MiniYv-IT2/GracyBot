# GracyVoice 语音合成插件 — 开发计划

## 一、概述

| 项目 | 内容 |
|---|---|
| 插件名 | GracyVoice |
| 开发风格 | **新风格**（`@on_command` + `@plugin_handler` + `PluginContext`） |
| 基础库 | [Genie-TTS](https://pypi.org/project/genie-tts/)（GPT-SoVITS ONNX 推理引擎，CPU 可运行） |
| Logger | `Gracy.GracyVoice` |
| 目录 | `plugins/GracyVoice/` |

### 新风格依据

> 文档 `05-插件开发指南（新风格）.md` 明确：**"推荐所有新插件使用"**

---

## 二、项目结构

```
plugins/GracyVoice/
├── metadata.toml              # 元数据（必填）
├── GracyVoice.py              # 主逻辑文件（必填，与目录同名）
├── core/
│   ├── __init__.py            # 可为空
│   ├── tts_engine.py          # Genie-TTS 引擎封装
│   ├── model_manager.py       # 模型下载/加载/切换
│   └── audio_utils.py         # 音频文件处理工具
├── data/
│   └── models/                # 模型存放目录（自动创建）
├── config.json                # 插件配置
└── __init__.py                # 可为空
```

---

## 三、依赖

```bash
pip install genie-tts
```

genie-tts 自动安装：onnxruntime、soundfile、numpy、huggingface-hub、pypinyin、rich 等。

---

## 四、metadata.toml

```toml
[plugin]
name        = "语音合成插件"
version     = "1.0.0"
author      = "GracyBot开发团队"
description = "文本转语音，支持 Genie-TTS 多种角色模型"
priority    = 50

[handler]
entry       = "handle_gracy_voice"

[trigger]
commands       = ["/语音", "/语音列表", "/语音设置"]
chat_type      = ["private", "group"]
permission     = "all"
is_at_required = false

[trigger.command_descriptions]
"/语音"     = "将文本转为语音并发送，用法：/语音 内容"
"/语音列表" = "查看可用的语音角色"
"/语音设置" = "切换语音角色，用法：/语音设置 角色名"
```

---

## 五、GracyVoice.py（新风格）

```python
"""GracyVoice 语音合成插件 — 文本转语音"""
import os
import logging

from graci import on_command, plugin_handler, PluginContext
from graci import GracyVoice  # 语音消息段（需确认框架是否支持）
from graci import get_current_master_id

_logger = logging.getLogger("Gracy.GracyVoice")

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
MODELS_DIR = os.path.join(DATA_DIR, "models")
TEMP_DIR = os.path.join(DATA_DIR, "temp")
```

### 命令处理

| 命令 | 函数 | 说明 | 权限 |
|---|---|---|---|
| `/语音 内容` | `handle_tts` | 文本→语音并发送 | all |
| `/语音列表` | `handle_list_voices` | 显示可用角色 | all |
| `/语音设置 角色` | `handle_set_voice` | 切换默认角色 | master |

---

## 六、导入顺序（按文档规范）

```python
# 第 1 层：标准库
import os
import logging

# 第 2 层：框架装饰器
from graci import on_command, plugin_handler, PluginContext

# 第 3 层：框架消息段
from graci import GracyText, GracyImage

# 第 4 层：框架工具
from graci import get_current_master_id, get_current_robot_id

# 第 5 层：插件自身模块
from .core.tts_engine import text_to_speech

_logger = logging.getLogger("Gracy.GracyVoice")
```

---

## 七、API 设计

### 7.1 内部 API（供其他插件调用）

```python
from plugins.GracyVoice.core.tts_engine import text_to_speech

audio_path = await text_to_speech(
    text="要合成的文字",
    voice="zh-CN-Xiaoxiao",     # 角色名
    save_path="data/temp/",
)
# 返回：绝对路径，如 "E:/.../data/temp/tts_20260623_120000.wav"
```

### 7.2 core/tts_engine.py

```python
"""Genie-TTS 引擎封装"""

import os
import logging
from typing import Optional
import genie_tts as genie

_logger = logging.getLogger("Gracy.GracyVoice")

# 全局引擎实例（单例）
_engine_loaded = False
_current_voice = "zh-CN-Xiaoxiao"


def load_engine(voice: str = "zh-CN-Xiaoxiao"):
    """加载语音模型（首次调用下载 ~230MB 模型）"""
    global _engine_loaded, _current_voice
    genie.load_character(
        character_name=voice,
        onnx_model_dir=...,
        language="zh",
    )
    _engine_loaded = True
    _current_voice = voice


async def text_to_speech(text: str, voice: Optional[str] = None, save_path: str = None) -> str:
    """文本 → 语音文件路径"""
    if not _engine_loaded or (voice and voice != _current_voice):
        load_engine(voice or _current_voice)
    # 调用 genie.tts()
    ...
```

### 7.3 core/model_manager.py

```python
"""模型下载与角色管理"""

# 预定义角色列表
PREDEFINED_VOICES = {
    "zh-CN-Xiaoxiao": "默认中文女声（晓晓）",
    "zh-CN-Yunyang":  "默认中文男声（云扬）",
}
```

### 7.4 core/audio_utils.py

```python
"""音频文件处理"""

def cleanup_temp_files(max_age_hours: int = 24):
    """清理过期临时音频文件"""
    ...

def get_audio_duration(file_path: str) -> float:
    """获取音频时长（秒）"""
    ...
```

---

## 八、配置项（config.json）

```json
{
    "default_voice": "zh-CN-Xiaoxiao",
    "auto_download": true,
    "temp_dir": "data/temp/",
    "max_text_length": 500,
    "voice_list": {
        "zh-CN-Xiaoxiao": "晓晓（中文女声）",
        "zh-CN-Yunyang": "云扬（中文男声）"
    }
}
```

---

## 九、实现步骤

### Step 1：插件骨架 ✅（本计划之后执行）

- 创建目录 `plugins/GracyVoice/`
- 编写 `metadata.toml`
- 编写 `GracyVoice.py` 主入口（3 个命令的空壳）
- 编写 `core/__init__.py`（空）
- 编写 `__init__.py`（空）
- 验证 `gracy run` 能正常加载且 `/语音` 命令可匹配

### Step 2：TTS 引擎

- 实现 `core/tts_engine.py`（封装 genie-tts）
- 实现 `core/model_manager.py`（角色列表、模型加载）
- 实现 `core/audio_utils.py`（文件清理）

### Step 3：集成验证

- 安装 `pip install genie-tts`
- `gracy run` 发送 `/语音 你好` 测试生成并发送语音
- 测试 `/语音列表`、`/语音设置`

### Step 4：LLM_Chat 桥接（v1.1）

- LLM_Chat 调用 `text_to_speech()` 使 AI 回复可选语音播报

---

## 十、注意事项

- Genie-TTS 首次推理需加载模型 ~230MB，后续推理快（~1.13s 首次）
- 临时音频文件定期清理（`cleanup_temp_files`）
- Windows / Linux 双平台兼容
- 语音消息段 `GracyVoice` 需确认框架是否支持，不支持则用 `GracyImage` 或文件消息兼容

---

**计划制定时间：2026-06-23**  
**状态：计划阶段，待实现**
