"""Schedule system notifications before calendar events."""

from __future__ import annotations

import threading
from datetime import datetime, timedelta
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Notify", "0.7")

from gi.repository import GLib, Notify

from events_cache import CalendarEvent

NOTIFY_BEFORE = timedelta(minutes=15)


class EventNotifier:
    def __init__(self, app_id: str, icon_path: Path) -> None:
        self._icon_path = icon_path
        self._timers: list[threading.Timer] = []
        self._notified: set[str] = set()
        Notify.init(app_id)

    def schedule(self, events: list[CalendarEvent]) -> None:
        self._cancel_timers()
        now = datetime.now().astimezone()

        for event in events:
            if not event.starts_at:
                continue

            try:
                starts_at = datetime.fromisoformat(event.starts_at)
            except ValueError:
                continue

            if now >= starts_at:
                continue

            key = f"{event.summary}|{event.starts_at}"
            if key in self._notified:
                continue

            notify_at = starts_at - NOTIFY_BEFORE
            if notify_at <= now:
                self._notify(event, key)
                continue

            delay = (notify_at - now).total_seconds()
            timer = threading.Timer(delay, self._notify, args=(event, key))
            timer.daemon = True
            timer.start()
            self._timers.append(timer)

    def _cancel_timers(self) -> None:
        for timer in self._timers:
            timer.cancel()
        self._timers.clear()

    def _notify(self, event: CalendarEvent, key: str) -> None:
        if key in self._notified:
            return
        self._notified.add(key)
        GLib.idle_add(self._show_notification, event)

    def _show_notification(self, event: CalendarEvent) -> bool:
        notification = Notify.Notification.new(
            "Upcoming event",
            f"{event.summary} at {event.when}",
            str(self._icon_path),
        )
        notification.show()
        return False
