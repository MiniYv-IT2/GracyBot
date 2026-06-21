"""
gracone_ext_plugins.py — 注入 NoneBot 外部插件的虚拟命名空间

为以下插件提供最小 fake 实现，使依赖它们的 NoneBot 插件能通过 import：
- nonebot_plugin_alconna: 命令系统
- nonebot_plugin_uninfo: 用户信息
- nonebot_plugin_orm: ORM 数据库
"""

import sys
import types
from typing import Any, Optional


def _reg(name: str) -> types.ModuleType:
    """注册一个虚拟模块到 sys.modules"""
    mod = types.ModuleType(name)
    mod.__package__ = name
    mod.__path__ = []
    sys.modules[name] = mod
    return mod


# ============================================================
# nonebot_plugin_alconna — 最小 fake
# ============================================================

_reg('nonebot_plugin_alconna')
nb_alconna = sys.modules['nonebot_plugin_alconna']

store_true = True


class Alconna:
    """最小 Alconna 命令定义 — 用于装饰器注解"""
    def __init__(self, command: str, *options, **kwargs):
        self.command = command
        self.options = options
        self._shortcut_handlers = []

    def shortcut(self, pattern: str, config: dict = None):
        """注册快捷方式"""
        self._shortcut_handlers.append((pattern, config or {}))


class Args:
    """位置参数定义 — 支持 Args['name', type] 下标语法"""
    def __init__(self, *args, **kwargs):
        pass
    
    def __class_getitem__(cls, item):
        """支持 Args['name', type] 语法"""
        return cls


class Option:
    """选项定义"""
    def __init__(self, *args, **kwargs):
        pass


class Query:
    """Alconna 查询 — 依赖注入"""
    def __init__(self, *args, key="", default=None, **kwargs):
        self._key = key or (args[0] if args else "")
        self._default = default
        self.result = self._default
    
    def __class_getitem__(cls, item):
        """支持 Query[bool] 语法"""
        return cls


class AlconnaQuery:
    """AlconnaQuery 工厂 — 支持 AlconnaQuery('key', default)"""
    def __init__(self, key: str = "", default=None):
        self._key = key
        self._default = default
    
    def __call__(self, *args, **kwargs):
        return Query(self._key, default=self._default)


class UniMessage:
    """统一消息构建器 — .text().image().send()"""
    def __init__(self, msg=None):
        self._parts = []
        if msg is not None:
            self._parts.append(msg)
    
    @staticmethod
    def image(**kwargs) -> "UniMessage":
        return UniMessage(Image(**kwargs))
    
    @staticmethod
    def text(text: str) -> "UniMessage":
        return UniMessage(Text(text))
    
    def __add__(self, other):
        if isinstance(other, UniMessage):
            new = UniMessage()
            new._parts = self._parts + other._parts
            return new
        elif isinstance(other, (Text, Image)):
            new = UniMessage()
            new._parts = self._parts + [other]
            return new
        elif isinstance(other, str):
            new = UniMessage()
            new._parts = self._parts + [Text(other)]
            return new
        return self
    
    async def send(self, *args, **kwargs):
        """发送 — 委托给 GraconeMatcher.send/finish"""
        from context import GraconeContext
        ctx = GraconeContext.get()
        text_parts = []
        image_raw = None
        for part in self._parts:
            if isinstance(part, Text):
                text_parts.append(str(part))
            elif isinstance(part, Image) and part.raw:
                image_raw = part.raw
        
        msg = '\n'.join(text_parts) if text_parts else None
        if ctx and ctx.gracy_event:
            target = ctx.gracy_event.target_id
            chat_type = getattr(ctx.gracy_event, 'chat_type', 'private')
            tag = getattr(ctx, 'adapter_tag', None)
            
            if msg and not image_raw:
                # 纯文本 → 直接 send
                if ctx.matcher:
                    await ctx.matcher.send(msg)
            elif image_raw:
                # 文字+图片 → 通过 gracy_send_msg 一条消息发送
                from core.gracy_adapter.send import gracy_send_msg
                from core.gracy_adapter.message import GracyText, GracyImage
                segs = []
                if msg:
                    segs.append(GracyText(text=msg))
                segs.append(GracyImage(file_data=image_raw))
                await gracy_send_msg(
                    target, *segs,
                    chat_type=chat_type,
                    tag=tag,
                )
            elif msg:
                if ctx.matcher:
                    await ctx.matcher.send(msg)


