from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from typing import Any
from urllib.parse import urljoin

import pandas as pd

from src.config import load_environment


class WebinarNetConfigError(RuntimeError):
    """Raised when Webinar.net configuration or dependencies are missing."""


DEFAULT_BASE_URL = "https://api.webinar.net"
DEFAULT_WEBINARS_PATH = "/v1/webinars"
DEFAULT_ATTENDEES_PATH_TEMPLATE = "/v1/webinars/{webinar_id}/registrants"
DEFAULT_USER_AGENT = "sme-advertiser-dashboard/1.0"


@dataclass(frozen=True)
class WebinarNetConfig:
    api_key: str
    api_secret: str
    base_url: str = DEFAULT_BASE_URL
    webinars_path: str = DEFAULT_WEBINARS_PATH
    attendees_path_template: str = DEFAULT_ATTENDEES_PATH_TEMPLATE
    user_agent: str = DEFAULT_USER_AGENT
    auth_mode: str = "headers"


def _empty_webinar_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "webinar_id",
            "webinar_title",
            "webinar_sponsor",
            "webinar_subheading",
            "webinar_registrant_companies",
            "webinar_match_text",
            "start_time",
            "registrations",
            "reports_url",
            "source_system",
        ]
    )


class WebinarNetClient:
    def __init__(self, config: WebinarNetConfig | None = None) -> None:
        load_environment()
        self.config = config or WebinarNetConfig(
            api_key=os.getenv("WEBINAR_NET_API_KEY", ""),
            api_secret=os.getenv("WEBINAR_NET_API_SECRET", ""),
            base_url=os.getenv("WEBINAR_NET_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
            webinars_path=os.getenv("WEBINAR_NET_WEBINARS_PATH", DEFAULT_WEBINARS_PATH),
            attendees_path_template=os.getenv(
                "WEBINAR_NET_ATTENDEES_PATH_TEMPLATE",
                DEFAULT_ATTENDEES_PATH_TEMPLATE,
            ),
            user_agent=os.getenv("WEBINAR_NET_USER_AGENT", DEFAULT_USER_AGENT),
            auth_mode=os.getenv("WEBINAR_NET_AUTH_MODE", "headers").lower(),
        )
        if not self.config.api_key or not self.config.api_secret:
            raise WebinarNetConfigError(
                "Webinar.net credentials are missing. Set WEBINAR_NET_API_KEY and "
                "WEBINAR_NET_API_SECRET in .env or Streamlit secrets."
            )

        try:
            import requests
        except ModuleNotFoundError as exc:
            raise WebinarNetConfigError("Install requests before fetching Webinar.net data.") from exc

        self.requests = requests

    def webinars(
        self,
        advertiser_name: str,
        start_date: date,
        end_date: date,
        match_text: str | None = None,
    ) -> pd.DataFrame:
        params = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "from": start_date.isoformat(),
            "to": end_date.isoformat(),
        }
        payload = self._get_json_with_fallback(
            self.config.webinars_path,
            fallback_path=DEFAULT_WEBINARS_PATH,
            params=params,
            label="webinar list",
        )
        rows = _extract_items(payload)
        frame = _normalize_webinars(rows, self.config.base_url)
        if frame.empty:
            return frame
        frame = _filter_by_date(frame, start_date, end_date)
        if frame.empty:
            return frame

        frame = self._add_attendee_counts(frame)

        search = (advertiser_name if match_text is None else match_text).strip().lower()
        if search:
            searchable = frame["webinar_match_text"].fillna("").str.lower()
            frame = frame[searchable.str.contains(search, regex=False)].copy()
        return frame.sort_values("start_time", ascending=False, ignore_index=True)

    def _get_json_with_fallback(
        self,
        path: str,
        fallback_path: str,
        params: dict[str, Any],
        label: str,
    ) -> Any:
        try:
            response = self._get(path, params=params)
            return _response_json(response, label)
        except WebinarNetConfigError as exc:
            if path == fallback_path or "non-JSON response" not in str(exc):
                raise
            response = self._get(fallback_path, params=params)
            return _response_json(response, f"{label} fallback")

    def _add_attendee_counts(self, frame: pd.DataFrame) -> pd.DataFrame:
        updated = frame.copy()
        for index, webinar in updated.iterrows():
            webinar_id = str(webinar.get("webinar_id", "") or "")
            if not webinar_id:
                continue
            try:
                attendees = self.attendees(webinar_id)
            except Exception:
                continue
            if int(webinar.get("registrations", 0) or 0) <= 0:
                updated.at[index, "registrations"] = int(attendees.attrs.get("total_count", len(attendees)))
            registrant_match_text = _registrant_match_text(attendees)
            updated.at[index, "webinar_registrant_companies"] = registrant_match_text
            updated.at[index, "webinar_match_text"] = " ".join(
                value
                for value in [
                    str(updated.at[index, "webinar_match_text"] or ""),
                    registrant_match_text,
                ]
                if value
            )
        return updated

    def attendees(self, webinar_id: str) -> pd.DataFrame:
        path = self.config.attendees_path_template.format(webinar_id=webinar_id)
        fallback_path = DEFAULT_ATTENDEES_PATH_TEMPLATE.format(webinar_id=webinar_id)
        try:
            response = self._get(path, params={"includeActivities": "false"})
            payload = _response_json(response, f"attendees for webinar {webinar_id}")
        except WebinarNetConfigError as exc:
            if path == fallback_path or "non-JSON response" not in str(exc):
                raise
            response = self._get(fallback_path, params={"includeActivities": "false"})
            payload = _response_json(response, f"registrants for webinar {webinar_id}")

        attendees = pd.DataFrame(_extract_items(payload))
        if isinstance(payload, dict):
            total_count = payload.get("totalCount") or payload.get("total_count")
            if total_count is not None:
                attendees.attrs["total_count"] = int(total_count)
        return attendees

    def _get(self, path: str, params: dict[str, Any] | None = None):
        url = urljoin(f"{self.config.base_url}/", path.lstrip("/"))
        request_kwargs: dict[str, Any] = {"params": params or {}, "timeout": 30}
        headers = {"Accept": "application/json", "User-Agent": self.config.user_agent}

        if self.config.auth_mode == "headers":
            headers["X-API-KEY"] = self.config.api_key
            headers["X-API-SECRET"] = self.config.api_secret
        elif self.config.auth_mode == "bearer":
            headers["Authorization"] = f"Bearer {self.config.api_key}"
            headers["X-API-Secret"] = self.config.api_secret
        elif self.config.auth_mode == "query":
            request_kwargs["params"].update(
                {"api_key": self.config.api_key, "api_secret": self.config.api_secret}
            )
        else:
            raise WebinarNetConfigError(
                "WEBINAR_NET_AUTH_MODE must be one of: headers, bearer, query."
            )

        request_kwargs["headers"] = headers
        try:
            response = self.requests.get(url, **request_kwargs)
        except self.requests.RequestException as exc:
            raise WebinarNetConfigError(f"Webinar.net request failed: {exc}") from exc
        if response.status_code in {401, 403}:
            raise WebinarNetConfigError(
                "Webinar.net rejected the API credentials. Check the key, secret, and auth mode."
            )
        if response.status_code == 404:
            raise WebinarNetConfigError(
                f"Webinar.net endpoint was not found: {url}. Check WEBINAR_NET_BASE_URL "
                "and WEBINAR_NET_WEBINARS_PATH."
            )
        try:
            response.raise_for_status()
        except self.requests.HTTPError as exc:
            preview = response.text[:300].replace("\n", " ").replace("\r", " ").strip()
            raise WebinarNetConfigError(
                f"Webinar.net request failed with status {response.status_code}. "
                f"URL: {response.url}. Body preview: {preview or '<empty response>'}"
            ) from exc
        return response


