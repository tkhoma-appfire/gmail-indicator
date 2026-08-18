#!/usr/bin/env python3
"""Show a sample upcoming-event notification."""

from __future__ import annotations

import json
import time
from pathlib import Path

import gi

gi.require_version("Notify", "0.7")

from gi.repository import Notify

APP_ID = "gmail-notification"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ICON_PATH = PROJECT_ROOT / "assets" / "icon.svg"
CACHE_PATH = PROJECT_ROOT / "events_cache.json"


def _event_from_cache() -> tuple[str, str]:
    if not CACHE_PATH.exists():
        return "Test Event", "3:00 pm"

    try:
        data = json.loads(CACHE_PATH.read_text())
        events = data.get("events", [])
        if not events:
            return "Test Event", "3:00 pm"
        event = events[0]
        return event["summary"], event["when"]
    except (OSError, json.JSONDecodeError, KeyError):
        return "Test Event", "3:00 pm"


def main() -> None:
    summary, when = _event_from_cache()
    Notify.init(APP_ID)
    notification = Notify.Notification.new(
        "Upcoming event",
        f"{summary} at {when}",
        str(ICON_PATH),
    )
    notification.show()
    time.sleep(2)


if __name__ == "__main__":
    main()
