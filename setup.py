"""Run interactively on your own Mac; credentials are never printed."""
import asyncio
from getpass import getpass
import os
from pathlib import Path

from telethon import TelegramClient
from telethon.sessions import StringSession

ROOT = Path(__file__).resolve().parent


async def main():
    destination = ROOT / ".env"
    if destination.exists():
        raise SystemExit(".env already exists. Move it to a safe backup before creating a new session.")
    print("Get your API ID and API hash from https://my.telegram.org → API development tools.")
    print("This creates a Telegram account session. Keep the resulting .env private.")
    api_id = int(input("API ID: ").strip())
    api_hash = getpass("API hash (hidden): ").strip()
    client = TelegramClient(StringSession(), api_id, api_hash,
                            device_model="Name Clock Setup", receive_updates=False)
    try:
        await client.start(phone=lambda: input("Telegram phone number (+country code): ").strip(),
                           code_callback=lambda: getpass("Telegram login code (hidden): "),
                           password=lambda: getpass("Telegram two-step password (hidden): "))
        me = await client.get_me()
        base = me.first_name or ""
        print(f"Your current first name is: {base}")
        base = input("Name before the clock (Enter keeps the current first name): ").strip() or base
        if not base or len(base) > 50 or any(c in base for c in "\r\n"):
            raise ValueError("Choose a single-line name of 1–50 characters.")
        values = {
            "TELEGRAM_API_ID": str(api_id), "TELEGRAM_API_HASH": api_hash,
            "TELEGRAM_SESSION": client.session.save(), "BASE_FIRST_NAME": base,
            "CLOCK_TIMEZONE": "Asia/Tashkent", "UPDATE_INTERVAL_SECONDS": "60",
        }
        fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as file:
            for key, value in values.items():
                # Quoting preserves spaces and punctuation in names.
                escaped = value.replace("\\", "\\\\").replace("'", "\\'")
                file.write(f"{key}='{escaped}'\n")
        print("Saved private settings to .env. Your Telegram name has not been changed.")
        print("Next: python clock.py (local), or follow README.md for Railway.")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
