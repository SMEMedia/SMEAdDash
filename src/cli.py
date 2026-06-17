from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from src.config import load_advertisers
from src.gam_client import GAMClient, GAMConfigError
from src.ga4_client import GA4ConfigError
from src.reporting import ReportRequest, build_advertiser_report, export_report_frames


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

    advertisers.to_csv(output_path, index=False)
    print(f"Wrote {len(advertisers)} advertisers to {output_path}")


def main() -> None:
    args = parse_args()
    try:
        if args.command == "export":
            export_all(args)
        elif args.command == "sync-gam-advertisers":
            sync_gam_advertisers(args)
    except (GA4ConfigError, GAMConfigError) as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
