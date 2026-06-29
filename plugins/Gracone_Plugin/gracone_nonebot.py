"""
gracone_nonebot.py — 单文件模拟完整 nonebot 命名空间

原理: 通过 sys.modules 注入 + _AutoModule 惰性子模块创建，
使得 NoneBot 插件的所有 import 语句命中此处定义的虚拟模块。

无任何真实 nonebot 依赖，所有实现最终翻译为 GracyBot API。
"""

import sys
import types
import contextvars
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from graci import get_logger

# ──────────────────────────────────────────────────────
# _AutoModule: 递归自动创建子模块
# ──────────────────────────────────────────────────────

class _AutoModule(types.ModuleType):
    """自动创建子模块的模块基类
    
    当访问 module.xxx 且 xxx 不存在时，自动创建同名子模块并注册到 sys.modules。
    这样 from nonebot.anything.any import something 无需预先注册中间路径。
    """
    def __getattr__(self, name: str) -> Any:
        if name.startswith('_'):
            raise AttributeError(name)
        full_name = f"{self.__name__}.{name}"
        # 如果已经存在，直接返回
        if full_name in sys.modules:
            mod = sys.modules[full_name]
            setattr(self, name, mod)
            return mod
        # 创建虚拟模块
        sub = types.ModuleType(full_name)
        sub.__package__ = full_name
        sub.__path__ = []
        sub.__file__ = __file__
        sub.__class__ = _AutoModule
        sys.modules[full_name] = sub
        setattr(self, name, sub)
        return sub


def _reg(name: str) -> types.ModuleType:
    """注册一个虚拟模块到 sys.modules（确保__path__存在，支持子导入）"""
    mod = types.ModuleType(name)
    mod.__package__ = name
    mod.__path__ = []
    mod.__file__ = __file__
    sys.modules[name] = mod
    return mod


# ──────────────────────────────────────────────────────
# 1. 注册 nonebot 根命名空间
# ──────────────────────────────────────────────────────

nonebot = _reg('nonebot')
nonebot.__class__ = _AutoModule  # 支持惰性自动创建任意子模块

# ──────────────────────────────────────────────────────
# 2. 预注册核心子模块（确保关键路径不会走惰性创建）
# ──────────────────────────────────────────────────────

# 导入系统和常用子模块（显式创建，确保路径可用）
NB_SUB_MODULES = [
    'nonebot.rule',
    'nonebot.params',
    'nonebot.permission',
    'nonebot.exception',
    'nonebot.matcher',
    'nonebot.log',
    'nonebot.message',
    'nonebot.typing',
    'nonebot.compat',
    'nonebot.plugin',
    'nonebot.plugin.load',
    'nonebot.adapters',
    'nonebot.internal',
    'nonebot.internal.matcher',
    'nonebot.internal.adapter',
    'nonebot.drivers',
    'nonebot.dependencies',
    'nonebot.plugins',
    'nonebot.version',
]
for name in NB_SUB_MODULES:
    _reg(name)

# 版本伪装
nonebot.__version__ = "2.3.3"
sys.modules['nonebot.version'].__version__ = nonebot.__version__


# ──────────────────────────────────────────────────────
# 3. 定义通用事件类型（平台无关）
# ──────────────────────────────────────────────────────

class Event:
    """事件基类 — 对应 nonebot.adapters.Event"""
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
    
    def get_type(self) -> str:
        return self.post_type if hasattr(self, 'post_type') else ""


class MessageEvent(Event):
    """消息事件基类 — 对应 nonebot.adapters.MessageEvent
    
    平台无关，仅包含 GracyBot 通用字段。
    """
    def __init__(self, **kwargs):
        if not hasattr(self, 'post_type') or not self.post_type:
            self.post_type: str = "message"
        if not hasattr(self, 'message_type'):
            self.message_type: str = ""
        if not hasattr(self, 'user_id'):
            self.user_id: str = ""
        if not hasattr(self, 'message'):
            self.message: Any = None
        if not hasattr(self, 'raw_message'):
            self.raw_message: str = ""
        if not hasattr(self, 'to_me'):
            self.to_me: bool = False
        if not hasattr(self, 'time'):
            self.time: int = 0
        if not hasattr(self, 'self_id'):
            self.self_id: str = ""
        super().__init__(**kwargs)


