from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from src.config import ROOT_DIR, load_environment, normalize_identifier


class GAMConfigError(RuntimeError):
    """Raised when Google Ad Manager configuration or dependencies are missing."""


DEFAULT_GAM_CONFIG_FILE = ROOT_DIR / "config" / "googleads.yaml"
DEFAULT_GAM_API_VERSION = "v202602"


@dataclass(frozen=True)
class GAMAdvertiser:
    advertiser_id: str
    advertiser_name: str
    gam_advertiser_id: str
    gam_advertiser_name: str
    gam_company_type: str
    gam_credit_status: str
    source_system: str = "GAM"


class GAMClient:
    def __init__(
        self,
        config_file: str | Path | None = None,
        api_version: str | None = None,
    ) -> None:
        load_environment()
        self.config_file = Path(
            config_file or os.getenv("GAM_CONFIG_FILE", "") or DEFAULT_GAM_CONFIG_FILE
        )
        self.api_version = api_version or os.getenv("GAM_API_VERSION", DEFAULT_GAM_API_VERSION)

        try:
            from googleads import ad_manager
        except ModuleNotFoundError as exc:
            raise GAMConfigError("Install requirements.txt before fetching Google Ad Manager data.") from exc

        self.ad_manager = ad_manager
        if self.config_file.exists():
            validate_googleads_config(self.config_file)
            self.client = ad_manager.AdManagerClient.LoadFromStorage(str(self.config_file))
        else:
            yaml_config = googleads_yaml_from_env()
            if not yaml_config:
                raise GAMConfigError(
                    "Google Ad Manager config was not found. Create config/googleads.yaml, "
                    "set GAM_CONFIG_FILE, or set GAM_NETWORK_CODE/GAM_CLIENT_ID/"
                    "GAM_CLIENT_SECRET/GAM_REFRESH_TOKEN environment variables."
                )
            self.client = ad_manager.AdManagerClient.LoadFromString(yaml_config)

    def advertisers(self, include_house_advertisers: bool = False) -> pd.DataFrame:
        company_service = self.client.GetService("CompanyService", version=self.api_version)
        company_types = {"ADVERTISER"}
        if include_house_advertisers:
            company_types.add("HOUSE_ADVERTISER")

        statement = (
            self.ad_manager.StatementBuilder(version=self.api_version)
            .Limit(500)
        )

        rows: list[dict[str, Any]] = []
        while True:
            page = company_service.getCompaniesByStatement(statement.ToStatement())
            for company in _soap_get(page, "results", []) or []:
                company_type = str(_soap_get(company, "type", ""))
                if company_type not in company_types:
                    continue

                advertiser_id = str(_soap_get(company, "id", ""))
                gam_advertiser_name = str(_soap_get(company, "name", ""))
                advertiser_name = clean_advertiser_name(gam_advertiser_name)
                rows.append(
                    GAMAdvertiser(
                        advertiser_id=advertiser_id,
                        advertiser_name=advertiser_name,
                        gam_advertiser_id=advertiser_id,
                        gam_advertiser_name=gam_advertiser_name,
                        gam_company_type=company_type,
                        gam_credit_status=str(_soap_get(company, "creditStatus", "")),
                    ).__dict__
                )

            statement.offset += statement.limit
            if statement.offset >= int(_soap_get(page, "totalResultSetSize", 0)):
                break

        if not rows:
            return pd.DataFrame(columns=list(GAMAdvertiser.__dataclass_fields__.keys()))
        return pd.DataFrame(rows).sort_values("advertiser_name", ignore_index=True)

    def advertiser_performance(
        self,
        start_date: date,
        end_date: date,
        advertiser_id: str | int | None = None,
        campaign_id: str | int | None = None,
    ) -> pd.DataFrame:
        report_downloader = self.client.GetDataDownloader(version=self.api_version)
        dimensions = [
            "DATE",
            "ADVERTISER_ID",
            "ADVERTISER_NAME",
            "ORDER_ID",
            "ORDER_NAME",
            "CREATIVE_ID",
            "CREATIVE_NAME",
        ]
        columns = ["AD_SERVER_IMPRESSIONS", "AD_SERVER_CLICKS", "AD_SERVER_CTR"]

        report_query: dict[str, Any] = {
            "dimensions": dimensions,
            "columns": columns,
            "dateRangeType": "CUSTOM_DATE",
            "startDate": _gam_date(start_date),
            "endDate": _gam_date(end_date),
        }
        statement_filters = []
        statement_values = []
        advertiser_id = normalize_identifier(advertiser_id)
        if advertiser_id:
            statement_filters.append("ADVERTISER_ID = :advertiser_id")
            statement_values.append(
                {
                    "key": "advertiser_id",
                    "value": {
                        "xsi_type": "NumberValue",
                        "value": str(advertiser_id),
                    },
                }
            )
        if campaign_id:
            statement_filters.append("ORDER_ID = :campaign_id")
            statement_values.append(
                {
                    "key": "campaign_id",
                    "value": {
                        "xsi_type": "NumberValue",
                        "value": str(campaign_id),
                    },
                }
            )

        if statement_filters:
            report_query["statement"] = {
                "query": f"WHERE {' AND '.join(statement_filters)}",
                "values": statement_values,
            }

        report_job = {"reportQuery": report_query}
        report_job_id = report_downloader.WaitForReport(report_job)

        with tempfile.NamedTemporaryFile(mode="w+b", suffix=".csv.gz", delete=False) as report_file:
            report_path = Path(report_file.name)
            report_downloader.DownloadReportToFile(report_job_id, "CSV_DUMP", report_file)

        try:
            frame = pd.read_csv(report_path, compression="gzip")
        finally:
            report_path.unlink(missing_ok=True)

        if frame.empty:
            return _empty_performance_frame()
        return _normalize_report_frame(frame)

    def campaigns_for_advertiser(
        self,
        start_date: date,
        end_date: date,
        advertiser_id: str | int,
    ) -> pd.DataFrame:
        frame = self.advertiser_performance(
            start_date=start_date,
            end_date=end_date,
            advertiser_id=advertiser_id,
        )
        if frame.empty:
            return pd.DataFrame(columns=["campaign_id", "campaign_name", "ad_impressions", "ad_clicks"])
        campaigns = (
            frame.groupby(["campaign_id", "campaign_name"], dropna=False)[["ad_impressions", "ad_clicks"]]
            .sum()
            .reset_index()
            .sort_values(["ad_impressions", "campaign_name"], ascending=[False, True], ignore_index=True)
        )
        return campaigns

    def creative_assets(self, creative_ids: list[str | int]) -> pd.DataFrame:
        ids = [str(creative_id) for creative_id in creative_ids if str(creative_id)]
        if not ids:
            return _empty_creative_assets_frame()

        creative_service = self.client.GetService("CreativeService", version=self.api_version)
        rows: list[dict[str, Any]] = []
        for creative_id in sorted(set(ids)):
            statement = (
                self.ad_manager.StatementBuilder(version=self.api_version)
                .Where("id = :creative_id")
                .WithBindVariable("creative_id", int(float(creative_id)))
                .Limit(1)
            )
            page = creative_service.getCreativesByStatement(statement.ToStatement())
            for creative in _soap_get(page, "results", []) or []:
                rows.append(_creative_asset_row(creative))

        if not rows:
            return _empty_creative_assets_frame()
        return pd.DataFrame(rows)


