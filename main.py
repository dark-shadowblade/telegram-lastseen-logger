import os
import asyncio
import json
from datetime import datetime, timedelta
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

DATA_FILE = "activity_7days.json"
CHECK_INTERVAL = 60


def now_ist():
    return datetime.now(IST)


def format_time(dt):
    return dt.strftime("%H:%M:%S")


def format_duration(seconds):
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)

    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m"
    return f"{secs}s"


def load_data():
    if not os.path.exists(DATA_FILE):
        return {
            "sessions": [],
            "current_online_since": None
        }

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {
            "sessions": [],
            "current_online_since": None
        }


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def clean_old_data(data):
    cutoff = now_ist() - timedelta(days=7)

    new_sessions = []

    for session in data["sessions"]:
        try:
            start = datetime.fromisoformat(session["start"])

            if start >= cutoff:
                new_sessions.append(session)

        except Exception:
            pass

    data["sessions"] = new_sessions


def get_status(user):
    status = user.status

    if isinstance(status, UserStatusOnline):
        return "ONLINE"

    if isinstance(status, UserStatusOffline):
        return "OFFLINE"

    if isinstance(status, UserStatusRecently):
        return "RECENTLY"

    if isinstance(status, UserStatusLastWeek):
        return "LAST_WEEK"

    if isinstance(status, UserStatusLastMonth):
        return "LAST_MONTH"

    return "UNKNOWN"


def add_finished_session(data, start, end):
    if not start or not end:
        return

    start_dt = datetime.fromisoformat(start)
    end_dt = datetime.fromisoformat(end)

    if end_dt <= start_dt:
        return

    data["sessions"].append({
        "start": start_dt.isoformat(),
        "end": end_dt.isoformat()
    })


def print_report(data, current_status):
    clean_old_data(data)

    print("\n")
    print("════════════════════════════════")
    print("       TELEGRAM ACTIVITY")
    print("════════════════════════════════")

    current_time = now_ist()

    if current_status == "ONLINE":
        online_since = data.get("current_online_since")

        if online_since:
            start = datetime.fromisoformat(online_since)
            duration = (current_time - start).total_seconds()

            print("LATEST")
            print("🟢 ONLINE")
            print(f"Online since: {format_time(start)}")
            print(f"Currently online: {format_duration(duration)}")
        else:
            print("LATEST")
            print("🟢 ONLINE")
            print(f"Online since: {format_time(current_time)}")
            print("Currently online: 0s")

    elif current_status == "OFFLINE":
        print("LATEST")
        print("⚪ OFFLINE")

        sessions = data["sessions"]

        if sessions:
            last_end = max(
                datetime.fromisoformat(x["end"])
                for x in sessions
            )

            print(f"Last seen: {last_end.strftime('%Y-%m-%d %H:%M:%S')}")

    else:
        print("LATEST")
        print(f"⚪ {current_status}")

    print("\nLAST 7 DAYS")
    print("────────────────────────────────")

    today = current_time.date()

    for days_ago in range(7):
        day = today - timedelta(days=days_ago)

        day_sessions = []

        for session in data["sessions"]:
            start = datetime.fromisoformat(session["start"])
            end = datetime.fromisoformat(session["end"])

            if start.date() == day:
                day_sessions.append((start, end))

        # Add currently active session to today's display
        if (
            day == today
            and current_status == "ONLINE"
            and data.get("current_online_since")
        ):
            start = datetime.fromisoformat(
                data["current_online_since"]
            )
            day_sessions.append((start, current_time))

        print(f"\n{day.strftime('%d %b %Y')}")

        if not day_sessions:
            print("No recorded activity")
            continue

        total = 0

        for start, end in sorted(day_sessions):
            duration = (end - start).total_seconds()
            total += duration

            print(
                f"🟢 {format_time(start)} → "
                f"{format_time(end)}   "
                f"{format_duration(duration)}"
            )

        print(f"Total online: {format_duration(total)}")

    print("\n════════════════════════════════")
    print(
        "Updated:",
        current_time.strftime("%d %b %Y %H:%M:%S IST")
    )
    print("════════════════════════════════")


async def main():

    data = load_data()
    clean_old_data(data)

    async with TelegramClient(
        StringSession(SESSION_STRING),
        API_ID,
        API_HASH
    ) as client:

        peer = InputPeerUser(
            user_id=TARGET_ID,
            access_hash=TARGET_ACCESS_HASH
        )

        print("Telegram activity tracker started.")

        while True:

            try:
                user = await client.get_entity(peer)
                status = get_status(user)
                current_time = now_ist()

                # ONLINE
                if status == "ONLINE":

                    if not data.get("current_online_since"):
                        data["current_online_since"] = (
                            current_time.isoformat()
                        )

                # OFFLINE
                elif status == "OFFLINE":

                    if data.get("current_online_since"):

                        start = data["current_online_since"]

                        # Telegram gives the actual last-online time
                        telegram_end = user.status.was_online

                        if telegram_end:
                            end = telegram_end.astimezone(IST)
                        else:
                            end = current_time

                        add_finished_session(
                            data,
                            start,
                            end.isoformat()
                        )

                        data["current_online_since"] = None

                clean_old_data(data)
                save_data(data)

                print_report(data, status)

            except Exception:
                # Keep the tracker alive if one check fails.
                pass

            await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
