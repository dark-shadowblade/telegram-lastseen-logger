import os
import asyncio
import json
import base64
import urllib.request
import urllib.error
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

# =========================
# TELEGRAM CONFIG
# =========================

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
SESSION_STRING = os.environ["SESSION_STRING"]

TARGET_ID = int(os.environ["TARGET_USERNAME"])
TARGET_ACCESS_HASH = int(os.environ["TARGET_ACCESS_HASH"])

# =========================
# GITHUB CONFIG
# =========================

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]

GITHUB_REPO = "dark-shadowblade/telegram-lastseen-logger"
GITHUB_FILE = "activity_7days.json"

# =========================
# OTHER CONFIG
# =========================

IST = ZoneInfo("Asia/Kolkata")
DATA_FILE = "activity_7days.json"
CHECK_INTERVAL = 60


# =========================
# TIME
# =========================

def now_ist():
    return datetime.now(IST)


# =========================
# DATA
# =========================

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

    cleaned = []

    for session in data.get("sessions", []):
        try:
            start = datetime.fromisoformat(session["start"])

            if start >= cutoff:
                cleaned.append(session)

        except Exception:
            pass

    data["sessions"] = cleaned


# =========================
# TELEGRAM STATUS
# =========================

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


# =========================
# SESSION
# =========================

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


# =========================
# GITHUB UPLOAD
# =========================

def upload_to_github():

    try:

        with open(DATA_FILE, "rb") as f:
            content = base64.b64encode(f.read()).decode("utf-8")

        api_url = (
            f"https://api.github.com/repos/"
            f"{GITHUB_REPO}/contents/{GITHUB_FILE}"
        )

        headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "telegram-activity-logger"
        }

        # Get current file SHA
        sha = None

        request = urllib.request.Request(
            api_url,
            headers=headers,
            method="GET"
        )

        try:

            with urllib.request.urlopen(request, timeout=20) as response:
                existing = json.loads(response.read().decode())
                sha = existing.get("sha")

        except urllib.error.HTTPError as e:

            if e.code != 404:
                raise

        payload = {
            "message": "Update Telegram activity data",
            "content": content
        }

        if sha:
            payload["sha"] = sha

        data = json.dumps(payload).encode("utf-8")

        request = urllib.request.Request(
            api_url,
            data=data,
            headers={
                **headers,
                "Content-Type": "application/json"
            },
            method="PUT"
        )

        with urllib.request.urlopen(request, timeout=20) as response:

            if response.status in (200, 201):
                print("GitHub: activity_7days.json updated.")

    except Exception as e:

        print(
            "GitHub upload error:",
            repr(e)
        )


# =========================
# TELEGRAM TRACKER
# =========================

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

                print(
                    current_time.strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                    status
                )

                # -------------------------
                # ONLINE
                # -------------------------

                if status == "ONLINE":

                    if not data.get(
                        "current_online_since"
                    ):

                        data[
                            "current_online_since"
                        ] = current_time.isoformat()

                        print(
                            "ONLINE session started:",
                            data[
                                "current_online_since"
                            ]
                        )

                # -------------------------
                # OFFLINE
                # -------------------------

                elif status == "OFFLINE":

                    if data.get(
                        "current_online_since"
                    ):

                        start = data[
                            "current_online_since"
                        ]

                        telegram_end = (
                            user.status.was_online
                        )

                        if telegram_end:

                            end = telegram_end.astimezone(
                                IST
                            )

                        else:

                            end = current_time

                        add_session(
                            data,
                            start,
                            end.isoformat()
                        )

                        print(
                            "Session recorded:",
                            start,
                            "→",
                            end.isoformat()
                        )

                        data[
                            "current_online_since"
                        ] = None

                # -------------------------
                # CLEAN OLD DATA
                # -------------------------

                clean_old_data(data)

                # -------------------------
                # SAVE LOCAL
                # -------------------------

                save_data(data)

                # -------------------------
                # UPLOAD GITHUB
                # -------------------------

                upload_to_github()

            except Exception as e:

                print(
                    "Tracker error:",
                    repr(e)
                )

            await asyncio.sleep(
                CHECK_INTERVAL
            )


# =========================
# START
# =========================

if __name__ == "__main__":

    asyncio.run(tracker())
