"""Sends the daily results to Telegram via a bot."""
import os
import requests

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
TELEGRAM_DOCUMENT_API = "https://api.telegram.org/bot{token}/sendDocument"
MAX_LEN = 3900  # Telegram hard cap is 4096; leave margin


def send_telegram(text, token=None, chat_id=None):
    token = token or os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set -- printing instead:\n")
        print(text)
        return

    for i in range(0, len(text), MAX_LEN):
        chunk = text[i:i + MAX_LEN]
        resp = requests.post(
            TELEGRAM_API.format(token=token),
            data={"chat_id": chat_id, "text": chunk, "parse_mode": "Markdown"},
            timeout=15,
        )
        if resp.status_code != 200:
            print(f"Telegram send failed: {resp.status_code} {resp.text}")


def send_telegram_document(file_path, caption=None, filename=None, token=None, chat_id=None):
    """Sends a file (e.g. the full HTML report) as a document, so the full
    visual report is one tap away in Telegram instead of a CI artifact download.
    filename overrides what Telegram displays -- the on-disk name (e.g.
    latest_report.html) is otherwise the same every day and old reports
    become indistinguishable in the chat history."""
    token = token or os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print(f"TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set -- skipping document send of {file_path}")
        return

    with open(file_path, "rb") as f:
        resp = requests.post(
            TELEGRAM_DOCUMENT_API.format(token=token),
            data={"chat_id": chat_id, "caption": (caption or "")[:1024]},
            files={"document": (filename or os.path.basename(file_path), f, "text/html")},
            timeout=30,
        )
    if resp.status_code != 200:
        print(f"Telegram document send failed: {resp.status_code} {resp.text}")
