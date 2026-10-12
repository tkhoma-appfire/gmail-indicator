"""Tray menu for AppIndicator (GMenu on glib API, Gtk.Menu on legacy)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import gi

gi.require_version("Gtk", "3.0")

import gdk_backend

from gi.repository import Gdk, Gio, Gtk

from .indicator import IndicatorBackend

MenuHandlers = dict[str, Callable[[], None]]


class TrayMenu:
    """Attach a menu to an AppIndicator and record pointer position for popups."""

    def __init__(self) -> None:
        self._anchor: tuple[int, int] | None = None

    def get_anchor(self) -> tuple[int, int] | None:
        return self._anchor

    @classmethod
    def attach(
        cls,
        indicator: Any,
        backend: IndicatorBackend,
        handlers: MenuHandlers,
    ) -> TrayMenu:
        tray = cls()
        if backend == IndicatorBackend.GLIB:
            tray._attach_glib(indicator, handlers)
        else:
            tray._attach_gtk(indicator, handlers)
        return tray

    def _record_pointer(self) -> None:
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

    def _on_menu_map(self, _menu: Gtk.Menu) -> None:
        self._record_pointer()

    def _on_indicator_activate(
        self,
        _indicator: Any,
        x: int,
        y: int,
    ) -> None:
        self._anchor = (x, y)

    def _attach_gtk(self, indicator: Any, handlers: MenuHandlers) -> None:
        menu = Gtk.Menu()

        popup_item = Gtk.MenuItem(label="Show today events")
        popup_item.connect("activate", lambda _w: handlers["show_popup"]())
        menu.append(popup_item)

        jira_item = Gtk.MenuItem(label="Show jira tickets")
        jira_item.connect("activate", lambda _w: handlers["show_jira"]())
        menu.append(jira_item)

        about_item = Gtk.MenuItem(label="About")
        about_item.connect("activate", lambda _w: handlers["about"]())
        menu.append(about_item)

        menu.append(Gtk.SeparatorMenuItem())

        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", lambda _w: handlers["quit"]())
        menu.append(quit_item)

        menu.connect("map", self._on_menu_map)
        menu.show_all()
        indicator.set_menu(menu)

    def _attach_glib(self, indicator: Any, handlers: MenuHandlers) -> None:
        prefix = "indicator."
        actions = Gio.SimpleActionGroup()

        def bind_action(name: str, handler: Callable[[], None]) -> None:
            action = Gio.SimpleAction.new(name, None)

            def on_activate(_action: Gio.SimpleAction, _param: Any) -> None:
                self._record_pointer()
                handler()

            action.connect("activate", on_activate)
            actions.add_action(action)

        bind_action("show-popup", handlers["show_popup"])
        bind_action("show-jira", handlers["show_jira"])
        bind_action("about", handlers["about"])
        bind_action("quit", handlers["quit"])

        main_section = Gio.Menu()
        main_section.append("Show today events", f"{prefix}show-popup")
        main_section.append("Show jira tickets", f"{prefix}show-jira")
        main_section.append("About", f"{prefix}about")

        quit_section = Gio.Menu()
        quit_section.append("Quit", f"{prefix}quit")

        menu = Gio.Menu()
        menu.append_section(None, main_section)
        menu.append_section(None, quit_section)

        indicator.set_actions(actions)
        indicator.set_menu(menu)

        try:
            indicator.connect("activate", self._on_indicator_activate)
        except TypeError:
            pass
