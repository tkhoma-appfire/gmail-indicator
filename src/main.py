#!/usr/bin/env python3
"""Ubuntu top-bar indicator using AppIndicator3."""

from __future__ import annotations

import signal
import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")

try:
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3 as AppIndicator3  # noqa: E402
except ValueError:
    gi.require_version("AppIndicator3", "0.1")
    from gi.repository import AppIndicator3  # noqa: E402

from gi.repository import Gtk  # noqa: E402

from event_notifier import EventNotifier
from google_calendar import GoogleCalendarClient
from jira_client import JiraClient
from popup import CalendarPopup, JiraPopup
from tray_menu import TrayMenu

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


def _anchor_from_menu_item(menu_item: Gtk.MenuItem) -> tuple[int, int] | None:
    widget: Gtk.Widget | None = menu_item
    while widget is not None and not isinstance(widget, Gtk.Menu):
        widget = widget.get_parent()

    if not isinstance(widget, Gtk.Menu):
        return None

    gdk_window = widget.get_window()
    if gdk_window is None:
        return None

    x, y = gdk_window.get_origin()
    return (x + widget.get_allocated_width() // 2, y)


def build_menu() -> Gtk.Menu:
    menu = Gtk.Menu()

    popup_item = Gtk.MenuItem(label="Show today events")
    popup_item.connect("activate", on_show_popup)
    menu.append(popup_item)

    jira_item = Gtk.MenuItem(label="Show jira tickets")
    jira_item.connect("activate", on_show_jira_tickets)
    menu.append(jira_item)

    about_item = Gtk.MenuItem(label="About")
    about_item.connect("activate", on_about)
    menu.append(about_item)

    menu.append(Gtk.SeparatorMenuItem())

    quit_item = Gtk.MenuItem(label="Quit")
    quit_item.connect("activate", on_quit)
    menu.append(quit_item)

    menu.show_all()
    return menu


def on_about(_widget: Gtk.MenuItem) -> None:
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


def on_show_popup(widget: Gtk.MenuItem) -> None:
    _toggle_popup(_calendar_popup, widget)


def on_show_jira_tickets(widget: Gtk.MenuItem) -> None:
    _toggle_popup(_jira_popup, widget)


def _toggle_popup(popup: CalendarPopup | JiraPopup, widget: Gtk.MenuItem) -> None:
    parent = widget.get_parent()
    if isinstance(parent, Gtk.Menu):
        parent.popdown()

    anchor = _tray_menu.get_anchor() if _tray_menu else None
    if anchor is not None:
        popup.toggle(anchor=anchor, below_click=True)
    else:
        popup.toggle(anchor=_anchor_from_menu_item(widget), below_click=False)


def on_quit(_widget: Gtk.MenuItem) -> None:
    Gtk.main_quit()


def _prefetch_todays_events() -> None:
    try:
        _calendar.refresh_todays_events()
    except Exception:
        pass


def main() -> None:
    global _tray_menu

    threading.Thread(target=_prefetch_todays_events, daemon=True).start()

    indicator = AppIndicator3.Indicator.new(
        APP_ID,
        str(ICON_PATH),
        AppIndicator3.IndicatorCategory.APPLICATION_STATUS,
    )
    indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
    indicator.set_title("Gmail Notification")
    _tray_menu = TrayMenu(indicator, build_menu())

    signal.signal(signal.SIGINT, signal.SIG_DFL)
    Gtk.main()


if __name__ == "__main__":
    main()
