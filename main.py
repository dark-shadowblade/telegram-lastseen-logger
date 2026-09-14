import os
from datetime import datetime, timezone
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import (
    UserStatusOnline,
    UserStatusOffline,
    UserStatusRecently,
    UserStatusLastWeek,
    UserStatusLastMonth,
    UserStatusEmpty,
)

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
SESSION_STRING = os.environ["SESSION_STRING"]
TARGET_ID = int(os.environ["TARGET_USERNAME"])

LOG_FILE = "last_seen.log"


def status_text(user):
    status = user.status

    if isinstance(status, UserStatusOnline):
        return "Online"

    if isinstance(status, UserStatusOffline):
        return "Last seen at " + status.was_online.astimezone().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

    if isinstance(status, UserStatusRecently):
        return "Last seen recently"

    if isinstance(status, UserStatusLastWeek):
        return "Last seen within a week"

    if isinstance(status, UserStatusLastMonth):
        return "Last seen within a month"

    if isinstance(status, UserStatusEmpty):
        return "Last seen a long time ago"

    return "Unknown"


async def main():
    async with TelegramClient(
        StringSession(SESSION_STRING),
        API_ID,
        API_HASH
    ) as client:

        target = None

        # First try Telegram's entity cache/dialogs
        async for dialog in client.iter_dialogs():
            if dialog.entity and getattr(dialog.entity, "id", None) == TARGET_ID:
                target = dialog.entity
                break

        # Try resolving the ID directly
        if target is None:
            try:
                target = await client.get_entity(TARGET_ID)
            except Exception:
                pass

        if target is None:
            raise RuntimeError(
                "Could not resolve this User ID. "
                "Make sure this person is accessible from your Telegram account."
            )

        current = status_text(target)
        now = datetime.now(timezone.utc).astimezone().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        previous = None

        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]

            if lines:
                previous = lines[-1].split(" | Status: ", 1)[-1]

        print("Current status:", current)
        print("Previous status:", previous)

        # Log only when the status changes
        if current != previous:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"{now} | Status: {current}\n")

            print("Status changed — added to log.")
        else:
            print("No change — nothing added.")


with __import__("asyncio").Runner() as runner:
    runner.run(main())
