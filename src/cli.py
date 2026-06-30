from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from src.config import load_advertisers, normalize_identifier
from src.gam_client import GAMClient, GAMConfigError
from src.ga4_client import GA4ConfigError
from src.hubspot_client import DEFAULT_NEWSLETTER_EXPORT, normalize_placement_frame
from src.reporting import ReportRequest, build_advertiser_report, export_report_frames
from src.webinar_listing import AdvancedManufacturingWebinarListing, WebinarListingError, normalize_name


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Advertiser dashboard automation tools.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    export = subparsers.add_parser("export", help="Export advertiser report tables for Power BI.")
    export.add_argument("--format", choices=["csv", "xlsx"], default="csv")
    export.add_argument("--output-dir", default="data/exports")
    export.add_argument("--start-date", default=(date.today() - timedelta(days=30)).isoformat())
    export.add_argument("--end-date", default=(date.today() - timedelta(days=1)).isoformat())
    export.add_argument("--allow-empty-ga4", action="store_true", help="Write empty GA4 tables when credentials are missing.")
    export.add_argument("--allow-empty-gam", action="store_true", help="Write empty GAM tables when credentials are missing.")

    sync_gam = subparsers.add_parser("sync-gam-advertisers", help="Pull advertiser names from Google Ad Manager.")
    sync_gam.add_argument("--output", default="config/advertisers.csv")
    sync_gam.add_argument("--include-house-advertisers", action="store_true")

    sync_webinars = subparsers.add_parser(
        "sync-webinar-sponsors",
        help="Add advertiser names from Advanced Manufacturing webinar sponsors to the advertiser CSV.",
    )
    sync_webinars.add_argument("--input", default="config/advertisers.csv")
    sync_webinars.add_argument("--output", default="config/advertisers.csv")
    sync_webinars.add_argument(
        "--include-enewsletter",
        action="store_true",
        help="Also add advertiser names from the eNewsletter placement export.",
    )
    sync_webinars.add_argument("--enewsletter-file", default=str(DEFAULT_NEWSLETTER_EXPORT))

    sync_enewsletter = subparsers.add_parser(
        "sync-enewsletter-advertisers",
        help="Add advertiser names from the eNewsletter placement export to the advertiser CSV.",
    )
    sync_enewsletter.add_argument("--input", default="config/advertisers.csv")
    sync_enewsletter.add_argument("--output", default="config/advertisers.csv")
    sync_enewsletter.add_argument("--placements", default=str(DEFAULT_NEWSLETTER_EXPORT))

    enrich = subparsers.add_parser(
        "enrich-advertisers",
        help="Enrich advertiser CSV with GAM, webinar, and eNewsletter advertisers and source flags.",
    )
    enrich.add_argument("--input", default="config/advertisers.csv")
    enrich.add_argument("--output", default="config/advertisers.csv")
    enrich.add_argument("--placements", default=str(DEFAULT_NEWSLETTER_EXPORT))
    enrich.add_argument("--include-house-advertisers", action="store_true")
    return parser.parse_args()


def export_all(args: argparse.Namespace) -> None:
    advertisers = load_advertisers()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    start_date = date.fromisoformat(args.start_date)
    end_date = date.fromisoformat(args.end_date)

    collected: dict[str, list[pd.DataFrame]] = {}
    for advertiser in advertisers.to_dict(orient="records"):
        request = ReportRequest(advertiser=advertiser, start_date=start_date, end_date=end_date)
        report = build_advertiser_report(
            request,
            allow_empty_ga4=args.allow_empty_ga4,
            allow_empty_gam=args.allow_empty_gam,
        )

        for table_name, frame in export_report_frames(report).items():
            collected.setdefault(table_name, []).append(frame)

    combined = {
        table_name: pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        for table_name, frames in collected.items()
    }

    if args.format == "xlsx":
        workbook = output_dir / f"advertiser_dashboard_export_{start_date:%Y%m%d}_{end_date:%Y%m%d}.xlsx"
        with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
            for table_name, frame in combined.items():
                frame.to_excel(writer, sheet_name=table_name[:31], index=False)
        print(f"Wrote {workbook}")
        return

    for table_name, frame in combined.items():
        output_path = output_dir / f"{table_name}.csv"
        frame.to_csv(output_path, index=False)
        print(f"Wrote {output_path}")


