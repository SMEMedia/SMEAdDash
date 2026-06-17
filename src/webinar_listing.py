from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

import pandas as pd

from src.config import load_environment


DEFAULT_WEBINAR_LISTING_URL = "https://www.advancedmanufacturing.org/resources/webinars/"
DEFAULT_USER_AGENT = "sme-advertiser-dashboard/1.0"


class WebinarListingError(RuntimeError):
    """Raised when the public webinar listing cannot be parsed."""


@dataclass(frozen=True)
class WebinarListingConfig:
    url: str = DEFAULT_WEBINAR_LISTING_URL
    user_agent: str = DEFAULT_USER_AGENT


def _empty_listing_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=["listing_title", "listing_sponsor", "listing_url", "listing_text"])


class AdvancedManufacturingWebinarListing:
    def __init__(self, config: WebinarListingConfig | None = None) -> None:
        load_environment()
        self.config = config or WebinarListingConfig(
            url=os.getenv("ADV_MFG_WEBINARS_URL", DEFAULT_WEBINAR_LISTING_URL),
            user_agent=os.getenv("WEBINAR_NET_USER_AGENT", DEFAULT_USER_AGENT),
        )
        try:
            import requests
            from bs4 import BeautifulSoup
        except ModuleNotFoundError as exc:
            raise WebinarListingError(
                "Install beautifulsoup4 and requests before scraping the webinar listing."
            ) from exc

        self.requests = requests
        self.BeautifulSoup = BeautifulSoup

    def webinars(self) -> pd.DataFrame:
        response = self.requests.get(
            self.config.url,
            headers={"User-Agent": self.config.user_agent},
            timeout=30,
        )
        response.raise_for_status()
        soup = self.BeautifulSoup(response.text, "html.parser")
        rows = self._parse_sponsored_webinars(soup)
        if not rows:
            return _empty_listing_frame()
        return pd.DataFrame(rows).drop_duplicates(subset=["listing_title", "listing_sponsor"])

    def _parse_sponsored_webinars(self, soup: Any) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        rows.extend(_parse_sponsored_text(soup.get_text(" ", strip=True), self.config.url))
        sponsor_nodes = soup.find_all(string=re.compile(r"Sponsored\s+by", re.I))
        for node in sponsor_nodes:
            container = _best_container(node)
            if container is None:
                continue
            text = _clean_text(container.get_text("\n", strip=True))
            sponsor = _extract_sponsor(text)
            title = _extract_title(text)
            if not sponsor or not title:
                continue
            link = container.find("a", href=True)
            rows.append(
                {
                    "listing_title": title,
                    "listing_sponsor": sponsor,
                    "listing_url": urljoin(self.config.url, link["href"]) if link else "",
                    "listing_text": text,
                }
            )
        return _dedupe_rows(rows)


def sponsor_matches(value: str, advertiser_name: str) -> bool:
    advertiser = normalize_name(advertiser_name)
    sponsor = normalize_name(value)
    return bool(advertiser and sponsor and (advertiser in sponsor or sponsor in advertiser))


def normalize_title(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()


def normalize_name(value: str) -> str:
    cleaned = re.sub(r"\b(inc|llc|ltd|corp|corporation|company|co)\b\.?", "", str(value).lower())
    return re.sub(r"[^a-z0-9]+", " ", cleaned).strip()


def _best_container(node: Any):
    current = getattr(node, "parent", None)
    best = current
    for _ in range(6):
        if current is None:
            break
        text = _clean_text(current.get_text("\n", strip=True))
        if "Sponsored by" in text and len(text) > 40:
            best = current
        current = getattr(current, "parent", None)
    return best


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value)).strip()


def _extract_sponsor(text: str) -> str:
    match = re.search(r"Sponsored\s+by\s+(.+?)(?:\s*\||$)", text, flags=re.I)
    return match.group(1).strip() if match else ""


def _extract_title(text: str) -> str:
    match = re.search(r"(.+?)\s+Sponsored\s+by\s+", text, flags=re.I)
    if not match:
        return ""
    title = match.group(1).strip()
    title = re.sub(r"^.*?(?=[A-Z0-9][A-Z0-9'’:&,\- ]{8,}$)", "", title).strip()
    return title


def _parse_sponsored_text(text: str, base_url: str) -> list[dict[str, str]]:
    cleaned = _clean_text(text)
    sponsor_pattern = re.compile(r"\bSponsored\s+by\s+(.+?)(?:\s*\||\s+Available|\s+Now Available|$)", re.I)
    status_pattern = re.compile(r"(?:Available\s+On[- ]Demand|Now\s+Available\s+On[- ]Demand|Available\s+On\s+Demand)", re.I)
    rows: list[dict[str, str]] = []

    for match in sponsor_pattern.finditer(cleaned):
        sponsor = match.group(1).strip()
        before = cleaned[: match.start()].strip()
        prior_statuses = list(status_pattern.finditer(before))
        title_start = prior_statuses[-1].end() if prior_statuses else 0
        title = before[title_start:].strip()
        title = _strip_listing_noise(title)
        if title and sponsor:
            rows.append(
                {
                    "listing_title": title,
                    "listing_sponsor": sponsor,
                    "listing_url": base_url,
                    "listing_text": f"{title} Sponsored by {sponsor}",
                }
            )
    return rows


def _strip_listing_noise(value: str) -> str:
    cleaned = re.sub(r"https?://\S+", "", value).strip()
    cleaned = re.sub(r"\bPresented\s+by\s+.+$", "", cleaned, flags=re.I).strip()
    cleaned = re.sub(r"^.*?\bResources\s+Webinars\s+", "", cleaned, flags=re.I).strip()
    cleaned = re.sub(r"^.*?\bWebinars\s+", "", cleaned, flags=re.I).strip()
    return cleaned.strip(" |-")


def _dedupe_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    deduped: list[dict[str, str]] = []
    for row in rows:
        key = (normalize_title(row.get("listing_title", "")), normalize_name(row.get("listing_sponsor", "")))
        if not key[0] or not key[1] or key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped
