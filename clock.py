"""A single-account Telegram name clock. No message handlers or bot token."""
import argparse
import asyncio
import fcntl
import json
import logging
import os
from pathlib import Path
import signal
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from telethon import TelegramClient, errors
from telethon.sessions import StringSession
from telethon.tl.functions.account import UpdateProfileRequest

ROOT = Path(__file__).resolve().parent
log = logging.getLogger("name-clock")


def display_name(base, zone, now=None):
    current = now or datetime.now(zone)
    return f"{base} | {current.astimezone(zone):%H:%M}"


class State:
    """Remember Telegram's required wait across restarts; fail on corrupt state."""
    def __init__(self, path):
        self.path = path
        self.data = json.loads(path.read_text()) if path.exists() else {}
        float(self.data.get("retry_at", 0))

    def wait_remaining(self):
        return max(0, float(self.data.get("retry_at", 0)) - time.time())

    def defer(self, seconds):
        self.data["retry_at"] = time.time() + seconds + 5
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.data))
        temporary.chmod(0o600)
        temporary.replace(self.path)


async def update_name(client, target, state):
    try:
        await client(UpdateProfileRequest(first_name=target))
        return True
    except errors.FloodWaitError as exc:
        state.defer(exc.seconds)
        log.warning("Telegram requested a %s-second pause; saved for restarts.", exc.seconds)
        return False


async def wait_or_stop(stop, seconds):
    try:
        await asyncio.wait_for(stop.wait(), timeout=max(0.1, seconds))
    except asyncio.TimeoutError:
        pass


async def run(restore=False):
    load_dotenv(ROOT / ".env", interpolate=False)
    required = ["TELEGRAM_API_ID", "TELEGRAM_API_HASH", "TELEGRAM_SESSION", "BASE_FIRST_NAME"]
    if any(not os.getenv(key) for key in required):
        raise ValueError("Missing settings. Run setup.py locally, or set Railway variables.")
    base = os.environ["BASE_FIRST_NAME"]
    if not base.strip() or len(base) > 50 or any(c in base for c in "\r\n"):
        raise ValueError("BASE_FIRST_NAME must be a nonempty single line, at most 50 characters.")
    zone = ZoneInfo(os.getenv("CLOCK_TIMEZONE", "Asia/Tashkent"))
    interval = int(os.getenv("UPDATE_INTERVAL_SECONDS", "60"))
    if interval < 60:
        raise ValueError("UPDATE_INTERVAL_SECONDS must be at least 60.")
    data_dir = Path(os.getenv("DATA_DIR", str(ROOT / "data")))
    data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    # A shared persistent volume also prevents two copies updating this account.
    with (data_dir / "clock.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("Another clock is running with this data directory.") from None
        state = State(data_dir / "state.json")
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)
        client = TelegramClient(
            StringSession(os.environ["TELEGRAM_SESSION"]),
            int(os.environ["TELEGRAM_API_ID"]), os.environ["TELEGRAM_API_HASH"],
            receive_updates=False, flood_sleep_threshold=0, request_retries=0,
            device_model="Railway Name Clock",
        )
        try:
            await client.connect()
            if not await client.is_user_authorized():
                raise ValueError("Telegram session expired or revoked. Run setup.py again.")
            last_name = None
            log.info("%s mode active; timezone=%s.", "Restore" if restore else "Clock", zone.key)
            while not stop.is_set():
                delay = state.wait_remaining()
                if delay:
                    await wait_or_stop(stop, delay)
                    continue
                target = base if restore else display_name(base, zone)
                try:
                    if target != last_name:
                        if not await update_name(client, target, state):
                            continue
                        last_name = target
                        log.info("Original first name restored." if restore else "Clock updated.")
                    if restore:
                        return
                except (OSError, ConnectionError, asyncio.TimeoutError, errors.ServerError):
                    log.warning("Temporary connection/server error; retrying in 60 seconds.")
                    await wait_or_stop(stop, 60)
                    continue
                # Align to the next minute with a one-second cushion.
                await wait_or_stop(stop, interval - time.time() % interval + 1)
        finally:
            await client.disconnect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--restore", action="store_true", help="Restore BASE_FIRST_NAME and exit")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("telethon").setLevel(logging.WARNING)
    try:
        asyncio.run(run(args.restore))
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        # Avoid writing credentials or request data into hosting logs.
        log.error("Stopped (%s). Check configuration, session, and persistent state.", type(exc).__name__)
        raise SystemExit(1)
