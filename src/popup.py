"""Top-bar popup window."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

import gi

gi.require_version("Gtk", "3.0")

from gi.repository import Gdk, GLib, Gtk

if TYPE_CHECKING:
    from google_calendar import GoogleCalendarClient, CalendarEvent

ICON_BELOW_OFFSET = 12
POPUP_WIDTH = 320
POPUP_MAX_HEIGHT = 400


class Popup:
    def __init__(self, calendar_client: GoogleCalendarClient | None = None) -> None:
        self._calendar_client = calendar_client
        self._window: Gtk.Window | None = None
        self._overlay: Gtk.Window | None = None
        self._content_box: Gtk.Box | None = None

    @property
    def is_visible(self) -> bool:
        return self._window is not None

    def toggle(self, anchor: tuple[int, int] | None = None, *, below_click: bool = True) -> None:
        if self.is_visible:
            self.close()
        else:
            self.show(anchor=anchor, below_click=below_click)

    def show(self, anchor: tuple[int, int] | None = None, *, below_click: bool = True) -> None:
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
        window.set_default_size(POPUP_WIDTH, -1)

        frame = Gtk.Frame()
        frame.set_shadow_type(Gtk.ShadowType.OUT)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.set_margin_top(12)
        outer.set_margin_bottom(12)
        outer.set_margin_start(16)
        outer.set_margin_end(16)

        title = Gtk.Label(label="Upcoming events")
        title.set_xalign(0)
        title.get_style_context().add_class("title")
        outer.pack_start(title, False, False, 0)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_max_content_height(POPUP_MAX_HEIGHT)
        scrolled.set_propagate_natural_height(True)

        self._content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        scrolled.add(self._content_box)
        outer.pack_start(scrolled, True, True, 0)

        frame.add(outer)
        window.add(frame)

        window.connect("destroy", self._on_window_destroy)
        window.connect("key-press-event", self._on_key_press)

        self._window = window
        self._overlay = self._create_overlay()

        self._set_message("Loading calendar…")
        window.show_all()

        self._position_window(window, anchor, below_click)
        window.present()

        GLib.idle_add(self._grab_keyboard)
        self._fetch_events_async()

    def close(self) -> None:
        if self._window is not None:
            self._window.destroy()

    def _fetch_events_async(self) -> None:
        if self._calendar_client is None:
            self._set_message("Calendar client not configured.")
            return

        thread = threading.Thread(target=self._load_events, daemon=True)
        thread.start()

    def _load_events(self) -> None:
        try:
            events = self._calendar_client.get_upcoming_events()
            GLib.idle_add(self._show_events, events, None)
        except Exception as exc:
            GLib.idle_add(self._show_events, None, str(exc))

    def _show_events(
        self,
        events: list[CalendarEvent] | None,
        error: str | None,
    ) -> bool:
        if self._content_box is None:
            return False

        if error:
            self._set_message(error)
            return False

        if not events:
            self._set_message("No upcoming events.")
            return False

        self._clear_content()
        for event in events:
            self._content_box.pack_start(self._create_event_row(event), False, False, 0)

        self._content_box.show_all()
        if self._window is not None:
            self._window.resize(POPUP_WIDTH, -1)
        return False

    def _create_event_row(self, event: CalendarEvent) -> Gtk.Widget:
        row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)

        summary = Gtk.Label(label=event.summary)
        summary.set_xalign(0)
        summary.set_line_wrap(True)
        summary.set_max_width_chars(36)
        row.pack_start(summary, False, False, 0)

        when = Gtk.Label(label=event.when)
        when.set_xalign(0)
        when.get_style_context().add_class("dim-label")
        row.pack_start(when, False, False, 0)

        return row

    def _set_message(self, text: str) -> None:
        self._clear_content()
        if self._content_box is None:
            return

        label = Gtk.Label(label=text)
        label.set_xalign(0)
        label.set_line_wrap(True)
        label.set_max_width_chars(36)
        self._content_box.pack_start(label, False, False, 0)
        self._content_box.show_all()

    def _clear_content(self) -> None:
        if self._content_box is None:
            return

        for child in self._content_box.get_children():
            self._content_box.remove(child)
            child.destroy()

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
