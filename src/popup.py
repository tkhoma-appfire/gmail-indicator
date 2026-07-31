"""Top-bar popup window."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "3.0")

from gi.repository import Gdk, GLib, Gtk

ICON_BELOW_OFFSET = 12


class Popup:
    def __init__(self, message: str = "Hello World") -> None:
        self._message = message
        self._window: Gtk.Window | None = None
        self._overlay: Gtk.Window | None = None

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

        frame = Gtk.Frame()
        frame.set_shadow_type(Gtk.ShadowType.OUT)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        box.set_margin_start(20)
        box.set_margin_end(20)

        label = Gtk.Label(label=self._message)
        box.pack_start(label, False, False, 0)

        frame.add(box)
        window.add(frame)

        window.connect("destroy", self._on_window_destroy)
        window.connect("key-press-event", self._on_key_press)

        self._window = window
        self._overlay = self._create_overlay()

        window.show_all()

        self._position_window(window, anchor, below_click)
        window.present()

        GLib.idle_add(self._grab_keyboard)

    def close(self) -> None:
        if self._window is not None:
            self._window.destroy()

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
