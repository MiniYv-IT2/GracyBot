"""Matcher 桥接 — NoneBot Matcher 的 Gracone 实现

将 NoneBot 的 on_command / on_regex / on_keyword 注册为 GraconeMatcher 实例。
当 GracyBot 事件到达时，匹配并执行 NoneBot 插件的 handler。
"""

import inspect
import re
from typing import Any, Callable, Dict, List, Optional, Pattern, Set, Tuple, Union

from graci import gracy_send_msg, get_logger
from graci import GracyText

from gracone_nonebot import (
    FinishedException, PausedException, StopPropagation, SkippedException,
    Message, MessageSegment, GraconeRule,
)
from context import GraconeContext
from bridge.event_translator import gracy_to_nb_event
from bridge.message_translator import nb_to_gracy_segments
from bridge.api_bridge import create_bot_for_event

logger = get_logger("Gracone.Matcher")


class GraconeMatcher:
    """Gracone 模拟的 NoneBot Matcher
    
    这是 NoneBot 插件开发者熟悉的入口：
        matcher = on_command("hello")
        @matcher.handle()
        async def _(event: ...): ...
    """
    
    def __init__(self, matcher_type: str = "command", 
                 cmds: Tuple[str, ...] = (),
                 pattern: Optional[str] = None,
                 keywords: Tuple[str, ...] = (),
                 rule: Optional[Any] = None,
                 permission: Optional[Any] = None,
                 handlers: Optional[list] = None,
                 block: bool = True,
                 **kwargs):
        self.matcher_type = matcher_type  # "command" | "regex" | "keyword" | "message"
        self.cmds = cmds
        self.pattern = pattern
        self._compiled: Optional[Pattern] = re.compile(pattern) if pattern else None
        self.keywords = keywords
        self.rule = rule
        self.permission = permission
        self.block = block
        self._handlers: List[Callable] = handlers or []
        self._preprocessors: List[Callable] = []
        self._postprocessors: List[Callable] = []
        
        # 解析 rule 中的条件
        self._need_to_me = self._check_rule_to_me(rule)
    
    def _check_rule_to_me(self, rule) -> bool:
        """检查 rule 中是否包含 to_me()"""
        if rule is None:
            return False
        # 单个 to_me 规则
        if hasattr(rule, 'rule_type') and rule.rule_type == 'to_me':
            return True
        # 组合规则（& 连接）
        if hasattr(rule, '_rules'):
            for sub in rule._rules:
                if hasattr(sub, 'rule_type') and sub.rule_type == 'to_me':
                    return True
        return False
    
    def evaluate_rules(self, rule: Any, raw_text: str, is_at_bot: bool,
                       chat_type: str) -> bool:
        """评估所有规则是否通过
        
        对于组合规则（& 连接），需要所有规则都通过。
        对于函数规则，调用函数检查。
        """
        if rule is None:
            return True
        
        # 获取规则列表
        rules = []
        if hasattr(rule, '_rules'):
            rules = rule._rules
        else:
            rules = [rule]
        
        for sub in rules:
            if isinstance(sub, GraconeRule):
                # 内建规则
                if sub.rule_type == 'to_me':
                    # 私聊天然 to_me，群聊需要 is_at_bot
                    if chat_type == 'private':
                        continue  # 私聊 always pass
                    if not is_at_bot:
                        return False
                elif sub.rule_type == 'startswith':
                    prefixes = sub.params.get('prefix', ())
                    if prefixes and not raw_text.startswith(prefixes[0] if isinstance(prefixes, (list, tuple)) else prefixes):
                        return False
                elif sub.rule_type == 'regex':
                    pattern = sub.params.get('pattern', '')
                    if pattern and not re.search(pattern, raw_text):
                        return False
            elif callable(sub):
                # 函数规则 — 调用它
                try:
                    from context import GraconeContext
                    ctx = GraconeContext.get()
                    event = ctx._nb_event if ctx and hasattr(ctx, '_nb_event') else None
                    result = sub(event) if event else sub()
                    if not result:
                        return False
                except Exception:
                    return False
        return True
    
    def handle(self) -> Callable:
        """注册 handler 的装饰器
        
        NoneBot 插件用法:
            @matcher.handle()
            async def my_handler(event: GroupMessageEvent, bot: Bot): ...
        """
        def decorator(func: Callable):
            self._handlers.append(func)
            return func
        return decorator
    
    def receive(self) -> Callable:
        """注册 receive handler（简化实现，等同于 handle）"""
        return self.handle()
    
    def got(self, key: str, prompt: Optional[Union[str, Message, MessageSegment]] = None,
            args_parser: Optional[Callable] = None) -> Callable:
        """简化 got 实现 — 直接当作 handler"""
        return self.handle()
    
    async def send(self, message: Any, **kwargs):
        """matcher.send() — 发送消息但不终止
        
        NoneBot 插件中调用 matcher.send("xxx") 发送回复但不停止处理。
        我们需要通过 GraconeContext 获取事件信息，然后调用 gracy_send_msg。
        """
        ctx = GraconeContext.get()
        if ctx is None:
            logger.warning("GraconeContext 不可用，无法发送")
            return
        
        await _send_via_context(ctx, message)
    
    async def finish(self, message: Any = None, **kwargs):
        """matcher.finish() — 发送消息并终止
        
        发送消息后抛出 FinishedException 终止 handler 链。
        """
        if message is not None:
            await self.send(message)
        raise FinishedException()
    
    async def pause(self, message: Any = None, **kwargs):
        """matcher.pause() — 暂停等待输入"""
        if message is not None:
            await self.send(message)
        raise PausedException()
    
    def skip(self):
        """跳过当前 handler"""
        raise SkippedException()
    
    def __repr__(self) -> str:
        return f"GraconeMatcher(type={self.matcher_type}, cmds={self.cmds})"
    
    def match_event(self, raw_text: str, is_at_bot: bool = False, 
                    chat_type: str = "private") -> bool:
        """判断本 matcher 是否匹配给定的消息"""
        text = raw_text.strip()
        
        # to_me 检查（私聊天然满足 to_me）
        if self._need_to_me and not is_at_bot:
            if chat_type != 'private':
                return False
        
        # 文本匹配
        matched = False
        self._last_regex_match = None  # 重置正则匹配结果
        if self.matcher_type == "command":
            for cmd in self.cmds:
                cmd = cmd.strip().lstrip('/').strip()
                stripped = text.lstrip('/').strip()
                if stripped == cmd or stripped.startswith(cmd + ' '):
                    matched = True
                    break
        
        elif self.matcher_type == "regex":
            if self._compiled:
                m = self._compiled.search(text)
                matched = bool(m)
                if m:
                    self._last_regex_match = m.groupdict()
        
        elif self.matcher_type == "keyword":
            for kw in self.keywords:
                if kw in text:
                    matched = True
                    break
        
        elif self.matcher_type == "message":
            matched = True
        
        if not matched:
            return False
        
        # 额外规则评估 — 只评估 GraconeRule 类型，函数规则在 dispatch 时处理
        if not self._evaluate_gracone_rules(self.rule, text, is_at_bot, chat_type):
            return False
        
        return True
    
    def _evaluate_gracone_rules(self, rule, raw_text, is_at_bot, chat_type) -> bool:
        """仅评估 GraconeRule 类型的内建规则，跳过 callable"""
        if rule is None:
            return True
        rules = getattr(rule, '_rules', [rule])
        for sub in rules:
            if isinstance(sub, GraconeRule):
                if sub.rule_type == 'to_me':
                    if chat_type == 'private':
                        continue
                    if not is_at_bot:
                        return False
                elif sub.rule_type == 'startswith':
                    prefixes = sub.params.get('prefix', ())
                    if prefixes and not raw_text.startswith(prefixes[0] if isinstance(prefixes, (list, tuple)) else prefixes):
                        return False
                elif sub.rule_type == 'regex':
                    pattern = sub.params.get('pattern', '')
                    if pattern and not re.search(pattern, raw_text):
                        return False
            # callable 规则跳过 — dispatch 时再处理
        return True
    
    def evaluate_callable_rules(self, rule) -> bool:
        """评估 callable 规则（函数规则），在 GraconeContext 就绪后调用
        
        注：NoneBot 的 Depends 注入在有参规则函数上无法使用，
        TypeError 说明函数需要注入参数 → 静默通过（由 handler 自行校验）。
        """
        if rule is None:
            return True
        rules = getattr(rule, '_rules', [rule])
        for sub in rules:
            if callable(sub) and not isinstance(sub, GraconeRule):
                try:
                    result = sub()
                    if not result:
                        logger.debug(f"  callable 规则 {sub.__name__} 返回 False")
                        return False
                except TypeError:
                    # 有参规则函数（依赖注入）— 跳过，由 handler 自行校验
                    continue
                except Exception:
                    return False
        return True
    
    def get_command(self) -> str:
        """获取匹配到的命令（NoneBot 插件可能通过 state 访问）"""
        if self.cmds:
            return self.cmds[0]
        return ""
    
    def shortcut(self, pattern: str, config: dict = None) -> None:
        """注册快捷方式 — 为当前 matcher 添加额外的关键词/正则匹配
        
        NoneBot Alconna 插件的 shortcut 功能，将自然语言映射到命令。
        
        关键设计：handlers 是在模块级装饰器 (@handle()) 中才注册的，
        shortcut() 调用时 handlers 为空。因此不复制 handlers，
        而是让新 matcher 通过 _parent 引用原 matcher 共享 handlers。
        """
        cfg = config or {}
        prefix = cfg.get('prefix', False)
        wrapper = cfg.get('wrapper', None)
        
        if prefix:
            import re
            # 提取纯文本前缀，去掉所有正则语法残留
            plain_prefix = re.sub(r'\(.*?\)|\[.*?\]|\\[a-zA-Z]|\?|<[^>]+>', '', pattern)
            # 清理残留的括号和空白
            plain_prefix = re.sub(r'[()\[\]{}]', '', plain_prefix).strip()
            if plain_prefix:
                new_matcher = GraconeMatcher(
                    matcher_type="keyword",
                    keywords=(plain_prefix.strip(),),
                    rule=self.rule,
                    permission=self.permission,
                    block=self.block,
                )
                new_matcher._parent = self  # 引用原 matcher 共享 handlers
                matcher_manager.register(new_matcher)
        else:
            new_matcher = GraconeMatcher(
                matcher_type="regex",
                pattern=pattern,
                rule=self.rule,
                permission=self.permission,
                block=self.block,
            )
            new_matcher._parent = self
            matcher_manager.register(new_matcher)


