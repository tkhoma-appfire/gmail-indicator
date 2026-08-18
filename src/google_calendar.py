"""Google Calendar API client."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from events_cache import CalendarEvent, EventsCache

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
TOKEN_URI = "https://oauth2.googleapis.com/token"

__all__ = ["CalendarEvent", "GoogleCalendarClient"]


class GoogleCalendarClient:
    def __init__(
        self,
        credentials_path: Path,
        token_path: Path,
        cache_path: Path,
        on_events_loaded: Callable[[list[CalendarEvent]], None] | None = None,
    ) -> None:
        self._credentials_path = credentials_path
        self._token_path = token_path
        self._cache = EventsCache(cache_path)
        self._on_events_loaded = on_events_loaded

    def has_valid_cache(self) -> bool:
        return self._cache.is_valid()

    def get_todays_events(self) -> list[CalendarEvent]:
        return self._cache.get_if_valid() or []

    def get_cached_events(self) -> list[CalendarEvent]:
        return self._cache.get_cached()

    def refresh_todays_events(self, max_results: int = 50) -> list[CalendarEvent]:
        cached = self._cache.get_if_valid()
        if cached is not None:
            events = cached
        else:
            events = self._refetch_from_api(max_results)

        if self._on_events_loaded is not None:
            self._on_events_loaded(list(events))
        return list(events)

    def refetch_todays_events(self, max_results: int = 50) -> list[CalendarEvent]:
        events = self._refetch_from_api(max_results)
        if self._on_events_loaded is not None:
            self._on_events_loaded(list(events))
        return list(events)

    def _refetch_from_api(self, max_results: int) -> list[CalendarEvent]:
        events = self._fetch_from_api(max_results)
        self._cache.save(events)
        return events

    def _fetch_from_api(self, max_results: int) -> list[CalendarEvent]:
        service = build("calendar", "v3", credentials=self._get_credentials())
        local_now = datetime.now().astimezone()
        start_of_day = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=start_of_day.isoformat(),
                timeMax=end_of_day.isoformat(),
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events: list[CalendarEvent] = []
        for item in result.get("items", []):
            starts_at = _parse_start(item)
            if starts_at is None:
                continue
            events.append(
                CalendarEvent(
                    summary=item.get("summary", "(No title)"),
                    when=_format_time(starts_at),
                    starts_at=starts_at.isoformat(),
                )
            )
        return events

    def _get_credentials(self) -> Credentials:
        creds = _load_credentials(self._token_path)

        if creds and creds.refresh_token and (not creds.valid or creds.expired):
            creds.refresh(Request())
            _save_credentials(self._token_path, creds)

        if not creds or not creds.valid:
            if not self._credentials_path.exists():
                raise FileNotFoundError(
                    f"Missing {self._credentials_path.name}. "
                    "Download OAuth credentials from Google Cloud Console."
                )

            flow = InstalledAppFlow.from_client_secrets_file(str(self._credentials_path), SCOPES)
            creds = flow.run_local_server(port=0)
            _save_credentials(self._token_path, creds)

        return creds


def _save_credentials(path: Path, creds: Credentials) -> None:
    if hasattr(creds, "to_json"):
        path.write_text(creds.to_json())
        return

    data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri or TOKEN_URI,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes) if creds.scopes else SCOPES,
    }
    expiry = getattr(creds, "expiry", None)
    if expiry is not None:
        data["expiry"] = expiry.isoformat()
    path.write_text(json.dumps(data, indent=2))


def _load_credentials(path: Path) -> Credentials | None:
    if not path.exists():
        return None

    data = json.loads(path.read_text())
    required = {"refresh_token", "client_id", "client_secret"}
    if not required.issubset(data.keys()):
        return None

    creds = Credentials(
        data.get("token"),
        refresh_token=data.get("refresh_token"),
        token_uri=data.get("token_uri", TOKEN_URI),
        client_id=data.get("client_id"),
        client_secret=data.get("client_secret"),
        scopes=data.get("scopes", SCOPES),
    )

    expiry = data.get("expiry")
    if expiry:
        creds.expiry = datetime.fromisoformat(expiry)

    return creds


def _parse_start(item: dict) -> datetime | None:
    raw = item.get("start", {}).get("dateTime")
    if not raw:
        return None

    return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone()


def _format_time(dt: datetime) -> str:
    return dt.strftime("%-I:%M %p").lower()
