"""One-time setup: sets the Telegram bot's profile description so it's not a
blank slate when someone opens it. This is a push-only bot (GitHub Actions
sends daily; nothing polls for or replies to incoming messages), so this
deliberately does NOT set a command list -- a command menu would imply the
bot listens for input, which it doesn't without a persistently running
server. Run manually: TELEGRAM_BOT_TOKEN=... python scripts/setup_bot.py
"""
import os
import sys

import requests

API = "https://api.telegram.org/bot{token}/{method}"

DESCRIPTION = (
    "Nifty Value Radar screens the Nifty 500 every weekday morning across "
    "seven rules-based strategies (value, trend, momentum, quality, and "
    "relative strength) and sends the stocks that clear a conviction bar, "
    "plus a full HTML report. This bot only sends -- it doesn't read replies."
)
SHORT_DESCRIPTION = "Daily Nifty 500 screener -- conviction-ranked signals every weekday morning."


def call(method, token, **params):
    resp = requests.post(API.format(token=token, method=method), data=params, timeout=15)
    ok = resp.status_code == 200 and resp.json().get("ok")
    print(f"{method}: {'OK' if ok else 'FAILED'} -- {resp.text}")
    return ok


def run():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Set TELEGRAM_BOT_TOKEN in the environment first.")
        return 1
    call("setMyDescription", token, description=DESCRIPTION)
    call("setMyShortDescription", token, short_description=SHORT_DESCRIPTION)
    return 0


if __name__ == "__main__":
    sys.exit(run())