def _response_json(response, label: str) -> Any:
    try:
        return response.json()
    except ValueError as exc:
        content_type = response.headers.get("content-type", "unknown")
        preview = response.text[:300].replace("\n", " ").replace("\r", " ").strip()
        if not preview:
            preview = "<empty response>"
        raise WebinarNetConfigError(
            f"Webinar.net returned a non-JSON response for {label}. "
            f"Status: {response.status_code}. Content-Type: {content_type}. "
            f"URL: {response.url}. Body preview: {preview}"
        ) from exc


def _extract_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ["webinars", "items", "data", "results", "events", "registrants", "attendees"]:
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return [payload]


def _first_value(row: dict[str, Any], keys: list[str], default: Any = "") -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return default


def _normalize_webinars(rows: list[dict[str, Any]], base_url: str) -> pd.DataFrame:
    if not rows:
        return _empty_webinar_frame()

    normalized = []
    for row in rows:
        latest_schedule = row.get("latestSchedule") if isinstance(row.get("latestSchedule"), dict) else {}
        urls = row.get("urls") if isinstance(row.get("urls"), dict) else {}
        webinar_id = str(_first_value(row, ["id", "webinarId", "webinar_id", "eventId"]))
        title = str(_first_value(row, ["title", "name", "webinarTitle", "webinar_title"]))
        sponsor = str(
            _first_value(
                row,
                [
                    "sponsor",
                    "sponsorName",
                    "sponsor_name",
                    "sponsoredBy",
                    "sponsored_by",
                    "client",
                    "advertiser",
                ],
            )
        )
        subheading = str(
            _first_value(
                row,
                [
                    "subtitle",
                    "subTitle",
                    "subheading",
                    "subHeading",
                    "description",
                    "shortDescription",
                    "summary",
                ],
            )
        )
        registrations = _first_value(
            row,
            ["registrations", "registrationCount", "registration_count", "totalRegistrants"],
            0,
        )
        reports_url = str(
            _first_value(row, ["reportsUrl", "reports_url", "reportUrl", "url"], "")
            or urls.get("reporting", "")
        )
        if webinar_id and not reports_url:
            reports_url = urljoin(f"{base_url}/", f"reports/{webinar_id}")
        match_text = " ".join(
            str(value)
            for value in [
                title,
                sponsor,
                subheading,
                reports_url,
                row.get("webinarKey", ""),
                urls.get("audience", ""),
                urls.get("reporting", ""),
            ]
            if value
        )
        normalized.append(
            {
                "webinar_id": webinar_id,
                "webinar_title": title,
                "webinar_sponsor": sponsor,
                "webinar_subheading": subheading,
                "webinar_registrant_companies": "",
                "webinar_match_text": match_text,
                "start_time": _first_value(
                    row,
                    ["startTime", "start_time", "date", "scheduledAt"],
                    latest_schedule.get("start", ""),
                ),
                "registrations": registrations,
                "reports_url": reports_url,
                "source_system": "Webinar.net",
            }
        )

    frame = pd.DataFrame(normalized)
    frame["registrations"] = pd.to_numeric(frame["registrations"], errors="coerce").fillna(0).astype(int)
    frame["start_time"] = pd.to_datetime(frame["start_time"], errors="coerce")
    return frame


def _registrant_match_text(attendees: pd.DataFrame) -> str:
    if attendees.empty:
        return ""
    values: set[str] = set()
    if "company" in attendees.columns:
        values.update(
            str(value).strip()
            for value in attendees["company"].dropna().tolist()
            if str(value).strip()
        )
    if "emailAddress" in attendees.columns:
        for email in attendees["emailAddress"].dropna().tolist():
            email_text = str(email).strip().lower()
            if "@" in email_text:
                values.add(email_text.split("@", 1)[1])
    return " ".join(sorted(values))


def _filter_by_date(frame: pd.DataFrame, start_date: date, end_date: date) -> pd.DataFrame:
    if frame.empty or "start_time" not in frame.columns:
        return frame
    dates = pd.to_datetime(frame["start_time"], errors="coerce").dt.date
    keep = dates.isna() | ((dates >= start_date) & (dates <= end_date))
    return frame[keep].copy()
