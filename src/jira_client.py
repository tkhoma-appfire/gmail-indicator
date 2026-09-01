"""Jira REST API client."""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

__all__ = ["JiraClient", "JiraSearchResult", "JiraTicket"]

SPRINT_FIELD_CUSTOM_TYPE = "com.pyxis.greenhopper.jira:gh-sprint"


@dataclass(frozen=True)
class JiraTicket:
    key: str
    summary: str
    status: str
    priority: str


@dataclass(frozen=True)
class JiraSearchResult:
    tickets: list[JiraTicket]
    sprint_name: str | None = None


class JiraClient:
    def __init__(self, config_path: Path) -> None:
        self._config_path = config_path
        self._sprint_field_id: str | None = None

    def search(self, jql: str | None = None, max_results: int = 50) -> JiraSearchResult:
        config = self._load_config()
        query = jql or config["jql"]
        sprint_field_id = self._get_sprint_field_id(config)
        fields = ["summary", "status", "priority", "issuetype"]
        if sprint_field_id:
            fields.append(sprint_field_id)

        data = self._post_search(config, query, max_results, fields)

        sprint_name: str | None = None
        tickets: list[JiraTicket] = []
        for issue in data.get("issues", []):
            issue_fields = issue.get("fields", {})
            if sprint_name is None:
                sprint_name = _parse_active_sprint_name(issue_fields, sprint_field_id)
            status = issue_fields.get("status", {}).get("name", "Unknown")
            priority = issue_fields.get("priority", {}).get("name", "Unknown")
            tickets.append(
                JiraTicket(
                    key=issue.get("key", "???"),
                    summary=issue_fields.get("summary", "(No summary)"),
                    status=status,
                    priority=priority,
                )
            )

        if sprint_name is None:
            sprint_name = self.get_active_sprint_name(config)

        return JiraSearchResult(tickets=tickets, sprint_name=sprint_name)

    def get_active_sprint_name(self, config: dict[str, str] | None = None) -> str | None:
        config = config or self._load_config()
        board_id = config.get("board_id")
        if not board_id:
            return None

        server = config["server"].rstrip("/")
        url = f"{server}/rest/agile/1.0/board/{board_id}/sprint?state=active"
        try:
            data = self._get_json(config, url)
        except (RuntimeError, urllib.error.URLError, json.JSONDecodeError):
            return None

        values = data.get("values", [])
        if not values:
            return None
        return values[0].get("name")

    def _get_sprint_field_id(self, config: dict[str, str]) -> str | None:
        if self._sprint_field_id is not None:
            return self._sprint_field_id

        server = config["server"].rstrip("/")
        try:
            fields = self._get_json(config, f"{server}/rest/api/3/field")
        except (RuntimeError, urllib.error.URLError, json.JSONDecodeError):
            return None

        for field in fields:
            schema = field.get("schema", {})
            if schema.get("custom") == SPRINT_FIELD_CUSTOM_TYPE:
                self._sprint_field_id = field["id"]
                return self._sprint_field_id

        return None

    def _get_json(self, config: dict[str, str], url: str) -> dict | list:
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "Authorization": _basic_auth(config["email"], config["api_token"]),
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Jira API error ({exc.code}): {body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Could not reach Jira: {exc.reason}") from exc

    def _post_search(
        self,
        config: dict[str, str],
        jql: str,
        max_results: int,
        fields: list[str],
    ) -> dict:
        server = config["server"].rstrip("/")
        url = f"{server}/rest/api/3/search/jql"
        payload = json.dumps(
            {
                "jql": jql,
                "maxResults": max_results,
                "fields": fields,
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
                return json.loads(response.read())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Jira API error ({exc.code}): {body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Could not reach Jira: {exc.reason}") from exc

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


def _parse_active_sprint_name(
    fields: dict,
    sprint_field_id: str | None = None,
) -> str | None:
    if sprint_field_id:
        name = _sprint_name_from_value(fields.get(sprint_field_id))
        if name:
            return name

    for value in fields.values():
        name = _sprint_name_from_value(value)
        if name:
            return name
    return None


def _sprint_name_from_value(value: object) -> str | None:
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict) and item.get("state", "").lower() == "active":
                name = item.get("name")
                if name:
                    return name
    elif isinstance(value, dict) and value.get("state", "").lower() == "active":
        name = value.get("name")
        if name:
            return name
    return None
