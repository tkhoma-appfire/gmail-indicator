"""Top-bar popup windows."""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from datetime import datetime

import gi

gi.require_version("Gtk", "3.0")

from gi.repository import Gdk, GLib, Gtk

from events_cache import CalendarEvent
from google_calendar import GoogleCalendarClient
from jira_client import JiraClient, JiraTicket

ICON_BELOW_OFFSET = 12
POPUP_WIDTH = 380
JIRA_POPUP_WIDTH = 520
POPUP_MAX_HEIGHT = 320

_POPUP_CSS = b"""
.popup-card {
    background-color: #ffffff;
    border-radius: 16px;
    border: 1px solid #e0e0e0;
}
.popup-date {
    color: #5f6368;
    font-size: 12px;
}
.popup-title {
    color: #202124;
    font-size: 20px;
    font-weight: bold;
}
.popup-close-icon-btn {
    background-color: transparent;
    border: none;
    padding: 4px;
    margin-top: 0;
}
.popup-close-icon {
    color: #5f6368;
    font-size: 16px;
}
.popup-separator {
    background-color: #e8eaed;
    min-height: 1px;
    margin-top: 12px;
    margin-bottom: 12px;
}
.event-row {
    background-color: #f8f9fa;
    border-radius: 8px;
    padding: 10px 12px;
}
.event-accent {
    background-color: #1a73e8;
    border-radius: 2px;
    min-width: 4px;
    min-height: 20px;
}
.event-time {
    color: #5f6368;
    font-size: 13px;
    min-width: 72px;
}
.event-title {
    color: #202124;
    font-size: 13px;
}
.popup-message {
    color: #5f6368;
    font-size: 13px;
    padding: 8px 0;
}
.popup-close-button {
    background-color: #ffffff;
    border: 1px solid #dadce0;
    border-radius: 8px;
    padding: 10px 16px;
    margin-top: 12px;
    color: #202124;
    font-size: 14px;
}
.popup-close-button:hover {
    background-color: #f8f9fa;
}
"""