# ─────────────────────────────────────────────────────
# Matcher 管理器 — 全局状态
# ─────────────────────────────────────────────────────

class MatcherManager:
    """管理所有已注册的 GraconeMatcher 实例"""
    
    def __init__(self):
        self._matchers: List[GraconeMatcher] = []
    
    def register(self, matcher: GraconeMatcher):
        """注册一个 matcher"""
        self._matchers.append(matcher)
        logger.debug(f"注册 Matcher: {matcher}")
    
    def get_matchers(self) -> List[GraconeMatcher]:
        """获取所有注册的 matcher"""
        return list(self._matchers)
    
    def find_matches(self, raw_text: str, is_at_bot: bool = False,
                     chat_type: str = "private") -> List[GraconeMatcher]:
        """查找匹配的 matcher，按 block 排序（block=True 的优先）"""
        matched = []
        for matcher in self._matchers:
            if matcher.match_event(raw_text, is_at_bot, chat_type):
                matched.append(matcher)
        # block=True 的 matcher 优先
        matched.sort(key=lambda m: (not m.block, 0))
        return matched
    
    def clear(self):
        """清除所有 matcher"""
        self._matchers.clear()
    
    def unregister_plugin(self, plugin_name: str):
        """移除属于指定插件的所有 matcher"""
        before = len(self._matchers)
        self._matchers = [m for m in self._matchers 
                          if getattr(m, '_plugin_name', None) != plugin_name]
        removed = before - len(self._matchers)
        if removed:
            logger.info(f"  ── 已移除 {removed} 个 {plugin_name} matcher")