# ──────────────────────────────────────────────────────
# 4. 定义 Message / MessageSegment
# ──────────────────────────────────────────────────────

class MessageSegment:
    """消息段 — 与 OneBot V11 完全兼容"""
    
    def __init__(self, type: str, data: dict = None):
        self.type = type
        self.data = data or {}
    
    def __str__(self) -> str:
        return f"[{self.type}:{self.data}]"
    
    def __repr__(self) -> str:
        return f"MessageSegment({self.type}, {self.data})"
    
    @staticmethod
    def text(text: str) -> "MessageSegment":
        return MessageSegment("text", {"text": text})
    
    @staticmethod
    def image(file: str = "", _type: str = "", url: str = "", 
              cache: bool = True, proxy: bool = True, timeout: int = 0) -> "MessageSegment":
        d = {"file": file}
        if _type: d["type"] = _type
        if url: d["url"] = url
        return MessageSegment("image", d)
    
    @staticmethod
    def at(user_id: Union[int, str]) -> "MessageSegment":
        return MessageSegment("at", {"qq": str(user_id)})
    
    @staticmethod
    def reply(id: Union[int, str]) -> "MessageSegment":
        return MessageSegment("reply", {"id": str(id)})
    
    @staticmethod
    def record(file: str = "", magic: bool = False, url: str = "",
               cache: bool = True, proxy: bool = True) -> "MessageSegment":
        d = {"file": file}
        return MessageSegment("record", d)
    
    @staticmethod
    def video(file: str = "", url: str = "", cache: bool = True, 
              proxy: bool = True, timeout: int = 0) -> "MessageSegment":
        d = {"file": file}
        if url: d["url"] = url
        return MessageSegment("video", d)
    
    @staticmethod
    def face(id: int) -> "MessageSegment":
        return MessageSegment("face", {"id": str(id)})
    
    @staticmethod
    def music(type: str = "", id: int = 0, url: str = "", 
              audio: str = "", title: str = "", content: str = "", 
              image: str = "") -> "MessageSegment":
        return MessageSegment("music", {"type": type, "id": str(id)})
    
    @staticmethod
    def json(data: str) -> "MessageSegment":
        return MessageSegment("json", {"data": data})
    
    @staticmethod
    def forward(id: Union[int, str]) -> "MessageSegment":
        return MessageSegment("forward", {"id": str(id)})
    
    @staticmethod
    def node(id: Union[int, str]) -> "MessageSegment":
        return MessageSegment("node", {"id": str(id)})
    
    @staticmethod
    def file(file: str = "", url: str = "", cache: bool = True, 
             proxy: bool = True, timeout: int = 0) -> "MessageSegment":
        d = {"file": file}
        if url: d["url"] = url
        return MessageSegment("file", d)


class Message(list):
    """消息序列 — 继承 list[MessageSegment]，与 OneBot V11 完全兼容"""
    
    def __init__(self, msg: Any = None):
        super().__init__()
        if isinstance(msg, str):
            self.append(MessageSegment.text(msg))
        elif isinstance(msg, MessageSegment):
            self.append(msg)
        elif isinstance(msg, (list, tuple)):
            for seg in msg:
                if isinstance(seg, MessageSegment):
                    self.append(seg)
                elif isinstance(seg, dict):
                    self.append(MessageSegment(seg.get("type", "text"), seg.get("data", {})))
        elif msg is not None:
            self.append(MessageSegment.text(str(msg)))
    
    def extract_plain_text(self) -> str:
        """提取纯文本内容"""
        parts = []
        for seg in self:
            if seg.type == "text":
                parts.append(str(seg.data.get("text", "")))
        return "".join(parts).strip()
    
    def __add__(self, other):
        if isinstance(other, Message):
            new = Message(self)
            new.extend(other)
            return new
        elif isinstance(other, MessageSegment):
            new = Message(self)
            new.append(other)
            return new
        elif isinstance(other, str):
            new = Message(self)
            new.append(MessageSegment.text(other))
            return new
        return NotImplemented
    
    def __radd__(self, other):
        if isinstance(other, str):
            new = Message(MessageSegment.text(other))
            new.extend(self)
            return new
        return NotImplemented


