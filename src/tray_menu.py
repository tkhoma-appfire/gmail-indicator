"""Tray menu for AppIndicator."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "3.0")

import gdk_backend

from gi.repository import Gdk, Gtk


class TrayMenu:
    """Attach a menu to an AppIndicator and record pointer position for popups."""

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
            return

        seat = display.get_default_seat()
        if seat is None:
            return

        pointer = seat.get_pointer()
        if pointer is None:
            return

        x, y, _mask = gdk_backend.pointer_position(pointer)
        self._anchor = (x, y)