# 全局单例
matcher_manager = MatcherManager()


# ─────────────────────────────────────────────────────
# NoneBot on_command/on_regex/on_keyword 实现
# ─────────────────────────────────────────────────────

def on_command(*cmds: str, aliases: Optional[Set[str]] = None,
               rule: Optional[Any] = None, permission: Optional[Any] = None,
               handlers: Optional[list] = None, block: bool = True,
               **kwargs) -> GraconeMatcher:
    """模拟 nonebot.on_command
    
    返回 GraconeMatcher 实例并自动注册到管理器。
    """
    full_cmds = tuple(cmd.lstrip('/') for cmd in cmds)
    if aliases:
        full_cmds = full_cmds + tuple(a.lstrip('/') for a in aliases)
    
    matcher = GraconeMatcher(
        matcher_type="command",
        cmds=full_cmds,
        rule=rule,
        permission=permission,
        handlers=handlers,
        block=block,
    )
    matcher_manager.register(matcher)
    return matcher


def on_regex(pattern: str, flags: int = 0, rule: Optional[Any] = None,
             permission: Optional[Any] = None, block: bool = True,
             **kwargs) -> GraconeMatcher:
    """模拟 nonebot.on_regex"""
    matcher = GraconeMatcher(
        matcher_type="regex",
        pattern=pattern,
        rule=rule,
        permission=permission,
        block=block,
    )
    matcher_manager.register(matcher)
    return matcher


