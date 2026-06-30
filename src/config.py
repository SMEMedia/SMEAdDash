from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT_DIR / "config"
ADVERTISER_SHEET_NAME = "Advertiser Source"
ADVERTISER_WORKSHEET_NAME = "advertisers"
GOOGLE_SHEETS_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.metadata.readonly",
]


def load_environment() -> None:
    try:
        from dotenv import load_dotenv
    except ModuleNotFoundError:
        return

    load_dotenv(ROOT_DIR / ".env")


def load_advertisers(path: Path | None = None) -> pd.DataFrame:
    advertiser_path = path or CONFIG_DIR / "advertisers.csv"
    if path is None:
        try:
            frame = load_advertisers_from_google_sheet()
            if not frame.empty:
                normalized = _normalize_advertisers(frame)
                normalized.attrs["source"] = "Google Sheet"
                return normalized
        except Exception:
            pass

    if not advertiser_path.exists():
        return pd.DataFrame()

    frame = pd.read_csv(advertiser_path, dtype=str).fillna("")
    normalized = _normalize_advertisers(frame)
    normalized.attrs["source"] = "Local CSV"
    return normalized


def load_advertisers_from_google_sheet(
    spreadsheet_name: str | None = None,
    worksheet_name: str | None = None,
) -> pd.DataFrame:
    return load_google_sheet_tab(spreadsheet_name or _advertiser_sheet_name(), worksheet_name or _advertiser_worksheet_name())


def load_google_sheet_tab(spreadsheet_name: str, worksheet_name: str) -> pd.DataFrame:
    session = _google_authorized_session()
    spreadsheet_id = _find_google_spreadsheet_id(session, spreadsheet_name)
    values = _get_sheet_values(session, spreadsheet_id, worksheet_name)
    return _values_to_frame(values)


def save_advertisers_to_google_sheet(
    frame: pd.DataFrame,
    spreadsheet_name: str | None = None,
    worksheet_name: str | None = None,
) -> None:
    normalized = _normalize_advertisers(frame).fillna("").astype(str)
    session = _google_authorized_session()
    spreadsheet_id = _find_google_spreadsheet_id(session, spreadsheet_name or _advertiser_sheet_name())
    worksheet = worksheet_name or _advertiser_worksheet_name()
    values = [normalized.columns.tolist()] + normalized.values.tolist()
    range_name = _quote_sheet_range(worksheet)

    clear_response = session.post(
        f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{range_name}:clear",
        timeout=30,
    )
    clear_response.raise_for_status()

    update_response = session.put(
        f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{range_name}",
        params={"valueInputOption": "RAW"},
        json={"values": values},
        timeout=30,
    )
    update_response.raise_for_status()


def google_advertiser_source_available() -> bool:
    try:
        _google_credentials_info()
        return True
    except Exception:
        return False


