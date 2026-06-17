from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from src.config import load_environment


class GA4ConfigError(RuntimeError):
    """Raised when GA4 credentials or property configuration are missing."""


DEFAULT_PROPERTY_ID = "432233519"
ROOT_DIR = Path(__file__).resolve().parents[1]
PLAYGROUND_DIR = ROOT_DIR.parent
WEBSCRAPING_CONFIG_DIR = PLAYGROUND_DIR / "webscraping" / "config"
DEFAULT_CLIENT_SECRET_FILE = WEBSCRAPING_CONFIG_DIR / "client_secret.json"
DEFAULT_TOKEN_FILE = WEBSCRAPING_CONFIG_DIR / "token.json"
SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]


@dataclass(frozen=True)
class AdvertiserGA4Filter:
    utm_source: str = ""
    utm_medium: str = ""
    utm_campaign: str = ""
    landing_page_contains: str = ""

    @classmethod
    def from_advertiser(cls, advertiser: dict[str, Any]) -> "AdvertiserGA4Filter":
        return cls(
            utm_source=str(advertiser.get("utm_source", "") or ""),
            utm_medium=str(advertiser.get("utm_medium", "") or ""),
            utm_campaign=str(advertiser.get("utm_campaign", "") or ""),
            landing_page_contains=str(advertiser.get("landing_page_contains", "") or ""),
        )


def _string_filter(field_name: str, value: str, match_type: Filter.StringFilter.MatchType) -> FilterExpression:
    from google.analytics.data_v1beta.types import Filter, FilterExpression

    return FilterExpression(
        filter=Filter(
            field_name=field_name,
            string_filter=Filter.StringFilter(match_type=match_type, value=value, case_sensitive=False),
        )
    )


def build_advertiser_filter(advertiser_filter: AdvertiserGA4Filter) -> FilterExpression | None:
    from google.analytics.data_v1beta.types import Filter, FilterExpression, FilterExpressionList

    expressions: list[FilterExpression] = []

    if advertiser_filter.utm_source:
        expressions.append(
            _string_filter("sessionSource", advertiser_filter.utm_source, Filter.StringFilter.MatchType.EXACT)
        )
    if advertiser_filter.utm_medium:
        expressions.append(
            _string_filter("sessionMedium", advertiser_filter.utm_medium, Filter.StringFilter.MatchType.EXACT)
        )
    if advertiser_filter.utm_campaign:
        expressions.append(
            _string_filter("sessionCampaignName", advertiser_filter.utm_campaign, Filter.StringFilter.MatchType.CONTAINS)
        )
    if advertiser_filter.landing_page_contains:
        expressions.append(
            _string_filter("landingPagePlusQueryString", advertiser_filter.landing_page_contains, Filter.StringFilter.MatchType.CONTAINS)
        )

    if not expressions:
        return None
    if len(expressions) == 1:
        return expressions[0]
    return FilterExpression(and_group=FilterExpressionList(expressions=expressions))


class GA4Client:
    def __init__(self, property_id: str | None = None) -> None:
        load_environment()
        self.property_id = property_id or os.getenv("GA4_PROPERTY_ID", DEFAULT_PROPERTY_ID)

        if not self.property_id:
            raise GA4ConfigError("GA4_PROPERTY_ID is not set in the environment.")

        try:
            from google.analytics.data_v1beta import BetaAnalyticsDataClient
        except ModuleNotFoundError as exc:
            raise GA4ConfigError("Install requirements.txt before fetching live GA4 data.") from exc

        credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
        if credentials_path:
            if not Path(credentials_path).exists():
                raise GA4ConfigError(f"Google credentials file was not found: {credentials_path}")
            self.client = BetaAnalyticsDataClient()
            return

        credentials = get_oauth_credentials()
        self.client = BetaAnalyticsDataClient(credentials=credentials)

    def website_performance(
        self,
        advertiser: dict[str, Any],
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        from google.analytics.data_v1beta.types import DateRange, Dimension, Metric, RunReportRequest

        advertiser_filter = build_advertiser_filter(AdvertiserGA4Filter.from_advertiser(advertiser))
        request_kwargs: dict[str, Any] = {
            "property": f"properties/{self.property_id}",
            "date_ranges": [DateRange(start_date=start_date.isoformat(), end_date=end_date.isoformat())],
            "dimensions": [
                Dimension(name="date"),
                Dimension(name="sessionSource"),
                Dimension(name="sessionMedium"),
                Dimension(name="sessionCampaignName"),
                Dimension(name="landingPagePlusQueryString"),
            ],
            "metrics": [
                Metric(name="sessions"),
                Metric(name="totalUsers"),
                Metric(name="conversions"),
                Metric(name="engagementRate"),
            ],
            "limit": 100000,
        }
        if advertiser_filter:
            request_kwargs["dimension_filter"] = advertiser_filter

        response = self.client.run_report(RunReportRequest(**request_kwargs))
        rows = []
        for row in response.rows:
            rows.append(
                {
                    "date": row.dimension_values[0].value,
                    "session_source": row.dimension_values[1].value,
                    "session_medium": row.dimension_values[2].value,
                    "session_campaign": row.dimension_values[3].value,
                    "landing_page": row.dimension_values[4].value,
                    "sessions": int(float(row.metric_values[0].value or 0)),
                    "total_users": int(float(row.metric_values[1].value or 0)),
                    "conversions": float(row.metric_values[2].value or 0),
                    "engagement_rate": float(row.metric_values[3].value or 0),
                }
            )

        frame = pd.DataFrame(rows)
        if frame.empty:
            return _empty_website_frame()

        frame.insert(0, "advertiser_id", advertiser["advertiser_id"])
        frame.insert(1, "advertiser_name", advertiser["advertiser_name"])
        return frame


def _empty_website_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "advertiser_id",
            "advertiser_name",
            "date",
            "session_source",
            "session_medium",
            "session_campaign",
            "landing_page",
            "sessions",
            "total_users",
            "conversions",
            "engagement_rate",
        ]
    )


def get_oauth_credentials():
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ModuleNotFoundError as exc:
        raise GA4ConfigError("Install requirements.txt before fetching live GA4 data.") from exc

    token_file = Path(os.getenv("GA4_TOKEN_FILE", "") or DEFAULT_TOKEN_FILE)
    client_secret_file = Path(os.getenv("GA4_CLIENT_SECRET_FILE", "") or DEFAULT_CLIENT_SECRET_FILE)
    creds = None

    if token_file.exists():
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    elif not creds or not creds.valid:
        if not client_secret_file.exists():
            raise GA4ConfigError(
                "GA4 OAuth setup was not found. Set GA4_CLIENT_SECRET_FILE/GA4_TOKEN_FILE "
                f"or add files under {WEBSCRAPING_CONFIG_DIR}."
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_file), scopes=SCOPES)
        creds = flow.run_local_server(port=0)
        token_file.parent.mkdir(parents=True, exist_ok=True)
        token_file.write_text(creds.to_json(), encoding="utf-8")

    return creds
