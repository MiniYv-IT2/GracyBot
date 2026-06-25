"""TTS 统一客户端：支持 GenieTTS 本地推理 + 云端 API"""
import os
import re
import wave
import asyncio
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("Gracy.LLM_Chat.TTS")


# ── Emoji 正则（精确范围，不误伤中文） ──
_EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # 表情符号
    "\U0001F300-\U0001F5FF"  # 符号和象形字
    "\U0001F680-\U0001F6FF"  # 交通地图
    "\U0001F1E0-\U0001F1FF"  # 国旗
    "\U0001F900-\U0001F9FF"  # 补充符号
    "\U0001FA00-\U0001FA6F"  # 扩展A
    "\U0001FA70-\U0001FAFF"  # 扩展B
    "\U0000FE00-\U0000FE0F"  # 变体选择器
    "\U0000200D"             # 零宽连接
    "\U00002139-\U000021AA"  # 字母符号
    "\U0000231A-\U00002323"  # 时钟等
    "\U000023E9-\U000023FA"  # 播放按钮等
    "\U000025AA-\U000027BF"  # 几何图形+装饰符号
    "\U00002934-\U00002935"  # 箭头
    "\U00002B05-\U00002B55"  # 箭头
    "\U00003030-\U0000303D"  # CJK符号（〰️〽️）
    "\U00003297-\U00003299"  # ㊗️㊙️
    "]+", flags=re.UNICODE
)


def clean_tts_text(text: str) -> str:
    """TTS 文本预处理：去 emoji、去括号描述、规范化标点"""
    # 1. 去 emoji
    text = _EMOJI_PATTERN.sub("", text)
    
    # 2. 去中文括号描述
    text = re.sub(r"（[^）]*）", "", text)
    
    # 3. 去英文括号描述
    text = re.sub(r"\([^)]*\)", "", text)
    
    # 4. 规范化空白
    text = re.sub(r"\s+", " ", text).strip()
    
    # 5. 去除尾部无效标点
    text = text.strip().rstrip("，、；：～")
    
    return text

class TTSClient:
    """TTS 统一客户端"""
    
    def __init__(self, config: dict):
        self.config = config
        self.enabled = config.get("enabled", False)
        self.mode = config.get("mode", "local")  # local | cloud
        self._genie = None
        self._ref_audio = None
        self._init_engine()
    
    def _init_engine(self):
        """初始化 TTS 引擎"""
        if not self.enabled:
            return
        
        if self.mode == "local":
            try:
                # 设置 GenieData 路径
                genie_data_dir = self.config.get("local", {}).get("genie_data_dir", "")
                if genie_data_dir:
                    os.environ["GENIE_DATA_DIR"] = genie_data_dir
                
                import genie_tts
                self._genie = genie_tts
                
                # 加载预定义角色（自带参考音频）
                character = self.config.get("local", {}).get("character", "Mika")
                self._character_lower = character.lower()
                self._genie.load_predefined_character(character)
                logger.info(f"[TTS] GenieTTS 本地引擎加载成功，角色: {character}")
            except Exception as e:
                logger.error(f"[TTS] GenieTTS 加载失败: {e}")
                self._genie = None
        
        elif self.mode == "cloud":
            cloud_cfg = self.config.get("cloud", {})
            self._cloud_url = cloud_cfg.get("url", "")
            self._cloud_key = cloud_cfg.get("api_key", "")
            self._cloud_model = cloud_cfg.get("model", "tts-1")
            logger.info(f"[TTS] 云端 API 已配置: {self._cloud_url}")
    
    async def synthesize(self, text: str, output_path: Optional[str] = None) -> Optional[str]:
        """合成语音，返回音频文件路径"""
        if not self.enabled:
            return None
        
        # 文本预处理
        text = clean_tts_text(text)
        if not text or len(text.strip()) == 0:
            return None
        
        if output_path is None:
            output_path = str(Path("data/tts") / f"tts_{hash(text)}.wav")
        
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        try:
            if self.mode == "local" and self._genie:
                return await self._local_synthesize(text, output_path)
            elif self.mode == "cloud":
                return await self._cloud_synthesize(text, output_path)
        except Exception as e:
            logger.error(f"[TTS] 合成失败: {e}")
            return None
        
        return None
    
    async def _local_synthesize(self, text: str, output_path: str) -> Optional[str]:
        """GenieTTS 本地合成"""
        if not self._genie:
            return None
        
        character = self._character_lower  # GenieTTS 内部使用小写角色名
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self._genie.tts(
                character_name=character,
                text=text,
                save_path=output_path,
                split_sentence=True  # 分句合成，避免长文本 internal error
            )
        )
        
        if Path(output_path).exists():
            try:
                with wave.open(output_path, 'rb') as wf:
                    frames = wf.getnframes()
                    rate = wf.getframerate()
                    dur = frames / rate if rate > 0 else 0
                logger.info(f"[TTS] 本地合成成功: {output_path} ({dur:.1f}s)")
            except Exception:
                logger.info(f"[TTS] 本地合成成功: {output_path}")
            return output_path
        return None
    
    async def _cloud_synthesize(self, text: str, output_path: str) -> Optional[str]:
        """云端 API 合成"""
        import aiohttp
        
        headers = {"Authorization": f"Bearer {self._cloud_key}"}
        payload = {
            "model": self._cloud_model,
            "input": text,
            "voice": self.config.get("cloud", {}).get("voice", "alloy")
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(self._cloud_url, json=payload, headers=headers) as resp:
                if resp.status == 200:
                    audio_data = await resp.read()
                    with open(output_path, "wb") as f:
                        f.write(audio_data)
                    logger.info(f"[TTS] 云端合成成功: {output_path}")
                    return output_path
                else:
                    logger.error(f"[TTS] 云端 API 返回错误: {resp.status}")
                    return None
