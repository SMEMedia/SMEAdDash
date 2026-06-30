from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from src.config import normalize_identifier


MASTER_METRICS_SHEET_NAME = "Master Digital Metrics File"
ENEWSLETTER_TAB = "2026 eNewsletter Ads"
WEB_ADS_TAB = "2026 Web Ads"
WEBINARS_TAB = "2026 Webinars"
CUSTOM_EMAILS_TAB = "2026 Custom Emails"
LEAD_GEN_TAB = "2026 Lead Gen"
ADVERTISER_TABS = [ENEWSLETTER_TAB, WEB_ADS_TAB, WEBINARS_TAB, CUSTOM_EMAILS_TAB, LEAD_GEN_TAB]


def load_master_tab(tab_name: str) -> pd.DataFrame:
    from src import config

    if hasattr(config, "load_google_sheet_tab"):
        return config.load_google_sheet_tab(MASTER_METRICS_SHEET_NAME, tab_name)

    session = config._google_authorized_session()
    spreadsheet_id = config._find_google_spreadsheet_id(session, MASTER_METRICS_SHEET_NAME)
    values = config._get_sheet_values(session, spreadsheet_id, tab_name)
    return config._values_to_frame(values)


def load_enewsletter_placements() -> pd.DataFrame:
    return load_master_tab(ENEWSLETTER_TAB)


def load_webinar_sheet() -> pd.DataFrame:
    frame = _rename_columns(load_master_tab(WEBINARS_TAB))
    if frame.empty:
        return _empty_webinar_sheet_frame()
    if "sponsor" not in frame.columns and "advertiser" in frame.columns:
        frame["sponsor"] = frame["advertiser"]
    if "webinar_title" not in frame.columns and "title" in frame.columns:
        frame["webinar_title"] = frame["title"]
    for column in ["registrations", "attendees", "on_demand_attendees", "total_attendance"]:
        if column in frame.columns:
            frame[column] = frame[column].map(_number)
    frame["webinar_date"] = frame.get("date", "").map(_parse_2026_date)
    frame["reports_url"] = frame.get("reports_url", frame.get("url", ""))
    frame["webinar_sponsor"] = frame.get("sponsor", "")
    frame["webinar_match_text"] = (
        frame.get("webinar_title", "").astype(str)
        + " "
        + frame.get("webinar_sponsor", "").astype(str)
    )
    return frame


def webinars_for_advertiser(advertiser_name: str, start_date: date, end_date: date) -> pd.DataFrame:
    frame = load_webinar_sheet()
    if frame.empty:
        return _empty_webinar_frame()
    normalized_advertiser = _normalize_name(advertiser_name)
    sponsor_match = frame["webinar_sponsor"].fillna("").astype(str).map(
        lambda value: _names_match(value, normalized_advertiser)
    )
    in_range = frame["webinar_date"].map(lambda value: not value or start_date <= value <= end_date)
    matched = frame[sponsor_match & in_range].copy()
    if matched.empty:
        return _empty_webinar_frame()
    matched["webinar_id"] = matched.index.map(lambda idx: f"sheet_webinar_{idx}")
    matched["webinar_subheading"] = ""
    matched["webinar_registrant_companies"] = ""
    matched["registrations"] = matched.get("registrations", 0).map(_number)
    return matched.rename(columns={"webinar_title": "webinar_title"})[
        [
            "webinar_id",
            "webinar_title",
            "webinar_sponsor",
            "webinar_subheading",
            "webinar_registrant_companies",
            "webinar_match_text",
            "registrations",
            "reports_url",
        ]
    ].reset_index(drop=True)


def load_lead_gen(advertiser_name: str, start_date: date, end_date: date) -> pd.DataFrame:
    frame = _rename_columns(load_master_tab(LEAD_GEN_TAB))
    if frame.empty:
        return _empty_lead_gen_frame()
    if "advertiser_name" not in frame.columns and "advertiser" in frame.columns:
        frame["advertiser_name"] = frame["advertiser"]
    for column in ["lead_goal", "leads_received", "leads_remaining"]:
        if column in frame.columns:
            frame[column] = frame[column].map(_number)
        else:
            frame[column] = 0
    frame["start_date"] = frame.get("start_date", "").map(_parse_2026_date)
    frame["end_date"] = frame.get("end_date", "").map(_parse_2026_date)
    normalized_advertiser = _normalize_name(advertiser_name)
    advertiser_match = frame["advertiser_name"].fillna("").astype(str).map(
        lambda value: _names_match(value, normalized_advertiser)
    )
    date_match = frame.apply(lambda row: _date_overlaps(row["start_date"], row["end_date"], start_date, end_date), axis=1)
    matched = frame[advertiser_match & date_match].copy()
    if matched.empty:
        return _empty_lead_gen_frame()
    return matched[
        ["advertiser_name", "start_date", "end_date", "lead_goal", "leads_received", "leads_remaining"]
    ].reset_index(drop=True)


def advertiser_rows_from_master_tabs() -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    for tab_name in ADVERTISER_TABS:
        try:
            frame = _rename_columns(load_master_tab(tab_name))
        except Exception:
            continue
        for advertiser in _advertiser_names_from_tab(frame, tab_name):
            normalized = _normalize_name(advertiser)
            if not normalized:
                continue
            rows.append(
                {
                    "advertiser_id": f"sheet_{_slug(normalized)}",
                    "advertiser_name": advertiser.strip(),
                    "gam_advertiser_id": "",
                    "gam_advertiser_name": "",
                    "gam_company_type": "",
                    "gam_credit_status": "",
                    "gam": "true" if tab_name == WEB_ADS_TAB else "false",
                    "webinar": "true" if tab_name == WEBINARS_TAB else "false",
                    "email": "true" if tab_name in {ENEWSLETTER_TAB, CUSTOM_EMAILS_TAB} else "false",
                    "lead_gen": "true" if tab_name == LEAD_GEN_TAB else "false",
                    "source_system": f"Google Sheet {tab_name}",
                    "utm_source": "",
                    "utm_medium": "",
                    "utm_campaign": "",
                    "landing_page_contains": "",
                    "notes": f"Added from {tab_name}.",
                }
            )
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows).drop_duplicates(subset=["advertiser_id"], keep="first")
    return frame


