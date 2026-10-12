"""Optional gtk-layer-shell helpers for Wayland popup positioning."""

from __future__ import annotations

import os

import gi

gi.require_version("Gtk", "3.0")

from gi.repository import Gdk, Gtk

_GTK_LAYER_SHELL = None
_GTK_LAYER_SHELL_CHECKED = False


def layer_shell_available() -> bool:
    global _GTK_LAYER_SHELL, _GTK_LAYER_SHELL_CHECKED
    if _GTK_LAYER_SHELL_CHECKED:
        return _GTK_LAYER_SHELL is not None

    _GTK_LAYER_SHELL_CHECKED = True

    try:
        gi.require_version("GtkLayerShell", "0.1")
        from gi.repository import GtkLayerShell
    except (ImportError, ValueError):
        return False

    if hasattr(GtkLayerShell, "is_supported") and not GtkLayerShell.is_supported():
        return False

    display = Gdk.Display.get_default()
    if display is None or display.get_name() != "wayland":
        return False

    _GTK_LAYER_SHELL = GtkLayerShell
    return True


def configure_popup_window(window: Gtk.Window) -> None:
    if not layer_shell_available():
        return

    layer_shell = _GTK_LAYER_SHELL
    layer_shell.init_for_window(window)
    layer_shell.set_namespace(window, "gmail-notification")
    layer_shell.set_layer(window, layer_shell.Layer.OVERLAY)
    layer_shell.set_keyboard_mode(window, layer_shell.KeyboardMode.ON_DEMAND)


def configure_overlay_window(window: Gtk.Window, monitor: Gdk.Monitor | None) -> None:
    if not layer_shell_available():
        return

    layer_shell = _GTK_LAYER_SHELL
    layer_shell.init_for_window(window)
    layer_shell.set_namespace(window, "gmail-notification-overlay")
    layer_shell.set_layer(window, layer_shell.Layer.OVERLAY)
    if monitor is not None:
        layer_shell.set_monitor(window, monitor)

    for edge in (
        layer_shell.Edge.LEFT,
        layer_shell.Edge.RIGHT,
        layer_shell.Edge.TOP,
        layer_shell.Edge.BOTTOM,
    ):
        layer_shell.set_anchor(window, edge, True)
        layer_shell.set_margin(window, edge, 0)

    layer_shell.set_keyboard_mode(window, layer_shell.KeyboardMode.ON_DEMAND)


def position_popup_window(
    window: Gtk.Window,
    *,
    anchor: tuple[int, int] | None,
    below_click: bool,
    width: int,
    height: int,
    geometry: Gdk.Rectangle,
    below_offset: int,
) -> bool:
    if not layer_shell_available():
        return False

    layer_shell = _GTK_LAYER_SHELL
    display = Gdk.Display.get_default()
    monitor = None
    if display is not None and anchor is not None:
        monitor = display.get_monitor_at_point(anchor[0], anchor[1])
    if monitor is not None:
        layer_shell.set_monitor(window, monitor)

    for edge in (
        layer_shell.Edge.LEFT,
        layer_shell.Edge.RIGHT,
        layer_shell.Edge.TOP,
        layer_shell.Edge.BOTTOM,
    ):
        layer_shell.set_anchor(window, edge, False)

    if anchor is None:
        layer_shell.set_anchor(window, layer_shell.Edge.TOP, True)
        layer_shell.set_anchor(window, layer_shell.Edge.RIGHT, True)
        layer_shell.set_margin(window, layer_shell.Edge.TOP, 32)
        layer_shell.set_margin(window, layer_shell.Edge.RIGHT, 12)
    else:
        anchor_x, anchor_y = anchor
        margin_left = anchor_x - width // 2 - geometry.x
        margin_top = anchor_y + (below_offset if below_click else 0) - geometry.y
        margin = 8
        margin_left = max(margin, min(margin_left, geometry.width - width - margin))
        margin_top = max(margin, min(margin_top, geometry.height - height - margin))

        layer_shell.set_anchor(window, layer_shell.Edge.TOP, True)
        layer_shell.set_anchor(window, layer_shell.Edge.LEFT, True)
        layer_shell.set_margin(window, layer_shell.Edge.LEFT, margin_left)
        layer_shell.set_margin(window, layer_shell.Edge.TOP, margin_top)

    gtk_window_resize(window, width, height)
    return True


def gtk_window_resize(window: Gtk.Window, width: int, height: int) -> None:
    window.resize(max(width, 1), max(height, 1))
