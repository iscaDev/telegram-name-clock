# Telegram name clock

Shows `21:45 | Your Name` in your Telegram first-name field, using Tashkent time.
Your last name is not changed. Premium and AI services are not needed.

The app attempts an update each minute. Telegram can impose a longer wait; the
app respects it and stores the retry deadline across restarts. Telegram clients
may cache names, and contacts may see the name they saved for you instead.
This is not a guaranteed real-time clock.

## 1. Create a private login on your Mac

Obtain an API ID and API hash from https://my.telegram.org → API development tools.
Use your own credentials. Do not send your login code or session to another person.

In this folder, run:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python setup.py
```

Follow the private terminal prompts. Setup reads your profile and saves a `.env`
file readable only by your OS user. It does not change your name or send messages.
The chosen `BASE_FIRST_NAME` is also the name used by the restore command; keep
your original first name there if you want exact restoration.

The Telegram session can access your account even though this application only
updates your first name. Never commit `.env`, paste it in chat, or publish it.
You can revoke it in Telegram → Settings → Devices.

## 2. Run locally (optional)

```sh
python clock.py
```

Ctrl+C stops updates; the last clock text stays in your name until restored.
Stop the local copy before starting a Railway copy.

## 3. Deploy on Railway

1. Upload only the source files to your own GitHub repository, excluding `.env`.
2. Create a Railway service from that repository; the Dockerfile is detected.
3. Add the six variables from the private `.env` in Railway's Variables editor:
   `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_SESSION`, `BASE_FIRST_NAME`,
   `CLOCK_TIMEZONE`, and `UPDATE_INTERVAL_SECONDS`. Copy values without the
   surrounding quotes. This entrusts Railway with a Telegram account session.
4. Attach a persistent volume at `/data` before the first successful deployment.
   It keeps Telegram's required wait through restarts and prevents overlapping
   processes sharing that volume. Keep exactly one replica and one service.
5. Keep Serverless/sleep disabled for this worker. No domain, public port,
   database, or HTTP health check is needed.
6. Deploy and check for `Clock updated.` in the logs and the new name in Telegram.

Railway's Hobby subscription includes $5 in resource usage, not unlimited hosting.
Usage is shared with your other project. Check the usage dashboard after a day.

## Stop and restore

Stop the clock service first. If Railway has logged a Telegram-required wait,
allow that wait to finish before attempting another profile change.
Then either edit your name back manually in Telegram, or run locally:

```sh
python clock.py --restore
```

The command restores `BASE_FIRST_NAME` and exits. A local copy does not share
Railway's wait-state file, so prefer restoring in Telegram after the wait.
Regular process shutdown deliberately does not edit your name, to avoid an old
deployment overwriting the name when a new deployment starts.

## References

- https://core.telegram.org/method/account.updateProfile
- https://core.telegram.org/api/errors
- https://docs.telethon.dev/en/stable/modules/sessions.html
- https://docs.railway.com/config-as-code/reference
- https://railway.com/pricing