class Image:
    """图片消息段"""
    def __init__(self, raw: bytes = b"", path: str = "", url: str = ""):
        # 处理 BytesIO → bytes（必须 seek(0) 否则读到空）
        if hasattr(raw, 'read'):
            raw.seek(0)
            raw = raw.read()
        self.raw = raw
        self.path = path
        self.url = url
    
    def __radd__(self, other):
        # str + Image → UniMessage
        if isinstance(other, str):
            um = UniMessage()
            um._parts = [Text(other), self]
            return um
        # Text + Image → UniMessage
        if isinstance(other, Text):
            um = UniMessage()
            um._parts = [other, self]
            return um
        return NotImplemented


class Text:
    """文本消息段"""
    def __init__(self, text: str = ""):
        self._text = text
    
    def __str__(self):
        return self._text
    
    def __add__(self, other):
        # Text + str → Text
        if isinstance(other, str):
            return Text(self._text + other)
        # Text + Text → Text
        if isinstance(other, Text):
            return Text(self._text + other._text)
        # Text + Image → UniMessage
        if isinstance(other, Image):
            um = UniMessage()
            um._parts = [self, other]
            return um
        # Text + UniMessage → 合并
        if isinstance(other, UniMessage):
            return NotImplemented
        return NotImplemented
    
    def __radd__(self, other):
        if isinstance(other, str):
            return Text(other + self._text)
        return NotImplemented


def on_alconna(cmd: Alconna, **kwargs) -> Any:
    """on_alconna 装饰器 — 简化为 on_command 方式
    
    对于 cchess 插件，它的 Alconna 命令如 "cchess" 会被简化为命令匹配。
    对于 "显示棋盘"、"结束下棋" 这类文本匹配，使用 keyword 模式。
    """
    from bridge.matcher_bridge import on_command, on_keyword
    
    command = cmd.command if hasattr(cmd, 'command') else str(cmd)
    
    # 如果是英文命令（如 "cchess"），用 on_command
    if command.isascii() and command.isalpha():
        return on_command(command, **kwargs)
    
    # 如果是中文文本（如 "显示棋盘"），用 on_keyword
    return on_keyword({command}, **kwargs)


class Command:
    """Alconna Command — 链式 builder API
    
    支持: Command("status").usage("...").action(lambda).build(...)
    """

    def __init__(self, name: str, help_text: str = "", **kwargs):
        self.name = name
        self.help_text = help_text
        self._usage_text = ""
        self._action_func = None
        self._options = {}

    def usage(self, text: str) -> "Command":
        self._usage_text = text
        return self

    def action(self, func) -> "Command":
        self._action_func = func
        return self

    def option(self, *args, **kwargs) -> "Command":
        return self

    def build(self, block: bool = True, rule=None, aliases=None,
              use_cmd_start: bool = False, permission=None, **kwargs) -> Any:
        """构建并注册 matcher"""
        from bridge.matcher_bridge import on_command

        # 合并原始命令名和别名
        all_triggers = [self.name] + list(aliases or [])

        # 注册命令 matcher
        matcher = on_command(
            self.name,
            aliases=list(aliases or []),
            block=block,
            rule=rule,
            permission=permission,
        )

        # 注册处理函数（调用 action 并发送结果）
        async def handler(*args, **kwargs):
            try:
                result = self._action_func() if self._action_func else None
                if result is not None:
                    from bridge.matcher_bridge import _send_via_context
                    from context import GraconeContext
                    from core.gracy_adapter.send import gracy_send_msg
                    from core.gracy_adapter.message import GracyImage, GracyText
                    ctx = GraconeContext.get()
                    if ctx:
                        target = ctx.gracy_event.target_id
                        chat_type = ctx.gracy_event.chat_type
                        tag = ctx.adapter_tag
                        # UniMessage.image(raw=...) → 提取图片字节
                        if hasattr(result, '_parts'):
                            for part in result._parts:
                                if hasattr(part, 'raw') and part.raw:
                                    await gracy_send_msg(target, GracyImage(file_data=part.raw),
                                                         chat_type=chat_type, tag=tag)
                                elif hasattr(part, '_text'):
                                    await gracy_send_msg(target, GracyText(text=part._text),
                                                         chat_type=chat_type, tag=tag)
                            return
                        await gracy_send_msg(target, GracyText(text=str(result)),
                                             chat_type=chat_type, tag=tag)
            except Exception as e:
                import logging
                logging.getLogger("Gracone").error(f"Command.build handler 异常: {e}", exc_info=True)

        matcher._handlers.append(handler)
        return matcher