def merge_advertiser_sources(base: pd.DataFrame, extra: pd.DataFrame) -> pd.DataFrame:
    if extra.empty:
        return base
    if base.empty:
        merged = extra.copy()
    else:
        merged = base.copy()
        for column in extra.columns:
            if column not in merged.columns:
                merged[column] = ""
        extra = extra.copy()
        for column in merged.columns:
            if column not in extra.columns:
                extra[column] = ""
        normalized_existing = {_normalize_name(value) for value in merged["advertiser_name"].fillna("").astype(str)}
        new_rows = extra[~extra["advertiser_name"].fillna("").astype(str).map(_normalize_name).isin(normalized_existing)]
        merged = pd.concat([merged, new_rows[merged.columns]], ignore_index=True)

        for _, row in extra.iterrows():
            name = _normalize_name(str(row.get("advertiser_name", "")))
            mask = merged["advertiser_name"].fillna("").astype(str).map(_normalize_name) == name
            for flag in ["gam", "webinar", "email", "lead_gen"]:
                if flag in merged.columns and str(row.get(flag, "")).lower() == "true":
                    merged.loc[mask, flag] = "true"
    for column in ["advertiser_id", "gam_advertiser_id"]:
        if column in merged.columns:
            merged[column] = merged[column].map(normalize_identifier)
    return merged.sort_values("advertiser_name", key=lambda series: series.str.lower(), ignore_index=True)


def _advertiser_names_from_tab(frame: pd.DataFrame, tab_name: str) -> list[str]:
    if frame.empty:
        return []
    if tab_name == WEBINARS_TAB and "sponsor" in frame.columns:
        return _clean_names(frame["sponsor"].tolist())
    for column in ["advertiser_name", "advertiser", "sponsor"]:
        if column in frame.columns:
            return _clean_names(frame[column].tolist())
    return []


def _clean_names(values: list[Any]) -> list[str]:
    return [str(value).strip() for value in values if str(value or "").strip()]


def _rename_columns(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    renamed = frame.copy().fillna("")
    renamed = renamed.rename(columns={column: _normalize_column_name(column) for column in renamed.columns})
    if "" in renamed.columns:
        renamed = renamed.drop(columns=[""])
    return renamed


def _normalize_column_name(column: object) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "_" for char in str(column).strip())
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    mapping = {
        "advertiser": "advertiser",
        "sponsor": "sponsor",
        "webinar_title": "webinar_title",
        "date": "date",
        "start_date": "start_date",
        "end_date": "end_date",
        "lead_goal": "lead_goal",
        "leads_received": "leads_received",
        "leads_remaining": "leads_remaining",
        "registrations": "registrations",
        "attendees": "attendees",
        "on_demand_attendees": "on_demand_attendees",
        "total_attendance": "total_attendance",
        "url": "url",
        "reports_url": "reports_url",
    }
    return mapping.get(cleaned, cleaned)


def _number(value: Any) -> int:
    text = str(value or "").strip().replace(",", "").replace("%", "")
    if not text:
        return 0
    try:
        return int(float(text))
    except ValueError:
        return 0


def _parse_2026_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    parsed = pd.to_datetime(text, errors="coerce")
    if pd.isna(parsed):
        parsed = pd.to_datetime(f"{text}-2026", format="%d-%b-%Y", errors="coerce")
    if pd.isna(parsed):
        return None
    parsed_date = parsed.date()
    if parsed_date.year < 2000:
        return parsed_date.replace(year=2026)
    return parsed_date


def _date_overlaps(row_start: date | None, row_end: date | None, start_date: date, end_date: date) -> bool:
    if not row_start and not row_end:
        return True
    actual_start = row_start or row_end
    actual_end = row_end or row_start
    return bool(actual_start and actual_end and actual_start <= end_date and actual_end >= start_date)


def _names_match(value: str, normalized_advertiser: str) -> bool:
    normalized_value = _normalize_name(value)
    return bool(
        normalized_value
        and normalized_advertiser
        and (normalized_advertiser in normalized_value or normalized_value in normalized_advertiser)
    )


def _normalize_name(value: str) -> str:
    cleaned = str(value).lower()
    for suffix in ["inc", "llc", "ltd", "corp", "corporation", "company", "co"]:
        cleaned = cleaned.replace(f" {suffix} ", " ")
    return " ".join("".join(char if char.isalnum() else " " for char in cleaned).split())


def _slug(value: str) -> str:
    return "_".join(_normalize_name(value).split())


def _empty_webinar_sheet_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=["webinar_title", "date", "sponsor", "registrations", "reports_url"])


def _empty_webinar_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "webinar_id",
            "webinar_title",
            "webinar_sponsor",
            "webinar_subheading",
            "webinar_registrant_companies",
            "webinar_match_text",
            "registrations",
            "reports_url",
        ]
    )


def _empty_lead_gen_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=["advertiser_name", "start_date", "end_date", "lead_goal", "leads_received", "leads_remaining"]
    )