def _normalize_advertisers(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy().fillna("")
    required = {"advertiser_id", "advertiser_name"}
    missing = required.difference(frame.columns)
    if missing:
        missing_list = ", ".join(sorted(missing))
        raise ValueError(f"Missing required advertiser columns: {missing_list}")
    for column in ["advertiser_id", "gam_advertiser_id"]:
        if column in frame.columns:
            frame[column] = frame[column].map(normalize_identifier)
    frame = frame.sort_values("advertiser_name", key=lambda series: series.str.lower(), ignore_index=True)
    return frame


def _advertiser_sheet_name() -> str:
    return str(
        os.getenv("ADVERTISER_SOURCE_SHEET_NAME")
        or _streamlit_secret_value("advertiser_source_sheet_name")
        or ADVERTISER_SHEET_NAME
    )


def _advertiser_worksheet_name() -> str:
    return str(
        os.getenv("ADVERTISER_SOURCE_WORKSHEET_NAME")
        or _streamlit_secret_value("advertiser_source_worksheet_name")
        or ADVERTISER_WORKSHEET_NAME
    )


def _google_authorized_session():
    try:
        from google.auth.transport.requests import AuthorizedSession
        from google.oauth2 import service_account
    except ModuleNotFoundError as exc:
        raise RuntimeError("Install google-auth to read advertisers from Google Sheets.") from exc

    credentials = service_account.Credentials.from_service_account_info(
        _google_credentials_info(),
        scopes=GOOGLE_SHEETS_SCOPES,
    )
    return AuthorizedSession(credentials)


def _google_credentials_info() -> dict[str, Any]:
    secret_info = _google_credentials_from_streamlit_secrets()
    if secret_info:
        return secret_info

    json_text = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON") or os.getenv("GCP_SERVICE_ACCOUNT_JSON")
    if json_text:
        return json.loads(json_text)

    configured_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE") or os.getenv("ADVERTISER_SOURCE_SERVICE_ACCOUNT_FILE")
    candidate_paths = [Path(configured_path)] if configured_path else []
    candidate_paths.extend(CONFIG_DIR.glob("*.json"))
    for path in candidate_paths:
        if not path or not path.exists():
            continue
        try:
            info = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if info.get("type") == "service_account" and info.get("client_email") and info.get("private_key"):
            return info
    raise RuntimeError("Google service account credentials were not found.")


def _google_credentials_from_streamlit_secrets() -> dict[str, Any]:
    try:
        import streamlit as st
    except ModuleNotFoundError:
        return {}
    try:
        for key in ["gcp_service_account", "google_service_account"]:
            if key in st.secrets:
                return dict(st.secrets[key])
    except Exception:
        return {}
    return {}


def _find_google_spreadsheet_id(session, spreadsheet_name: str) -> str:
    configured_id = os.getenv("ADVERTISER_SOURCE_SPREADSHEET_ID") or _streamlit_secret_value(
        "advertiser_source_spreadsheet_id"
    )
    if configured_id:
        return str(configured_id)

    escaped_name = spreadsheet_name.replace("\\", "\\\\").replace("'", "\\'")
    response = session.get(
        "https://www.googleapis.com/drive/v3/files",
        params={
            "q": (
                f"name = '{escaped_name}' and "
                "mimeType = 'application/vnd.google-apps.spreadsheet' and trashed = false"
            ),
            "fields": "files(id,name)",
            "pageSize": 10,
        },
        timeout=30,
    )
    response.raise_for_status()
    files = response.json().get("files", [])
    if not files:
        raise RuntimeError(f"Google Sheet not found: {spreadsheet_name}")
    return str(files[0]["id"])


def _streamlit_secret_value(key: str) -> Any:
    try:
        import streamlit as st
    except ModuleNotFoundError:
        return ""
    try:
        return st.secrets.get(key, "")
    except Exception:
        return ""


def _get_sheet_values(session, spreadsheet_id: str, worksheet_name: str) -> list[list[str]]:
    response = session.get(
        f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{_quote_sheet_range(worksheet_name)}",
        timeout=30,
    )
    response.raise_for_status()
    return response.json().get("values", [])


def _values_to_frame(values: list[list[str]]) -> pd.DataFrame:
    if not values:
        return pd.DataFrame()
    headers = [str(value).strip() for value in values[0]]
    rows = [row + [""] * (len(headers) - len(row)) for row in values[1:]]
    return pd.DataFrame(rows, columns=headers).fillna("")


def _quote_sheet_range(worksheet_name: str) -> str:
    from urllib.parse import quote

    escaped = worksheet_name.replace("'", "''")
    return quote(f"'{escaped}'!A:ZZ", safe="")


def normalize_identifier(value: object) -> str:
    text = str(value or "").strip()
    if text.endswith(".0") and text[:-2].isdigit():
        return text[:-2]
    return text


def load_report_sources(path: Path | None = None) -> dict:
    source_path = path or CONFIG_DIR / "report_sources.yml"
    if not source_path.exists():
        return {"categories": {}}

    import yaml

    with source_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {"categories": {}}
