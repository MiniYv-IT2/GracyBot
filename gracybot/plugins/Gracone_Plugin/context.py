"""GraconeContext — NoneBot handler 执行期间的上下文桥

NoneBot 插件的 handler 执行时需要访问当前消息的上下文（命令参数、消息内容等），
GraconeContext 通过 contextvars 在此过程期间暂存上下文。
"""

import contextvars
from typing import Any, Optional


class GraconeContext:
    """NoneBot handler 执行期间的运行时上下文
    
    用法:
        ctx = GraconeContext(gracy_event=..., nb_event=..., raw_text=..., command=...)
        ctx.set()   # 进入上下文
        # ... 执行 NoneBot handler ...
        GraconeContext.get()  # 在任意位置获取当前上下文
        ctx.unset()  # 退出上下文
    """
    
    _ctx_var: contextvars.ContextVar[Optional['GraconeContext']] = \
        contextvars.ContextVar('gracone_context', default=None)
    
    def __init__(self, *, gracy_event=None, nb_event=None, 
                 raw_text: str = "", command: str = "", 
                 matcher=None, adapter_tag=None):
        self.gracy_event = gracy_event
        self.nb_event = nb_event
        self.raw_text = raw_text
        self.command = command
        self.matcher = matcher
        self.adapter_tag = adapter_tag
        self._token: Optional[contextvars.Token] = None
    
    def set(self):
        """设置当前上下文（进入 NoneBot handler 前调用）"""
        self._token = self._ctx_var.set(self)
        return self
    
    def unset(self):
        """清除当前上下文（NoneBot handler 返回后调用）"""
        if self._token is not None:
            self._ctx_var.reset(self._token)
            self._token = None
    
    @classmethod
    def get(cls) -> Optional['GraconeContext']:
        """获取当前线程/协程的 GraconeContext"""
        return cls._ctx_var.get()
    
    def __enter__(self):
        self.set()
        return self
    
    def __exit__(self, *args):
        self.unset()
