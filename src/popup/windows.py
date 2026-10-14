"""Top-bar popup windows."""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from datetime import datetime

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")

from gi.repository import Gdk, GLib, Gtk

from events_cache import CalendarEvent
from clients import GoogleCalendarClient, JiraClient, JiraSearchResult, JiraTicket
from .layer_shell import configure_overlay_window

ICON_BELOW_OFFSET = 12
TOP_POPUP_GAP = 2
POPUP_SCREEN_MARGIN = 0
TOP_PANEL_FALLBACK_HEIGHT = 18
POPUP_WIDTH = 380
JIRA_POPUP_WIDTH = 520
POPUP_MAX_HEIGHT = 320
CALENDAR_LIST_MAX_HEIGHT = 320
CALENDAR_LIST_MAX_HEIGHT_MULTI = 560
CALENDAR_EVENT_ROW_HEIGHT = 62
JIRA_VISIBLE_TICKET_ROWS = 4
JIRA_TICKET_ROW_HEIGHT = 82
JIRA_LIST_ROW_SPACING = 8
JIRA_LIST_PADDING = 16
JIRA_LIST_BOTTOM_PADDING = 16


def _jira_list_viewport_height(visible_rows: int) -> int:
    rows = max(1, visible_rows)
    return (
        JIRA_LIST_PADDING
        + rows * JIRA_TICKET_ROW_HEIGHT
        + max(0, rows - 1) * JIRA_LIST_ROW_SPACING
        + JIRA_LIST_BOTTOM_PADDING
    )


JIRA_LIST_MIN_VIEWPORT = _jira_list_viewport_height(JIRA_VISIBLE_TICKET_ROWS)

L3_TICKETS_JQL = (
    'cf[10900] = "L3 Support" AND assignee = currentUser() '
    "AND sprint in openSprints() ORDER BY statusCategory DESC"
)

def _build_support_jql(l3_issue_keys: list[str]) -> str | None:
    keys = sorted({key for key in l3_issue_keys if key})
    if not keys:
        return None

    linked_clauses = " OR ".join(f"issue in linkedIssues({key})" for key in keys)
    return f"project = SUPPORT AND ({linked_clauses}) ORDER BY status"


def _load_support_tickets_for_l3(
    client: JiraClient,
    l3_tickets: list[JiraTicket],
) -> tuple[list[JiraTicket], dict[str, set[str]]]:
    """Load SUPPORT issues linked to each L3 key; map support key -> linking L3 keys."""
    by_key: dict[str, JiraTicket] = {}
    links: dict[str, set[str]] = {}
    for l3 in l3_tickets:
        jql = f'project = SUPPORT AND issue in linkedIssues({l3.key}) ORDER BY status'
        try:
            result = client.search(jql=jql)
        except Exception:
            continue
        for ticket in result.tickets:
            by_key[ticket.key] = ticket
            links.setdefault(ticket.key, set()).add(l3.key)
    return list(by_key.values()), links


_POPUP_CSS = b"""
.popup-card {
    background-color: #ffffff;
    border-radius: 16px;
    border: 1px solid #e0e0e0;
}
.popup-date {
    color: #5f6368;
    font-size: 12px;
}
.popup-title {
    color: #202124;
    font-size: 20px;
    font-weight: bold;
}
.popup-close-icon-btn {
    background-color: transparent;
    border: none;
    padding: 4px;
    margin-top: 0;
}
.popup-close-icon {
    color: #5f6368;
    font-size: 16px;
}
.popup-separator {
    background-color: #e8eaed;
    min-height: 1px;
    margin-top: 12px;
    margin-bottom: 12px;
}
.event-row {
    background-color: #f8f9fa;
    border-radius: 8px;
    padding: 10px 12px;
}
.event-accent {
    background-color: #1a73e8;
    border-radius: 2px;
    min-width: 4px;
    min-height: 20px;
}
.event-time {
    color: #5f6368;
    font-size: 13px;
    min-width: 72px;
}
.jira-ticket-key {
    background-color: transparent;
    border: none;
    padding: 0;
    min-height: 0;
    min-width: 72px;
}
.jira-ticket-key label {
    color: #1a73e8;
}
.event-title {
    color: #202124;
    font-size: 13px;
}
.popup-message {
    color: #5f6368;
    font-size: 13px;
    padding: 8px 0;
}
.popup-close-button {
    background-color: #ffffff;
    border: 1px solid #dadce0;
    border-radius: 8px;
    padding: 10px 16px;
    margin-top: 12px;
    color: #202124;
    font-size: 14px;
}
.popup-close-button:hover {
    background-color: #f8f9fa;
}
.jira-status-default {
    color: #5f6368;
    font-size: 12px;
}
.jira-status-todo {
    color: #1a73e8;
    font-size: 12px;
    font-weight: 600;
}
.jira-status-in-progress {
    color: #1e8e3e;
    font-size: 12px;
    font-weight: 600;
}
.jira-status-review {
    color: #e37400;
    font-size: 12px;
    font-weight: 600;
}
.jira-status-blocked {
    color: #d93025;
    font-size: 12px;
    font-weight: 600;
}
.jira-status-done {
    color: #0052CC;
    font-size: 12px;
    font-weight: 600;
}
.jira-status-acceptance {
    color: #6554C0;
    font-size: 12px;
    font-weight: 600;
}
.jira-status-waiting-for-release {
    color: #FF991F;
    font-size: 12px;
    font-weight: 600;
}
.jira-status-waiting-for-level-3 {
    color: #d93025;
    font-size: 12px;
    font-weight: 600;
}
.jira-status-filters {
    margin-top: 8px;
}
.popup-shell-window {
    background-color: rgba(0, 0, 0, 0);
}
.popup-shell-overlay {
    background-color: rgba(0, 0, 0, 0);
}
"""