# ──────────────────────────────────────────────────────
# 5. 定义异常
# ──────────────────────────────────────────────────────

class FinishedException(Exception):
    """matcher.finish() 触发的终止异常"""
    pass

class PausedException(Exception):
    """matcher.pause() 触发的等待异常"""
    pass

class StopPropagation(Exception):
    """停止事件传播"""
    pass

class SkippedException(Exception):
    """跳过当前 handler"""
    pass


# ──────────────────────────────────────────────────────
# 6. 填充 nonebot 根模块导出
# ──────────────────────────────────────────────────────

def _lazy_on_command(*cmds, **kwargs):
    """惰性 on_command — 由 bridge/matcher_bridge.py 运行时动态替换"""
    raise RuntimeError("Gracone未初始化: 请先加载Gracone_Plugin")

# 设置默认值（运行时会被 bridge 替换为真实实现）
nonebot.on_command   = _lazy_on_command
nonebot.on_regex     = lambda *a, **kw: _lazy_on_command()
nonebot.on_message   = lambda **kw: _lazy_on_command()
nonebot.on_keyword   = lambda *a, **kw: _lazy_on_command()
nonebot.on_notice    = lambda **kw: _lazy_on_command()
nonebot.on_request   = lambda **kw: _lazy_on_command()
nonebot.on_metaevent = lambda **kw: _lazy_on_command()
nonebot.on_startswith = lambda *a, **kw: _lazy_on_command()
nonebot.on_fullmatch = lambda *a, **kw: _lazy_on_command()
nonebot.on_endswith  = lambda *a, **kw: _lazy_on_command()
nonebot.on_shell_command = lambda *a, **kw: _lazy_on_command()

def _get_bot():
    """获取当前消息的 Bot 实例"""
    from bridge.api_bridge import get_current_bot
    return get_current_bot()

def _get_bots():
    """获取所有 Bot 实例"""
    from bridge.api_bridge import get_all_bots
    return get_all_bots()

# ── Fake Driver（含 on_startup 钩子，供 data_source 等插件使用） ──

class _FakeDriver:
    """假 Driver — 持有 on_startup/on_shutdown 钩子，供插件装饰"""
    def __init__(self):
        self._startup_hooks: list = []
        self._shutdown_hooks: list = []
    
    def on_startup(self, func):
        """注册启动钩子"""
        self._startup_hooks.append(func)
        return func
    
    def on_shutdown(self, func):
        """注册关闭钩子"""
        self._shutdown_hooks.append(func)
        return func
    
    async def _run_startup(self):
        """触发所有 on_startup 钩子"""
        for hook in self._startup_hooks:
            try:
                r = hook()
                if hasattr(r, '__await__'):
                    await r
            except Exception:
                pass

_fake_driver = _FakeDriver()

def _get_driver():
    return _fake_driver

def _run(*args, **kwargs):
    pass  # 空壳

nonebot.get_bot     = _get_bot
nonebot.get_bots    = _get_bots
nonebot.get_driver  = _get_driver
nonebot.run         = _run
nonebot.init        = lambda **kw: None
nonebot.require     = lambda name: sys.modules.get(f'nonebot.plugins.{name}')
nonebot.load_plugin = lambda path: None

def _get_loaded_nb_plugins():
    """获取已加载的 NoneBot 插件列表（只返回顶层包名，去重）"""
    seen = set()
    result = []
    for mod_name, mod in list(sys.modules.items()):
        if mod_name.startswith('nonebot_plugins.') and mod is not None:
            # 只取顶层包名：nonebot_plugins.cchess.game → cchess
            parts = mod_name.split('.')
            if len(parts) >= 2:
                pkg_name = parts[1]
                if pkg_name not in seen:
                    seen.add(pkg_name)
                    try:
                        p = Plugin(name=pkg_name, module=sys.modules.get(f'nonebot_plugins.{pkg_name}') or mod)
                        meta = getattr(sys.modules.get(f'nonebot_plugins.{pkg_name}', mod), '__plugin_meta__', None)
                        if meta:
                            p.metadata = meta
                        result.append(p)
                    except Exception:
                        pass
    return result

nonebot.get_loaded_plugins = _get_loaded_nb_plugins

