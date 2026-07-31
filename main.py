#!/usr/bin/env python3
"""Ubuntu top-bar indicator using AppIndicator3."""

from __future__ import annotations

import signal
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

APP_ID = "gmail-notification"
ICON_PATH = Path(__file__).resolve().parent / "assets" / "icon.svg"


def build_menu() -> Gtk.Menu:
    menu = Gtk.Menu()

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


def on_quit(_widget: Gtk.MenuItem) -> None:
    Gtk.main_quit()


def main() -> None:
    indicator = AppIndicator3.Indicator.new(
        APP_ID,
        str(ICON_PATH),
        AppIndicator3.IndicatorCategory.APPLICATION_STATUS,
    )
    indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
    indicator.set_title("Gmail Notification")
    indicator.set_menu(build_menu())

    signal.signal(signal.SIGINT, signal.SIG_DFL)
    Gtk.main()


if __name__ == "__main__":
    main()
