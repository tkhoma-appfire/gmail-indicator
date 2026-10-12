"""GDK helpers and optional backend tweaks before GTK initializes."""

from __future__ import annotations

from typing import Any


def configure() -> None:
    # Popup positioning on GNOME Wayland uses a fullscreen shell (see popup/windows.py).
    return None


def pointer_position(device: Any) -> tuple[int, int, int]:
    """Return (x, y, button_mask) from Gdk.Device.get_position() across GDK versions."""
    from gi.repository import Gdk

    pos = device.get_position()
    if len(pos) == 4:
        _screen, x, y, mask = pos
    elif len(pos) == 3:
        first, second, third = pos
        if isinstance(first, (int, float)):
            x, y, mask = first, second, third
        else:
            _screen, x, y = first, second, third
            mask = Gdk.ModifierType(0)
    else:
        x, y = pos
        mask = Gdk.ModifierType(0)

    return int(x), int(y), int(mask)
