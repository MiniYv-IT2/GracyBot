# 测试：伪造事件塞进 pipeline，看回复能不能发到群里
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
_log = logging.getLogger("TestFakeEvent")

from gracybot.core.event import event_bus
from gracybot.core.gracy_adapter.event import GracyEvent
from gracybot.core.gracy_adapter.message import GracyText
from gracybot.core.gracy_adapter.identity import IdentityTag

_log.info("starting fake event test")
tag = IdentityTag(platform="satori", bot_name="Satori机器人", conn_type="WebSocket")
fake = GracyEvent(
    sender_id="192004908",
    target_id="735540557",
    chat_type="group",
    segments=[GracyText(text="/运行状态")],
    raw_text="/运行状态",
    message_id="fake_001",
    nickname="脚本测试",
    is_at_bot=True,
    source=tag,
)
import asyncio
_log.info("publishing event to group 735540557")
asyncio.run(event_bus.publish(fake))
_log.info("done")
