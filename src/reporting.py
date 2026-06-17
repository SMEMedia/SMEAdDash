from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd

from src.gam_client import GAMClient, GAMConfigError, _empty_performance_frame
from src.ga4_client import GA4Client, GA4ConfigError, _empty_website_frame


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


def build_advertiser_report(
    request: ReportRequest,
    allow_empty_ga4: bool = False,
    allow_empty_gam: bool = False,
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

    return AdvertiserReport(
        advertiser=request.advertiser,
        start_date=request.start_date,
        end_date=request.end_date,
        campaign_id=request.campaign_id,
        campaign_name=request.campaign_name,
        ga4_website_performance=ga4_website,
        gam_ad_performance=gam_ads,
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
    }