class _PopupBase(ABC):
    def __init__(self) -> None:
        self._window: Gtk.Window | None = None
        self._overlay: Gtk.Window | None = None
        self._content_box: Gtk.Box | None = None
        _ensure_popup_styles()

    @property
    def is_visible(self) -> bool:
        return self._window is not None

    @abstractmethod
    def _header_title(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def _loading_message(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def _fetch_content(self) -> None:
        raise NotImplementedError

    def _popup_width(self) -> int:
        return POPUP_WIDTH

    def toggle(
        self,
        anchor: tuple[int, int] | None = None,
        *,
        below_click: bool = True,
    ) -> None:
        if self.is_visible:
            self.close()
        else:
            self.show(anchor=anchor, below_click=below_click)

    def show(
        self,
        anchor: tuple[int, int] | None = None,
        *,
        below_click: bool = True,
    ) -> None:
        if self.is_visible:
            return

        window = Gtk.Window(type=Gtk.WindowType.POPUP)
        window.set_decorated(False)
        window.set_resizable(False)
        window.set_skip_taskbar_hint(True)
        window.set_skip_pager_hint(True)
        window.set_type_hint(Gdk.WindowTypeHint.NOTIFICATION)
        window.set_can_focus(True)
        window.add_events(Gdk.EventMask.KEY_PRESS_MASK)
        window.set_default_size(self._popup_width(), 80)

        card = Gtk.EventBox()
        card.get_style_context().add_class("popup-card")

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.set_margin_top(20)
        outer.set_margin_bottom(20)
        outer.set_margin_start(20)
        outer.set_margin_end(20)

        outer.pack_start(self._build_header(), False, False, 0)

        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        separator.get_style_context().add_class("popup-separator")
        outer.pack_start(separator, False, False, 0)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_max_content_height(POPUP_MAX_HEIGHT)
        scrolled.set_propagate_natural_height(True)

        self._content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        scrolled.add(self._content_box)
        outer.pack_start(scrolled, True, True, 0)

        card.add(outer)
        window.add(card)

        window.connect("destroy", self._on_window_destroy)
        window.connect("key-press-event", self._on_key_press)

        self._window = window
        self._overlay = self._create_overlay()

        self._set_message(self._loading_message())
        window.show_all()

        self._position_window(window, anchor, below_click)
        window.present()

        GLib.idle_add(self._grab_keyboard)
        threading.Thread(target=self._fetch_content, daemon=True).start()

    def _build_header(self) -> Gtk.Widget:
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        titles = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        local_now = datetime.now().astimezone()
        date_label = Gtk.Label(label=local_now.strftime("%A, %B %-d"))
        date_label.set_xalign(0)
        date_label.get_style_context().add_class("popup-date")
        titles.pack_start(date_label, False, False, 0)

        title_label = Gtk.Label(label=self._header_title())
        title_label.set_xalign(0)
        title_label.get_style_context().add_class("popup-title")
        titles.pack_start(title_label, False, False, 0)

        header.pack_start(titles, True, True, 0)

        close_button = Gtk.Button()
        close_button.set_relief(Gtk.ReliefStyle.NONE)
        close_button.get_style_context().add_class("popup-close-icon-btn")
        close_icon = Gtk.Label(label="✕")
        close_icon.get_style_context().add_class("popup-close-icon")
        close_button.add(close_icon)
        close_button.connect("clicked", lambda _btn: self.close())
        header.pack_start(close_button, False, False, 0)

        return header

    def close(self) -> None:
        if self._window is not None:
            self._window.destroy()

    def _set_message(self, text: str) -> None:
        self._clear_content()
        if self._content_box is None:
            return

        label = Gtk.Label(label=text)
        label.set_xalign(0)
        label.set_line_wrap(True)
        label.get_style_context().add_class("popup-message")
        self._content_box.pack_start(label, False, False, 0)
        self._content_box.show_all()

    def _clear_content(self) -> None:
        if self._content_box is None:
            return

        for child in self._content_box.get_children():
            self._content_box.remove(child)
            child.destroy()

    def _show_rows(self, rows: list[Gtk.Widget], *, empty_message: str) -> None:
        if self._content_box is None:
            return

        if not rows:
            self._set_message(empty_message)
            return

        self._clear_content()
        for row in rows:
            self._content_box.pack_start(row, False, False, 0)

        self._content_box.show_all()
        if self._window is not None:
            self._window.queue_resize()

    def _position_window(
        self,
        window: Gtk.Window,
        anchor: tuple[int, int] | None,
        below_click: bool,
    ) -> None:
        geometry = self._get_primary_monitor_geometry()
        width, height = window.get_size()

        if anchor is not None:
            anchor_x, anchor_y = anchor
            x = anchor_x - width // 2
            y = anchor_y + (ICON_BELOW_OFFSET if below_click else 0)
        else:
            x = geometry.x + geometry.width - width - 12
            y = geometry.y + 32

        margin = 8
        x = max(geometry.x + margin, min(x, geometry.x + geometry.width - width - margin))
        y = max(geometry.y + margin, min(y, geometry.y + geometry.height - height - margin))
        window.move(x, y)

    def _get_primary_monitor_geometry(self) -> Gdk.Rectangle:
        display = Gdk.Display.get_default()
        if display is not None:
            monitor = display.get_primary_monitor()
            if monitor is not None:
                return monitor.get_geometry()

        screen = Gdk.Screen.get_default()
        monitor_num = screen.get_primary_monitor()
        return screen.get_monitor_geometry(monitor_num)

    def _create_overlay(self) -> Gtk.Window:
        geometry = self._get_primary_monitor_geometry()

        overlay = Gtk.Window(type=Gtk.WindowType.POPUP)
        overlay.set_decorated(False)
        overlay.set_app_paintable(True)
        overlay.set_skip_taskbar_hint(True)
        overlay.set_skip_pager_hint(True)
        overlay.set_can_focus(True)
        overlay.add_events(Gdk.EventMask.KEY_PRESS_MASK)
        overlay.resize(geometry.width, geometry.height)
        overlay.move(geometry.x, geometry.y)

        screen = Gdk.Screen.get_default()
        if screen is not None:
            visual = screen.get_rgba_visual()
            if visual is not None and screen.is_composited():
                overlay.set_visual(visual)

        overlay.connect("button-press-event", self._on_overlay_press)
        overlay.connect("key-press-event", self._on_key_press)
        overlay.connect("draw", self._on_overlay_draw)
        overlay.show_all()

        return overlay

    def _grab_keyboard(self) -> bool:
        if self._overlay is None:
            return False

        self._overlay.grab_focus()
        gdk_window = self._overlay.get_window()
        display = Gdk.Display.get_default()
        if gdk_window is not None and display is not None and hasattr(display, "get_default_seat"):
            seat = display.get_default_seat()
            if seat is not None and hasattr(seat, "grab"):
                seat.grab(
                    gdk_window,
                    Gdk.SeatCapabilities.KEYBOARD,
                    False,
                    None,
                    None,
                    None,
                    None,
                )
        return False

    def _release_keyboard(self) -> None:
        display = Gdk.Display.get_default()
        if display is not None and hasattr(display, "get_default_seat"):
            seat = display.get_default_seat()
            if seat is not None and hasattr(seat, "ungrab"):
                seat.ungrab()

    def _on_window_destroy(self, _window: Gtk.Window) -> None:
        self._release_keyboard()
        if self._overlay is not None:
            self._overlay.destroy()
            self._overlay = None
        self._window = None
        self._content_box = None

    def _on_overlay_press(self, _widget: Gtk.Widget, _event: Gdk.EventButton) -> bool:
        self.close()
        return True

    def _on_key_press(self, _widget: Gtk.Widget, event: Gdk.EventKey) -> bool:
        if event.keyval == Gdk.KEY_Escape:
            self.close()
            return True
        return False

    def _on_overlay_draw(self, _widget: Gtk.Widget, cr) -> bool:
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        return False


class CalendarPopup(_PopupBase):
    def __init__(self, calendar_client: GoogleCalendarClient) -> None:
        super().__init__()
        self._calendar_client = calendar_client

    def _header_title(self) -> str:
        return "Today's events"

    def _loading_message(self) -> str:
        return "Loading calendar…"

    def _fetch_content(self) -> None:
        try:
            cached = self._calendar_client.get_cached_events()
            if self._calendar_client.has_valid_cache() and cached:
                events = cached
            else:
                events = self._calendar_client.refetch_todays_events()
            GLib.idle_add(self._show_events, events, None)
        except Exception as exc:
            GLib.idle_add(self._show_events, None, str(exc))

    def _show_events(
        self,
        events: list[CalendarEvent] | None,
        error: str | None,
    ) -> bool:
        if error:
            self._set_message(error)
            return False

        if events is None:
            return False

        rows = [_create_event_row(event) for event in events]
        self._show_rows(rows, empty_message="No events today.")
        return False


class JiraPopup(_PopupBase):
    def __init__(self, jira_client: JiraClient) -> None:
        super().__init__()
        self._jira_client = jira_client

    def _popup_width(self) -> int:
        return JIRA_POPUP_WIDTH

    def _header_title(self) -> str:
        return "Jira tickets"

    def _loading_message(self) -> str:
        return "Loading tickets…"

    def _fetch_content(self) -> None:
        try:
            tickets = self._jira_client.search()
            GLib.idle_add(self._show_tickets, tickets, None)
        except Exception as exc:
            GLib.idle_add(self._show_tickets, None, str(exc))

    def _show_tickets(
        self,
        tickets: list[JiraTicket] | None,
        error: str | None,
    ) -> bool:
        if error:
            self._set_message(error)
            return False

        if tickets is None:
            return False

        rows = [_create_ticket_row(ticket) for ticket in tickets]
        self._show_rows(rows, empty_message="No tickets found.")
        return False


def _create_event_row(event: CalendarEvent) -> Gtk.Widget:
    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    row.get_style_context().add_class("event-row")

    accent = Gtk.EventBox()
    accent.get_style_context().add_class("event-accent")
    row.pack_start(accent, False, False, 0)

    time_label = Gtk.Label(label=event.when)
    time_label.set_xalign(0)
    time_label.set_yalign(0.5)
    time_label.get_style_context().add_class("event-time")
    row.pack_start(time_label, False, False, 0)

    title_label = Gtk.Label(label=event.summary)
    title_label.set_xalign(0)
    title_label.set_yalign(0.5)
    title_label.set_line_wrap(True)
    title_label.get_style_context().add_class("event-title")
    row.pack_start(title_label, True, True, 0)

    return row


def _create_ticket_row(ticket: JiraTicket) -> Gtk.Widget:
    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    row.get_style_context().add_class("event-row")

    accent = Gtk.EventBox()
    accent.get_style_context().add_class("event-accent")
    row.pack_start(accent, False, False, 0)

    key_label = Gtk.Label(label=ticket.key)
    key_label.set_xalign(0)
    key_label.set_yalign(0.5)
    key_label.get_style_context().add_class("event-time")
    row.pack_start(key_label, False, False, 0)

    details = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
    title_label = Gtk.Label(label=ticket.summary)
    title_label.set_xalign(0)
    title_label.set_line_wrap(True)
    title_label.get_style_context().add_class("event-title")
    details.pack_start(title_label, False, False, 0)

    status_label = Gtk.Label(label=ticket.status)
    status_label.set_xalign(0)
    status_label.get_style_context().add_class("popup-message")
    details.pack_start(status_label, False, False, 0)

    row.pack_start(details, True, True, 0)
    return row


_styles_loaded = False


def _ensure_popup_styles() -> None:
    global _styles_loaded
    if _styles_loaded:
        return

    screen = Gdk.Screen.get_default()
    if screen is None:
        return

    provider = Gtk.CssProvider()
    provider.load_from_data(_POPUP_CSS)
    Gtk.StyleContext.add_provider_for_screen(
        screen,
        provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )
    _styles_loaded = True