nb_alconna.Alconna       = Alconna
nb_alconna.Command      = Command
nb_alconna.Args          = Args
nb_alconna.Option        = Option
nb_alconna.Query         = Query
nb_alconna.AlconnaQuery  = AlconnaQuery
nb_alconna.UniMessage    = UniMessage
nb_alconna.Image         = Image
nb_alconna.Text          = Text
nb_alconna.on_alconna    = on_alconna
nb_alconna.store_true    = store_true

# ── nonebot_plugin_alconna.uniseg ──
_reg('nonebot_plugin_alconna.uniseg')
nb_alconna_uniseg = sys.modules['nonebot_plugin_alconna.uniseg']
nb_alconna_uniseg.UniMessage = UniMessage


# ============================================================
# nonebot_plugin_uninfo — 最小 fake
# ============================================================

_reg('nonebot_plugin_uninfo')
nb_uninfo = sys.modules['nonebot_plugin_uninfo']


class Scene:
    def __init__(self, is_private: bool = False):
        self.is_private = is_private


class Member:
    def __init__(self, nick: str = ""):
        self.nick = nick


class User:
    def __init__(self, id: str = "0", nick: str = "", name: str = ""):
        self.id = id
        self.nick = nick
        self.name = name


class Uninfo:
    """统一用户信息"""
    def __init__(self, user_id: str = "0", nick: str = "", is_private: bool = True):
        self.scope = "gracone"
        self.self_id = "0"
        self.scene = Scene(is_private=is_private)
        self.scene_path = f"{'private' if is_private else 'group'}_{user_id}"
        self.user = User(id=user_id, nick=nick, name=nick)
        self.member = Member(nick=nick)


nb_uninfo.Uninfo = Uninfo
nb_uninfo.Scene  = Scene
nb_uninfo.Member = Member
nb_uninfo.User   = User


# ============================================================
# nonebot_plugin_orm — 内存存储替代 SQLAlchemy ORM
# ============================================================

_reg('nonebot_plugin_orm')
nb_orm = sys.modules['nonebot_plugin_orm']

# 内存数据库 — {ModelClass: {pk_value: instance}}
_memory_db: dict = {}

def _pk(model_inst) -> tuple:
    """获取模型主键值（第一个 mapped_column）"""
    pk_cols = getattr(model_inst.__class__, '_pk_cols', None)
    if pk_cols:
        return tuple(getattr(model_inst, c, None) for c in pk_cols)
    return (id(model_inst),)

class Model:
    """ORM 模型基类 — 内存存储"""
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
    
    def __repr__(self):
        cls_name = self.__class__.__name__
        attrs = ', '.join(f'{k}={v!r}' for k, v in self.__dict__.items() if not k.startswith('_'))
        return f'{cls_name}({attrs})'
    
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # 收集主键列
        pk_cols = []
        for attr_name in dir(cls):
            if attr_name.startswith('_'):
                continue
            col = getattr(cls, attr_name, None)
            if hasattr(col, '_is_mapped_column'):
                if getattr(col, 'primary_key', False):
                    pk_cols.append(attr_name)
        cls._pk_cols = tuple(pk_cols) if pk_cols else ('id',)
        # 注册存储空间
        if cls not in _memory_db:
            _memory_db[cls] = {}

# 假 mapped_column
class _FakeColumn:
    def __init__(self, type=None, primary_key=False, default=None, **kwargs):
        self.type = type
        self.primary_key = primary_key
        self.default = default
        self._is_mapped_column = True
    
    def __set_name__(self, owner, name):
        self.name = name
    
    def __eq__(self, other):
        return _WhereClause((self.name, '==', other))
    
    def __ne__(self, other):
        return _WhereClause((self.name, '!=', other))
    
    def desc(self):
        """模拟 desc() 排序"""
        return ('desc', self.name)
    
    def __hash__(self):
        return id(self)