def get_plugin_config(config_model):
    """获取插件配置 — 返回默认配置实例
    
    cchess 插件的引擎路径重定向到 Gracone 内置 data 目录。
    """
    try:
        inst = config_model()
        # 重定向 cchess 引擎路径到 Gracone 内部 data 目录
        if hasattr(inst, 'cchess_engine_path'):
            from pathlib import Path
            gracone_dir = Path(__file__).parent.resolve()
            engine_dir = gracone_dir / "data" / "cchess"
            # 自动查找引擎文件（支持 fairy-stockfish、pikafish 等任意引擎）
            engine_files = sorted(engine_dir.glob("*"))
            # 过滤掉目录和非可执行文件
            engine_files = [f for f in engine_files 
                           if f.is_file() and f.suffix not in ('.txt', '.md', '.json', '.yaml', '.yml')]
            # 偏好已知引擎名
            known = [f for f in engine_files if 'stockfish' in f.name.lower() or 'pikafish' in f.name.lower() or 'engine' in f.name.lower()]
            engine_files = known or engine_files
            if engine_files:
                inst.cchess_engine_path = engine_files[0]
            else:
                inst.cchess_engine_path = engine_dir / "fairy-stockfish"
        return inst
    except Exception:
        return config_model

nonebot.get_plugin_config = get_plugin_config

# ──────────────────────────────────────────────────────
# 7. 填充 nonebot.rule
# ──────────────────────────────────────────────────────

nb_rule = sys.modules['nonebot.rule']

class GraconeRule:
    """规则包装器 — 支持 & 组合"""
    def __init__(self, rule_type: str = "custom", **params):
        self.rule_type = rule_type
        self.params = params
        self._rules = [self]  # 组合规则列表
    
    def __and__(self, other):
        """支持 rule1 & rule2 语法"""
        result = GraconeRule("combined")
        # 收集所有子规则
        if hasattr(self, '_rules'):
            result._rules = list(self._rules)
        else:
            result._rules = [self]
        if hasattr(other, '_rules'):
            result._rules.extend(other._rules)
        elif callable(other):
            result._rules.append(other)  # 直接存可调用对象
        else:
            result._rules.append(other)
        return result
    
    def __rand__(self, other):
        """支持 callable & rule 语法"""
        return self.__and__(other)
    
    def __call__(self, *args, **kwargs):
        return True

class Rule:
    """假 Rule — 模拟 nonebot.rule.Rule，供 kawaii_status 等插件使用"""
    def __init__(self, *args):
        self._callbacks = [a for a in args if callable(a)]
    def __and__(self, other):
        return GraconeRule("combined")

nb_rule.Rule = Rule

nb_rule.to_me      = lambda: GraconeRule("to_me")
nb_rule.startswith = lambda *a, **kw: GraconeRule("startswith", prefix=a, **kw)
nb_rule.endswith   = lambda *a, **kw: GraconeRule("endswith", suffix=a, **kw)
nb_rule.fullmatch  = lambda *a, **kw: GraconeRule("fullmatch", text=a, **kw)
nb_rule.keyword    = lambda *a, **kw: GraconeRule("keyword", keywords=a, **kw)
nb_rule.regex      = lambda pattern, **kw: GraconeRule("regex", pattern=pattern, **kw)

# ──────────────────────────────────────────────────────
# 8. 填充 nonebot.params
# ──────────────────────────────────────────────────────

nb_params = sys.modules['nonebot.params']

class _CommandArg:
    """伪装为 CommandArg — 从 GraconeContext 提取"""
    def __call__(self):
        from context import GraconeContext
        ctx = GraconeContext.get()
        if ctx and ctx.raw_text:
            cmd = ctx.command
            arg_text = ctx.raw_text[len(cmd):].strip() if cmd else ctx.raw_text
            return Message(MessageSegment.text(arg_text))
        return Message("")

class _EventMessage:
    def __call__(self):
        from context import GraconeContext
        ctx = GraconeContext.get()
        if ctx and hasattr(ctx, '_nb_event') and ctx._nb_event:
            return ctx._nb_event.message
        return Message("")

class _EventPlainText:
    def __call__(self):
        from context import GraconeContext
        ctx = GraconeContext.get()
        return ctx.raw_text if ctx else ""

class _State:
    def __call__(self):
        return {}

