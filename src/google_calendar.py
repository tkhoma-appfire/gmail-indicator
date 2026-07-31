"""Google Calendar API client."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
TOKEN_URI = "https://oauth2.googleapis.com/token"


@dataclass(frozen=True)
class CalendarEvent:
    summary: str
    when: str


class GoogleCalendarClient:
    def __init__(self, credentials_path: Path, token_path: Path) -> None:
        self._credentials_path = credentials_path
        self._token_path = token_path

    def get_upcoming_events(self, days: int = 7, max_results: int = 15) -> list[CalendarEvent]:
        service = build("calendar", "v3", credentials=self._get_credentials())
        now = datetime.now(timezone.utc)
        time_min = now.isoformat()
        time_max = (now + timedelta(days=days)).isoformat()

        result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=time_min,
                timeMax=time_max,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events: list[CalendarEvent] = []
        for item in result.get("items", []):
            events.append(
                CalendarEvent(
                    summary=item.get("summary", "(No title)"),
                    when=_format_when(item),
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


def _format_when(item: dict) -> str:
    start = item.get("start", {})
    raw = start.get("dateTime") or start.get("date")
    if not raw:
        return ""

    if "T" in raw:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        local = dt.astimezone()
        return local.strftime("%a %b %d, %H:%M")

    dt = datetime.fromisoformat(raw)
    return dt.strftime("%a %b %d, All day")
