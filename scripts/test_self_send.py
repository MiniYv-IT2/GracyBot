"""测试：机器人自己发消息给自己，看能不能收到并处理"""
import argparse
import asyncio
import json
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
_log = logging.getLogger("TestSelfSend")


def load_config():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base, "style", "instances", "satori", "config.json")
    if not os.path.isfile(path):
        print(f"no config: {path}")
        sys.exit(1)
    with open(path) as f:
        return json.load(f)


async def self_test(cfg):
    from satori.client import App, WebsocketsInfo

    app = App(WebsocketsInfo(
        host=cfg.get("host", "127.0.0.1"),
        port=cfg.get("port", 8080),
        path=cfg.get("path", ""),
        token=cfg.get("token") or None,
    ))

    master_id = cfg.get("master_id", "")
    result = {"sent": False, "received": False, "error": None}
    event_log = []

    async def on_event(account, event):
        if event.type == "message-created":
            event_log.append(event)
            _log.info(f"RECEIVED event: user={event.user.id if event.user else '?'} channel={event.channel.id if event.channel else '?'}")
            result["received"] = True
            asyncio.get_event_loop().stop()

    app.register(on_event)

    async def on_ready(account, state):
        _log.info(f"connected: {account}")
        try:
            channel_id = f"private:{master_id}"
            msg = f"[self-test-{os.urandom(2).hex()}]"
            _log.info(f"sending: channel_id={channel_id!r} msg={msg!r}")
            await account.protocol.message_create(channel_id=channel_id, content=msg)
            result["sent"] = True
            _log.info("sent ok")
        except Exception as e:
            result["error"] = repr(e)
            _log.error(f"send error: {e}")
            asyncio.get_event_loop().stop()

    app.lifecycle_callbacks.append(on_ready)
    try:
        await app.run_async()
    except Exception as e:
        if not result["error"]:
            result["error"] = repr(e)

    if result["sent"] and result["received"]:
        _log.info("PASS: sent and received")
    else:
        _log.info(f"FAIL: sent={result['sent']} received={result['received']} error={result.get('error')}")
    return result


def main():
    cfg = load_config()
    print(json.dumps(cfg, indent=2))
    r = asyncio.run(self_test(cfg))
    print(f"result: sent={r['sent']} received={r['received']} error={r.get('error')}")


if __name__ == "__main__":
    main()