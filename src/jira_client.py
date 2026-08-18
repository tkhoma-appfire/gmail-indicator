"""Jira REST API client."""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

__all__ = ["JiraClient", "JiraTicket"]


@dataclass(frozen=True)
class JiraTicket:
    key: str
    summary: str
    status: str
    priority: str


class JiraClient:
    def __init__(self, config_path: Path) -> None:
        self._config_path = config_path

    def search(self, jql: str | None = None, max_results: int = 50) -> list[JiraTicket]:
        config = self._load_config()
        query = jql or config["jql"]
        server = config["server"].rstrip("/")
        url = f"{server}/rest/api/3/search/jql"
        payload = json.dumps(
            {
                "jql": query,
                "maxResults": max_results,
                "fields": ["summary", "status", "priority", "issuetype"],
            }
        ).encode()
        request = urllib.request.Request(
            url,
            data=payload,
            method="POST",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": _basic_auth(config["email"], config["api_token"]),
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                data = json.loads(response.read())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Jira API error ({exc.code}): {body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Could not reach Jira: {exc.reason}") from exc

        tickets: list[JiraTicket] = []
        for issue in data.get("issues", []):
            fields = issue.get("fields", {})
            status = fields.get("status", {}).get("name", "Unknown")
            priority = fields.get("priority", {}).get("name", "Unknown")
            tickets.append(
                JiraTicket(
                    key=issue.get("key", "???"),
                    summary=fields.get("summary", "(No summary)"),
                    status=status,
                    priority=priority,
                )
            )
        return tickets

    def _load_config(self) -> dict[str, str]:
        if not self._config_path.exists():
            raise FileNotFoundError(
                f"Missing {self._config_path.name}. "
                "Copy jira_config.json.example and fill in your Jira credentials."
            )

        config = json.loads(self._config_path.read_text())
        required = {"server", "email", "api_token", "jql"}
        missing = required - config.keys()
        if missing:
            missing_fields = ", ".join(sorted(missing))
            raise ValueError(f"Missing fields in {self._config_path.name}: {missing_fields}")

        return config


def _basic_auth(email: str, api_token: str) -> str:
    credentials = base64.b64encode(f"{email}:{api_token}".encode()).decode()
    return f"Basic {credentials}"
