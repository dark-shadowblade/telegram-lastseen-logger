import os
from datetime import datetime
from zoneinfo import ZoneInfo

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import (
    InputPeerUser,
    UserStatusOnline,
    UserStatusOffline,
    UserStatusRecently,
    UserStatusLastWeek,
    UserStatusLastMonth,
)

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
SESSION_STRING = os.environ["SESSION_STRING"]

TARGET_ID = int(os.environ["TARGET_USERNAME"])
TARGET_ACCESS_HASH = int(os.environ["TARGET_ACCESS_HASH"])

IST = ZoneInfo("Asia/Kolkata")
LOG_FILE = "last_seen.log"


def get_status(user):
    status = user.status

    if isinstance(status, UserStatusOnline):
        return "Online"

    if isinstance(status, UserStatusOffline):
        return (
            "Last seen at "
            + status.was_online.astimezone(IST).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        )

    if isinstance(status, UserStatusRecently):
        return "Last seen recently"

    if isinstance(status, UserStatusLastWeek):
        return "Last seen within a week"

    if isinstance(status, UserStatusLastMonth):
        return "Last seen within a month"

    return "Unknown"


async def main():
    async with TelegramClient(
        StringSession(SESSION_STRING),
        API_ID,
        API_HASH
    ) as client:

        peer = InputPeerUser(
            user_id=TARGET_ID,
            access_hash=TARGET_ACCESS_HASH
        )

        user = await client.get_entity(peer)

        current_status = get_status(user)

        now = datetime.now(IST).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        previous_status = None

        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]

            if lines:
                previous_status = lines[-1].split(
                    " | Status: ", 1
                )[-1]

        print("Current status:", current_status)
        print("Previous status:", previous_status)

        if current_status != previous_status:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(
                    f"{now} | Status: {current_status}\n"
                )

            print("Status changed — logged.")
        else:
            print("No change — nothing logged.")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
