"""Right-click-only tray menu for AppIndicator."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "3.0")

from gi.repository import Gdk, GLib, Gtk


class TrayMenu:
    """Attach a menu to an AppIndicator and suppress left-click menu opens."""

    def __init__(self, indicator, menu: Gtk.Menu) -> None:
        self._menu = menu
        self._anchor: tuple[int, int] | None = None
        menu.connect("map", self._on_menu_map)
        indicator.set_menu(menu)

    def get_anchor(self) -> tuple[int, int] | None:
        return self._anchor

    def _on_menu_map(self, _menu: Gtk.Menu) -> None:
        display = Gdk.Display.get_default()
        if display is None:
            GLib.idle_add(self._menu.popdown)
            return

        seat = display.get_default_seat()
        if seat is None:
            GLib.idle_add(self._menu.popdown)
            return

        pointer = seat.get_pointer()
        if pointer is None:
            GLib.idle_add(self._menu.popdown)
            return

        _screen, x, y, mask = pointer.get_position()

        is_right_click = mask & Gdk.ModifierType.BUTTON3_MASK
        is_left_click = mask & Gdk.ModifierType.BUTTON1_MASK

        if is_left_click and not is_right_click:
            GLib.idle_add(self._menu.popdown)
            return

        self._anchor = (x, y)
