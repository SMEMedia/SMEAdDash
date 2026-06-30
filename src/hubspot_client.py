from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from src.config import ROOT_DIR, load_environment


class HubSpotConfigError(RuntimeError):
    """Raised when HubSpot configuration or API access is unavailable."""


DEFAULT_BASE_URL = "https://api.hubapi.com"
MARKETING_EMAILS_PATH = "/marketing/emails/2026-03"
DEFAULT_NEWSLETTER_PLACEMENTS = ROOT_DIR / "data" / "newsletter_placements.csv"
DEFAULT_NEWSLETTER_EXPORT = ROOT_DIR / "eNewsletter Ad Metrics.csv"
DEFAULT_CUSTOM_EMAIL_PLACEMENTS = ROOT_DIR / "data" / "custom_email_placements.csv"


@dataclass(frozen=True)
class HubSpotEmailMatch:
    email_id: str
    email_name: str
    subject: str
    delivered: int
    opened: int
    clicks: int
    open_rate: float
    click_rate: float
    web_version_url: str
    creative: str
    created_at: str
    updated_at: str


class HubSpotMarketingEmailClient:
    def __init__(self, access_token: str | None = None, base_url: str | None = None) -> None:
        load_environment()
        self.access_token = access_token or os.getenv("HUBSPOT_ACCESS_TOKEN", "")
        self.base_url = (base_url or os.getenv("HUBSPOT_BASE_URL", DEFAULT_BASE_URL)).rstrip("/")
        if not self.access_token:
            raise HubSpotConfigError("HUBSPOT_ACCESS_TOKEN is not set in .env.")

    def marketing_emails(self, created_after: date | None = None) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": 100}
        if created_after:
            params["createdAfter"] = f"{created_after.isoformat()}T00:00:00Z"

        emails: list[dict[str, Any]] = []
        after = ""
        while True:
            if after:
                params["after"] = after
            payload = self._get_json(MARKETING_EMAILS_PATH, params=params)
            results = payload.get("results") if isinstance(payload, dict) else None
            if not isinstance(results, list):
                results = payload if isinstance(payload, list) else []
            emails.extend(result for result in results if isinstance(result, dict))

            paging = payload.get("paging", {}) if isinstance(payload, dict) else {}
            after = str(paging.get("next", {}).get("after", "") or "")
            if not after:
                break
        return emails

    def email_detail(self, email_id: str) -> dict[str, Any]:
        return self._get_json(f"{MARKETING_EMAILS_PATH}/{email_id}", params={"includeStats": "true"})

    def newsletter_ads(
        self,
        advertiser: dict[str, Any],
        start_date: date,
        end_date: date,
        placement_path: Path | None = None,
        placement_frame: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        placements = load_newsletter_placements(advertiser, start_date, end_date, placement_path, placement_frame)
        emails = self.marketing_emails()
        if placements.empty:
            return _email_frame([])

        rows: list[dict[str, Any]] = []
        for placement in placements.to_dict(orient="records"):
            placement_date = _coerce_date(
                placement.get("placement_date")
                or placement.get("date")
                or placement.get("newsletter_date")
                or placement.get("send_date")
            )
            if not placement_date:
                continue
            email = find_newsletter_by_date(emails, placement_date)
            if email:
                rows.append(
                    self._match_row(
                        email=email,
                        advertiser=advertiser,
                        placement=placement,
                        match_type=f"MW {placement_date.month}/{placement_date.day}/{placement_date:%y}",
                        report_type="eNewsletter Ad",
                    )
                )
            else:
                rows.append(_unmatched_row(advertiser, placement, "eNewsletter Ad", f"No HubSpot email matched MW {placement_date.month}/{placement_date.day}/{placement_date:%y}"))
        return _email_frame(rows)

    def custom_emails(
        self,
        advertiser: dict[str, Any],
        start_date: date,
        end_date: date,
        placement_path: Path | None = None,
    ) -> pd.DataFrame:
        placements = load_custom_email_placements(advertiser, start_date, end_date, placement_path)
        emails = self.marketing_emails()
        advertiser_name = str(advertiser.get("advertiser_name", "") or "")
        matched_emails = [
            email
            for email in emails
            if is_custom_email_for_advertiser(email, advertiser_name) and _date_in_range(email, start_date, end_date)
        ]

        if placements.empty:
            return _email_frame(
                [
                    self._match_row(
                        email=email,
                        advertiser=advertiser,
                        placement={},
                        match_type=f"{advertiser_name} Custom Email",
                        report_type="Custom Email",
                    )
                    for email in matched_emails
                ]
            )

        rows: list[dict[str, Any]] = []
        used_ids: set[str] = set()
        for placement in placements.to_dict(orient="records"):
            email = find_custom_email_for_placement(matched_emails, advertiser_name, placement, used_ids)
            if email:
                email_id = _email_id(email)
                used_ids.add(email_id)
                rows.append(
                    self._match_row(
                        email=email,
                        advertiser=advertiser,
                        placement=placement,
                        match_type=f"{advertiser_name} Custom Email",
                        report_type="Custom Email",
                    )
                )
            else:
                rows.append(_unmatched_row(advertiser, placement, "Custom Email", f"No HubSpot email title matched {advertiser_name} Custom Email"))
        return _email_frame(rows)

    def _match_row(
        self,
        email: dict[str, Any],
        advertiser: dict[str, Any],
        placement: dict[str, Any],
        match_type: str,
        report_type: str,
    ) -> dict[str, Any]:
        detail = self.email_detail(_email_id(email))
        email_detail = detail or email
        match = normalize_email_detail(email_detail)
        email_date = _email_date(email_detail)
        placement_date = _placement_date_text(placement) or (email_date.isoformat() if email_date else "")
        delivered = _number_or_default(placement.get("placement_delivered"), match.delivered)
        opened = _number_or_default(placement.get("placement_opened"), match.opened)
        clicks = _number_or_default(
            placement.get("placement_clicks") or placement.get("clicks"),
            match.clicks,
        )
        open_rate = _safe_rate(opened, delivered)
        click_rate = _safe_rate(clicks, delivered)
        advertiser_id = str(placement.get("advertiser_id", "") or advertiser.get("advertiser_id", "") or "")
        advertiser_name = str(placement.get("advertiser_name", "") or advertiser.get("advertiser_name", "") or "")
        return {
            "advertiser_id": advertiser_id,
            "advertiser_name": advertiser_name,
            "report_type": report_type,
            "placement_date": placement_date,
            "placement_name": str(placement.get("placement_name", "") or placement.get("name", "") or ""),
            "placement_notes": str(placement.get("notes", "") or ""),
            "placement_ad_type": str(placement.get("ad_type", "") or ""),
            "placement_clicks": str(placement.get("placement_clicks", "") or placement.get("clicks", "") or ""),
            "placement_delivered": str(placement.get("placement_delivered", "") or ""),
            "placement_opened": str(placement.get("placement_opened", "") or ""),
            "match_type": match_type,
            "match_status": "Matched",
            "metric_source": _metric_source(placement),
            "hubspot_delivered": match.delivered,
            "hubspot_opened": match.opened,
            "hubspot_clicks": match.clicks,
            **match.__dict__,
            "delivered": delivered,
            "opened": opened,
            "clicks": clicks,
            "open_rate": open_rate,
            "click_rate": click_rate,
        }

    def _get_json(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        response = requests.get(
            url,
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Accept": "application/json",
            },
            params=params,
            timeout=30,
        )
        if response.status_code in {401, 403}:
            raise HubSpotConfigError("HubSpot rejected HUBSPOT_ACCESS_TOKEN. Check private app scopes and token value.")
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise HubSpotConfigError(f"HubSpot API request failed: {response.status_code} {response.text[:300]}") from exc
        return response.json()


def load_newsletter_placements(
    advertiser: dict[str, Any],
    start_date: date,
    end_date: date,
    path: Path | None = None,
    frame: pd.DataFrame | None = None,
) -> pd.DataFrame:
    return _load_placements(advertiser, start_date, end_date, path or _default_newsletter_path(), frame)


def load_custom_email_placements(
    advertiser: dict[str, Any],
    start_date: date,
    end_date: date,
    path: Path | None = None,
) -> pd.DataFrame:
    return _load_placements(advertiser, start_date, end_date, path or DEFAULT_CUSTOM_EMAIL_PLACEMENTS)


def normalize_email_detail(email: dict[str, Any]) -> HubSpotEmailMatch:
    stats = email.get("stats", {}) if isinstance(email.get("stats"), dict) else {}
    delivered = _first_number(stats, ["delivered", "deliveries", "deliveredCount", "successfulDeliveries", "sent"])
    opened = _first_number(stats, ["opened", "opens", "open", "uniqueOpens", "openCount"])
    clicks = _first_number(stats, ["clicks", "click", "clicked", "uniqueClicks", "clickCount"])
    open_rate = _first_hubspot_ratio(stats, ["openratio", "openRate", "open_rate"]) or _safe_rate(opened, delivered)
    click_rate = _first_hubspot_ratio(stats, ["clickratio", "clickRate", "click_rate", "ctr"]) or _safe_rate(clicks, delivered)
    subject = str(_first_value(email, ["subject", "emailSubject", "previewText"]) or "")
    name = _email_name(email)
    return HubSpotEmailMatch(
        email_id=_email_id(email),
        email_name=name,
        subject=subject,
        delivered=delivered,
        opened=opened,
        clicks=clicks,
        open_rate=open_rate,
        click_rate=click_rate,
        web_version_url=str(_first_value(email, ["webVersionUrl", "webversionUrl", "publishedUrl", "absoluteUrl", "url"]) or ""),
        creative=str(_first_value(email, ["creative", "templatePath", "templatePathForRender"]) or subject or name),
        created_at=str(_first_value(email, ["createdAt", "created", "publishDate"]) or ""),
        updated_at=str(_first_value(email, ["updatedAt", "updated", "publishedAt"]) or ""),
    )


def find_newsletter_by_date(emails: list[dict[str, Any]], placement_date: date) -> dict[str, Any] | None:
    pattern = re.compile(rf"\bMW\s+0?{placement_date.month}/0?{placement_date.day}/{placement_date:%y}\b", re.IGNORECASE)
    for email in emails:
        if pattern.search(_email_name(email)):
            return email
    return None


def find_custom_email_for_placement(
    emails: list[dict[str, Any]],
    advertiser_name: str,
    placement: dict[str, Any],
    used_ids: set[str],
) -> dict[str, Any] | None:
    placement_date = _coerce_date(placement.get("placement_date") or placement.get("date") or placement.get("send_date"))
    candidates = [email for email in emails if _email_id(email) not in used_ids]
    if placement_date:
        dated = [email for email in candidates if _email_date(email) == placement_date]
        if dated:
            return dated[0]
    return candidates[0] if candidates else None


def is_newsletter_email(email: dict[str, Any]) -> bool:
    return bool(re.search(r"\bMW\s+\d{1,2}/\d{1,2}/\d{2}\b", _email_name(email), re.IGNORECASE))


def is_custom_email_for_advertiser(email: dict[str, Any], advertiser_name: str) -> bool:
    normalized_name = _normalize_text(advertiser_name)
    email_title = _normalize_text(_email_name(email))
    has_custom_email_marker = "custom email" in email_title or (
        "custom" in email_title and "email" in email_title
    )
    return bool(normalized_name and _normalized_text_contains(email_title, normalized_name) and has_custom_email_marker)


def _default_newsletter_path() -> Path:
    configured = os.getenv("HUBSPOT_NEWSLETTER_PLACEMENTS_FILE", "")
    if configured:
        configured_path = Path(configured.strip().strip('"'))
        if configured_path.suffix.lower() != ".url":
            return configured_path
    if DEFAULT_NEWSLETTER_PLACEMENTS.exists():
        return DEFAULT_NEWSLETTER_PLACEMENTS
    return DEFAULT_NEWSLETTER_EXPORT


def _load_placements(
    advertiser: dict[str, Any],
    start_date: date,
    end_date: date,
    path: Path,
    frame: pd.DataFrame | None = None,
) -> pd.DataFrame:
    if frame is None and not path.exists():
        return pd.DataFrame()
    frame = normalize_placement_frame(frame if frame is not None else _read_placement_file(path))
    if frame.empty:
        return frame

    advertiser_id = str(advertiser.get("advertiser_id", "") or "")
    advertiser_name = _normalize_text(str(advertiser.get("advertiser_name", "") or ""))
    if "advertiser_id" in frame.columns and advertiser_id:
        frame = frame[frame["advertiser_id"].astype(str) == advertiser_id]
    elif "advertiser_name" in frame.columns and advertiser_name:
        frame = frame[frame["advertiser_name"].map(_normalize_text) == advertiser_name]

    date_column = next((column for column in ["placement_date", "date", "newsletter_date", "send_date"] if column in frame.columns), "")
    if date_column:
        parsed = pd.to_datetime(frame[date_column], errors="coerce").dt.date
        frame = frame[(parsed >= start_date) & (parsed <= end_date)].copy()
    return frame.reset_index(drop=True)


def _read_placement_file(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path, dtype=str).fillna("")
    return pd.read_csv(path, dtype=str).fillna("")


def normalize_placement_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame

    normalized = frame.copy().fillna("")
    normalized = normalized.rename(columns={column: _normalize_column_name(column) for column in normalized.columns})
    if "" in normalized.columns:
        normalized = normalized.drop(columns=[""])

    for column in ["date", "delivered", "opened"]:
        if column in normalized.columns:
            normalized[column] = normalized[column].replace("", pd.NA).ffill().fillna("")

    if "advertiser" in normalized.columns and "advertiser_name" not in normalized.columns:
        normalized["advertiser_name"] = normalized["advertiser"]
    if "date" in normalized.columns and "placement_date" not in normalized.columns:
        normalized["placement_date"] = normalized["date"]
    if "ad_type" in normalized.columns and "placement_name" not in normalized.columns:
        normalized["placement_name"] = normalized["ad_type"]
    if "clicks" in normalized.columns and "placement_clicks" not in normalized.columns:
        normalized["placement_clicks"] = normalized["clicks"]
    if "delivered" in normalized.columns and "placement_delivered" not in normalized.columns:
        normalized["placement_delivered"] = normalized["delivered"]
    if "opened" in normalized.columns and "placement_opened" not in normalized.columns:
        normalized["placement_opened"] = normalized["opened"]

    if "advertiser_name" in normalized.columns:
        normalized = normalized[normalized["advertiser_name"].astype(str).str.strip() != ""].copy()
    return normalized


def _normalize_column_name(column: object) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", str(column).strip().lower()).strip("_")
    mapping = {
        "advertiser": "advertiser",
        "advertizer": "advertiser",
        "advertiser_name": "advertiser_name",
        "date": "date",
        "newsletter_date": "newsletter_date",
        "send_date": "send_date",
        "delivered": "delivered",
        "opened": "opened",
        "ad_type": "ad_type",
        "clicks": "clicks",
    }
    return mapping.get(cleaned, cleaned)


def _email_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    columns = [
        "advertiser_id",
        "advertiser_name",
        "report_type",
        "placement_date",
        "placement_name",
        "placement_notes",
        "placement_ad_type",
        "placement_clicks",
        "placement_delivered",
        "placement_opened",
        "match_type",
        "match_status",
        "match_note",
        "metric_source",
        "hubspot_delivered",
        "hubspot_opened",
        "hubspot_clicks",
        "email_id",
        "email_name",
        "subject",
        "delivered",
        "opened",
        "clicks",
        "open_rate",
        "click_rate",
        "creative",
        "web_version_url",
        "created_at",
        "updated_at",
    ]
    frame = pd.DataFrame(rows)
    for column in columns:
        if column not in frame.columns:
            frame[column] = pd.NA
    return frame[columns]


def _unmatched_row(advertiser: dict[str, Any], placement: dict[str, Any], report_type: str, note: str) -> dict[str, Any]:
    return {
        "advertiser_id": str(placement.get("advertiser_id", "") or advertiser.get("advertiser_id", "") or ""),
        "advertiser_name": str(placement.get("advertiser_name", "") or advertiser.get("advertiser_name", "") or ""),
        "report_type": report_type,
        "placement_date": _placement_date_text(placement),
        "placement_name": str(placement.get("placement_name", "") or placement.get("name", "") or ""),
        "placement_notes": str(placement.get("notes", "") or ""),
        "placement_ad_type": str(placement.get("ad_type", "") or ""),
        "placement_clicks": str(placement.get("placement_clicks", "") or placement.get("clicks", "") or ""),
        "placement_delivered": str(placement.get("placement_delivered", "") or ""),
        "placement_opened": str(placement.get("placement_opened", "") or ""),
        "match_type": "",
        "match_status": "Unmatched",
        "match_note": note,
        "metric_source": "spreadsheet",
    }


def _number_or_default(value: Any, default: int) -> int:
    text = str(value or "").strip()
    if not text:
        return int(default or 0)
    cleaned = text.replace(",", "").replace("$", "")
    try:
        return int(float(cleaned))
    except ValueError:
        return int(default or 0)


def _metric_source(placement: dict[str, Any]) -> str:
    sources = []
    for label, key in [
        ("delivered", "placement_delivered"),
        ("opened", "placement_opened"),
        ("clicks", "placement_clicks"),
    ]:
        if str(placement.get(key, "") or placement.get(label, "") or "").strip():
            sources.append(f"{label}:spreadsheet")
        else:
            sources.append(f"{label}:hubspot")
    return "; ".join(sources)


def _first_number(value: Any, keys: list[str]) -> int:
    found = _first_value(value, keys)
    try:
        return int(float(found or 0))
    except (TypeError, ValueError):
        return 0


def _first_rate(value: Any, keys: list[str]) -> float:
    found = _first_value(value, keys)
    try:
        rate = float(found)
    except (TypeError, ValueError):
        return 0
    return rate / 100 if rate > 1 else rate


def _first_hubspot_ratio(value: Any, keys: list[str]) -> float:
    found = _first_value(value, keys)
    try:
        return float(found) / 100
    except (TypeError, ValueError):
        return 0


def _first_value(value: Any, keys: list[str]) -> Any:
    if isinstance(value, dict):
        for key in keys:
            if key in value and value[key] not in (None, ""):
                return value[key]
        for nested in value.values():
            found = _first_value(nested, keys)
            if found not in (None, ""):
                return found
    if isinstance(value, list):
        for item in value:
            found = _first_value(item, keys)
            if found not in (None, ""):
                return found
    return None


def _safe_rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0


def _email_id(email: dict[str, Any]) -> str:
    return str(email.get("id") or email.get("emailId") or email.get("hs_email_id") or "")


def _email_name(email: dict[str, Any]) -> str:
    return str(email.get("name") or email.get("emailName") or email.get("title") or "")


def _email_date(email: dict[str, Any]) -> date | None:
    return _coerce_date(
        _first_value(
            email,
            [
                "publishedAt",
                "publishDate",
                "sentAt",
                "sendDate",
                "lastSendTime",
                "lastSentAt",
                "lastPublishedAt",
            ],
        )
    )


def _date_in_range(email: dict[str, Any], start_date: date, end_date: date) -> bool:
    email_date = _email_date(email)
    return not email_date or start_date <= email_date <= end_date


def _placement_date_text(placement: dict[str, Any]) -> str:
    return str(
        placement.get("placement_date")
        or placement.get("date")
        or placement.get("newsletter_date")
        or placement.get("send_date")
        or ""
    )


def _coerce_date(value: Any) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    parsed = pd.to_datetime(text, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.date()


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", str(value).lower())).strip()


def _normalized_text_contains(text: str, query: str) -> bool:
    if not text or not query:
        return False
    if len(query) <= 3:
        return query in text.split()
    return query in text