def on_keyword(keywords: Set[str], rule: Optional[Any] = None,
               permission: Optional[Any] = None, block: bool = True,
               **kwargs) -> GraconeMatcher:
    """模拟 nonebot.on_keyword"""
    matcher = GraconeMatcher(
        matcher_type="keyword",
        keywords=tuple(keywords),
        rule=rule,
        permission=permission,
        block=block,
    )
    matcher_manager.register(matcher)
    return matcher


def on_message(rule: Optional[Any] = None, permission: Optional[Any] = None,
               block: bool = True, **kwargs) -> GraconeMatcher:
    """模拟 nonebot.on_message"""
    matcher = GraconeMatcher(
        matcher_type="message",
        rule=rule,
        permission=permission,
        block=block,
    )
    matcher_manager.register(matcher)
    return matcher


def on_notice(*, block: bool = True, **kwargs) -> GraconeMatcher:
    return GraconeMatcher(matcher_type="notice", block=block)


def on_request(*, block: bool = True, **kwargs) -> GraconeMatcher:
    return GraconeMatcher(matcher_type="request", block=block)


# ─────────────────────────────────────────────────────
# 事件分发 — 从 GracyBot EventBus 到 NoneBot handler
# ─────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────
# 依赖注入 — 自动解析 NoneBot handler 的 Depends 参数
# ─────────────────────────────────────────────────────

