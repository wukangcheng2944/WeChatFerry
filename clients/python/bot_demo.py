#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
from queue import Empty
from threading import Thread

from wcferry import Wcf


logging.basicConfig(
    level="INFO",
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
LOG = logging.getLogger("BotDemo")


def target_receiver(msg):
    return msg.roomid if getattr(msg, "roomid", "") else msg.sender


def normalize_text(msg):
    return (getattr(msg, "content", "") or "").strip()


def handle_message(wcf: Wcf, msg):
    text = normalize_text(msg)
    if not text:
        return

    receiver = target_receiver(msg)

    if text == "ping":
        wcf.send_text("pong", receiver)
        LOG.info("Replied pong to %s", receiver)
        return

    if text == "status":
        wcf.send_text("status: ok", receiver)
        LOG.info("Replied status to %s", receiver)
        return


def process_messages(wcf: Wcf):
    while wcf.is_receiving_msg():
        try:
            msg = wcf.get_msg()
            LOG.info("Message: %s", msg)
            handle_message(wcf, msg)
        except Empty:
            continue
        except Exception as exc:
            LOG.exception("Message loop error: %s", exc)


def main():
    LOG.info("Starting bot demo")
    wcf = Wcf(debug=True)

    LOG.info("Logged in: %s", wcf.is_login())
    LOG.info("Self wxid: %s", wcf.get_self_wxid())

    wcf.enable_receiving_msg(pyq=False)
    Thread(target=process_messages, args=(wcf,), daemon=True, name="BotMessageLoop").start()
    LOG.info("Bot is running. Send 'ping' or 'status' to test.")
    wcf.keep_running()


if __name__ == "__main__":
    main()
