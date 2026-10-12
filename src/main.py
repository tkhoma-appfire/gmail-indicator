#!/usr/bin/env python3
"""Ubuntu top-bar indicator using Ayatana AppIndicator."""

from __future__ import annotations

import gdk_backend

gdk_backend.configure()

import signal
import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")

from gi.repository import Gdk, Gtk  # noqa: E402

from notification import EventNotifier
from clients import GoogleCalendarClient, JiraClient
from popup import CalendarPopup, JiraPopup
from tray import TrayMenu, create_indicator, load_indicator_api

APP_ID = "gmail-notification"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ICON_PATH = PROJECT_ROOT / "assets" / "icon.svg"
CREDENTIALS_PATH = PROJECT_ROOT / "credentials.json"
TOKEN_PATH = PROJECT_ROOT / "token.json"
EVENTS_CACHE_PATH = PROJECT_ROOT / "events_cache.json"
JIRA_CONFIG_PATH = PROJECT_ROOT / "jira_config.json"

_notifier = EventNotifier(APP_ID, ICON_PATH)
_calendar = GoogleCalendarClient(
    CREDENTIALS_PATH,
    TOKEN_PATH,
    EVENTS_CACHE_PATH,
    on_events_loaded=_notifier.schedule,
)
_calendar_popup = CalendarPopup(_calendar)
_jira_popup = JiraPopup(JiraClient(JIRA_CONFIG_PATH))
_tray_menu: TrayMenu | None = None


def on_about() -> None:
    dialog = Gtk.MessageDialog(
        transient_for=None,
        flags=0,
        message_type=Gtk.MessageType.INFO,
        buttons=Gtk.ButtonsType.OK,
        text="Gmail Notification",
    )
    dialog.format_secondary_text("Running in the Ubuntu top bar.")
    dialog.run()
    dialog.destroy()


def on_show_popup() -> None:
    _toggle_popup(_calendar_popup)


def on_show_jira_tickets() -> None:
    _toggle_popup(_jira_popup)


def _pointer_anchor() -> tuple[int, int] | None:
    display = Gdk.Display.get_default()
    if display is None:
        return None

    seat = display.get_default_seat()
    if seat is None:
        return None

    pointer = seat.get_pointer()
    if pointer is None:
        return None

    x, y, _mask = gdk_backend.pointer_position(pointer)
    return (x, y)


def _monitor_at_point(x: int, y: int) -> Gdk.Monitor | None:
    display = Gdk.Display.get_default()
    if display is None:
        return None
    return display.get_monitor_at_point(x, y)


def _tray_fallback_anchor() -> tuple[int, int] | None:
    """Top-bar tray strip on the monitor under the pointer (or primary)."""
    display = Gdk.Display.get_default()
    if display is None:
        return None

    pointer = _pointer_anchor()
    monitor = None
    if pointer is not None:
        monitor = _monitor_at_point(pointer[0], pointer[1])
    if monitor is None:
        monitor = display.get_primary_monitor()
    if monitor is None:
        return None

    geometry = monitor.get_geometry()
    return (geometry.x + geometry.width - 48, geometry.y + 16)


def _toggle_popup(popup: CalendarPopup | JiraPopup) -> None:
    anchor = _pointer_anchor()
    if anchor is None and _tray_menu is not None:
        anchor = _tray_menu.get_anchor()
    if anchor is None:
        anchor = _tray_fallback_anchor()

    popup.toggle(anchor=anchor, below_click=False)


def on_quit() -> None:
    Gtk.main_quit()


def _prefetch_todays_events() -> None:
    try:
        _calendar.refresh_todays_events()
    except Exception:
        pass


def main() -> None:
    global _tray_menu

    threading.Thread(target=_prefetch_todays_events, daemon=True).start()

    backend, api = load_indicator_api()
    indicator = create_indicator(backend, api, APP_ID, ICON_PATH)
    indicator.set_status(api.IndicatorStatus.ACTIVE)
    indicator.set_title("Gmail Notification")
    _tray_menu = TrayMenu.attach(
        indicator,
        backend,
        {
            "show_popup": on_show_popup,
            "show_jira": on_show_jira_tickets,
            "about": on_about,
            "quit": on_quit,
        },
    )

    signal.signal(signal.SIGINT, signal.SIG_DFL)
    Gtk.main()


if __name__ == "__main__":
    main()
