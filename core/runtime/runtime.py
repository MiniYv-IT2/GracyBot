"""Runtime 数据类、全局注册表、上下文透传

每个 QQ 账号 = 一个 Runtime 实例，所有身份信息绑定在此。
消息链路全程通过 RuntimeContext（contextvars）透传当前 Runtime。
"""

import logging
import threading
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import Dict, Optional, List

from core.gracy_adapter.identity import IdentityTag

_logger = logging.getLogger("Core.Runtime")


# ══════════════════════════════════════════════════════════
# Runtime 数据类
# ══════════════════════════════════════════════════════════

@dataclass
class Runtime:
    """一个 QQ 账号 = 一个 Runtime 实例

    每个实例拥有独立的 Pipeline、日志器、数据目录。
    上游（EventBus → Pipeline）在消息处理时通过 RuntimeRegistry
    获取对应的 Runtime，并通过 RuntimeContext 透传给下游。
    """

    # ── 身份（从 style/instances/<name>/config.json 读取） ──
    instance_name: str                        # "主号" / "小号"
    robot_id: str                             # 机器人 ID
    master_id: str                            # 主人 QQ
    adapter_tag: IdentityTag                  # 关联适配器标签

    # ── 独立组件（每个 Runtime 独享） ──
    pipeline: object = None                   # 独立 Pipeline 实例
    logger: logging.Logger = None             # 独立文件日志器

    # ── 全局共享引用（只读，由框架注入） ──
    plugin_manager: object = None             # PluginManager 单例
    adapter_pool: object = None               # AdapterPool 单例

    # ── 账号专属数据路径 ──

    @property
    def instance_data_dir(self) -> str:
        """当前实例的插件独立数据目录

        style/instances/<name>/data/<plugin_name>/...
        """
        return f"style/instances/{self.instance_name}/data"

    @property
    def log_tag(self) -> str:
        """日志前缀，如 [Runtime:主号]"""
        return f"[Runtime:{self.instance_name}]"

    def __str__(self) -> str:
        return f"Runtime({self.instance_name}, robot={self.robot_id[:4]}****)"


# ══════════════════════════════════════════════════════════
# RuntimeRegistry — 全局注册表
# ══════════════════════════════════════════════════════════

class RuntimeRegistry:
    """全局 Runtime 注册表 — 管理所有 Runtime 实例

    支持按 tag / robot_id 查找，线程安全。
    """
    _lock = threading.Lock()
    _runtimes: Dict[str, Runtime] = {}        # key = identity_key
    _by_robot_id: Dict[str, Runtime] = {}     # key = robot_id

    @classmethod
    def register(cls, runtime: Runtime) -> None:
        """注册一个 Runtime 实例"""
        key = runtime.adapter_tag.identity_key
        rid = runtime.robot_id
        with cls._lock:
            cls._runtimes[key] = runtime
            if rid:
                cls._by_robot_id[rid] = runtime
            _logger.info(f"{runtime.log_tag} 已注册 (robot_id={rid})")

    @classmethod
    def unregister(cls, runtime: Runtime) -> bool:
        """注销一个 Runtime 实例"""
        key = runtime.adapter_tag.identity_key
        rid = runtime.robot_id
        with cls._lock:
            if key not in cls._runtimes:
                return False
            del cls._runtimes[key]
            if rid and rid in cls._by_robot_id:
                del cls._by_robot_id[rid]
            _logger.info(f"{runtime.log_tag} 已注销")
            return True

    @classmethod
    def get_by_tag(cls, tag: IdentityTag) -> Optional[Runtime]:
        """按适配器标签查找 Runtime"""
        key = tag.identity_key
        with cls._lock:
            return cls._runtimes.get(key)

    @classmethod
    def get_by_robot_id(cls, robot_id: str) -> Optional[Runtime]:
        """按 QQ 号查找 Runtime"""
        with cls._lock:
            return cls._by_robot_id.get(robot_id)

    @classmethod
    def get_all(cls) -> List[Runtime]:
        """获取所有已注册的 Runtime 列表"""
        with cls._lock:
            return list(cls._runtimes.values())

    @classmethod
    def count(cls) -> int:
        """已注册 Runtime 数量"""
        with cls._lock:
            return len(cls._runtimes)


# ══════════════════════════════════════════════════════════
# RuntimeContext — 消息链路透传
# ══════════════════════════════════════════════════════════

_current_runtime: ContextVar[Runtime] = ContextVar("_current_runtime")


class RuntimeContext:
    """当前消息处理中的 Runtime（通过 contextvars 透传）

    用法（框架内部 Pipeline 设置）:
        token = RuntimeContext.set(runtime)
        try:
            await pipeline.process(event)
        finally:
            RuntimeContext.reset(token)

    用法（插件/旧风格 handler 读取）:
        runtime = RuntimeContext.get()
        rid = runtime.robot_id
    """

    @staticmethod
    def set(runtime: Runtime) -> Token:
        """设置当前消息的 Runtime，返回 Token 供后续 reset"""
        return _current_runtime.set(runtime)

    @staticmethod
    def get() -> Runtime:
        """获取当前消息所属的 Runtime 实例

        如果无上下文（例如在非消息处理路径调用），
        返回第一个注册的 Runtime 作为兜底。
        """
        try:
            return _current_runtime.get()
        except LookupError:
            # 无上下文时回退到第一个注册的 Runtime
            runtimes = RuntimeRegistry.get_all()
            if runtimes:
                return runtimes[0]
            raise RuntimeError("当前无 Runtime 上下文，且无已注册的 Runtime 实例")

    @staticmethod
    def reset(token: Token) -> None:
        """重置 contextvar 到之前的状态"""
        _current_runtime.reset(token)

    @staticmethod
    def has_context() -> bool:
        """检查当前是否在 Runtime 上下文中"""
        try:
            _current_runtime.get()
            return True
        except LookupError:
            return False
