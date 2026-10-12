# Architecture

How **gmail-notification** fits together: tray entry point, calendar and Jira popups, caching, and desktop notifications.

> **Viewing diagrams:** Many editors (including Cursor’s Markdown preview) show Mermaid as plain text. Open **[architecture.html](architecture.html)** in a browser for rendered diagrams. On [GitHub](https://github.com), this file renders Mermaid in the web UI.

## Component overview

```mermaid
flowchart TB
    subgraph desktop["Ubuntu desktop"]
        User["User"]
        Tray["AppIndicator tray icon"]
        Menu["GTK context menu"]
        Popups["CalendarPopup / JiraPopup\n(transparent monitor shell)"]
        Notify["Libnotify toasts"]
    end

    subgraph app["Python app — src/main.py"]
        Main["main() + Gtk.main loop"]
        TrayMenu["TrayMenu\n(pointer anchor)"]
        GdkB["gdk_backend\n(pointer position)"]
    end

    subgraph calendar["Calendar path"]
        GCal["GoogleCalendarClient"]
        Cache["EventsCache\n(events_cache.json, 3h TTL)"]
        EN["EventNotifier\n(15 min before event)"]
    end

    subgraph jira["Jira path"]
        Jira["JiraClient"]
        JCfg["jira_config.json"]
    end

    subgraph external["External services"]
        GAPI["Google Calendar API v3"]
        JAPI["Jira REST / Agile API"]
        OAuth["Google OAuth\n(credentials.json, token.json)"]
    end

    User --> Tray
    Tray --> Menu
    Menu --> Main
    Main --> TrayMenu
    Main --> Popups
    Main --> GCal
    Main --> Jira

    GCal --> Cache
    GCal --> OAuth
    GCal --> GAPI
    GCal --> EN
    EN --> Notify

    Jira --> JCfg
    Jira --> JAPI

    Popups --> GCal
    Popups --> Jira
    Main --> GdkB
```

## Source modules

| Module | Responsibility |
|--------|----------------|
| `main.py` | AppIndicator, menu, popup toggles, startup prefetch |
| `tray_menu.py` | Attaches menu to indicator; records pointer position for monitor anchoring |
| `popup/windows.py` | `CalendarPopup`, `JiraPopup`, shared shell UI and positioning |
| `clients/google_calendar.py` | OAuth, Calendar API, today’s events |
| `events_cache.py` | In-memory + disk cache, TTL, `CalendarEvent` model |
| `notification/event_notifier.py` | Schedules libnotify reminders 15 minutes before events |
| `clients/jira_client.py` | JQL search, sprint name, ticket parsing |
| `gdk_backend.py` | GDK pointer position compatibility (Wayland / GTK versions) |
| `popup/layer_shell.py` | Optional gtk-layer-shell helpers (wlroots; not used on GNOME Mutter) |
| `notification/simulate_notification.py` | Dev helper for notification testing |

## Startup

```mermaid
sequenceDiagram
    participant Main as main.py
    participant Thread as background thread
    participant GCal as GoogleCalendarClient
    participant Cache as EventsCache
    participant API as Google Calendar API
    participant EN as EventNotifier
    participant GTK as Gtk.main

    Main->>Thread: start _prefetch_todays_events()
    Main->>Main: AppIndicator + TrayMenu + menu
    Main->>GTK: Gtk.main()

    Thread->>GCal: refresh_todays_events()
    alt cache valid (today + TTL)
        GCal->>Cache: get_if_valid()
    else cache miss
        GCal->>API: events.list (today)
        GCal->>Cache: save()
    end
    GCal->>EN: schedule(events)
    EN->>EN: threading.Timer per upcoming event
```

On launch, `gdk_backend.configure()` runs before GTK imports (reserved for future GDK tweaks).

## Show today’s events

```mermaid
sequenceDiagram
    participant User
    participant Menu
    participant Main as main._toggle_popup
    participant Pop as CalendarPopup
    participant GCal as GoogleCalendarClient
    participant Cache as EventsCache
    participant API as Google Calendar API
    participant GTK as GLib.idle_add

    User->>Menu: activate menu item
    Menu->>Main: anchor from pointer / tray / fallback
    Main->>Pop: toggle(anchor)
    Pop->>Pop: transparent shell on monitor, card top-center
    Pop->>Pop: worker thread _fetch_content()

    alt has_valid_cache and cached rows
        Pop->>GCal: get_cached_events()
    else
        Pop->>GCal: refetch_todays_events()
        GCal->>API: fetch if needed
        GCal->>Cache: save
    end
    Pop->>GTK: _show_events on main thread
    GTK->>User: render event rows
```

## Show Jira tickets

```mermaid
sequenceDiagram
    participant User
    participant Pop as JiraPopup
    participant Jira as JiraClient
    participant API as Jira POST /search/jql
    participant GTK as GLib.idle_add

    User->>Pop: toggle()
    Pop->>Pop: shell + status filter checkboxes
    Pop->>Jira: search() in background
    Jira->>API: JQL from jira_config.json
    API-->>Jira: issues + sprint custom field
    Jira-->>Pop: JiraSearchResult
    Pop->>GTK: _show_tickets
    GTK->>User: rows; click ticket key to copy
```

## Popup UI layering

```mermaid
flowchart LR
    W["Gtk.Window\nundecorated, transparent"]
    O["Gtk.Overlay"]
    C["EventBox catcher\nclick outside → close"]
    Card["Card\nCalendar or Jira content"]

    W --> O
    O --> C
    O --> Card
```

On GNOME Wayland the shell is sized to the target monitor (`gdk_window.move_resize`) instead of moving a small popup window. The card is placed with overlay margins (horizontally centered, vertically just below the top bar work area).

## Local data files

| File | Role |
|------|------|
| `credentials.json` | Google OAuth client configuration |
| `token.json` | Stored user OAuth token (expiry normalized to naive UTC for google-auth) |
| `events_cache.json` | Today’s events and `filled_at` timestamp (3 hour TTL) |
| `jira_config.json` | Jira server URL, auth, JQL, optional `board_id` for sprint name |

## Threading model

- **GTK main thread**: All UI (`Gtk.main`, popups, notifications via `GLib.idle_add`).
- **Background threads**: Calendar prefetch on startup; popup `_fetch_content` for API calls; `EventNotifier` uses `threading.Timer` for reminder delays.

API results are always applied on the main loop with `GLib.idle_add` before updating widgets.
