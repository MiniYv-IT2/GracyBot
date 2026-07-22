"""Satori 适配器调试脚本 — 仅校验语法，供以后手动使用"""

import argparse
import asyncio
import json
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
_log = logging.getLogger("DebugSatori")


def load_config():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base, "res", "instances", "satori", "config.json")
    if not os.path.isfile(path):
        print(f"no config: {path}")
        sys.exit(1)
    with open(path) as f:
        return json.load(f)


async def send_test(cfg, chat_type, target, text):
    from satori.client import App, WebsocketsInfo

    app = App(WebsocketsInfo(
        host=cfg.get("host", "127.0.0.1"),
        port=cfg.get("port", 8080),
        path=cfg.get("path", ""),
        token=cfg.get("token") or None,
    ))

    result = {"sent": False, "channel_id": None, "error": None}

    async def on_ready(account, state):
        result["account"] = account
        try:
            channel_id = target
            if not channel_id.startswith("private:") and not channel_id.startswith("group:"):
                channel_id = f"private:{target}" if chat_type == "private" else target
            result["channel_id"] = channel_id
            _log.info(f"sending channel_id={channel_id!r} text={text!r}")
            await account.protocol.message_create(channel_id=channel_id, content=text)
            result["sent"] = True
            _log.info("send ok")
        except Exception as e:
            result["error"] = repr(e)
            _log.error(f"send error: {e}")
        finally:
            asyncio.get_event_loop().stop()

    app.lifecycle_callbacks.append(on_ready)
    try:
        await app.run_async()
    except Exception as e:
        if not result["error"]:
            result["error"] = repr(e)

    status = "OK" if result["sent"] else f"FAIL: {result.get('error')}"
    _log.info(f"{status}  channel_id={result['channel_id']}")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--send-private", action="store_true")
    parser.add_argument("--send-group", type=str)
    parser.add_argument("--text", default="脚本调试")
    args = parser.parse_args()

    cfg = load_config()
    print(json.dumps(cfg, indent=2))

    if args.send_private:
        master_id = cfg.get("master_id", "")
        asyncio.run(send_test(cfg, "private", master_id, args.text))
    elif args.send_group:
        asyncio.run(send_test(cfg, "group", args.send_group, args.text))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()