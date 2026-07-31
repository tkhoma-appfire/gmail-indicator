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
        event = Gtk.get_current_event()
        if event is None:
            return

        if event.type not in (Gdk.EventType.BUTTON_PRESS, Gdk.EventType.BUTTON_RELEASE):
            return

        if event.button == Gdk.BUTTON_PRIMARY:
            GLib.idle_add(self._menu.popdown)
            return

        self._anchor = (int(event.x_root), int(event.y_root))