def _resolve_depends_handler(handler, extra_kwargs: dict = None):
    """自动解析 NoneBot handler 的依赖注入参数
    
    处理两种情况：
    1. param: str = Depends(func) — 默认值是 callable
    2. param: UserId — Annotated 类型别名，无默认值，从 annotation 提取 Depends 元数据
    
    支持多层依赖链（如 get_user_id(uninfo: Uninfo) → 先解析 Uninfo）。
    extra_kwargs 用于注入预解析的值（如 regex match groups）。
    """
    sig = inspect.signature(handler)
    resolved_kwargs = dict(extra_kwargs or {})
    
    # 从 GraconeContext 获取通用注入对象
    ctx = GraconeContext.get()
    _common_injections = {}
    if ctx and ctx.nb_event:
        from gracone_nonebot import Matcher
        # 创建 Uninfo — 从事件中提取用户信息
        ev = ctx.nb_event
        user_id = str(getattr(ev, 'user_id', '0'))
        nickname = str(getattr(ev, '_nickname', ''))
        chat_type = str(getattr(ev, 'message_type', 'private'))
        is_private = chat_type != 'group'
        try:
            from nonebot_plugin_uninfo import Uninfo
            _uninfo = Uninfo(user_id=user_id, nick=nickname, is_private=is_private)
        except Exception:
            _uninfo = None
        
        _common_injections = {
            'Matcher': Matcher(),
            'Event': ev,
            'MessageEvent': ev,
            'Uninfo': _uninfo,
        }
    
    def _try_resolve(callable_obj):
        """尝试解析一个依赖，支持递归"""
        try:
            return callable_obj()
        except TypeError:
            # 可能需要参数 — 检查其签名
            try:
                inner_sig = inspect.signature(callable_obj)
                inner_kwargs = {}
                for inner_name, inner_param in inner_sig.parameters.items():
                    inner_ann = inner_param.annotation
                    inner_default = inner_param.default
                    
                    # 尝试从已解析结果取
                    if inner_name in resolved_kwargs:
                        inner_kwargs[inner_name] = resolved_kwargs[inner_name]
                        continue
                    
                    # 尝试从 annotation 匹配已解析结果
                    if inner_ann is not inspect.Parameter.empty:
                        ann_name = getattr(inner_ann, '__name__' if not hasattr(inner_ann, '__metadata__') else '__origin__', str(inner_ann))
                        for k, v in resolved_kwargs.items():
                            if type(v).__name__ == ann_name or type(v).__class__.__name__ == ann_name:
                                inner_kwargs[inner_name] = v
                                break
                        else:
                            # 尝试通用注入
                            for k, v in _common_injections.items():
                                if k == ann_name or type(v).__class__.__name__ == ann_name:
                                    inner_kwargs[inner_name] = v
                                    break
                    
                    # 有默认值则用默认值
                    if inner_name not in inner_kwargs and inner_default is not inspect.Parameter.empty:
                        inner_kwargs[inner_name] = inner_default
                
                return callable_obj(**inner_kwargs)
            except Exception:
                return None
        except Exception:
            return None
    
    # 多轮解析参数
    for name, param in sig.parameters.items():
        # 已在 extra_kwargs 中（如 regex matched）→ 跳过
        if name in resolved_kwargs:
            continue
        
        resolved = None
        
        # 情况 1：默认值是 callable（Depends 包装）
        default = param.default
        if default is not inspect.Parameter.empty:
            if callable(default) and not isinstance(default, (str, int, float, bool, bytes, type(None))):
                resolved = _try_resolve(default)
            else:
                resolved_kwargs[name] = default
                continue
        
        # 情况 2：从 Annotated 类型别名提取 Depends
        if resolved is None:
            ann = param.annotation
            if ann is not inspect.Parameter.empty:
                metadata = getattr(ann, '__metadata__', None)
                if metadata:
                    for meta in metadata:
                        if callable(meta):
                            resolved = _try_resolve(meta)
                            if resolved is not None:
                                break
        
        # 情况 3：从通用注入匹配类型名
        if resolved is None and ann is not inspect.Parameter.empty:
            ann_name = getattr(ann, '__name__' if not hasattr(ann, '__metadata__') else '__origin__', None)
            if ann_name and ann_name in _common_injections:
                resolved = _common_injections[ann_name]
        
        if resolved is not None:
            resolved_kwargs[name] = resolved
    
    return handler(**resolved_kwargs)


async def _send_via_context(ctx: GraconeContext, message: Any):
    """通过 GraconeContext 发送消息"""
    if ctx is None or ctx.gracy_event is None:
        return
    
    gracy_event = ctx.gracy_event
    target = getattr(gracy_event, 'target_id', '')
    chat_type = getattr(gracy_event, 'chat_type', 'private')
    tag = ctx.adapter_tag
    
    if isinstance(message, str):
        await gracy_send_msg(target, GracyText(text=message), 
                             chat_type=chat_type, tag=tag)
    elif isinstance(message, MessageSegment):
        segments = nb_to_gracy_segments(Message(message))
        await gracy_send_msg(target, *segments, chat_type=chat_type, tag=tag)
    elif isinstance(message, Message):
        segments = nb_to_gracy_segments(message)
        await gracy_send_msg(target, *segments, chat_type=chat_type, tag=tag)
    else:
        await gracy_send_msg(target, GracyText(text=str(message)),
                             chat_type=chat_type, tag=tag)