class _PopupBase(ABC):
    def __init__(self) -> None:
        self._window: Gtk.Window | None = None
        self._fixed: Gtk.Fixed | None = None
        self._card: Gtk.Widget | None = None
        self._catcher: Gtk.EventBox | None = None
        self._monitor: Gdk.Monitor | None = None
        self._monitor_geometry: Gdk.Rectangle | None = None
        self._content_box: Gtk.Box | None = None
        self._scrolled_list: Gtk.ScrolledWindow | None = None
        self._title_label: Gtk.Label | None = None
        self._popup_anchor: tuple[int, int] | None = None
        self._popup_below_click = True
        self._shell_placed = False
        _ensure_popup_styles()

    @property
    def is_visible(self) -> bool:
        return self._window is not None

    @abstractmethod
    def _header_title(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def _loading_message(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def _fetch_content(self) -> None:
        raise NotImplementedError

    def _popup_width(self) -> int:
        return POPUP_WIDTH

    def _max_list_content_height(self, row_count: int) -> int:
        return POPUP_MAX_HEIGHT

    def _apply_list_height(self, row_count: int) -> None:
        if self._scrolled_list is None:
            return
        self._scrolled_list.set_max_content_height(
            self._max_list_content_height(row_count),
        )
        if self._card is not None:
            self._card.queue_resize()
        if self._window is not None:
            GLib.idle_add(self._reposition_popup)

    def toggle(
        self,
        anchor: tuple[int, int] | None = None,
        *,
        below_click: bool = True,
    ) -> None:
        if self.is_visible:
            self.close()
        else:
            self.show(anchor=anchor, below_click=below_click)

    def show(
        self,
        anchor: tuple[int, int] | None = None,
        *,
        below_click: bool = True,
    ) -> None:
        if self.is_visible:
            return

        monitor = self._monitor_for_anchor(anchor)
        self._monitor = monitor
        self._monitor_geometry = (
            monitor.get_geometry() if monitor is not None else self._get_primary_monitor_geometry()
        )
        geometry = self._monitor_geometry

        window = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        window.set_decorated(False)
        window.set_app_paintable(True)
        window.set_resizable(False)
        window.set_skip_taskbar_hint(True)
        window.set_skip_pager_hint(True)
        window.set_default_size(geometry.width, geometry.height)
        window.set_size_request(geometry.width, geometry.height)
        window.get_style_context().add_class("popup-shell-window")
        window.set_keep_above(True)
        _apply_transparent_visual(window)
        window.set_can_focus(True)
        window.add_events(Gdk.EventMask.KEY_PRESS_MASK)
        self._shell_placed = False
        self._popup_anchor = anchor
        self._popup_below_click = below_click

        configure_overlay_window(window, monitor)

        fixed = Gtk.Fixed()
        window.add(fixed)

        catcher = Gtk.EventBox()
        catcher.connect("button-press-event", self._on_overlay_press)
        catcher.connect("draw", self._on_overlay_draw)
        fixed.put(catcher, 0, 0)

        card = Gtk.EventBox()
        card.set_size_request(self._popup_width(), -1)
        card.get_style_context().add_class("popup-card")

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.set_margin_top(20)
        outer.set_margin_bottom(20)
        outer.set_margin_start(20)
        outer.set_margin_end(20)

        outer.pack_start(self._build_header(), False, False, 0)

        below_header = self._build_below_header()
        if below_header is not None:
            outer.pack_start(below_header, False, False, 0)

        self._pack_main_content(outer)

        card.add(outer)
        fixed.put(card, 0, 0)

        window.connect("destroy", self._on_window_destroy)
        window.connect("draw", self._on_shell_draw)
        window.connect("key-press-event", self._on_key_press)
        window.connect("realize", self._on_window_realize)
        window.connect("configure-event", self._on_window_configure)

        self._window = window
        self._fixed = fixed
        self._card = card
        self._catcher = catcher

        self._set_message(self._loading_message())
        window.show_all()
        window.present()
        GLib.idle_add(self._place_shell_on_monitor)
        GLib.idle_add(self._reposition_popup)
        GLib.idle_add(self._reposition_popup)
        GLib.idle_add(self._focus_popup)
        threading.Thread(target=self._fetch_content, daemon=True).start()

    def _build_header(self) -> Gtk.Widget:
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        titles = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        local_now = datetime.now().astimezone()
        date_label = Gtk.Label(label=local_now.strftime("%A, %B %-d"))
        date_label.set_xalign(0)
        date_label.get_style_context().add_class("popup-date")
        titles.pack_start(date_label, False, False, 0)

        title_label = Gtk.Label(label=self._header_title())
        title_label.set_xalign(0)
        title_label.get_style_context().add_class("popup-title")
        titles.pack_start(title_label, False, False, 0)
        self._title_label = title_label

        header.pack_start(titles, True, True, 0)

        close_button = Gtk.Button()
        close_button.set_relief(Gtk.ReliefStyle.NONE)
        close_button.get_style_context().add_class("popup-close-icon-btn")
        close_icon = Gtk.Label(label="✕")
        close_icon.get_style_context().add_class("popup-close-icon")
        close_button.add(close_icon)
        close_button.connect("clicked", lambda _btn: self.close())
        header.pack_start(close_button, False, False, 0)

        return header

    def _build_below_header(self) -> Gtk.Widget | None:
        return None

    def _pack_main_content(self, outer: Gtk.Box) -> None:
        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        separator.get_style_context().add_class("popup-separator")
        outer.pack_start(separator, False, False, 0)

        scrolled, content_box = self._create_scrolled_list()
        self._scrolled_list = scrolled
        self._content_box = content_box
        outer.pack_start(scrolled, True, True, 0)

    def _create_scrolled_list(self) -> tuple[Gtk.ScrolledWindow, Gtk.Box]:
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_max_content_height(POPUP_MAX_HEIGHT)
        scrolled.set_propagate_natural_height(True)

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        scrolled.add(content_box)
        return scrolled, content_box

    def _set_header_title(self, text: str) -> None:
        if self._title_label is not None:
            self._title_label.set_text(text)

    def close(self) -> None:
        if self._window is not None:
            self._window.destroy()

    def _set_message(self, text: str) -> None:
        if self._content_box is not None:
            self._set_message_in(self._content_box, text)

    def _set_message_in(self, content_box: Gtk.Box, text: str) -> None:
        self._clear_content_box(content_box)
        label = Gtk.Label(label=text)
        label.set_xalign(0)
        label.set_line_wrap(True)
        label.get_style_context().add_class("popup-message")
        content_box.pack_start(label, False, False, 0)
        content_box.show_all()

    def _clear_content(self) -> None:
        if self._content_box is not None:
            self._clear_content_box(self._content_box)

    def _clear_content_box(self, content_box: Gtk.Box) -> None:
        for child in content_box.get_children():
            content_box.remove(child)
            child.destroy()

    def _show_rows(self, rows: list[Gtk.Widget], *, empty_message: str) -> None:
        if self._content_box is None:
            return
        self._show_rows_in(self._content_box, rows, empty_message=empty_message)

    def _show_rows_in(
        self,
        content_box: Gtk.Box,
        rows: list[Gtk.Widget],
        *,
        empty_message: str,
    ) -> None:
        if not rows:
            self._set_message_in(content_box, empty_message)
            return

        self._clear_content_box(content_box)
        for row in rows:
            content_box.pack_start(row, False, False, 0)

        content_box.show_all()
        if self._window is not None:
            self._window.queue_resize()
            self._reposition_popup()

    def _reposition_popup(self) -> bool:
        self._position_card()
        return False

    def _place_shell_on_monitor(self) -> bool:
        if self._window is None or self._monitor_geometry is None:
            return False

        gdk_window = self._window.get_window()
        if gdk_window is None:
            return False

        geometry = self._monitor_geometry
        gdk_window.move_resize(geometry.x, geometry.y, geometry.width, geometry.height)
        self._apply_transparent_gdk_window(gdk_window)
        self._sync_monitor_from_window()
        self._shell_placed = True
        self._position_card()
        return False

    def _apply_transparent_gdk_window(self, gdk_window: Gdk.Window) -> None:
        transparent = Gdk.RGBA()
        transparent.red = 0.0
        transparent.green = 0.0
        transparent.blue = 0.0
        transparent.alpha = 0.0
        gdk_window.set_background_rgba(transparent)

    def _sync_monitor_from_window(self) -> None:
        if self._window is None:
            return

        gdk_window = self._window.get_window()
        display = Gdk.Display.get_default()
        if gdk_window is None or display is None:
            return

        monitor = display.get_monitor_at_window(gdk_window)
        if monitor is None:
            return

        self._monitor = monitor
        self._monitor_geometry = monitor.get_geometry()

    def _on_window_realize(self, _window: Gtk.Window) -> None:
        self._place_shell_on_monitor()

    def _on_window_configure(self, _window: Gtk.Window, _event: Gdk.EventConfigure) -> bool:
        if not self._shell_placed:
            self._place_shell_on_monitor()
        else:
            self._position_card()
        return False

    def _on_shell_draw(self, _widget: Gtk.Widget, cr) -> bool:
        cr.set_source_rgba(0.0, 0.0, 0.0, 0.0)
        cr.paint()
        return False

    def _position_card(self) -> None:
        if (
            self._fixed is None
            or self._card is None
            or self._catcher is None
            or self._monitor_geometry is None
            or self._window is None
        ):
            return

        if self._window.get_window() is None:
            return

        geometry = self._monitor_geometry
        self._catcher.set_size_request(geometry.width, geometry.height)
        self._fixed.move(self._catcher, 0, 0)

        card_width, card_height = self._card_size()
        x, y = self._card_top_right_position(card_width, card_height)
        self._fixed.move(self._card, x, y)
        self._card.queue_resize()

    def _card_top_right_position(
        self,
        card_width: int,
        card_height: int,
    ) -> tuple[int, int]:
        geometry = self._monitor_geometry
        if geometry is None:
            return (0, TOP_POPUP_GAP)

        margin_end = self._card_margin_end()
        x = geometry.width - card_width - margin_end
        y = self._top_edge_offset()
        max_y = max(0, geometry.height - card_height - POPUP_SCREEN_MARGIN)
        return (max(0, x), min(y, max_y))

    def _card_margin_end(self) -> int:
        geometry = self._monitor_geometry
        if geometry is None:
            return POPUP_SCREEN_MARGIN

        monitor = self._monitor
        if monitor is not None and hasattr(monitor, "get_workarea"):
            workarea = monitor.get_workarea()
            physical_right = geometry.x + geometry.width
            workarea_right = workarea.x + workarea.width
            inset = max(0, physical_right - workarea_right)
            return POPUP_SCREEN_MARGIN + inset

        return POPUP_SCREEN_MARGIN

    def _top_edge_offset(self) -> int:
        geometry = self._monitor_geometry
        if geometry is None:
            return TOP_POPUP_GAP

        monitor = self._monitor
        panel_inset = TOP_PANEL_FALLBACK_HEIGHT
        if monitor is not None and hasattr(monitor, "get_workarea"):
            workarea = monitor.get_workarea()
            reported = workarea.y - geometry.y
            if reported > 0:
                panel_inset = reported

        return panel_inset + TOP_POPUP_GAP

    def _card_size(self) -> tuple[int, int]:
        if self._card is None:
            return self._popup_width(), 80

        width = self._card.get_allocated_width()
        height = self._card.get_allocated_height()
        if width > 1 and height > 1:
            return width, height

        _, natural = self._card.get_preferred_size()
        return max(natural.width, self._popup_width()), max(natural.height, 80)

    def _monitor_for_anchor(self, anchor: tuple[int, int] | None) -> Gdk.Monitor | None:
        display = Gdk.Display.get_default()
        if display is None:
            return None
        if anchor is not None:
            return display.get_monitor_at_point(anchor[0], anchor[1])
        return display.get_primary_monitor()

    def _monitor_geometry_at(self, x: int, y: int) -> Gdk.Rectangle:
        display = Gdk.Display.get_default()
        if display is not None:
            monitor = display.get_monitor_at_point(x, y)
            if monitor is not None:
                return monitor.get_geometry()
        return self._get_primary_monitor_geometry()

    def _get_primary_monitor_geometry(self) -> Gdk.Rectangle:
        display = Gdk.Display.get_default()
        if display is not None:
            monitor = display.get_primary_monitor()
            if monitor is not None:
                return monitor.get_geometry()

        screen = Gdk.Screen.get_default()
        monitor_num = screen.get_primary_monitor()
        return screen.get_monitor_geometry(monitor_num)

    def _focus_popup(self) -> bool:
        """Focus the popup without a seat keyboard grab (avoids GNOME shortcut-inhibit prompts)."""
        focus_widget = self._window or self._catcher
        if focus_widget is not None:
            focus_widget.grab_focus()
        return False

    def _on_window_destroy(self, _window: Gtk.Window) -> None:
        self._window = None
        self._fixed = None
        self._card = None
        self._catcher = None
        self._monitor = None
        self._monitor_geometry = None
        self._content_box = None
        self._title_label = None
        self._popup_anchor = None
        self._shell_placed = False

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


class CalendarPopup(_PopupBase):
    def __init__(self, calendar_client: GoogleCalendarClient) -> None:
        super().__init__()
        self._calendar_client = calendar_client

    def _header_title(self) -> str:
        return "Today's events"

    def _loading_message(self) -> str:
        return "Loading calendar…"

    def _pack_main_content(self, outer: Gtk.Box) -> None:
        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        separator.get_style_context().add_class("popup-separator")
        outer.pack_start(separator, False, False, 0)

        scrolled, content_box = self._create_scrolled_list()
        self._scrolled_list = scrolled
        self._content_box = content_box
        # Do not expand: card height should follow the event list, not the overlay.
        outer.pack_start(scrolled, False, False, 0)

    def _list_viewport_height(self, row_count: int) -> int:
        spacing = 8
        padding = 16
        return min(
            CALENDAR_LIST_MAX_HEIGHT_MULTI,
            padding
            + row_count * CALENDAR_EVENT_ROW_HEIGHT
            + max(0, row_count - 1) * spacing,
        )

    def _apply_list_height(self, row_count: int) -> None:
        if self._scrolled_list is None:
            return
        if row_count <= 1:
            self._scrolled_list.set_min_content_height(-1)
            self._scrolled_list.set_max_content_height(CALENDAR_LIST_MAX_HEIGHT)
        else:
            height = self._list_viewport_height(row_count)
            self._scrolled_list.set_min_content_height(height)
            self._scrolled_list.set_max_content_height(height)
        self._scrolled_list.queue_resize()
        if self._card is not None:
            self._card.queue_resize()
        if self._window is not None:
            self._window.queue_resize()
            GLib.idle_add(self._reposition_popup)

    def _fetch_content(self) -> None:
        try:
            cached = self._calendar_client.get_cached_events()
            if self._calendar_client.has_valid_cache() and cached:
                events = cached
            else:
                events = self._calendar_client.refetch_todays_events()
            GLib.idle_add(self._show_events, events, None)
        except Exception as exc:
            GLib.idle_add(self._show_events, None, str(exc))

    def _show_events(
        self,
        events: list[CalendarEvent] | None,
        error: str | None,
    ) -> bool:
        if error:
            self._set_message(error)
            return False

        if events is None:
            return False

        rows = [_create_event_row(event) for event in events]
        self._show_rows(rows, empty_message="No events today.")
        if rows:
            self._apply_list_height(len(rows))
        return False


class JiraPopup(_PopupBase):
    def __init__(self, jira_client: JiraClient) -> None:
        super().__init__()
        self._jira_client = jira_client
        self._filters_box: Gtk.FlowBox | None = None
        self._l3_content_box: Gtk.Box | None = None
        self._support_content_box: Gtk.Box | None = None
        self._tickets: list[JiraTicket] = []
        self._l3_tickets: list[JiraTicket] = []
        self._support_tickets: list[JiraTicket] = []
        self._support_linked_l3: dict[str, set[str]] = {}
        self._hidden_statuses: set[str] = set()
        self._hide_done_l3 = False
        self._hide_done_support = False
        self._l3_done_checkbox: Gtk.CheckButton | None = None
        self._support_done_checkbox: Gtk.CheckButton | None = None
        self._scrolled_lists: list[Gtk.ScrolledWindow] = []

    def _popup_width(self) -> int:
        return JIRA_POPUP_WIDTH

    def _header_title(self) -> str:
        return "Jira tickets"

    def _loading_message(self) -> str:
        return "Loading tickets…"

    def _create_scrolled_list(self) -> tuple[Gtk.ScrolledWindow, Gtk.Box]:
        scrolled, content_box = super()._create_scrolled_list()
        content_box.set_margin_bottom(JIRA_LIST_BOTTOM_PADDING)
        scrolled.set_max_content_height(JIRA_LIST_MIN_VIEWPORT)
        return scrolled, content_box

    def _apply_tab_list_height(
        self,
        scrolled: Gtk.ScrolledWindow,
        row_count: int,
    ) -> None:
        viewport = JIRA_LIST_MIN_VIEWPORT
        if row_count <= 0:
            scrolled.set_min_content_height(-1)
            scrolled.set_max_content_height(viewport)
        else:
            scrolled.set_min_content_height(viewport)
            scrolled.set_max_content_height(viewport)
        scrolled.queue_resize()

    def _after_list_resize(self) -> None:
        if self._card is not None:
            self._card.queue_resize()
        if self._window is not None:
            self._window.queue_resize()
            GLib.idle_add(self._reposition_popup)

    def _set_message(self, text: str) -> None:
        super()._set_message(text)
        for box in (self._l3_content_box, self._support_content_box):
            if box is not None:
                self._set_message_in(box, text)

    def _pack_main_content(self, outer: Gtk.Box) -> None:
        notebook = Gtk.Notebook()
        notebook.get_style_context().add_class("jira-tabs")

        all_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._filters_box = Gtk.FlowBox()
        self._filters_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self._filters_box.set_max_children_per_line(3)
        self._filters_box.set_column_spacing(12)
        self._filters_box.set_row_spacing(4)
        self._filters_box.get_style_context().add_class("jira-status-filters")
        all_page.pack_start(self._filters_box, False, False, 0)

        scrolled_all, self._content_box = self._create_scrolled_list()
        all_page.pack_start(scrolled_all, False, False, 0)
        notebook.append_page(all_page, Gtk.Label(label="All Tickets"))

        l3_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        l3_filters = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        l3_filters.get_style_context().add_class("jira-status-filters")
        self._l3_done_checkbox = Gtk.CheckButton(label="Done")
        self._l3_done_checkbox.connect("toggled", self._on_l3_done_toggled)
        l3_filters.pack_start(self._l3_done_checkbox, False, False, 0)
        l3_page.pack_start(l3_filters, False, False, 0)

        scrolled_l3, self._l3_content_box = self._create_scrolled_list()
        l3_page.pack_start(scrolled_l3, False, False, 0)
        notebook.append_page(l3_page, Gtk.Label(label="L3 tickets"))

        support_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        support_filters = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        support_filters.get_style_context().add_class("jira-status-filters")
        self._support_done_checkbox = Gtk.CheckButton(label="Done")
        self._support_done_checkbox.connect("toggled", self._on_support_done_toggled)
        support_filters.pack_start(self._support_done_checkbox, False, False, 0)
        support_page.pack_start(support_filters, False, False, 0)

        scrolled_support, self._support_content_box = self._create_scrolled_list()
        support_page.pack_start(scrolled_support, False, False, 0)
        notebook.append_page(support_page, Gtk.Label(label="Support"))

        self._scrolled_lists = [scrolled_all, scrolled_l3, scrolled_support]
        outer.pack_start(notebook, False, False, 0)

    def _fetch_content(self) -> None:
        try:
            all_result = self._jira_client.search()
            l3_result = self._jira_client.search(jql=L3_TICKETS_JQL)
            support_tickets, support_links = _load_support_tickets_for_l3(
                self._jira_client,
                l3_result.tickets,
            )
            support_result = JiraSearchResult(tickets=support_tickets)
            GLib.idle_add(
                self._show_tickets,
                all_result,
                l3_result,
                support_result,
                support_links,
                None,
            )
        except Exception as exc:
            GLib.idle_add(self._show_tickets, None, None, None, None, str(exc))

    def _show_tickets(
        self,
        all_result: JiraSearchResult | None,
        l3_result: JiraSearchResult | None,
        support_result: JiraSearchResult | None,
        support_links: dict[str, set[str]] | None,
        error: str | None,
    ) -> bool:
        if error:
            self._set_message(error)
            return False

        if all_result is None or l3_result is None or support_result is None:
            return False

        if all_result.sprint_name:
            self._set_header_title(f"Jira tickets · {all_result.sprint_name}")

        self._tickets = all_result.tickets
        self._l3_tickets = l3_result.tickets
        self._support_tickets = support_result.tickets
        self._support_linked_l3 = support_links or {}
        self._hidden_statuses.clear()
        self._build_status_filters()
        self._render_tickets()
        self._render_l3_tickets()
        self._render_support_tickets()
        return False

    def _build_status_filters(self) -> None:
        if self._filters_box is None:
            return

        for child in self._filters_box.get_children():
            self._filters_box.remove(child)
            child.destroy()

        statuses = sorted({ticket.status for ticket in self._tickets}, key=str.lower)
        for status in statuses:
            item = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            checkbox = Gtk.CheckButton()
            checkbox.set_active(True)
            checkbox.connect("toggled", self._on_status_filter_toggled, status)
            item.pack_start(checkbox, False, False, 0)

            label = Gtk.Label(label=status)
            label.set_xalign(0)
            label.get_style_context().add_class(_status_css_class(status))
            item.pack_start(label, False, False, 0)

            self._filters_box.add(item)

        self._filters_box.show_all()

    def _on_status_filter_toggled(self, checkbox: Gtk.CheckButton, status: str) -> None:
        if checkbox.get_active():
            self._hidden_statuses.discard(status)
        else:
            self._hidden_statuses.add(status)
        self._render_tickets()

    def _on_l3_done_toggled(self, checkbox: Gtk.CheckButton) -> None:
        self._hide_done_l3 = checkbox.get_active()
        self._render_l3_tickets()

    def _on_support_done_toggled(self, checkbox: Gtk.CheckButton) -> None:
        self._hide_done_support = checkbox.get_active()
        self._render_support_tickets()

    def _visible_l3_tickets(self) -> list[JiraTicket]:
        tickets = self._l3_tickets
        if self._hide_done_l3:
            tickets = [ticket for ticket in tickets if not _ticket_is_done(ticket.status)]
        return _sort_tickets_done_last(tickets)

    def _done_l3_keys(self) -> set[str]:
        return {ticket.key for ticket in self._l3_tickets if _ticket_is_done(ticket.status)}

    def _support_links_to_done_l3(self, support_key: str) -> bool:
        linked_l3 = self._support_linked_l3.get(support_key, set())
        if not linked_l3:
            return False
        return bool(linked_l3 & self._done_l3_keys())

    def _visible_support_tickets(self) -> list[JiraTicket]:
        tickets = self._support_tickets
        if self._hide_done_support:
            tickets = [
                ticket
                for ticket in tickets
                if not self._support_links_to_done_l3(ticket.key)
            ]
        return tickets

    def _render_tickets(self) -> None:
        if self._content_box is None:
            return
        visible = [ticket for ticket in self._tickets if ticket.status not in self._hidden_statuses]
        rows = [_create_ticket_row(ticket) for ticket in visible]
        self._show_rows_in(self._content_box, rows, empty_message="No tickets found.")
        if len(self._scrolled_lists) > 0:
            self._apply_tab_list_height(self._scrolled_lists[0], len(rows))
            self._after_list_resize()

    def _render_l3_tickets(self) -> None:
        if self._l3_content_box is None:
            return
        visible = self._visible_l3_tickets()
        rows = [_create_ticket_row(ticket) for ticket in visible]
        self._show_rows_in(self._l3_content_box, rows, empty_message="No L3 tickets found.")
        if len(self._scrolled_lists) > 1:
            self._apply_tab_list_height(self._scrolled_lists[1], len(rows))
            self._after_list_resize()

    def _render_support_tickets(self) -> None:
        if self._support_content_box is None:
            return
        visible = self._visible_support_tickets()
        rows = [_create_ticket_row(ticket) for ticket in visible]
        self._show_rows_in(
            self._support_content_box,
            rows,
            empty_message="No Support tickets found.",
        )
        if len(self._scrolled_lists) > 2:
            self._apply_tab_list_height(self._scrolled_lists[2], len(rows))
            self._after_list_resize()

    def _on_window_destroy(self, window: Gtk.Window) -> None:
        self._filters_box = None
        self._l3_content_box = None
        self._support_content_box = None
        self._l3_done_checkbox = None
        self._support_done_checkbox = None
        self._scrolled_lists = []
        self._tickets = []
        self._l3_tickets = []
        self._support_tickets = []
        self._support_linked_l3 = {}
        self._hidden_statuses.clear()
        self._hide_done_l3 = False
        self._hide_done_support = False
        super()._on_window_destroy(window)


def _create_event_row(event: CalendarEvent) -> Gtk.Widget:
    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    row.get_style_context().add_class("event-row")

    accent = Gtk.EventBox()
    accent.get_style_context().add_class("event-accent")
    row.pack_start(accent, False, False, 0)

    time_label = Gtk.Label(label=event.when)
    time_label.set_xalign(0)
    time_label.set_yalign(0.5)
    time_label.get_style_context().add_class("event-time")
    row.pack_start(time_label, False, False, 0)

    title_label = Gtk.Label(label=event.summary)
    title_label.set_xalign(0)
    title_label.set_yalign(0.5)
    title_label.set_line_wrap(True)
    title_label.get_style_context().add_class("event-title")
    row.pack_start(title_label, True, True, 0)

    return row


def _create_ticket_row(ticket: JiraTicket) -> Gtk.Widget:
    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    row.get_style_context().add_class("event-row")

    accent = Gtk.EventBox()
    accent.get_style_context().add_class("event-accent")
    row.pack_start(accent, False, False, 0)

    key_button = Gtk.Button(label=ticket.key)
    key_button.set_relief(Gtk.ReliefStyle.NONE)
    key_button.set_can_focus(False)
    key_button.set_tooltip_text(f"Click to copy {ticket.key}")
    key_button.get_style_context().add_class("jira-ticket-key")
    key_button.connect("clicked", _on_copy_ticket_key_clicked, ticket.key)
    key_button.connect("button-press-event", _on_ticket_key_button_press)
    key_button.connect("enter-notify-event", _on_ticket_key_enter)
    key_button.connect("leave-notify-event", _on_ticket_key_leave)
    row.pack_start(key_button, False, False, 0)

    details = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
    title_label = Gtk.Label(label=ticket.summary)
    title_label.set_xalign(0)
    title_label.set_line_wrap(True)
    title_label.get_style_context().add_class("event-title")
    details.pack_start(title_label, False, False, 0)

    meta = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
    priority_label = Gtk.Label(label=ticket.priority)
    priority_label.set_xalign(0)
    priority_label.get_style_context().add_class("popup-message")
    meta.pack_start(priority_label, False, False, 0)

    dot_label = Gtk.Label(label="·")
    dot_label.get_style_context().add_class("popup-message")
    meta.pack_start(dot_label, False, False, 0)

    status_label = Gtk.Label(label=ticket.status)
    status_label.set_xalign(0)
    status_label.get_style_context().add_class(_status_css_class(ticket.status))
    meta.pack_start(status_label, False, False, 0)
    details.pack_start(meta, False, False, 0)

    row.pack_start(details, True, True, 0)
    return row


def _on_ticket_key_enter(widget: Gtk.Widget, _event: Gdk.EventCrossing) -> bool:
    window = widget.get_window()
    display = Gdk.Display.get_default()
    if window is not None and display is not None:
        cursor = Gdk.Cursor.new_for_display(display, Gdk.CursorType.HAND2)
        window.set_cursor(cursor)
    return False


def _on_ticket_key_leave(widget: Gtk.Widget, _event: Gdk.EventCrossing) -> bool:
    window = widget.get_window()
    if window is not None:
        window.set_cursor(None)
    return False


def _copy_text_to_clipboard(text: str) -> None:
    clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
    clipboard.set_text(text, -1)


def _on_copy_ticket_key_clicked(_button: Gtk.Button, key: str) -> None:
    _copy_text_to_clipboard(key)


def _on_ticket_key_button_press(_widget: Gtk.Widget, event: Gdk.EventButton) -> bool:
    if event.button == 3:
        return True
    return False


def _ticket_is_done(status: str) -> bool:
    normalized = status.strip().lower()
    return normalized in {"done", "closed", "resolved", "complete", "completed"}


def _sort_tickets_done_last(tickets: list[JiraTicket]) -> list[JiraTicket]:
    active = [ticket for ticket in tickets if not _ticket_is_done(ticket.status)]
    done = [ticket for ticket in tickets if _ticket_is_done(ticket.status)]
    return active + done


def _status_css_class(status: str) -> str:
    normalized = status.strip().lower()
    if normalized == "acceptance":
        return "jira-status-acceptance"
    if normalized == "waiting for release":
        return "jira-status-waiting-for-release"
    if normalized == "waiting for level 3":
        return "jira-status-waiting-for-level-3"
    if normalized in {"done", "closed", "resolved", "complete", "completed"}:
        return "jira-status-done"
    if normalized in {"in progress", "in development", "working"}:
        return "jira-status-in-progress"
    if normalized in {"to do", "open", "backlog", "selected for development", "ready for dev"}:
        return "jira-status-todo"
    if normalized in {"in review", "code review", "peer review", "qa", "testing"}:
        return "jira-status-review"
    if normalized in {"blocked", "on hold", "impediment"}:
        return "jira-status-blocked"
    return "jira-status-default"


_styles_loaded = False


def _apply_transparent_visual(window: Gtk.Window) -> None:
    screen = Gdk.Screen.get_default()
    if screen is None:
        return

    visual = screen.get_rgba_visual()
    if visual is not None and screen.is_composited():
        window.set_visual(visual)


def _ensure_popup_styles() -> None:
    global _styles_loaded
    if _styles_loaded:
        return

    screen = Gdk.Screen.get_default()
    if screen is None:
        return

    provider = Gtk.CssProvider()
    provider.load_from_data(_POPUP_CSS)
    Gtk.StyleContext.add_provider_for_screen(
        screen,
        provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )
    _styles_loaded = True
