"""Disk cache for today's calendar events."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

CACHE_TTL = timedelta(hours=3)


@dataclass(frozen=True)
class CalendarEvent:
    summary: str
    when: str
    starts_at: str


class EventsCache:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._cached_at: datetime | None = None
        self._events: list[CalendarEvent] | None = None
        self._load_from_disk()

    def is_valid(self) -> bool:
        with self._lock:
            return self._is_valid_unlocked()

    def get_if_valid(self) -> list[CalendarEvent] | None:
        with self._lock:
            if self._is_valid_unlocked():
                return list(self._events or [])
            return None

    def get_cached(self) -> list[CalendarEvent]:
        with self._lock:
            if self._cached_at is None or self._events is None:
                return []
            if self._cached_at.date().isoformat() != _today_key():
                return []
            return list(self._events)

    def save(self, events: list[CalendarEvent]) -> None:
        with self._lock:
            self._cached_at = datetime.now().astimezone()
            self._events = list(events)
            payload = {
                "filled_at": self._cached_at.isoformat(),
                "events": [
                    {
                        "summary": event.summary,
                        "when": event.when,
                        "starts_at": event.starts_at,
                    }
                    for event in events
                ],
            }
            self._path.write_text(json.dumps(payload, indent=2))

    def _is_valid_unlocked(self) -> bool:
        if self._events is None or self._cached_at is None:
            return False

        now = datetime.now().astimezone()
        if self._cached_at.date() != now.date():
            return False

        return now - self._cached_at < CACHE_TTL

    def _load_from_disk(self) -> None:
        if not self._path.exists():
            return

        try:
            data = json.loads(self._path.read_text())
            filled_at = datetime.fromisoformat(data["filled_at"])
        except (json.JSONDecodeError, OSError, KeyError, ValueError):
            return

        if filled_at.date().isoformat() != _today_key():
            return

        self._cached_at = filled_at
        self._events = [
            CalendarEvent(
                summary=item["summary"],
                when=item["when"],
                starts_at=item.get("starts_at", ""),
            )
            for item in data.get("events", [])
        ]


def _today_key() -> str:
    return datetime.now().astimezone().date().isoformat()
