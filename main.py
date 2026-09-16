import os
import json
import time
import base64
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import (
    UserStatusOnline,
    UserStatusOffline,
    UserStatusRecently,
    UserStatusLastWeek,
    UserStatusLastMonth,
)

# =========================================================
# CONFIG
# =========================================================

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
SESSION_STRING = os.environ["SESSION_STRING"]

TARGET_ID = int(os.environ["TARGET_USERNAME"])
TARGET_ACCESS_HASH = int(os.environ["TARGET_ACCESS_HASH"])

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]

# DATA REPOSITORY — NOT THE CODE REPOSITORY
DATA_REPO = "dark-shadowblade/telegram-activity-data"
DATA_FILE = "activity_7days.json"

CHECK_INTERVAL = 60

IST = timezone(timedelta(hours=5, minutes=30))

# =========================================================
# LOCAL DATA
# =========================================================

DATA = {
    "sessions": [],
    "current_online_since": None,
    "last_seen": None,
    "last_status": "OFFLINE",
    "updated_at": None,
}

last_uploaded_snapshot = None


# =========================================================
# TIME
# =========================================================

def now_ist():
    return datetime.now(IST)


def iso(dt):
    if dt is None:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(IST).isoformat()


# =========================================================
# GITHUB API
# =========================================================

def github_url():
    return (
        f"https://api.github.com/repos/"
        f"{DATA_REPO}/contents/{DATA_FILE}"
    )


def github_request(method, url, body=None):
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "telegram-activity-logger",
    }

    data = None

    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(
                response.read().decode("utf-8")
            )

    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="ignore")

        print(
            f"GitHub API error {e.code}: {error_body}",
            flush=True
        )

        return e.code, None

    except Exception as e:
        print(
            f"GitHub request error: {e}",
            flush=True
        )

        return None, None


# =========================================================
# LOAD DATA FROM DATA REPOSITORY
# =========================================================

def load_remote_data():

    print("Loading activity data from GitHub...", flush=True)

    status, response = github_request(
        "GET",
        github_url()
    )

    if status == 200 and response:

        try:
            content = response["
