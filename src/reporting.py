from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd

from src.gam_client import GAMClient, GAMConfigError, _empty_performance_frame
from src.ga4_client import GA4Client, GA4ConfigError, _empty_website_frame
from src.hubspot_client import HubSpotConfigError, HubSpotMarketingEmailClient


@dataclass(frozen=True)
class ReportRequest:
    advertiser: dict[str, Any]
    start_date: date
    end_date: date
    campaign_id: str | None = None
    campaign_name: str | None = None


@dataclass
class AdvertiserReport:
    advertiser: dict[str, Any]
    start_date: date
    end_date: date
    campaign_id: str | None
    campaign_name: str | None
    ga4_website_performance: pd.DataFrame
    gam_ad_performance: pd.DataFrame
    hubspot_enewsletter_performance: pd.DataFrame
    hubspot_custom_email_performance: pd.DataFrame


def build_advertiser_report(
    request: ReportRequest,
    allow_empty_ga4: bool = False,
    allow_empty_gam: bool = False,
    include_hubspot: bool = False,
    allow_empty_hubspot: bool = True,
    hubspot_newsletter_placements: pd.DataFrame | None = None,
) -> AdvertiserReport:
    if allow_empty_ga4:
        ga4_website = _empty_website_frame()
    else:
        try:
            ga4_website = GA4Client().website_performance(
                advertiser=request.advertiser,
                start_date=request.start_date,
                end_date=request.end_date,
            )
        except GA4ConfigError:
            if not allow_empty_ga4:
                raise
            ga4_website = _empty_website_frame()

    gam_advertiser_id = request.advertiser.get("gam_advertiser_id") or request.advertiser.get("advertiser_id")
    if allow_empty_gam:
        gam_ads = _empty_performance_frame()
    else:
        try:
            gam_ads = GAMClient().advertiser_performance(
                start_date=request.start_date,
                end_date=request.end_date,
                advertiser_id=gam_advertiser_id,
                campaign_id=request.campaign_id,
            )
        except GAMConfigError:
            if not allow_empty_gam:
                raise
            gam_ads = _empty_performance_frame()

    hubspot_enewsletter = _empty_hubspot_email_frame()
    hubspot_custom_email = _empty_hubspot_email_frame()
    if include_hubspot:
        try:
            hubspot = HubSpotMarketingEmailClient()
            hubspot_enewsletter = hubspot.newsletter_ads(
                advertiser=request.advertiser,
                start_date=request.start_date,
                end_date=request.end_date,
                placement_frame=hubspot_newsletter_placements,
            )
            hubspot_custom_email = hubspot.custom_emails(
                advertiser=request.advertiser,
                start_date=request.start_date,
                end_date=request.end_date,
            )
        except HubSpotConfigError:
            if not allow_empty_hubspot:
                raise
            hubspot_enewsletter = _empty_hubspot_email_frame()
            hubspot_custom_email = _empty_hubspot_email_frame()

    return AdvertiserReport(
        advertiser=request.advertiser,
        start_date=request.start_date,
        end_date=request.end_date,
        campaign_id=request.campaign_id,
        campaign_name=request.campaign_name,
        ga4_website_performance=ga4_website,
        gam_ad_performance=gam_ads,
        hubspot_enewsletter_performance=hubspot_enewsletter,
        hubspot_custom_email_performance=hubspot_custom_email,
    )


def export_report_frames(report: AdvertiserReport) -> dict[str, pd.DataFrame]:
    metadata = pd.DataFrame(
        [
            {
                "advertiser_id": report.advertiser["advertiser_id"],
                "advertiser_name": report.advertiser["advertiser_name"],
                "start_date": report.start_date.isoformat(),
                "end_date": report.end_date.isoformat(),
                "campaign_id": report.campaign_id or "",
                "campaign_name": report.campaign_name or "",
            }
        ]
    )
    return {
        "report_metadata": metadata,
        "ga4_website_performance": report.ga4_website_performance,
        "gam_ad_performance": report.gam_ad_performance,
        "hubspot_enewsletter_performance": report.hubspot_enewsletter_performance,
        "hubspot_custom_email_performance": report.hubspot_custom_email_performance,
    }


def _empty_hubspot_email_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
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
    )
