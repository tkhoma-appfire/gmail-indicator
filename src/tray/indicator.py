"""Ayatana AppIndicator (legacy DBusMenu default; optional GLib GMenu)."""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Any, Callable

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")

_DEPRECATION_LOG_HANDLER_INSTALLED = False


class IndicatorBackend(str, Enum):
    GLIB = "glib"
    LEGACY = "legacy"


def _suppress_appindicator_deprecation_warning() -> None:
    global _DEPRECATION_LOG_HANDLER_INSTALLED
    if _DEPRECATION_LOG_HANDLER_INSTALLED:
        return

    from gi.repository import GLib

    def _handler(
        domain: str,
        level: GLib.LogLevelFlags,
        message: str,
        user_data: object,
    ) -> None:
        if domain == "libayatana-appindicator" and "deprecated" in message:
            return
        GLib.log_default_handler(domain, level, message, user_data)

    GLib.log_set_handler(
        "libayatana-appindicator",
        GLib.LogLevelFlags.LEVEL_WARNING | GLib.LogLevelFlags.LEVEL_MESSAGE,
        _handler,
        None,
    )
    _DEPRECATION_LOG_HANDLER_INSTALLED = True


def _load_glib() -> tuple[IndicatorBackend, Any]:
    gi.require_version("AyatanaAppIndicatorGlib", "2.0")
    from gi.repository import AyatanaAppIndicatorGlib as api

    return IndicatorBackend.GLIB, api


def _load_legacy() -> tuple[IndicatorBackend, Any]:
    try:
        gi.require_version("AyatanaAppIndicator3", "0.1")
        from gi.repository import AyatanaAppIndicator3 as api
    except ValueError:
        gi.require_version("AppIndicator3", "0.1")
        from gi.repository import AppIndicator3 as api

    _suppress_appindicator_deprecation_warning()
    return IndicatorBackend.LEGACY, api


def load_indicator_api() -> tuple[IndicatorBackend, Any]:
    """Load tray bindings (legacy DBusMenu + Gtk.Menu by default on GNOME)."""
    preference = os.environ.get("GMAIL_NOTIFICATION_TRAY_BACKEND", "legacy").lower()
    if preference == "glib":
        loaders: list[Callable[[], tuple[IndicatorBackend, Any]]] = [
            _load_glib,
            _load_legacy,
        ]
    else:
        loaders = [_load_legacy, _load_glib]

    last_error: ValueError | None = None
    for loader in loaders:
        try:
            return loader()
        except ValueError as exc:
            last_error = exc

    if last_error is not None:
        raise last_error
    raise ValueError("No AppIndicator GObject bindings found")


def create_indicator(
    backend: IndicatorBackend,
    api: Any,
    app_id: str,
    icon_path: Path,
) -> Any:
    category = api.IndicatorCategory.APPLICATION_STATUS
    if backend == IndicatorBackend.GLIB:
        return api.Indicator.new_with_path(
            app_id,
            icon_path.name,
            category,
            str(icon_path.parent),
        )
    return api.Indicator.new(app_id, str(icon_path), category)
