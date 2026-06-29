"""GracyBot 适配器抽象基类 — 所有平台适配器必须实现此接口

设计原则：
- 适配层只定义契约，不关心具体协议
- 新增平台：只需新建一个平台目录，实现 GracyAdapter 接口
- 无需修改本文件或上层框架代码
"""

from abc import ABC, abstractmethod
from typing import Callable, List, Optional

from core.gracy_adapter.event import GracyEvent
from core.gracy_adapter.identity import IdentityTag
from core.gracy_adapter.message import GracyMsg


class GracyAdapter(ABC):
    """适配器抽象基类

    每个平台各有一个实现类。
    每个适配器实例应包含一个 IdentityTag，由调用方在 AdapterPool.register() 时设置。
    """

    @abstractmethod
    def start(self, on_event: Callable[[GracyEvent], None]) -> None:
        """启动适配器，开始监听消息

        Args:
            on_event: 收到消息时的回调，传入归一化后的 GracyEvent
        """
        ...

    @abstractmethod
    def send(self, target: str, segments: List[GracyMsg], chat_type: str) -> bool:
        """发送消息到指定目标

        Args:
            target: 目标 ID
            segments: 结构化消息段列表（支持 GracyText, GracyImage, GracyAt, GracyReply, GracyVoice, GracyFile, GracyVideo, GracyForward）
            chat_type: "private" | "group"

        Returns:
            发送成功返回 True
        """
        ...

    @abstractmethod
    def stop(self) -> None:
        """停止适配器，释放资源"""
        ...

    def call_api(self, action: str, params: dict = None) -> Optional[dict]:
        """通用 API 调用（可选，各平台按需实现）

        默认返回 None，表示不支持或未实现。

        Args:
            action: 平台特定的 API 名称
            params: 参数字典

        Returns:
            成功返回 data 字段，失败返回 None
        """
        return None

    @abstractmethod
    def get_platform_info(self) -> dict:
        """获取平台/机器人统计信息（所有平台必须实现）

        返回统一结构，各平台自行填充：
        {
            "friend_count": int | None,     # 好友/联系人数量，不支持返回 None
            "group_count": int | None,      # 群组/频道数量，不支持返回 None
            "platform": str,                # 平台标识
            "protocol_version": str | None, # 协议端版本，不支持返回 None
        }
        """

    def parse_http_request(self, body: dict) -> Optional[GracyEvent]:
        """将 HTTP 请求体解析为 GracyEvent（可选，仅支持 HTTP 入站的适配器实现）

        默认返回 None，表示不支持 HTTP 入站。

        Args:
            body: HTTP 请求体（已解析为 dict）

        Returns:
            解析成功返回 GracyEvent，失败或不支持返回 None
        """
        return None

    @property
    def tag(self) -> Optional[IdentityTag]:
        """获取适配器身份标签

        由 AdapterPool.register() 在注册时设置。
        子类可以覆盖此属性返回固定 tag。
        """
        return getattr(self, '_tag', None)

    @tag.setter
    def tag(self, value: IdentityTag) -> None:
        """设置适配器身份标签"""
        self._tag = value

    def register_routes(self, app) -> None:
        """注册 HTTP 路由到框架应用（可选，仅需 HTTP 入站的适配器实现）

        默认空实现。

        Args:
            app: Quart 应用实例
        """
        pass
