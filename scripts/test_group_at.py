"""测试：机器人在群里@自己，看能不能收到并响应"""
import asyncio
import json
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
_log = logging.getLogger("TestGroupAt")


def load_config():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base, "style", "instances", "satori", "config.json")
    if not os.path.isfile(path):
        print(f"no config: {path}")
        sys.exit(1)
    with open(path) as f:
        return json.load(f)


async def group_at_test(cfg, group_id):
    from satori.client import App, WebsocketsInfo
    from satori.element import At, Text as SText

    app = App(WebsocketsInfo(
        host=cfg.get("host", "127.0.0.1"),
        port=cfg.get("port", 8080),
        path=cfg.get("path", ""),
        token=cfg.get("token") or None,
    ))

    master_id = cfg.get("master_id", "")
    result = {"sent": False, "event_received": False, "error": None}

    async def on_event(account, event):
        if event.type != "message-created":
            return
        _log.info(f"event: user={event.user.id if event.user else '?'} channel={event.channel.id if event.channel else '?'} guild={event.guild.id if event.guild else '?'}")
        if event.guild and event.guild.id == group_id:
            result["event_received"] = True
            _log.info("收到群消息回显")
            asyncio.get_event_loop().stop()

    app.register(on_event)

    async def on_ready(account, state):
        _log.info(f"connected: {account}")
        try:
            msg = [SText(" "), At(id=master_id), SText(" 自测")]
            _log.info(f"sending to group {group_id} with @{master_id}")
            await account.protocol.send_message(channel=group_id, message=msg)
            result["sent"] = True
            _log.info("send ok, waiting for reply...")
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

    if result["sent"] and result["event_received"]:
        _log.info("PASS: sent and received group echo")
    else:
        _log.info(f"RESULT: sent={result['sent']} event_received={result['event_received']} error={result.get('error')}")
    return result


def main():
    cfg = load_config()
    print(json.dumps(cfg, indent=2))
    group_id = "735540557"
    r = asyncio.run(group_at_test(cfg, group_id))
    print(f"result: sent={r['sent']} event_received={r['event_received']} error={r.get('error')}")


if __name__ == "__main__":
    main()