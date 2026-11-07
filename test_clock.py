import asyncio
from datetime import datetime, timezone
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

from telethon import errors
import clock


class ClockTests(unittest.IsolatedAsyncioTestCase):
    def test_tashkent_midnight_and_unicode_name(self):
        now = datetime(2026, 11, 7, 19, 4, tzinfo=timezone.utc)
        self.assertEqual(clock.display_name("O‘tkir", ZoneInfo("Asia/Tashkent"), now),
                         "O‘tkir | 00:04")

    async def test_only_first_name_is_modified(self):
        client = AsyncMock()
        with tempfile.TemporaryDirectory() as folder:
            state = clock.State(Path(folder) / "state.json")
            self.assertTrue(await clock.update_name(client, "12:00 | Name", state))
        request = client.call_args.args[0]
        self.assertEqual(request.first_name, "12:00 | Name")
        self.assertIsNone(request.last_name)
        self.assertIsNone(request.about)

    async def test_flood_wait_survives_restart(self):
        client = AsyncMock(side_effect=errors.FloodWaitError(request=None, capture=90))
        with tempfile.TemporaryDirectory() as folder, patch("clock.time.time", return_value=1000):
            path = Path(folder) / "state.json"
            self.assertFalse(await clock.update_name(client, "12:00 | Name", clock.State(path)))
            self.assertEqual(clock.State(path).wait_remaining(), 95)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            client.assert_awaited_once()

    def test_corrupt_wait_state_does_not_silently_reset(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "state.json"
            path.write_text('{"retry_at": "broken"}')
            with self.assertRaises(ValueError):
                clock.State(path)

    async def test_restore_uses_saved_base_and_disconnects(self):
        fake = AsyncMock()
        fake.is_user_authorized.return_value = True
        with tempfile.TemporaryDirectory() as folder:
            env = {"TELEGRAM_API_ID": "123", "TELEGRAM_API_HASH": "test",
                   "TELEGRAM_SESSION": "test", "BASE_FIRST_NAME": "Original",
                   "DATA_DIR": folder, "UPDATE_INTERVAL_SECONDS": "60"}
            with patch.dict(os.environ, env), patch("clock.load_dotenv"), \
                 patch("clock.StringSession"), patch("clock.TelegramClient", return_value=fake), \
                 patch.object(asyncio.get_running_loop(), "add_signal_handler"):
                await clock.run(restore=True)
        self.assertEqual(fake.call_args.args[0].first_name, "Original")
        fake.assert_awaited_once()
        fake.disconnect.assert_awaited_once()

    async def test_shutdown_interrupts_wait(self):
        event = asyncio.Event()
        event.set()
        await asyncio.wait_for(clock.wait_or_stop(event, 3600), timeout=0.2)


if __name__ == "__main__":
    unittest.main()