def _Depends(callable=None, *, cache=True):
    """简化 Depends 实现"""
    if callable is None:
        def decorator(f):
            return f
        return decorator
    return callable

nb_params.CommandArg     = _CommandArg()
nb_params.EventMessage   = _EventMessage()
nb_params.EventPlainText = _EventPlainText()
nb_params.State          = _State()
class _RegexDict(dict):
    """伪 RegexDict — 从命令匹配中提取正则组"""
    def __call__(self):
        return dict(self)

nb_params.Depends   = _Depends
nb_params.RegexDict = _RegexDict()

# ──────────────────────────────────────────────────────
# 9. 填充 nonebot.permission
# ──────────────────────────────────────────────────────

nb_perm = sys.modules['nonebot.permission']

def _USER(*ids):
    return lambda: True

def _SUPERUSER():
    return lambda: True

def _MESSAGE():
    return lambda event, **kw: True if hasattr(event, 'post_type') and event.post_type == 'message' else False

def _NOTICE():
    return lambda event, **kw: True if hasattr(event, 'post_type') and event.post_type == 'notice' else False

def _REQUEST():
    return lambda event, **kw: True

def _METAEVENT():
    return lambda event, **kw: False

nb_perm.USER      = _USER
nb_perm.SUPERUSER = _SUPERUSER
nb_perm.MESSAGE   = _MESSAGE
nb_perm.NOTICE    = _NOTICE
nb_perm.REQUEST   = _REQUEST
nb_perm.METAEVENT = _METAEVENT

# ──────────────────────────────────────────────────────
# 10. 填充 nonebot.exception
# ──────────────────────────────────────────────────────

nb_exc = sys.modules['nonebot.exception']
nb_exc.FinishedException  = FinishedException
nb_exc.PausedException    = PausedException
nb_exc.StopPropagation    = StopPropagation
nb_exc.SkippedException   = SkippedException

# ──────────────────────────────────────────────────────
# 11. 填充 nonebot.matcher
# ──────────────────────────────────────────────────────

nb_matcher = sys.modules['nonebot.matcher']

class Matcher:
    """Matcher 基类 — 插件 handler 的 context 载体"""
    def __init__(self, _gracone_matcher=None):
        self._gracone_matcher = _gracone_matcher
    
    async def finish(self, message=None, **kwargs):
        # 优先从当前上下文获取 GraconeMatcher
        gracone_matcher = self._gracone_matcher
        if gracone_matcher is None:
            from context import GraconeContext
            ctx = GraconeContext.get()
            if ctx and ctx.matcher:
                gracone_matcher = ctx.matcher
        
        if gracone_matcher and hasattr(gracone_matcher, 'finish'):
            await gracone_matcher.finish(message, **kwargs)
        raise FinishedException()
    
    async def send(self, message=None, **kwargs):
        gracone_matcher = self._gracone_matcher
        if gracone_matcher is None:
            from context import GraconeContext
            ctx = GraconeContext.get()
            if ctx and ctx.matcher:
                gracone_matcher = ctx.matcher
        
        if gracone_matcher and hasattr(gracone_matcher, 'send'):
            await gracone_matcher.send(message, **kwargs)
    
    def __repr__(self):
        return "Matcher()"

nb_matcher.Matcher        = Matcher
nb_matcher.current_bot     = contextvars.ContextVar('current_bot', default=None)
nb_matcher.current_event   = contextvars.ContextVar('current_event', default=None)
nb_matcher.current_matcher = contextvars.ContextVar('current_matcher', default=None)
nb_matcher.current_handler = contextvars.ContextVar('current_handler', default=None)

# ──────────────────────────────────────────────────────
# 12. 填充 nonebot.log
# ──────────────────────────────────────────────────────

nb_log = sys.modules['nonebot.log']
nb_log.logger = get_logger("Gracone.NoneBot")

# ──────────────────────────────────────────────────────
# 12b. 填充 nonebot.utils
# ──────────────────────────────────────────────────────

import asyncio
import functools

def run_sync(func):
    """将同步函数包装为异步（NoneBot utils.run_sync 兼容）"""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, functools.partial(func, *args, **kwargs))
    return wrapper

_reg('nonebot.utils')
nb_utils = sys.modules['nonebot.utils']
nb_utils.run_sync = run_sync