def _gam_date(value: date) -> dict[str, int]:
    return {"year": value.year, "month": value.month, "day": value.day}


def _soap_get(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _creative_asset_row(creative: Any) -> dict[str, Any]:
    primary_image = _soap_get(creative, "primaryImageAsset")
    size = _soap_get(creative, "size")
    image_size = _soap_get(primary_image, "size") if primary_image else size
    creative_type = "Image" if primary_image else str(type(creative).__name__).replace("Creative", "")
    return {
        "creative_id": str(_soap_get(creative, "id", "")),
        "creative_name": str(_soap_get(creative, "name", "")),
        "creative_type": creative_type or "Unknown",
        "image_url": _soap_get(primary_image, "assetUrl", "") if primary_image else "",
        "preview_url": _soap_get(creative, "previewUrl", ""),
        "destination_url": _soap_get(creative, "destinationUrl", ""),
        "file_name": _soap_get(primary_image, "fileName", "") if primary_image else "",
        "width": _soap_get(image_size, "width", ""),
        "height": _soap_get(image_size, "height", ""),
    }


def _normalize_report_frame(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.rename(columns={column: _normalize_column(column) for column in frame.columns})
    expected = _empty_performance_frame().columns.tolist()
    for column in expected:
        if column not in normalized.columns:
            normalized[column] = pd.NA

    normalized = normalized[expected]
    for column in ["ad_impressions", "ad_clicks", "ad_ctr"]:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce").fillna(0)
    normalized["advertiser_id"] = normalized["gam_advertiser_id"].astype(str)
    normalized["advertiser_name"] = normalized["gam_advertiser_name"].astype(str).map(clean_advertiser_name)
    normalized["campaign_name"] = normalized["campaign_name"].astype(str).map(clean_advertiser_name)
    normalized["creative_name"] = normalized["creative_name"].fillna("Unassigned").astype(str)
    return normalized


def _normalize_column(column: str) -> str:
    cleaned = column.replace("Dimension.", "").replace("Column.", "")
    cleaned = cleaned.lower()
    mapping = {
        "date": "date",
        "advertiser_id": "gam_advertiser_id",
        "advertiser_name": "gam_advertiser_name",
        "order_id": "campaign_id",
        "order_name": "campaign_name",
        "creative_id": "creative_id",
        "creative_name": "creative_name",
        "ad_server_impressions": "ad_impressions",
        "ad_server_clicks": "ad_clicks",
        "ad_server_ctr": "ad_ctr",
    }
    return mapping.get(cleaned, cleaned)


def clean_advertiser_name(name: str) -> str:
    prefixes = [
        "SMES - advancedmanufacturing.org - YUP - ",
    ]
    cleaned = str(name).strip()
    for prefix in prefixes:
        if cleaned.startswith(prefix):
            return cleaned[len(prefix):].strip()
    return cleaned


def _empty_performance_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "advertiser_id",
            "advertiser_name",
            "date",
            "gam_advertiser_id",
            "gam_advertiser_name",
            "campaign_id",
            "campaign_name",
            "creative_id",
            "creative_name",
            "ad_impressions",
            "ad_clicks",
            "ad_ctr",
        ]
    )


