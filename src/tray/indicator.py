"""Load Ayatana AppIndicator (glib 2.0 preferred, legacy 0.1 fallback)."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

import gi

gi.require_version("Gtk", "3.0")


class IndicatorBackend(str, Enum):
    GLIB = "glib"
    LEGACY = "legacy"


def load_indicator_api() -> tuple[IndicatorBackend, Any]:
    try:
        gi.require_version("AyatanaAppIndicatorGlib", "2.0")
        from gi.repository import AyatanaAppIndicatorGlib as api

        return IndicatorBackend.GLIB, api
    except ValueError:
        pass

    try:
        gi.require_version("AyatanaAppIndicator3", "0.1")
        from gi.repository import AyatanaAppIndicator3 as api

        return IndicatorBackend.LEGACY, api
    except ValueError:
        gi.require_version("AppIndicator3", "0.1")
        from gi.repository import AppIndicator3 as api

        return IndicatorBackend.LEGACY, api


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
