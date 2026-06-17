from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT_DIR / "config"


def load_environment() -> None:
    try:
        from dotenv import load_dotenv
    except ModuleNotFoundError:
        return

    load_dotenv(ROOT_DIR / ".env")


def load_advertisers(path: Path | None = None) -> pd.DataFrame:
    advertiser_path = path or CONFIG_DIR / "advertisers.csv"
    if not advertiser_path.exists():
        return pd.DataFrame()

    frame = pd.read_csv(advertiser_path).fillna("")
    required = {"advertiser_id", "advertiser_name"}
    missing = required.difference(frame.columns)
    if missing:
        missing_list = ", ".join(sorted(missing))
        raise ValueError(f"Missing required advertiser columns: {missing_list}")
    return frame


def load_report_sources(path: Path | None = None) -> dict:
    source_path = path or CONFIG_DIR / "report_sources.yml"
    if not source_path.exists():
        return {"categories": {}}

    import yaml

    with source_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {"categories": {}}