def _empty_creative_assets_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "creative_id",
            "creative_name",
            "creative_type",
            "image_url",
            "preview_url",
            "destination_url",
            "file_name",
            "width",
            "height",
        ]
    )


def validate_googleads_config(config_file: Path) -> None:
    ad_manager_config = _read_simple_ad_manager_yaml(config_file)
    if not ad_manager_config:
        raise GAMConfigError(f"{config_file} must contain an ad_manager mapping.")

    network_code = str(ad_manager_config.get("network_code", "") or "")
    if not network_code or network_code == "INSERT_NETWORK_CODE_HERE":
        raise GAMConfigError(
            f"{config_file} still needs your Google Ad Manager network_code. "
            "You can find it in the Ad Manager URL after admanager.google.com/."
        )

    key_file = str(ad_manager_config.get("path_to_private_key_file", "") or "")
    has_service_account = bool(key_file)
    has_oauth = all(
        ad_manager_config.get(key)
        for key in ("client_id", "client_secret", "refresh_token")
    )

    if key_file == r"C:\path\to\gam-service-account.json":
        raise GAMConfigError(
            f"{config_file} still has the placeholder service-account path. "
            "Replace path_to_private_key_file with a real JSON key path, or remove it "
            "and use client_id/client_secret/refresh_token instead."
        )

    if has_service_account and not Path(key_file).exists():
        raise GAMConfigError(f"The GAM service-account key file does not exist: {key_file}")

    if not has_service_account and not has_oauth:
        raise GAMConfigError(
            f"{config_file} needs either path_to_private_key_file or "
            "client_id/client_secret/refresh_token."
        )


def googleads_yaml_from_env() -> str:
    network_code = os.getenv("GAM_NETWORK_CODE", "")
    client_id = os.getenv("GAM_CLIENT_ID", "")
    client_secret = os.getenv("GAM_CLIENT_SECRET", "")
    refresh_token = os.getenv("GAM_REFRESH_TOKEN", "")
    application_name = os.getenv("GAM_APPLICATION_NAME", "Advertiser Dashboard Automation")

    if not all([network_code, client_id, client_secret, refresh_token]):
        return ""

    return "\n".join(
        [
            "ad_manager:",
            f"  application_name: {application_name}",
            f"  network_code: {network_code}",
            f"  client_id: {client_id}",
            f"  client_secret: {client_secret}",
            f"  refresh_token: {refresh_token}",
        ]
    )


def _read_simple_ad_manager_yaml(config_file: Path) -> dict[str, str]:
    config: dict[str, str] = {}
    in_ad_manager = False

    for raw_line in config_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not raw_line.startswith((" ", "\t")):
            in_ad_manager = stripped == "ad_manager:"
            continue
        if not in_ad_manager or ":" not in stripped:
            continue

        key, value = stripped.split(":", 1)
        value = value.strip().strip("'\"")
        if value and not value.startswith("#"):
            config[key.strip()] = value

    return config