def sync_gam_advertisers(args: argparse.Namespace) -> None:
    advertisers = GAMClient().advertisers(
        include_house_advertisers=args.include_house_advertisers
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    for column in ["utm_source", "utm_medium", "utm_campaign", "landing_page_contains", "notes"]:
        if column not in advertisers.columns:
            advertisers[column] = ""
    advertisers["gam"] = "true"
    advertisers["webinar"] = "false"
    advertisers["email"] = "false"
    advertisers = _finalize_advertiser_sheet(advertisers)

    advertisers.to_csv(output_path, index=False)
    print(f"Wrote {len(advertisers)} advertisers to {output_path}")


def sync_webinar_sponsors(args: argparse.Namespace) -> None:
    advertisers = _load_advertiser_sheet(Path(args.input))
    sponsors = webinar_advertiser_names()
    advertisers, webinar_added = add_named_source_rows(
        advertisers=advertisers,
        advertiser_names=sponsors,
        source_column="webinar",
        source_system="Webinar scrape",
        advertiser_id_prefix="webinar",
        notes="Added from Advanced Manufacturing webinar sponsor listing.",
    )

    enewsletter_added = 0
    if args.include_enewsletter:
        advertisers, enewsletter_added = add_enewsletter_rows(
            advertisers,
            Path(args.enewsletter_file),
        )

    advertisers = _finalize_advertiser_sheet(advertisers)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    advertisers.to_csv(output_path, index=False)
    print(
        f"Added {webinar_added} webinar sponsors and {enewsletter_added} eNewsletter advertisers. "
        f"Wrote {len(advertisers)} advertisers to {output_path}"
    )


def sync_enewsletter_advertisers(args: argparse.Namespace) -> None:
    advertisers = _load_advertiser_sheet(Path(args.input))
    advertisers, added = add_enewsletter_rows(advertisers, Path(args.placements))
    advertisers = _finalize_advertiser_sheet(advertisers)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    advertisers.to_csv(output_path, index=False)
    print(f"Added {added} eNewsletter advertisers. Wrote {len(advertisers)} advertisers to {output_path}")


def enrich_advertisers(args: argparse.Namespace) -> None:
    advertisers = _load_advertiser_sheet(Path(args.input))

    gam = GAMClient().advertisers(include_house_advertisers=args.include_house_advertisers)
    advertisers, gam_added = add_gam_rows(advertisers, gam)

    advertisers, webinar_added = add_named_source_rows(
        advertisers=advertisers,
        advertiser_names=webinar_advertiser_names(),
        source_column="webinar",
        source_system="Webinar scrape",
        advertiser_id_prefix="webinar",
        notes="Added from Advanced Manufacturing webinar sponsor listing.",
    )

    advertisers, email_added = add_enewsletter_rows(advertisers, Path(args.placements))
    advertisers = _finalize_advertiser_sheet(advertisers)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    advertisers.to_csv(output_path, index=False)
    print(
        f"Added {gam_added} GAM, {webinar_added} webinar, and {email_added} eNewsletter advertisers. "
        f"Wrote {len(advertisers)} advertisers to {output_path}"
    )


def webinar_advertiser_names() -> list[str]:
    listing = AdvancedManufacturingWebinarListing().webinars()
    return sorted(
        {
            str(value).strip()
            for value in listing["listing_sponsor"].dropna().tolist()
            if str(value).strip()
        },
        key=str.lower,
    )


def add_gam_rows(advertisers: pd.DataFrame, gam_advertisers: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    advertisers = _ensure_advertiser_columns(advertisers)
    existing = _existing_advertiser_names(advertisers)
    new_rows = []

    for _, row in gam_advertisers.fillna("").iterrows():
        advertiser_name = str(row.get("advertiser_name", "") or "").strip()
        normalized = normalize_name(advertiser_name)
        if not normalized:
            continue
        if normalized in existing:
            mask = advertisers["advertiser_name"].map(normalize_name) == normalized
            advertisers.loc[mask, "gam"] = "true"
            for column in ["gam_advertiser_id", "gam_advertiser_name", "gam_company_type", "gam_credit_status"]:
                if column in row:
                    advertisers.loc[mask & (advertisers[column].astype(str).str.strip() == ""), column] = str(row.get(column, "") or "")
            continue

        new_rows.append(
            {
                "advertiser_id": str(row.get("advertiser_id", "") or row.get("gam_advertiser_id", "") or ""),
                "advertiser_name": advertiser_name,
                "gam_advertiser_id": str(row.get("gam_advertiser_id", "") or ""),
                "gam_advertiser_name": str(row.get("gam_advertiser_name", "") or ""),
                "gam_company_type": str(row.get("gam_company_type", "") or ""),
                "gam_credit_status": str(row.get("gam_credit_status", "") or ""),
                "source_system": "GAM",
                "utm_source": "",
                "utm_medium": "",
                "utm_campaign": "",
                "landing_page_contains": "",
                "notes": "Added from Google Ad Manager advertiser list.",
                "gam": "true",
                "webinar": "false",
                "email": "false",
            }
        )
        existing.add(normalized)

    if new_rows:
        advertisers = pd.concat([advertisers, pd.DataFrame(new_rows)], ignore_index=True)
    return advertisers, len(new_rows)


def add_enewsletter_rows(advertisers: pd.DataFrame, placements_path: Path) -> tuple[pd.DataFrame, int]:
    if not placements_path.exists():
        raise FileNotFoundError(f"eNewsletter placement file was not found: {placements_path}")

    if placements_path.suffix.lower() in {".xlsx", ".xls"}:
        raw = pd.read_excel(placements_path, dtype=str).fillna("")
    else:
        raw = pd.read_csv(placements_path, dtype=str).fillna("")
    placements = normalize_placement_frame(raw)
    if placements.empty or "advertiser_name" not in placements.columns:
        return advertisers, 0

    advertiser_names = sorted(
        {
            str(value).strip()
            for value in placements["advertiser_name"].dropna().tolist()
            if str(value).strip()
        },
        key=str.lower,
    )
    return add_named_source_rows(
        advertisers=advertisers,
        advertiser_names=advertiser_names,
        source_column="email",
        source_system="HubSpot eNewsletter CSV",
        advertiser_id_prefix="enewsletter",
        notes="Added from eNewsletter placement export.",
    )


def add_named_source_rows(
    advertisers: pd.DataFrame,
    advertiser_names: list[str],
    source_column: str,
    source_system: str,
    advertiser_id_prefix: str,
    notes: str,
) -> tuple[pd.DataFrame, int]:
    advertisers = _ensure_advertiser_columns(advertisers)
    existing = _existing_advertiser_names(advertisers)
    new_rows = []
    for advertiser_name in advertiser_names:
        normalized = normalize_name(advertiser_name)
        if not normalized or normalized in existing:
            if normalized:
                mask = advertisers["advertiser_name"].map(normalize_name) == normalized
                advertisers.loc[mask, source_column] = "true"
            continue
        advertiser_id = f"{advertiser_id_prefix}_{normalized.replace(' ', '_')}"
        new_rows.append(
            {
                "advertiser_id": advertiser_id,
                "advertiser_name": advertiser_name,
                "gam_advertiser_id": "",
                "gam_advertiser_name": "",
                "gam_company_type": "",
                "gam_credit_status": "",
                "source_system": source_system,
                "utm_source": "",
                "utm_medium": "",
                "utm_campaign": "",
                "landing_page_contains": "",
                "notes": notes,
                "gam": "false",
                "webinar": "false",
                "email": "false",
                source_column: "true",
            }
        )
        existing.add(normalized)

    if new_rows:
        advertisers = pd.concat([advertisers, pd.DataFrame(new_rows)], ignore_index=True)
    return advertisers, len(new_rows)


def _load_advertiser_sheet(input_path: Path) -> pd.DataFrame:
    if input_path.exists():
        advertisers = pd.read_csv(input_path, dtype=str).fillna("")
    else:
        advertisers = pd.DataFrame(columns=["advertiser_id", "advertiser_name"])
    return _ensure_advertiser_columns(advertisers)


def _ensure_advertiser_columns(advertisers: pd.DataFrame) -> pd.DataFrame:
    required_columns = _advertiser_columns()
    for column in required_columns:
        if column not in advertisers.columns:
            advertisers[column] = ""
    for column in ["gam", "webinar", "email"]:
        advertisers[column] = advertisers[column].map(_bool_text)
    if "gam_advertiser_id" in advertisers.columns:
        gam_mask = advertisers["gam_advertiser_id"].astype(str).str.strip() != ""
        advertisers.loc[gam_mask, "gam"] = "true"
    if "source_system" in advertisers.columns:
        source_text = advertisers["source_system"].astype(str).str.lower()
        advertisers.loc[source_text.str.contains("webinar", na=False), "webinar"] = "true"
        advertisers.loc[source_text.str.contains("enewsletter|hubspot", regex=True, na=False), "email"] = "true"
    for column in ["advertiser_id", "gam_advertiser_id"]:
        advertisers[column] = advertisers[column].map(normalize_identifier)
    return advertisers


def _finalize_advertiser_sheet(advertisers: pd.DataFrame) -> pd.DataFrame:
    advertisers = _ensure_advertiser_columns(advertisers)
    advertisers = advertisers[_advertiser_columns()]
    return advertisers.sort_values(
        "advertiser_name",
        key=lambda series: series.str.lower(),
        ignore_index=True,
    )


def _existing_advertiser_names(advertisers: pd.DataFrame) -> set[str]:
    return {
        normalize_name(value)
        for value in advertisers["advertiser_name"].dropna().tolist()
        if str(value).strip()
    }


def _advertiser_columns() -> list[str]:
    return [
        "advertiser_id",
        "advertiser_name",
        "gam_advertiser_id",
        "gam_advertiser_name",
        "gam_company_type",
        "gam_credit_status",
        "gam",
        "webinar",
        "email",
        "source_system",
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "landing_page_contains",
        "notes",
    ]


def _bool_text(value: object) -> str:
    return "true" if str(value or "").strip().lower() in {"true", "1", "yes", "y"} else "false"


def main() -> None:
    args = parse_args()
    try:
        if args.command == "export":
            export_all(args)
        elif args.command == "sync-gam-advertisers":
            sync_gam_advertisers(args)
        elif args.command == "sync-webinar-sponsors":
            sync_webinar_sponsors(args)
        elif args.command == "sync-enewsletter-advertisers":
            sync_enewsletter_advertisers(args)
        elif args.command == "enrich-advertisers":
            enrich_advertisers(args)
    except (GA4ConfigError, GAMConfigError, WebinarListingError) as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