class _Mapped:
    """假 Mapped 类型注解"""
    def __class_getitem__(cls, item):
        return cls

# ── 假 select ──

class _WhereClause:
    def __init__(self, condition):
        self._condition = condition

class _SelectStatement:
    def __init__(self, model_cls):
        self._model_cls = model_cls
        self._where_conditions = []
        self._order_by_cols = []
    
    def where(self, *conditions):
        self._where_conditions.extend(conditions)
        return self
    
    def order_by(self, *cols):
        self._order_by_cols.extend(cols)
        return self

def select(model_cls):
    """假 select — 返回查询描述对象"""
    return _SelectStatement(model_cls)

# ── 假 Session ──

class _MemorySession:
    def __init__(self):
        self._to_add = []
        self._to_delete = []
    
    async def scalar(self, statement):
        """执行查询并返回单条结果"""
        if not isinstance(statement, _SelectStatement):
            return None
        table = _memory_db.get(statement._model_cls, {})
        records = list(table.values())
        
        # 应用 where 条件
        for cond in statement._where_conditions:
            records = _apply_condition(records, cond)
        
        if not records:
            return None
        
        # 应用 order_by
        for col in statement._order_by_cols:
            if isinstance(col, tuple) and col[0] == 'desc':
                col_name = col[1]
                records.sort(key=lambda r, cn=col_name: getattr(r, cn, ''), reverse=True)
            else:
                col_name = str(col)
                records.sort(key=lambda r, cn=col_name: getattr(r, cn, ''), reverse=False)
        
        return records[0] if records else None
    
    def add(self, instance):
        self._to_add.append(instance)
    
    def delete(self, instance):
        self._to_delete.append(instance)
    
    async def commit(self):
        for inst in self._to_add:
            table = _memory_db[inst.__class__]
            pk = _pk(inst)
            table[pk] = inst
        self._to_add.clear()
        for inst in self._to_delete:
            table = _memory_db.get(inst.__class__, {})
            pk = _pk(inst)
            table.pop(pk, None)
        self._to_delete.clear()
    
    async def flush(self):
        pass
    
    async def close(self):
        pass
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, *args):
        pass

def _apply_condition(records, cond):
    """应用 where 条件过滤 — 处理 _WhereClause"""
    if isinstance(cond, _WhereClause):
        col_name, op, value = cond._condition
        if op == '==':
            return [r for r in records if getattr(r, col_name, None) == value]
        elif op == '!=':
            return [r for r in records if getattr(r, col_name, None) != value]
    # 处理 and_、or_ 组合 — 逐个过滤
    if hasattr(cond, 'clauses'):
        for sub_cond in cond.clauses:
            records = _apply_condition(records, sub_cond)
    return records

# ── 公开接口 ──

def get_session():
    """返回内存 session"""
    return _MemorySession()

# ── 注册到命名空间 ──

nb_orm.Model         = Model
nb_orm.Mapped        = _Mapped
nb_orm.mapped_column = _FakeColumn
nb_orm.select        = select
nb_orm.get_session   = get_session
nb_orm.Boolean       = bool
nb_orm.String        = str
nb_orm.Text          = str
nb_orm.Integer       = int
nb_orm.DateTime      = type('DateTime', (), {})()
nb_orm.Column        = _FakeColumn

# 覆盖 sqlalchemy.select — 因为 game.py 用 from sqlalchemy import select
import sqlalchemy as _real_sa
_real_sa.select = select

# 覆盖 sqlalchemy.orm.Mapped / mapped_column — model.py 直接 from sqlalchemy.orm import
import sqlalchemy.orm as _real_sa_orm
_real_sa_orm.Mapped = _Mapped
_real_sa_orm.mapped_column = _FakeColumn

# 确保 from sqlalchemy import xxx 在插件包内也可用（通过 sys.modules 已有真实模块）


# ============================================================
# 清理
# ============================================================

del _reg
