"""工厂函数 — 根据配置创建 QQOfficialAdapter 实例"""

from core.gracy_adapter.adapter import GracyAdapter
from core.gracy_adapter.qq_official.adapter import QQOfficialAdapter


def create_adapter(config: dict) -> GracyAdapter:
    """根据实例配置创建 QQOfficialAdapter 实例

    Args:
        config: 来自 style/instances/<name>/config.json

    Returns:
        QQOfficialAdapter 实例
    """
    if not config.get("app_id"):
        raise ValueError("QQ 官方适配器缺少必填字段: app_id")
    if not config.get("app_secret"):
        raise ValueError("QQ 官方适配器缺少必填字段: app_secret")

    adapter = QQOfficialAdapter(
        app_id=config["app_id"],
        app_secret=config["app_secret"],
        is_sandbox=config.get("is_sandbox", False),
        robot_id=config["app_id"],
        config_path=config.get("_config_path", ""),
    )
    adapter.conn_type_display = "WebSocket Gateway"
    return adapter
