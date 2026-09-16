import os
import asyncio
import json
import threading
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

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

# ============================================================
# TELEGRAM CONFIGURATION
# ============================================================

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
SESSION_STRING = os.environ["SESSION_STRING"]

TARGET_ID = int(os.environ["TARGET_USERNAME"])
TARGET_ACCESS_HASH = int(os.environ["TARGET_ACCESS_HASH"])

# ============================================================
# GENERAL CONFIGURATION
# ============================================================

IST = ZoneInfo("Asia/Kolkata")

DATA_FILE = "activity_7days.json"
CHECK_INTERVAL = 60


# ============================================================
# WEB DASHBOARD SERVER
# ============================================================

def start_web_server():
    port_env = os.environ.get("PORT")

    print("PORT environment variable:", port_env)

    port = int(port_env or "8080")

    server = ThreadingHTTPServer(
        ("0.0.0.0", port),
        SimpleHTTPRequestHandler
    )

    print(f"Dashboard server running on port {port}")

    server.serve_forever()


# ============================================================
# TIME
# ============================================================

def now_ist():
    return datetime.now(IST)


# ============================================================
# DATA STORAGE
# ============================================================

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


# ============================================================
# KEEP ONLY LAST 7 DAYS
# ============================================================

def clean_old_data(data):
    cutoff = now_ist() - timedelta(days=7)

    cleaned_sessions = []

    for session in data.get("sessions", []):
        try:
            start = datetime.fromisoformat(session["start"])

            if start >= cutoff:
                cleaned_sessions.append(session)

        except Exception:
            pass

    data["sessions"] = cleaned_sessions


# ============================================================
# TELEGRAM STATUS
# ============================================================

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


# ============================================================
# ADD COMPLETED SESSION
# ============================================================

def add_session(data, start, end):
    if not start or not end:
        return

    try:
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)

    except Exception:
        return

    if end_dt <= start_dt:
        return

    data["sessions"].append({
        "start": start_dt.isoformat(),
        "end": end_dt.isoformat()
    })


# ============================================================
# TELEGRAM ACTIVITY TRACKER
# ============================================================

async def tracker():

    data = load_data()

    clean_old_data(data)
    save_data(data)

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
        print("Checking every 60 seconds...")

        while True:

            try:
                user = await client.get_entity(peer)

                status = get_status(user)

                current_time = now_ist()

                # ------------------------------------------------
                # ONLINE
                # ------------------------------------------------

                if status == "ONLINE":

                    if not data.get("current_online_since"):

                        data["current_online_since"] = (
                            current_time.isoformat()
                        )

                # ------------------------------------------------
                # OFFLINE
                # ------------------------------------------------

                elif status == "OFFLINE":

                    if data.get("current_online_since"):

                        start = data["current_online_since"]

                        telegram_end = user.status.was_online

                        if telegram_end:
                            end = telegram_end.astimezone(IST)
                        else:
                            end = current_time

                        add_session(
                            data,
                            start,
                            end.isoformat()
                        )

                        data["current_online_since"] = None

                # ------------------------------------------------
                # CLEAN OLD DATA
                # ------------------------------------------------

                clean_old_data(data)

                # ------------------------------------------------
                # SAVE
                # ------------------------------------------------

                save_data(data)

                print(
                    now_ist().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                    status
                )

            except Exception as e:

                print(
                    "Tracker error:",
                    repr(e)
                )

            await asyncio.sleep(CHECK_INTERVAL)


# ============================================================
# START EVERYTHING
# ============================================================

if __name__ == "__main__":

    web_thread = threading.Thread(
        target=start_web_server,
        daemon=True
    )

    web_thread.start()

    asyncio.run(tracker())