# ──────────────────────────────────────────────────────
# 12.5 填充 nonebot.config
# ──────────────────────────────────────────────────────

_reg('nonebot.config')
nb_config = sys.modules['nonebot.config']

class _FakeBotConfig:
    """假 Bot Config（仅提供 kawaii_status 所需的 nickname）"""
    def __init__(self):
        self.nickname = {"bot"}

class _FakeConfig:
    """空 Config 类，让 get_plugin_config(Config) 实例化时不报错"""
    pass

nb_config.Config = _FakeBotConfig

# ──────────────────────────────────────────────────────
# 13. 填充 nonebot.message（空壳）
# ──────────────────────────────────────────────────────

nb_msg = sys.modules['nonebot.message']
def _event_preprocessor(func):
    return func
def _event_postprocessor(func):
    return func
nb_msg.event_preprocessor  = _event_preprocessor
nb_msg.event_postprocessor = _event_postprocessor
nb_msg.handle_event        = lambda *a, **kw: None

# ──────────────────────────────────────────────────────
# 14. 填充 nonebot.plugin
# ──────────────────────────────────────────────────────

class PluginMetadata:
    """PluginMetadata 数据类"""
    def __init__(self, name: str = "", version: str = "1.0.0",
                 description: str = "", usage: str = "", type: str = "application",
                 homepage: str = "", supported_adapters: Set[str] = None,
                 config: Any = None, extra: dict = None):
        self.name = name
        self.version = version
        self.description = description
        self.usage = usage
        self.type = type
        self.homepage = homepage
        self.supported_adapters = supported_adapters or set()
        self.config = config
        self.extra = extra or {}

nb_plug = sys.modules['nonebot.plugin']

class Plugin:
    """假 Plugin — 供 get_loaded_plugins() 返回"""
    def __init__(self, name: str, module):
        self.name = name
        self.module = module
        self.metadata = None
        self.id_ = name

nb_plug.Plugin = Plugin
nb_plug.PluginMetadata = PluginMetadata
nb_plug.require = lambda name: None
nb_plug.get_plugin = lambda name: None
nb_plug.get_loaded_plugins = _get_loaded_nb_plugins
nb_plug.get_plugin_config = lambda: None
nb_plug.inherit_supported_adapters = lambda *a: set()

# 用后面定义的真实 get_plugin_config 覆盖 plugin 命名空间的假壳
# （注：get_plugin_config 在文件末尾附近定义，此处将在运行时被覆盖）
try:
    nb_plug.get_plugin_config = get_plugin_config
except NameError:
    pass  # 函数尚未定义，稍后处理

nb_plug_load = sys.modules['nonebot.plugin.load']
nb_plug_load.load_plugin = lambda *a, **kw: None
nb_plug_load.load_plugins = lambda *a, **kw: []
nb_plug_load.load_all_plugins = lambda *a, **kw: []
nb_plug_load.load_from_json = lambda *a, **kw: []
nb_plug_load.load_from_toml = lambda *a, **kw: []
nb_plug_load.load_builtin_plugin = lambda *a, **kw: None

# ──────────────────────────────────────────────────────
# 15. 填充 nonebot.adapters（通用基类）
# ──────────────────────────────────────────────────────

nb_adapters = sys.modules['nonebot.adapters']
nb_adapters.Event = Event
nb_adapters.MessageEvent = MessageEvent
nb_adapters.Bot = object
nb_adapters.Message = Message
nb_adapters.MessageSegment = MessageSegment

# ──────────────────────────────────────────────────────
# 16. 填充 nonebot.internal / drivers / dependencies（空壳）
# ──────────────────────────────────────────────────────

_nb_int = sys.modules['nonebot.internal']
_nb_int_matcher = sys.modules['nonebot.internal.matcher']
_nb_int_adapter = sys.modules['nonebot.internal.adapter']

_nb_drivers = sys.modules['nonebot.drivers']
_nb_drivers.Driver = object

_nb_deps = sys.modules['nonebot.dependencies']
_nb_deps.Dependent = object

_nb_plugins = sys.modules['nonebot.plugins']

# ──────────────────────────────────────────────────────
# 18. 清理临时变量
# ──────────────────────────────────────────────────────

del _reg, _lazy_on_command, _AutoModule