async def dispatch_event(gracy_event, adapter_tag=None) -> bool:
    """将 GracyBot 事件分发给匹配的 NoneBot handler
    
    Args:
        gracy_event: GracyBot 原始事件
        adapter_tag: 适配器标签
        
    Returns:
        bool: True 如果有 handler 处理了事件且设置了 block，否则 False
    """
    raw_text = getattr(gracy_event, 'raw_text', '') or ''
    is_at_bot = getattr(gracy_event, 'is_at_bot', False)
    chat_type = getattr(gracy_event, 'chat_type', 'private')
    
    # 查找匹配的 matcher
    matched = matcher_manager.find_matches(raw_text, is_at_bot, chat_type)
    if not matched:
        return False
    
    # 翻译事件
    bot_self_id = "0"
    raw_data = getattr(gracy_event, 'raw_data', {}) or {}
    if isinstance(raw_data, dict):
        bot_self_id = str(raw_data.get('self_id', raw_data.get('robot_id', '0')))
    
    nb_event = gracy_to_nb_event(gracy_event, bot_self_id)
    
    # 创建 Bot 实例
    bot = create_bot_for_event(gracy_event, adapter_tag)
    
    # 设置 matcher 上下文变量
    from gracone_nonebot import nb_matcher as nb_matcher_mod
    nb_matcher_mod.current_bot.set(bot)
    nb_matcher_mod.current_event.set(nb_event)
    
    # 处理每个匹配的 matcher
    for matcher in matched:
        # 获取 handlers（支持 _parent 共享）
        handlers = matcher._handlers
        if not handlers and hasattr(matcher, '_parent') and matcher._parent:
            handlers = matcher._parent._handlers
        if not handlers:
            logger.debug(f"  matcher {matcher} 无 handlers，跳过")
            continue
        
        # 创建 GraconeContext（必须在 callable 规则评估前）
        ctx = GraconeContext(
            gracy_event=gracy_event,
            nb_event=nb_event,
            raw_text=raw_text,
            command=matcher.get_command(),
            matcher=matcher,
            adapter_tag=adapter_tag,
        )
        
        # 设置 matcher 上下文
        nb_matcher_mod.current_matcher.set(matcher)
        
        with ctx:
            # 重新评估 callable 规则（函数如 game_not_running 等）
            if not matcher.evaluate_callable_rules(matcher.rule):
                logger.debug(f"  matcher {matcher} callable 规则不通过，跳过")
                continue
            
            try:
                for handler in handlers:
                    try:
                        # NoneBot handler 使用依赖注入取参数 — 自动解析 Depends
                        # regex matcher 传递正则匹配结果
                        extra_kwargs = {}
                        if matcher._last_regex_match:
                            extra_kwargs['matched'] = matcher._last_regex_match
                        result = _resolve_depends_handler(handler, extra_kwargs)
                        if inspect.isawaitable(result):
                            await result
                    except FinishedException:
                        raise  # 重新抛出，让外层捕获
                    except StopPropagation:
                        logger.debug(f"Matcher {matcher} 停止传播")
                        break
                    except PausedException:
                        logger.debug(f"Matcher {matcher} pause() 调用")
                        break
            except FinishedException:
                pass
            except Exception as e:
                logger.error(f"Handler 执行出错: {e}", exc_info=True)
        
        # 如果 matcher 设置了 block，不再继续
        if matcher.block:
            return True
    
    return True


# ─────────────────────────────────────────────────────
# 导出替换 — 替换 gracone_nonebot 中的惰性函数
# ─────────────────────────────────────────────────────

def inject_into_nonebot():
    """在 Gracone 初始化时调用，替换 gracone_nonebot 中的惰性 on_command 等"""
    import sys
    nb = sys.modules.get('nonebot')
    if nb is None:
        return
    nb.on_command = on_command
    nb.on_regex = on_regex
    nb.on_keyword = on_keyword
    nb.on_message = on_message
    nb.on_notice = on_notice
    nb.on_request = on_request
    logger.info("已注入 NoneBot 模块的真实实现")
