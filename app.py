from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
import altair as alt

from src.config import load_advertisers, load_report_sources
from src.gam_client import GAMClient, GAMConfigError
from src.hubspot_client import HubSpotConfigError, normalize_placement_frame
from src.pdf_report import build_pdf_report
from src.reporting import ReportRequest, build_advertiser_report
from src.webinar_client import WebinarNetClient, WebinarNetConfigError, _empty_webinar_frame
from src.webinar_listing import (
    AdvancedManufacturingWebinarListing,
    WebinarListingError,
    normalize_title,
    sponsor_matches,
)


BASE_DIR = Path(__file__).resolve().parent
LOGO_PATH = BASE_DIR / "assets" / "sme_logo.png"
SME_COLORS = {
    "navy": "#153254",
    "blue": "#5F8BB3",
    "lime": "#D6D65E",
    "gray": "#969696",
    "teal": "#4EA08A",
    "charcoal": "#414141",
    "gold": "#FFC72C",
    "deep_teal": "#00788B",
    "red": "#CF323B",
    "pale_blue": "#BCD9E9",
}
WEBINAR_API_CACHE_VERSION = 3
WEBINAR_LISTING_CACHE_VERSION = 2

REPORT_ELEMENTS = {
    "kpi_impressions": {"label": "KPI: Ad impressions", "section": "Website Ads", "type": "kpi"},
    "kpi_clicks": {"label": "KPI: Ad clicks", "section": "Website Ads", "type": "kpi"},
    "kpi_ctr": {"label": "KPI: CTR", "section": "Website Ads", "type": "kpi"},
    "kpi_campaigns": {"label": "KPI: Campaigns", "section": "Website Ads", "type": "kpi"},
    "kpi_creatives": {"label": "KPI: Creatives", "section": "Website Ads", "type": "kpi"},
    "kpi_webinar_registrations": {"label": "KPI: Webinar registrations", "section": "Webinars", "type": "kpi"},
    "kpi_email_delivered": {"label": "KPI: Emails delivered", "section": "HubSpot Email", "type": "kpi"},
    "kpi_email_opened": {"label": "KPI: Emails opened", "section": "HubSpot Email", "type": "kpi"},
    "kpi_email_open_rate": {"label": "KPI: Email open rate", "section": "HubSpot Email", "type": "kpi"},
    "kpi_email_clicks": {"label": "KPI: Email clicks", "section": "HubSpot Email", "type": "kpi"},
    "kpi_email_click_rate": {"label": "KPI: Email click rate", "section": "HubSpot Email", "type": "kpi"},
    "table_webinars": {"label": "Table: Webinars", "section": "Webinars", "type": "table"},
    "chart_daily_delivery": {"label": "Chart: Daily delivery", "section": "Website Ads", "type": "visualization"},
    "chart_daily_ctr": {"label": "Chart: Daily CTR", "section": "Website Ads", "type": "visualization"},
    "chart_campaign_performance": {"label": "Chart: Campaign performance", "section": "Website Ads", "type": "visualization"},
    "chart_campaign_ctr": {"label": "Chart: Campaign CTR", "section": "Website Ads", "type": "visualization"},
    "chart_creative_performance": {"label": "Chart: Creative performance", "section": "Website Ads", "type": "visualization"},
    "chart_creative_ctr": {"label": "Chart: Creative CTR", "section": "Website Ads", "type": "visualization"},
    "chart_email_ad_type": {"label": "Chart: Email metrics by ad type", "section": "HubSpot Email", "type": "visualization"},
    "chart_email_rates_ad_type": {"label": "Chart: Email rates by ad type", "section": "HubSpot Email", "type": "visualization"},
    "chart_email_time": {"label": "Chart: Email metrics over time", "section": "HubSpot Email", "type": "visualization"},
    "chart_email_rates_time": {"label": "Chart: Email rates over time", "section": "HubSpot Email", "type": "visualization"},
    "table_campaign_detail": {"label": "Table: Campaign detail", "section": "Website Ads", "type": "table"},
    "table_creative_detail": {"label": "Table: Creative detail", "section": "Website Ads", "type": "table"},
    "image_creatives": {"label": "Image creative previews", "section": "Website Ads", "type": "visualization"},
    "manual_enewsletter": {"label": "HubSpot: eNewsletter ads", "section": "HubSpot Email", "type": "table"},
    "manual_retargeting": {"label": "Manual: Retargeting", "section": "Manual data", "type": "table"},
    "manual_custom_email": {"label": "HubSpot: Custom email", "section": "HubSpot Email", "type": "table"},
    "manual_lead_gen": {"label": "Manual: Lead gen", "section": "Manual data", "type": "table"},
}


st.set_page_config(
    page_title="Advertiser Dashboard Automation",
    page_icon="bar_chart",
    layout="wide",
)


st.markdown(
    """
    <style>
    :root {
        --sme-navy: #153254;
        --sme-blue: #5F8BB3;
        --sme-lime: #D6D65E;
        --sme-gray: #969696;
        --sme-teal: #4EA08A;
        --sme-charcoal: #414141;
        --sme-gold: #FFC72C;
        --sme-deep-teal: #00788B;
        --sme-red: #CF323B;
        --sme-pale-blue: #BCD9E9;
    }
    .stApp {
        background: linear-gradient(180deg, #ffffff 0%, #f6f9fb 100%);
        color: var(--sme-charcoal);
    }
    .block-container {
        padding-top: 1.2rem;
        padding-bottom: 2rem;
    }
    [data-testid="stSidebar"] {
        background: #f3f7f9;
        border-right: 1px solid #d8e4ea;
    }
    [data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #d8e4ea;
        border-top: 5px solid var(--sme-lime);
        border-radius: 8px;
        padding: 14px 16px;
        box-shadow: 0 1px 4px rgba(21, 50, 84, 0.06);
    }
    [data-testid="stMetricLabel"] {
        color: var(--sme-charcoal);
    }
    [data-testid="stMetricValue"] {
        color: var(--sme-navy);
    }
    h1, h2, h3 {
        letter-spacing: 0;
        color: var(--sme-navy);
    }
    .report-kicker {
        color: var(--sme-charcoal);
        font-size: 0.95rem;
        margin-top: -0.4rem;
    }
    .section-label {
        color: var(--sme-navy);
        font-weight: 700;
        font-size: 1.05rem;
        margin: 0.7rem 0 0.35rem;
        border-left: 5px solid var(--sme-lime);
        padding-left: 0.5rem;
    }
    .stButton > button, .stDownloadButton > button {
        background: var(--sme-navy);
        border: 1px solid var(--sme-navy);
        color: #ffffff;
        border-radius: 6px;
        font-weight: 700;
    }
    .stButton > button:hover, .stDownloadButton > button:hover {
        background: var(--sme-deep-teal);
        border-color: var(--sme-deep-teal);
        color: #ffffff;
    }
    div[data-testid="stCaptionContainer"] {
        color: var(--sme-charcoal);
    }
    [data-testid="stDataFrame"] {
        border: 1px solid #d8e4ea;
        border-radius: 8px;
    }
    [data-testid="stDataFrame"] [role="columnheader"],
    [data-testid="stDataFrame"] [data-testid="stTable"] th {
        background: var(--sme-blue);
        color: #ffffff;
    }
    [data-testid="stCheckbox"] label {
        white-space: nowrap;
    }
    .preview-card {
        border: 1px solid #d8e4ea;
        border-left: 5px solid var(--sme-gray);
        border-radius: 8px;
        background: #ffffff;
        padding: 0.65rem 0.75rem;
        min-height: 82px;
        box-shadow: 0 1px 4px rgba(21, 50, 84, 0.05);
    }
    .preview-card.selected {
        border-left-color: var(--sme-lime);
        background: #fbfde8;
    }
    .preview-title {
        color: var(--sme-navy);
        font-weight: 700;
        margin-bottom: 0.2rem;
    }
    .preview-meta {
        color: var(--sme-charcoal);
        font-size: 0.82rem;
    }
    .removed-element {
        background: #f1f1f1;
        border: 1px dashed #969696;
        border-radius: 8px;
        color: #666666;
        padding: 0.75rem;
        margin: 0.25rem 0 0.75rem;
    }
    .removed-heading {
        color: #666666;
        font-weight: 700;
        margin-bottom: 0.2rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data
def cached_advertisers() -> pd.DataFrame:
    return load_advertisers()


@st.cache_data
def cached_gam_advertisers(include_house_advertisers: bool) -> pd.DataFrame:
    return GAMClient().advertisers(include_house_advertisers=include_house_advertisers)


@st.cache_data(show_spinner=False)
def cached_campaigns(advertiser_id: str, start_date: date, end_date: date) -> pd.DataFrame:
    return GAMClient().campaigns_for_advertiser(
        advertiser_id=advertiser_id,
        start_date=start_date,
        end_date=end_date,
    )


@st.cache_data(show_spinner=False)
def cached_creative_assets(creative_ids: tuple[str, ...]) -> pd.DataFrame:
    return GAMClient().creative_assets(list(creative_ids))


@st.cache_data(show_spinner=False)
def cached_webinars(
    advertiser_name: str,
    match_text: str,
    start_date: date,
    end_date: date,
    cache_version: int,
) -> pd.DataFrame:
    return WebinarNetClient().webinars(
        advertiser_name=advertiser_name,
        match_text=match_text,
        start_date=start_date,
        end_date=end_date,
    )


@st.cache_data(show_spinner=False)
def cached_webinar_listing(cache_version: int) -> pd.DataFrame:
    return AdvancedManufacturingWebinarListing().webinars()


@st.cache_data
def cached_sources() -> dict:
    return load_report_sources()


def read_uploaded_placement_file(uploaded_file) -> pd.DataFrame:
    if uploaded_file is None:
        return pd.DataFrame()
    name = str(uploaded_file.name).lower()
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(uploaded_file, dtype=str).fillna("")
    return pd.read_csv(uploaded_file, dtype=str).fillna("")


def render_metric_row(metrics: dict[str, float | int | str | None]) -> None:
    cols = st.columns(len(metrics))
    for col, (label, value) in zip(cols, metrics.items()):
        col.metric(label, value if value not in (None, "") else "-")


def sync_element_from_checkbox(element_id: str) -> None:
    selected = set(selected_report_elements())
    if st.session_state.get(f"include_{element_id}", False):
        selected.add(element_id)
    else:
        selected.discard(element_id)
    st.session_state["selected_report_elements"] = [
        element for element in all_report_element_ids() if element in selected
    ]
    available = set(st.session_state.get("available_pdf_elements", all_report_element_ids()))
    for section_name in report_section_names():
        section_ids = [element for element in report_section_element_ids(section_name) if element in available]
        st.session_state[f"include_section_{safe_filename(section_name)}"] = bool(section_ids) and all(
            element in selected for element in section_ids
        )


def format_integer(value: float | int) -> str:
    return f"{int(value):,}"


def format_percent(value: float | int) -> str:
    return f"{float(value):.2%}"


def safe_filename(value: str) -> str:
    cleaned = "".join(char if char.isalnum() else "_" for char in value.lower())
    return "_".join(part for part in cleaned.split("_") if part)


def normalize_match_text(value: str) -> str:
    return " ".join("".join(char.lower() if char.isalnum() else " " for char in str(value)).split())


def find_gam_advertiser_by_name(advertiser_name: str, include_house_advertisers: bool) -> dict[str, Any]:
    query = normalize_match_text(advertiser_name)
    if not query:
        return {}
    try:
        gam_advertisers = cached_gam_advertisers(include_house_advertisers)
    except GAMConfigError:
        return {}
    if gam_advertisers.empty:
        return {}
    candidates = gam_advertisers.copy()
    candidates["match_name"] = candidates["advertiser_name"].map(normalize_match_text)
    exact = candidates[candidates["match_name"] == query]
    if not exact.empty:
        return exact.iloc[0].to_dict()
    contains = candidates[candidates["match_name"].str.contains(query, regex=False, na=False)]
    if not contains.empty:
        return contains.iloc[0].to_dict()
    reverse_contains = candidates[candidates["match_name"].map(lambda value: query in value or value in query)]
    if not reverse_contains.empty:
        return reverse_contains.iloc[0].to_dict()
    return {}


def all_report_element_ids() -> list[str]:
    return list(REPORT_ELEMENTS.keys())


def report_section_names() -> list[str]:
    return sorted({value["section"] for value in REPORT_ELEMENTS.values()})


def report_section_element_ids(section_name: str) -> list[str]:
    return [key for key, value in REPORT_ELEMENTS.items() if value["section"] == section_name]


def table_report_element_ids() -> list[str]:
    return [key for key, value in REPORT_ELEMENTS.items() if value["type"] == "table"]


def no_visual_report_element_ids() -> list[str]:
    return [key for key, value in REPORT_ELEMENTS.items() if value["type"] != "visualization"]


def set_report_elements(elements: list[str]) -> None:
    st.session_state["selected_report_elements"] = elements
    selected = set(elements)
    available = set(st.session_state.get("available_pdf_elements", all_report_element_ids()))
    for element_id in all_report_element_ids():
        st.session_state[f"include_{element_id}"] = element_id in selected
    for section_name in report_section_names():
        section_ids = [element for element in report_section_element_ids(section_name) if element in available]
        st.session_state[f"include_section_{safe_filename(section_name)}"] = bool(section_ids) and all(
            element_id in selected for element_id in section_ids
        )


def selected_report_elements() -> list[str]:
    if "selected_report_elements" not in st.session_state:
        st.session_state["selected_report_elements"] = all_report_element_ids()
    return st.session_state["selected_report_elements"]


def toggle_report_element(element_id: str) -> None:
    current = set(selected_report_elements())
    if element_id in current:
        current.remove(element_id)
    else:
        current.add(element_id)
    st.session_state["selected_report_elements"] = [
        element for element in all_report_element_ids() if element in current
    ]


def apply_section_selection(section_names: list[str]) -> None:
    selected = [
        key for key, value in REPORT_ELEMENTS.items()
        if value["section"] in section_names
    ]
    set_report_elements(selected)


def sync_section_from_checkbox(section_name: str) -> None:
    current = set(selected_report_elements())
    available = set(st.session_state.get("available_pdf_elements", all_report_element_ids()))
    section_ids = [element for element in report_section_element_ids(section_name) if element in available]
    if st.session_state.get(f"include_section_{safe_filename(section_name)}", False):
        current.update(section_ids)
    else:
        current.difference_update(section_ids)
    set_report_elements([element for element in all_report_element_ids() if element in current])


def element_selected(element_id: str) -> bool:
    return element_id in set(selected_report_elements())


def ensure_report_element_widget_state() -> None:
    selected = set(selected_report_elements())
    available = set(st.session_state.get("available_pdf_elements", all_report_element_ids()))
    for element_id in all_report_element_ids():
        st.session_state.setdefault(f"include_{element_id}", element_id in selected)
    for section_name in report_section_names():
        section_ids = [element for element in report_section_element_ids(section_name) if element in available]
        st.session_state.setdefault(
            f"include_section_{safe_filename(section_name)}",
            bool(section_ids) and all(element_id in selected for element_id in section_ids),
        )


def section_checkbox(section_name: str) -> None:
    ensure_report_element_widget_state()
    st.checkbox(
        section_name,
        key=f"include_section_{safe_filename(section_name)}",
        on_change=sync_section_from_checkbox,
        args=(section_name,),
    )


def available_report_elements(
    gam_frame: pd.DataFrame,
    webinar_frame: pd.DataFrame,
    email_frame: pd.DataFrame,
    manual_data: dict[str, dict[str, Any]],
) -> list[str]:
    available: set[str] = set()
    if not gam_frame.empty:
        available.update(report_section_element_ids("Website Ads"))
    if not webinar_frame.empty:
        available.update(report_section_element_ids("Webinars"))
    if not email_frame.empty:
        available.update(report_section_element_ids("HubSpot Email"))
    for element_id in ["manual_retargeting", "manual_lead_gen"]:
        if element_id in manual_data and has_manual_values(manual_data[element_id]):
            available.add(element_id)
    return [element for element in all_report_element_ids() if element in available]


def multiple_nonempty_values(frame: pd.DataFrame, column: str) -> bool:
    if frame.empty or column not in frame.columns:
        return False
    values = {str(value).strip() for value in frame[column].dropna().tolist() if str(value).strip()}
    return len(values) > 1


def multiple_dates(frame: pd.DataFrame, column: str = "placement_date") -> bool:
    if frame.empty or column not in frame.columns:
        return False
    dates = pd.to_datetime(frame[column], errors="coerce").dropna().dt.date.unique()
    return len(dates) > 1


def element_checkbox(element_id: str) -> None:
    ensure_report_element_widget_state()
    st.checkbox(
        "PDF",
        key=f"include_{element_id}",
        on_change=sync_element_from_checkbox,
        args=(element_id,),
    )


def element_header(title: str, element_id: str) -> None:
    label_col, checkbox_col = st.columns([5, 1.6], vertical_alignment="center")
    with label_col:
        style = "section-label" if element_selected(element_id) else "section-label removed-heading"
        st.markdown(f'<div class="{style}">{title}</div>', unsafe_allow_html=True)
    with checkbox_col:
        element_checkbox(element_id)


def selectable_metric(element_id: str, label: str, value: str) -> None:
    element_checkbox(element_id)
    if element_selected(element_id):
        st.metric(label, value if value not in (None, "") else "-")
    else:
        st.markdown(
            f"""
            <div class="removed-element">
                <div class="removed-heading">{label}</div>
                <div>{value if value not in (None, "") else "-"}</div>
                <div class="preview-meta">Removed from PDF</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def removed_notice(element_id: str) -> None:
    if not element_selected(element_id):
        st.markdown(
            '<div class="removed-element">Removed from PDF. Use Add back to include it.</div>',
            unsafe_allow_html=True,
        )


def render_if_selected(element_id: str, render_fn) -> None:
    if element_selected(element_id):
        render_fn()
    else:
        removed_notice(element_id)


def manual_number(label: str, key: str, min_value: int = 0) -> int:
    return int(st.number_input(label, min_value=min_value, step=1, key=key))


def collect_manual_data() -> dict[str, dict[str, Any]]:
    with st.sidebar.expander("Manual Data Entry", expanded=False):
        st.caption("Use these fields for report data that is not automated yet.")

        st.markdown("**Retargeting**")
        retargeting_impressions = manual_number("Ad impressions", "manual_retargeting_impressions")
        retargeting_clicks = manual_number("Ad clicks", "manual_retargeting_clicks")
        retargeting_creative = st.text_area("Ad creative notes or URL", key="manual_retargeting_creative")
        retargeting_performance = st.text_area(
            "Performance by ad creative",
            key="manual_retargeting_performance",
        )

        st.markdown("**Custom Email**")
        email_delivered = manual_number("Total delivered", "manual_email_delivered")
        email_opened = manual_number("Total opened", "manual_email_opened")
        email_click_rate = st.text_input("Click rate", key="manual_email_click_rate")
        email_ctr = st.text_input("CTR", key="manual_email_ctr")
        email_screenshot = st.text_input("Email screenshot URL", key="manual_email_screenshot")

        st.markdown("**Lead Gen**")
        anteriad_campaign = st.text_input("Anteriad campaign or asset", key="manual_anteriad_campaign")
        anteriad_leads = manual_number("Anteriad leads received", "manual_anteriad_leads")
        anteriad_lead_list = st.text_area("Anteriad lead list or notes", key="manual_anteriad_lead_list")

    retargeting_ctr = retargeting_clicks / retargeting_impressions if retargeting_impressions else 0
    email_open_rate = email_opened / email_delivered if email_delivered else 0

    return {
        "manual_retargeting": {
            "title": "Retargeting",
            "rows": [
                ("Ad impressions", format_integer(retargeting_impressions)),
                ("Ad clicks", format_integer(retargeting_clicks)),
                ("Ad CTR", format_percent(retargeting_ctr)),
                ("Ad creative", retargeting_creative),
                ("Performance by ad creative", retargeting_performance),
            ],
        },
        "manual_custom_email": {
            "title": "Custom Email",
            "rows": [
                ("Total delivered", format_integer(email_delivered)),
                ("Total opened", format_integer(email_opened)),
                ("Open rate", format_percent(email_open_rate)),
                ("Click rate", email_click_rate),
                ("CTR", email_ctr),
                ("Screenshot of email", email_screenshot),
            ],
        },
        "manual_lead_gen": {
            "title": "Lead Gen",
            "rows": [
                ("Anteriad campaign or asset", anteriad_campaign),
                ("Leads received", format_integer(anteriad_leads)),
                ("Lead list or notes", anteriad_lead_list),
            ],
        },
    }


def has_manual_values(section: dict[str, Any]) -> bool:
    rows = section.get("rows", [])
    return any(str(value).strip() and str(value).strip() not in {"0", "0.00%"} for _, value in rows)


def render_manual_section(element_id: str, manual_data: dict[str, dict[str, Any]]) -> None:
    section = manual_data[element_id]
    element_header(section["title"], element_id)

    def render_table() -> None:
        rows = [
            {"Metric": metric, "Value": value or "-"}
            for metric, value in section.get("rows", [])
        ]
        if not has_manual_values(section):
            st.info("No manual values entered for this section yet.")
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    render_if_selected(element_id, render_table)


def hubspot_email_detail_table(frame: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "Type",
        "Placement date",
        "Ad type",
        "Placement clicks",
        "Email",
        "Delivered",
        "Opened",
        "Open rate",
        "Clicks",
        "Click rate",
        "Creative",
        "Web-version URL",
        "Metric source",
        "Status",
    ]
    if frame.empty:
        return pd.DataFrame(columns=columns)

    detail = frame.copy()
    for column in ["delivered", "opened", "clicks", "open_rate", "click_rate"]:
        detail[column] = pd.to_numeric(detail[column], errors="coerce").fillna(0)
    detail["Delivered"] = detail["delivered"].map(format_integer)
    detail["Opened"] = detail["opened"].map(format_integer)
    detail["Clicks"] = detail["clicks"].map(format_integer)
    detail["Open rate"] = detail["open_rate"].map(format_percent)
    detail["Click rate"] = detail["click_rate"].map(format_percent)
    detail["Status"] = detail["match_status"].fillna("").astype(str)
    note = detail.get("match_note", pd.Series([""] * len(detail))).fillna("").astype(str)
    detail.loc[note != "", "Status"] = detail.loc[note != "", "Status"] + ": " + note[note != ""]
    return detail.rename(
        columns={
            "report_type": "Type",
            "placement_date": "Placement date",
            "placement_ad_type": "Ad type",
            "placement_clicks": "Placement clicks",
            "email_name": "Email",
            "creative": "Creative",
            "web_version_url": "Web-version URL",
            "metric_source": "Metric source",
        }
    )[columns]


def hubspot_manual_section(title: str, frame: pd.DataFrame) -> dict[str, Any] | None:
    if frame.empty:
        return None
    matched = frame[frame["match_status"].fillna("") == "Matched"].copy()
    if matched.empty:
        return None
    delivered = int(pd.to_numeric(matched["delivered"], errors="coerce").fillna(0).sum())
    opened = int(pd.to_numeric(matched["opened"], errors="coerce").fillna(0).sum())
    clicks = int(pd.to_numeric(matched["clicks"], errors="coerce").fillna(0).sum())
    open_rate = opened / delivered if delivered else 0
    click_rate = clicks / delivered if delivered else 0
    creative_values = "\n".join(
        value for value in matched["creative"].fillna("").astype(str).tolist() if value.strip()
    )
    url_values = "\n".join(
        value for value in matched["web_version_url"].fillna("").astype(str).tolist() if value.strip()
    )
    return {
        "title": title,
        "rows": [
            ("Delivered", format_integer(delivered)),
            ("Opened", format_integer(opened)),
            ("Open rate", format_percent(open_rate)),
            ("Clicks", format_integer(clicks)),
            ("Click rate", format_percent(click_rate)),
            ("Creative", creative_values),
            ("Web-version URL", url_values),
        ],
    }


def render_hubspot_email_section(
    element_id: str,
    title: str,
    frame: pd.DataFrame,
    fallback_manual_data: dict[str, dict[str, Any]],
) -> None:
    element_header(title, element_id)

    def render_table() -> None:
        if frame.empty:
            st.info("No HubSpot marketing emails matched this advertiser and date range.")
            section = fallback_manual_data.get(element_id, {"rows": []})
            rows = [
                {"Metric": metric, "Value": value or "-"}
                for metric, value in section.get("rows", [])
            ]
            if has_manual_values(section):
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            return
        table = hubspot_email_detail_table(frame)
        st.dataframe(table, use_container_width=True, hide_index=True)

    render_if_selected(element_id, render_table)


def webinar_detail_table(webinar_frame: pd.DataFrame) -> pd.DataFrame:
    if webinar_frame.empty:
        return pd.DataFrame(columns=["Webinar", "Registrations", "URL"])
    detail = webinar_frame.copy()
    detail["Registrations"] = detail["registrations"].map(format_integer)
    return detail.rename(
        columns={
            "webinar_title": "Webinar",
            "reports_url": "URL",
        }
    )[["Webinar", "Registrations", "URL"]]


def match_webinars_from_listing(
    webinar_frame: pd.DataFrame,
    listing_frame: pd.DataFrame,
    advertiser_name: str,
) -> pd.DataFrame:
    if webinar_frame.empty or listing_frame.empty:
        return webinar_frame.iloc[0:0].copy()

    sponsored = listing_frame[
        listing_frame["listing_sponsor"].fillna("").apply(lambda value: sponsor_matches(value, advertiser_name))
    ].copy()
    if sponsored.empty:
        return webinar_frame.iloc[0:0].copy()

    sponsored["title_key"] = sponsored["listing_title"].map(normalize_title)
    matched_titles = set(sponsored["title_key"].dropna())

    matched = webinar_frame.copy()
    matched["title_key"] = matched["webinar_title"].map(normalize_title)
    matched = matched[matched["title_key"].isin(matched_titles)].copy()
    if matched.empty:
        return matched

    sponsor_lookup = sponsored.set_index("title_key")["listing_sponsor"].to_dict()
    matched["webinar_sponsor"] = matched["title_key"].map(sponsor_lookup).fillna(matched["webinar_sponsor"])
    return matched.drop(columns=["title_key"])


def prepare_gam_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame

    prepared = frame.copy()
    prepared["date"] = pd.to_datetime(prepared["date"], errors="coerce")
    prepared["campaign_name"] = prepared["campaign_name"].fillna("Unassigned")
    if "creative_id" not in prepared.columns:
        prepared["creative_id"] = pd.NA
    if "creative_name" not in prepared.columns:
        prepared["creative_name"] = "Unassigned"
    prepared["creative_name"] = prepared["creative_name"].fillna("Unassigned")
    prepared["ad_impressions"] = pd.to_numeric(prepared["ad_impressions"], errors="coerce").fillna(0)
    prepared["ad_clicks"] = pd.to_numeric(prepared["ad_clicks"], errors="coerce").fillna(0)
    prepared["ad_ctr"] = pd.to_numeric(prepared["ad_ctr"], errors="coerce").fillna(0)
    return prepared


def delivery_line_chart(daily: pd.DataFrame) -> alt.Chart:
    chart_data = daily.melt(
        id_vars=["date"],
        value_vars=["ad_impressions", "ad_clicks"],
        var_name="Metric",
        value_name="Value",
    )
    chart_data["Metric"] = chart_data["Metric"].map(
        {"ad_impressions": "Impressions", "ad_clicks": "Clicks"}
    )
    return (
        alt.Chart(chart_data)
        .mark_line(point=True, strokeWidth=2.5)
        .encode(
            x=alt.X("date:T", title=None),
            y=alt.Y("Value:Q", title=None),
            color=alt.Color(
                "Metric:N",
                scale=alt.Scale(range=[SME_COLORS["navy"], SME_COLORS["lime"]]),
                legend=alt.Legend(orient="bottom", title=None),
            ),
            tooltip=["date:T", "Metric:N", alt.Tooltip("Value:Q", format=",")],
        )
        .properties(height=300)
    )


def ctr_line_chart(daily: pd.DataFrame) -> alt.Chart:
    return (
        alt.Chart(daily)
        .mark_line(point=True, strokeWidth=2.5, color=SME_COLORS["deep_teal"])
        .encode(
            x=alt.X("date:T", title=None),
            y=alt.Y("ctr:Q", title=None, axis=alt.Axis(format="%")),
            tooltip=["date:T", alt.Tooltip("ctr:Q", title="CTR", format=".2%")],
        )
        .properties(height=300)
    )


def campaign_bar_chart(campaign_summary: pd.DataFrame) -> alt.Chart:
    chart_data = campaign_summary.melt(
        id_vars=["campaign_name"],
        value_vars=["ad_impressions", "ad_clicks"],
        var_name="Metric",
        value_name="Value",
    )
    chart_data["Metric"] = chart_data["Metric"].map(
        {"ad_impressions": "Impressions", "ad_clicks": "Clicks"}
    )
    return (
        alt.Chart(chart_data)
        .mark_bar()
        .encode(
            y=alt.Y("campaign_name:N", sort="-x", title=None),
            x=alt.X("Value:Q", title=None),
            color=alt.Color(
                "Metric:N",
                scale=alt.Scale(range=[SME_COLORS["blue"], SME_COLORS["gold"]]),
                legend=alt.Legend(orient="bottom", title=None),
            ),
            tooltip=["campaign_name:N", "Metric:N", alt.Tooltip("Value:Q", format=",")],
        )
        .properties(height=max(220, min(520, len(campaign_summary) * 34)))
    )


def campaign_ctr_chart(campaign_summary: pd.DataFrame) -> alt.Chart:
    return (
        alt.Chart(campaign_summary)
        .mark_bar(color=SME_COLORS["teal"])
        .encode(
            y=alt.Y("campaign_name:N", sort="-x", title=None),
            x=alt.X("ctr:Q", title=None, axis=alt.Axis(format="%")),
            tooltip=["campaign_name:N", alt.Tooltip("ctr:Q", title="CTR", format=".2%")],
        )
        .properties(height=max(220, min(520, len(campaign_summary) * 34)))
    )


def creative_bar_chart(creative_summary: pd.DataFrame) -> alt.Chart:
    chart_data = creative_summary.head(12).melt(
        id_vars=["creative_name"],
        value_vars=["ad_impressions", "ad_clicks"],
        var_name="Metric",
        value_name="Value",
    )
    chart_data["Metric"] = chart_data["Metric"].map(
        {"ad_impressions": "Impressions", "ad_clicks": "Clicks"}
    )
    return (
        alt.Chart(chart_data)
        .mark_bar()
        .encode(
            y=alt.Y("creative_name:N", sort="-x", title=None),
            x=alt.X("Value:Q", title=None),
            color=alt.Color(
                "Metric:N",
                scale=alt.Scale(range=[SME_COLORS["navy"], SME_COLORS["gold"]]),
                legend=alt.Legend(orient="bottom", title=None),
            ),
            tooltip=["creative_name:N", "Metric:N", alt.Tooltip("Value:Q", format=",")],
        )
        .properties(height=max(240, min(560, len(creative_summary.head(12)) * 36)))
    )


def creative_ctr_chart(creative_summary: pd.DataFrame) -> alt.Chart:
    return (
        alt.Chart(creative_summary.head(12))
        .mark_bar(color=SME_COLORS["deep_teal"])
        .encode(
            y=alt.Y("creative_name:N", sort="-x", title=None),
            x=alt.X("ctr:Q", title=None, axis=alt.Axis(format="%")),
            tooltip=["creative_name:N", alt.Tooltip("ctr:Q", title="CTR", format=".2%")],
        )
        .properties(height=max(240, min(560, len(creative_summary.head(12)) * 36)))
    )


def prepare_email_frame(*frames: pd.DataFrame) -> pd.DataFrame:
    available = [frame.copy() for frame in frames if frame is not None and not frame.empty]
    if not available:
        return pd.DataFrame()
    prepared = pd.concat(available, ignore_index=True)
    for column in ["delivered", "opened", "clicks", "open_rate", "click_rate"]:
        if column not in prepared.columns:
            prepared[column] = 0
        prepared[column] = pd.to_numeric(prepared[column], errors="coerce").fillna(0)
    prepared["placement_date"] = pd.to_datetime(prepared.get("placement_date", ""), errors="coerce")
    prepared["email_label"] = prepared["email_name"].fillna("").astype(str)
    fallback_label = prepared["report_type"].fillna("Email").astype(str)
    prepared.loc[prepared["email_label"].str.strip() == "", "email_label"] = fallback_label
    if "placement_ad_type" not in prepared.columns:
        prepared["placement_ad_type"] = ""
    prepared["ad_type"] = prepared["placement_ad_type"].fillna("").astype(str)
    prepared.loc[prepared["ad_type"].str.strip() == "", "ad_type"] = prepared["report_type"].fillna("Email").astype(str)
    return prepared


def filter_email_frame_for_advertiser(frame: pd.DataFrame, advertiser: dict[str, Any]) -> pd.DataFrame:
    if frame.empty:
        return frame
    current_id = str(advertiser.get("advertiser_id", "") or "").strip()
    current_name = normalize_match_text(str(advertiser.get("advertiser_name", "") or ""))
    mask = pd.Series(False, index=frame.index)
    if current_id and "advertiser_id" in frame.columns:
        mask = mask | (frame["advertiser_id"].fillna("").astype(str).str.strip() == current_id)
    if current_name and "advertiser_name" in frame.columns:
        mask = mask | (frame["advertiser_name"].fillna("").astype(str).map(normalize_match_text) == current_name)
    return frame[mask].copy().reset_index(drop=True)


def email_totals(email_frame: pd.DataFrame) -> dict[str, float]:
    delivered = float(email_frame["delivered"].sum()) if not email_frame.empty else 0
    opened = float(email_frame["opened"].sum()) if not email_frame.empty else 0
    clicks = float(email_frame["clicks"].sum()) if not email_frame.empty else 0
    return {
        "delivered": delivered,
        "opened": opened,
        "open_rate": opened / delivered if delivered else 0,
        "clicks": clicks,
        "click_rate": clicks / delivered if delivered else 0,
    }


def email_metric_melt(frame: pd.DataFrame, id_vars: list[str]) -> pd.DataFrame:
    melted = frame.melt(
        id_vars=id_vars,
        value_vars=["delivered", "opened", "clicks"],
        var_name="Metric",
        value_name="Value",
    )
    melted["Metric"] = melted["Metric"].map({"delivered": "Delivered", "opened": "Opened", "clicks": "Clicks"})
    return melted


def email_metrics_by_ad_type_chart(email_frame: pd.DataFrame) -> alt.Chart:
    summary = (
        email_frame.groupby("ad_type", dropna=False)[["delivered", "opened", "clicks"]]
        .sum()
        .reset_index()
        .sort_values("delivered", ascending=False)
    )
    melted = email_metric_melt(summary, ["ad_type"])
    return (
        alt.Chart(melted)
        .mark_bar()
        .encode(
            x=alt.X("ad_type:N", sort="-y", title=None),
            xOffset="Metric:N",
            y=alt.Y("Value:Q", title=None),
            color=alt.Color(
                "Metric:N",
                scale=alt.Scale(range=[SME_COLORS["navy"], SME_COLORS["teal"], SME_COLORS["gold"]]),
                legend=alt.Legend(orient="bottom", title=None),
            ),
            tooltip=["ad_type:N", "Metric:N", alt.Tooltip("Value:Q", format=",")],
        )
        .properties(height=320)
    )


def email_metrics_by_date_chart(email_frame: pd.DataFrame) -> alt.Chart:
    chart_data = email_frame.dropna(subset=["placement_date"]).copy()
    if chart_data.empty:
        chart_data = email_frame.copy()
        chart_data["date_label"] = "Unscheduled"
    else:
        chart_data["date_label"] = chart_data["placement_date"].dt.strftime("%Y-%m-%d")
    summary = (
        chart_data.groupby("date_label", dropna=False)[["delivered", "opened", "clicks"]]
        .sum()
        .reset_index()
        .sort_values("date_label")
    )
    melted = email_metric_melt(summary, ["date_label"])
    return (
        alt.Chart(melted)
        .mark_bar()
        .encode(
            x=alt.X("date_label:N", title=None),
            xOffset="Metric:N",
            y=alt.Y("Value:Q", title=None),
            color=alt.Color(
                "Metric:N",
                scale=alt.Scale(range=[SME_COLORS["navy"], SME_COLORS["teal"], SME_COLORS["gold"]]),
                legend=alt.Legend(orient="bottom", title=None),
            ),
            tooltip=["date_label:N", "Metric:N", alt.Tooltip("Value:Q", format=",")],
        )
        .properties(height=320)
    )


def email_rates_by_ad_type_chart(email_frame: pd.DataFrame) -> alt.Chart:
    summary = (
        email_frame.groupby("ad_type", dropna=False)[["delivered", "opened", "clicks"]]
        .sum()
        .reset_index()
        .sort_values("delivered", ascending=False)
    )
    summary["open_rate"] = summary["opened"] / summary["delivered"].replace(0, pd.NA)
    summary["click_rate"] = summary["clicks"] / summary["delivered"].replace(0, pd.NA)
    summary[["open_rate", "click_rate"]] = summary[["open_rate", "click_rate"]].fillna(0)
    melted = summary.melt(
        id_vars=["ad_type"],
        value_vars=["open_rate", "click_rate"],
        var_name="Metric",
        value_name="Rate",
    )
    melted["Metric"] = melted["Metric"].map({"open_rate": "Open rate", "click_rate": "Click rate"})
    return (
        alt.Chart(melted)
        .mark_bar()
        .encode(
            x=alt.X("ad_type:N", sort="-y", title=None),
            xOffset="Metric:N",
            y=alt.Y("Rate:Q", title=None, axis=alt.Axis(format="%")),
            color=alt.Color(
                "Metric:N",
                scale=alt.Scale(range=[SME_COLORS["deep_teal"], SME_COLORS["red"]]),
                legend=alt.Legend(orient="bottom", title=None),
            ),
            tooltip=["ad_type:N", "Metric:N", alt.Tooltip("Rate:Q", format=".2%")],
        )
        .properties(height=320)
    )


def email_metrics_over_time_chart(email_frame: pd.DataFrame) -> alt.Chart:
    chart_data = email_frame.dropna(subset=["placement_date"]).copy()
    if chart_data.empty:
        return alt.Chart(pd.DataFrame({"placement_date": [], "Metric": [], "Value": []})).mark_line()
    summary = (
        chart_data.groupby("placement_date", dropna=False)[["delivered", "opened", "clicks"]]
        .sum()
        .reset_index()
        .sort_values("placement_date")
    )
    melted = email_metric_melt(summary, ["placement_date"])
    return (
        alt.Chart(melted)
        .mark_line(point=True)
        .encode(
            x=alt.X("placement_date:T", title=None),
            y=alt.Y("Value:Q", title=None),
            color=alt.Color(
                "Metric:N",
                scale=alt.Scale(range=[SME_COLORS["navy"], SME_COLORS["teal"], SME_COLORS["gold"]]),
                legend=alt.Legend(orient="bottom", title=None),
            ),
            tooltip=[alt.Tooltip("placement_date:T", title="Date"), "Metric:N", alt.Tooltip("Value:Q", format=",")],
        )
        .properties(height=320)
    )


def email_rates_over_time_chart(email_frame: pd.DataFrame) -> alt.Chart:
    chart_data = email_frame.dropna(subset=["placement_date"]).copy()
    if chart_data.empty:
        return alt.Chart(pd.DataFrame({"placement_date": [], "Metric": [], "Rate": []})).mark_line()
    summary = (
        chart_data.groupby("placement_date", dropna=False)[["delivered", "opened", "clicks"]]
        .sum()
        .reset_index()
        .sort_values("placement_date")
    )
    summary["open_rate"] = summary["opened"] / summary["delivered"].replace(0, pd.NA)
    summary["click_rate"] = summary["clicks"] / summary["delivered"].replace(0, pd.NA)
    summary[["open_rate", "click_rate"]] = summary[["open_rate", "click_rate"]].fillna(0)
    melted = summary.melt(
        id_vars=["placement_date"],
        value_vars=["open_rate", "click_rate"],
        var_name="Metric",
        value_name="Rate",
    )
    melted["Metric"] = melted["Metric"].map({"open_rate": "Open rate", "click_rate": "Click rate"})
    return (
        alt.Chart(melted)
        .mark_line(point=True)
        .encode(
            x=alt.X("placement_date:T", title=None),
            y=alt.Y("Rate:Q", title=None, axis=alt.Axis(format="%")),
            color=alt.Color(
                "Metric:N",
                scale=alt.Scale(range=[SME_COLORS["deep_teal"], SME_COLORS["red"]]),
                legend=alt.Legend(orient="bottom", title=None),
            ),
            tooltip=[alt.Tooltip("placement_date:T", title="Date"), "Metric:N", alt.Tooltip("Rate:Q", format=".2%")],
        )
        .properties(height=320)
    )
    melted = email_metric_melt(summary, ["placement_date"])
    return (
        alt.Chart(melted)
        .mark_line(point=True)
        .encode(
            x=alt.X("placement_date:T", title=None),
            y=alt.Y("Value:Q", title=None),
            color=alt.Color(
                "Metric:N",
                scale=alt.Scale(range=[SME_COLORS["navy"], SME_COLORS["teal"], SME_COLORS["gold"]]),
                legend=alt.Legend(orient="bottom", title=None),
            ),
            tooltip=[alt.Tooltip("placement_date:T", title="Date"), "Metric:N", alt.Tooltip("Value:Q", format=",")],
        )
        .properties(height=320)
    )


def image_creative_stats(gam_ads: pd.DataFrame, assets: pd.DataFrame) -> pd.DataFrame:
    if gam_ads.empty or assets.empty:
        return pd.DataFrame()
    stats = (
        gam_ads.groupby(["creative_id", "creative_name"], dropna=False)[["ad_impressions", "ad_clicks"]]
        .sum()
        .reset_index()
    )
    stats["creative_id"] = stats["creative_id"].astype(str)
    assets = assets.copy()
    assets["creative_id"] = assets["creative_id"].astype(str)
    stats["ctr"] = stats["ad_clicks"] / stats["ad_impressions"].replace(0, pd.NA)
    stats["ctr"] = stats["ctr"].fillna(0)
    merged = stats.merge(assets, on="creative_id", how="left", suffixes=("", "_asset"))
    merged["creative_type"] = merged["creative_type"].fillna("Unknown")
    merged["image_url"] = merged["image_url"].fillna("")
    image_rows = merged[
        (merged["creative_type"].str.lower() == "image") & (merged["image_url"] != "")
    ].copy()
    return image_rows.sort_values("ad_impressions", ascending=False, ignore_index=True)


def render_source_status() -> None:
    sources = load_report_sources().get("categories", {})
    rows = []
    for key, category in sources.items():
        configured_status = str(category.get("status", "")).lower()
        if configured_status == "live" or key == "website_ads":
            status = "Live"
        elif configured_status == "starter":
            status = "Starter"
        else:
            status = "Planned"
        rows.append(
            {
                "Section": category["label"],
                "Source": category["source"],
                "Status": status,
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


header_logo, header_text = st.columns([1, 5], vertical_alignment="center")
with header_logo:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=160)
with header_text:
    st.title("Advertiser Dashboard Automation")
    st.markdown(
        '<div class="report-kicker">Client-facing campaign performance powered by Google Ad Manager</div>',
        unsafe_allow_html=True,
    )


uploaded_newsletter_file = None
with st.sidebar:
    st.header("Report")
    advertiser_source = st.radio("Advertiser source", ["Local CSV", "Google Ad Manager"])
    include_house = st.checkbox("Include house advertisers", value=False)
    search_missing_advertiser = st.checkbox("Search advertiser not shown in list", value=False)

    if advertiser_source == "Google Ad Manager":
        try:
            advertisers = cached_gam_advertisers(include_house)
        except GAMConfigError as exc:
            st.warning(str(exc))
            advertisers = cached_advertisers()
            st.caption("Using local CSV.")
    else:
        advertisers = cached_advertisers()

    if advertisers.empty:
        st.error("No advertisers found.")
        st.stop()

    selected_name = st.selectbox(
        "Advertiser",
        advertisers["advertiser_name"].tolist(),
        disabled=search_missing_advertiser,
        help="Disabled while searching for an advertiser not shown in the list.",
    )
    selected = advertisers.loc[advertisers["advertiser_name"] == selected_name].iloc[0].to_dict()
    if search_missing_advertiser:
        typed_advertiser_name = st.text_input(
            "Advertiser name",
            value="",
            placeholder="Type company name",
            help="Searches this name across Google Ad Manager, Webinar.net, and HubSpot custom emails for the selected date range.",
        ).strip()
        if typed_advertiser_name:
            gam_match = find_gam_advertiser_by_name(typed_advertiser_name, include_house)
            selected = {
                "advertiser_id": gam_match.get("advertiser_id") or f"search_{safe_filename(typed_advertiser_name)}",
                "advertiser_name": typed_advertiser_name,
                "gam_advertiser_id": gam_match.get("gam_advertiser_id", ""),
                "gam_advertiser_name": gam_match.get("gam_advertiser_name", ""),
                "gam_company_type": gam_match.get("gam_company_type", ""),
                "gam_credit_status": gam_match.get("gam_credit_status", ""),
                "source_system": "Search",
            }
            if gam_match:
                st.caption(f"Matched in Google Ad Manager: {gam_match.get('advertiser_name', typed_advertiser_name)}")
            else:
                st.caption("No Google Ad Manager advertiser match found. Webinar.net and HubSpot will still search by name.")
    gam_advertiser_id = str(selected.get("gam_advertiser_id") or selected.get("advertiser_id") or "").strip()
    has_gam_advertiser_id = bool(gam_advertiser_id and gam_advertiser_id.isdigit())

    default_end_date = date.today() - timedelta(days=1)
    start_date = st.date_input("Start date", default_end_date - timedelta(days=29))
    end_date = st.date_input("End date", default_end_date)

    if start_date > end_date:
        st.error("Start date must be before end date.")
        st.stop()

    st.markdown("**Connected data pulls**")
    use_gam_data = st.checkbox("Pull Google Ad Manager data", value=True, key="pull_gam_data")
    use_webinar_api = st.checkbox("Pull Webinar.net data", value=True, key="pull_webinar_net")
    use_hubspot_email = st.checkbox("Pull HubSpot email data", value=True, key="pull_hubspot_email")
    webinar_match_text = ""
    if use_webinar_api:
        webinar_match_text = st.text_input(
            "Webinar fallback match text",
            value=str(selected["advertiser_name"]),
            help="Used only if the Advanced Manufacturing sponsor listing does not find a match.",
            key=f"webinar_fallback_match_text_{safe_filename(str(selected['advertiser_name']))}",
        )
    if use_hubspot_email:
        with st.expander("eNewsletter placement file", expanded=False):
            default_newsletter_file = BASE_DIR / "eNewsletter Ad Metrics.csv"
            if default_newsletter_file.exists():
                st.caption(f"Default: {default_newsletter_file.name}")
            else:
                st.caption("Default: data/newsletter_placements.csv")
            uploaded_newsletter_file = st.file_uploader(
                "Upload latest CSV or Excel",
                type=["csv", "xlsx", "xls"],
                key="hubspot_newsletter_upload",
            )

    try:
        if use_gam_data and has_gam_advertiser_id:
            with st.spinner("Loading campaigns..."):
                campaigns = cached_campaigns(gam_advertiser_id, start_date, end_date)
        else:
            campaigns = pd.DataFrame(columns=["campaign_id", "campaign_name"])
    except GAMConfigError as exc:
        st.warning(str(exc))
        campaigns = pd.DataFrame(columns=["campaign_id", "campaign_name"])

    campaign_labels = ["All campaigns"]
    campaign_lookup: dict[str, tuple[str | None, str | None]] = {"All campaigns": (None, None)}
    for row in campaigns.to_dict(orient="records"):
        label = str(row.get("campaign_name") or "Unassigned")
        campaign_id = str(row.get("campaign_id") or "")
        display_label = f"{label} ({campaign_id})" if campaign_id else label
        campaign_labels.append(display_label)
        campaign_lookup[display_label] = (campaign_id or None, label)

    selected_campaign = st.selectbox("Campaign", campaign_labels)
    campaign_id, campaign_name = campaign_lookup[selected_campaign]
    run_report = st.button("Run report", type="primary", use_container_width=True)

manual_data = collect_manual_data()
hubspot_newsletter_placements: pd.DataFrame | None = None
newsletter_file_key = "default"
if uploaded_newsletter_file is not None:
    try:
        uploaded_newsletter_file.seek(0)
        raw_newsletter_placements = read_uploaded_placement_file(uploaded_newsletter_file)
        hubspot_newsletter_placements = raw_newsletter_placements
        normalized_preview = normalize_placement_frame(raw_newsletter_placements)
        newsletter_file_key = f"upload:{uploaded_newsletter_file.name}:{uploaded_newsletter_file.size}"
        st.sidebar.caption(f"Using uploaded eNewsletter file: {len(normalized_preview):,} placement rows")
    except Exception as exc:
        st.sidebar.error(f"Could not read uploaded eNewsletter file: {exc}")
        st.stop()
elif (BASE_DIR / "eNewsletter Ad Metrics.csv").exists():
    default_stat = (BASE_DIR / "eNewsletter Ad Metrics.csv").stat()
    newsletter_file_key = f"default:eNewsletter Ad Metrics.csv:{default_stat.st_mtime_ns}"

report_key = (
    str(selected.get("advertiser_id")),
    str(selected.get("advertiser_name")),
    str(gam_advertiser_id),
    start_date.isoformat(),
    end_date.isoformat(),
    str(campaign_id or ""),
    str(use_gam_data),
    str(use_webinar_api),
    str(use_hubspot_email),
    newsletter_file_key,
)

st.caption(
    f"{selected['advertiser_name']} | {start_date:%Y-%m-%d} to {end_date:%Y-%m-%d}"
    + (f" | {campaign_name}" if campaign_name else "")
)

if not run_report and st.session_state.get("report_key") != report_key:
    st.markdown('<div class="section-label">Connected Sources</div>', unsafe_allow_html=True)
    render_source_status()
    st.stop()

if run_report or st.session_state.get("report_key") != report_key:
    request = ReportRequest(
        advertiser=selected,
        start_date=start_date,
        end_date=end_date,
        campaign_id=campaign_id,
        campaign_name=campaign_name,
    )
    try:
        with st.spinner("Building report..."):
            report = build_advertiser_report(
                request,
                allow_empty_ga4=True,
                allow_empty_gam=(not use_gam_data) or (not has_gam_advertiser_id),
                include_hubspot=use_hubspot_email,
                allow_empty_hubspot=False,
                hubspot_newsletter_placements=hubspot_newsletter_placements,
            )
    except (GAMConfigError, HubSpotConfigError) as exc:
        st.error(str(exc))
        st.stop()
    st.session_state["report_key"] = report_key
    st.session_state["report"] = report
    st.session_state["report_needs_pdf_defaults"] = True
else:
    report = st.session_state["report"]

gam_ads = prepare_gam_frame(report.gam_ad_performance)
hubspot_enewsletter = filter_email_frame_for_advertiser(report.hubspot_enewsletter_performance, selected)
hubspot_custom_email = filter_email_frame_for_advertiser(report.hubspot_custom_email_performance, selected)
webinar_frame = _empty_webinar_frame()
webinar_status = ""
if use_webinar_api:
    try:
        with st.spinner("Loading Webinar.net data..."):
            all_webinars = cached_webinars(
                advertiser_name=str(selected["advertiser_name"]),
                match_text="",
                start_date=start_date,
                end_date=end_date,
                cache_version=WEBINAR_API_CACHE_VERSION,
            )
        try:
            with st.spinner("Matching webinars by sponsor..."):
                listing_frame = cached_webinar_listing(WEBINAR_LISTING_CACHE_VERSION)
                webinar_frame = match_webinars_from_listing(
                    all_webinars,
                    listing_frame,
                    str(selected["advertiser_name"]),
                )
        except WebinarListingError as exc:
            st.warning(f"Advanced Manufacturing webinar listing could not be used: {exc}")
            webinar_frame = _empty_webinar_frame()

        if webinar_frame.empty and webinar_match_text:
            searchable = all_webinars["webinar_match_text"].fillna("").str.lower()
            webinar_frame = all_webinars[
                searchable.str.contains(webinar_match_text.lower(), regex=False)
            ].copy()
        if webinar_frame.empty:
            webinar_status = "No Webinar.net webinars matched this advertiser and date range."
    except WebinarNetConfigError as exc:
        webinar_status = str(exc)
        st.warning(webinar_status)

email_ads = prepare_email_frame(hubspot_enewsletter, hubspot_custom_email)

campaign_summary = (
    gam_ads.groupby("campaign_name", dropna=False)[["ad_impressions", "ad_clicks"]]
    .sum()
    .reset_index()
)
campaign_summary["ctr"] = campaign_summary["ad_clicks"] / campaign_summary["ad_impressions"].replace(0, pd.NA)
campaign_summary["ctr"] = campaign_summary["ctr"].fillna(0)
campaign_summary = campaign_summary.sort_values("ad_impressions", ascending=False, ignore_index=True)

creative_summary = (
    gam_ads.groupby(["creative_id", "creative_name"], dropna=False)[["ad_impressions", "ad_clicks"]]
    .sum()
    .reset_index()
)
creative_summary["ctr"] = creative_summary["ad_clicks"] / creative_summary["ad_impressions"].replace(0, pd.NA)
creative_summary["ctr"] = creative_summary["ctr"].fillna(0)
creative_summary = creative_summary.sort_values("ad_impressions", ascending=False, ignore_index=True)

available_pdf_elements = available_report_elements(gam_ads, webinar_frame, email_ads, manual_data)
unavailable_chart_elements = set()
if not multiple_dates(gam_ads, "date"):
    unavailable_chart_elements.update(["chart_daily_delivery", "chart_daily_ctr"])
if not multiple_nonempty_values(campaign_summary, "campaign_name"):
    unavailable_chart_elements.update(["chart_campaign_performance", "chart_campaign_ctr"])
if not multiple_nonempty_values(creative_summary, "creative_name"):
    unavailable_chart_elements.update(["chart_creative_performance", "chart_creative_ctr"])
if not multiple_nonempty_values(email_ads, "ad_type"):
    unavailable_chart_elements.update(["chart_email_ad_type", "chart_email_rates_ad_type"])
if not multiple_dates(email_ads, "placement_date"):
    unavailable_chart_elements.update(["chart_email_time", "chart_email_rates_time"])
available_pdf_elements = [
    element for element in available_pdf_elements
    if element not in unavailable_chart_elements
]
st.session_state["available_pdf_elements"] = available_pdf_elements
if st.session_state.pop("report_needs_pdf_defaults", False):
    set_report_elements(available_pdf_elements)

with st.sidebar:
    st.divider()
    st.header("PDF Selection")
    st.caption("Sections without available data are deselected by default.")
    if st.button("Select available", use_container_width=True):
        set_report_elements(available_pdf_elements)
        st.rerun()
    available_visuals = [
        element for element in available_pdf_elements
        if REPORT_ELEMENTS[element]["type"] == "visualization"
    ]
    selected_visuals = [
        element for element in selected_report_elements()
        if REPORT_ELEMENTS[element]["type"] == "visualization"
    ]
    visual_button_label = "Exclude visuals" if selected_visuals else "Include visuals"
    if st.button(visual_button_label, use_container_width=True):
        available_non_visual = [
            element for element in available_pdf_elements
            if REPORT_ELEMENTS[element]["type"] != "visualization"
        ]
        if selected_visuals:
            set_report_elements(available_non_visual)
        else:
            current = set(selected_report_elements())
            current.update(available_visuals)
            set_report_elements([element for element in all_report_element_ids() if element in current])
        st.rerun()

    with st.expander("Sections", expanded=True):
        for section_name in report_section_names():
            section_ids = report_section_element_ids(section_name)
            has_available_data = any(element_id in available_pdf_elements for element_id in section_ids)
            if has_available_data:
                section_checkbox(section_name)
            else:
                st.checkbox(
                    f"{section_name} (no data)",
                    value=False,
                    disabled=True,
                    key=f"disabled_section_{safe_filename(section_name)}",
                )

st.subheader("Website Ads")
if gam_ads.empty:
    st.info("No GAM rows returned for this advertiser, campaign, and date range.")

total_impressions = gam_ads["ad_impressions"].sum()
total_clicks = gam_ads["ad_clicks"].sum()
weighted_ctr = total_clicks / total_impressions if total_impressions else 0
active_campaigns = gam_ads["campaign_id"].nunique(dropna=True)
active_creatives = gam_ads["creative_id"].nunique(dropna=True)

if not gam_ads.empty:
    kpi_cols = st.columns(5)
    with kpi_cols[0]:
        selectable_metric("kpi_impressions", "Ad impressions", format_integer(total_impressions))
    with kpi_cols[1]:
        selectable_metric("kpi_clicks", "Ad clicks", format_integer(total_clicks))
    with kpi_cols[2]:
        selectable_metric("kpi_ctr", "CTR", format_percent(weighted_ctr))
    with kpi_cols[3]:
        selectable_metric("kpi_campaigns", "Campaigns", format_integer(active_campaigns))
    with kpi_cols[4]:
        selectable_metric("kpi_creatives", "Creatives", format_integer(active_creatives))

daily = (
    gam_ads.groupby("date", dropna=False)[["ad_impressions", "ad_clicks"]]
    .sum()
    .reset_index()
    .sort_values("date")
)
daily["ctr"] = daily["ad_clicks"] / daily["ad_impressions"].replace(0, pd.NA)
daily["ctr"] = daily["ctr"].fillna(0)

if not gam_ads.empty and multiple_dates(gam_ads, "date"):
    trend_left, trend_right = st.columns([2, 1])
    with trend_left:
        element_header("Daily Delivery", "chart_daily_delivery")
        render_if_selected(
            "chart_daily_delivery",
            lambda: st.altair_chart(delivery_line_chart(daily), use_container_width=True),
        )
    with trend_right:
        element_header("Daily CTR", "chart_daily_ctr")
        render_if_selected(
            "chart_daily_ctr",
            lambda: st.altair_chart(ctr_line_chart(daily), use_container_width=True),
        )

has_multiple_campaigns = multiple_nonempty_values(campaign_summary, "campaign_name")
if not gam_ads.empty and has_multiple_campaigns:
    campaign_left, campaign_right = st.columns([2, 1])
    with campaign_left:
        element_header("Performance by Campaign", "chart_campaign_performance")
        render_if_selected(
            "chart_campaign_performance",
            lambda: st.altair_chart(campaign_bar_chart(campaign_summary), use_container_width=True),
        )
    with campaign_right:
        element_header("Campaign CTR", "chart_campaign_ctr")
        render_if_selected(
            "chart_campaign_ctr",
            lambda: st.altair_chart(campaign_ctr_chart(campaign_summary), use_container_width=True),
        )
if not gam_ads.empty:
    element_header("Campaign Detail", "table_campaign_detail")
    detail = campaign_summary.copy()
    detail["ad_impressions"] = detail["ad_impressions"].map(format_integer)
    detail["ad_clicks"] = detail["ad_clicks"].map(format_integer)
    detail["ctr"] = detail["ctr"].map(format_percent)
    detail = detail.rename(
        columns={
            "campaign_name": "Campaign",
            "ad_impressions": "Ad impressions",
            "ad_clicks": "Ad clicks",
            "ctr": "CTR",
        }
    )
    render_if_selected(
        "table_campaign_detail",
        lambda: st.dataframe(detail, use_container_width=True, hide_index=True),
    )

has_multiple_creatives = multiple_nonempty_values(creative_summary, "creative_name")
if not gam_ads.empty and has_multiple_creatives:
    creative_left, creative_right = st.columns([2, 1])
    with creative_left:
        element_header("Performance by Ad Creative", "chart_creative_performance")
        render_if_selected(
            "chart_creative_performance",
            lambda: st.altair_chart(creative_bar_chart(creative_summary), use_container_width=True),
        )
    with creative_right:
        element_header("Creative CTR", "chart_creative_ctr")
        render_if_selected(
            "chart_creative_ctr",
            lambda: st.altair_chart(creative_ctr_chart(creative_summary), use_container_width=True),
        )
if not gam_ads.empty:
    element_header("Ad Creative Detail", "table_creative_detail")
    creative_detail = creative_summary.copy()
    creative_detail["ad_impressions"] = creative_detail["ad_impressions"].map(format_integer)
    creative_detail["ad_clicks"] = creative_detail["ad_clicks"].map(format_integer)
    creative_detail["ctr"] = creative_detail["ctr"].map(format_percent)
    creative_detail = creative_detail.rename(
        columns={
            "creative_id": "Creative ID",
            "creative_name": "Creative",
            "ad_impressions": "Ad impressions",
            "ad_clicks": "Ad clicks",
            "ctr": "CTR",
        }
    )
    render_if_selected(
        "table_creative_detail",
        lambda: st.dataframe(creative_detail, use_container_width=True, hide_index=True),
    )

creative_ids = tuple(
    sorted(str(value) for value in gam_ads["creative_id"].dropna().astype(str).unique() if str(value))
)
if gam_ads.empty:
    creative_assets = pd.DataFrame()
else:
    try:
        with st.spinner("Loading creative assets..."):
            creative_assets = cached_creative_assets(creative_ids)
    except GAMConfigError as exc:
        st.warning(str(exc))
        creative_assets = pd.DataFrame()

image_creatives = image_creative_stats(gam_ads, creative_assets)

if not gam_ads.empty:
    element_header("Image Creative Preview", "image_creatives")
    def render_image_creatives() -> None:
        if image_creatives.empty:
            st.info("No image creative assets were found for this report.")
            return
        for _, creative in image_creatives.head(8).iterrows():
            image_col, stat_col = st.columns([1, 2], vertical_alignment="center")
            with image_col:
                st.image(str(creative["image_url"]), use_container_width=True)
            with stat_col:
                st.markdown(f"**{creative['creative_name']}**")
                render_metric_row(
                    {
                        "Impressions": format_integer(creative["ad_impressions"]),
                        "Clicks": format_integer(creative["ad_clicks"]),
                        "CTR": format_percent(creative["ctr"]),
                    }
                )
                size_text = ""
                if creative.get("width") and creative.get("height"):
                    size_text = f"{creative['width']} x {creative['height']}"
                st.caption(f"Type: {creative['creative_type']} | Size: {size_text or 'Unknown'}")
                link_cols = st.columns(2)
                if creative.get("preview_url"):
                    link_cols[0].link_button("Preview", str(creative["preview_url"]), use_container_width=True)
                if creative.get("destination_url"):
                    link_cols[1].link_button("Destination", str(creative["destination_url"]), use_container_width=True)


    render_if_selected("image_creatives", render_image_creatives)

st.subheader("Webinars")
if webinar_frame.empty:
    st.info(webinar_status or "No Webinar.net webinars matched this advertiser and date range.")
else:
    webinar_registrations = int(webinar_frame["registrations"].sum())
    webinar_kpi_col, _ = st.columns([1, 4])
    with webinar_kpi_col:
        selectable_metric(
            "kpi_webinar_registrations",
            "Total registrations",
            format_integer(webinar_registrations),
        )

    element_header("Webinar Detail", "table_webinars")
    render_if_selected(
        "table_webinars",
        lambda: st.dataframe(webinar_detail_table(webinar_frame), use_container_width=True, hide_index=True),
    )

st.subheader("HubSpot Email")
if email_ads.empty:
    st.info("No HubSpot email ad rows are available for visualizations.")
else:
    totals = email_totals(email_ads)
    email_kpis = st.columns(5)
    with email_kpis[0]:
        selectable_metric("kpi_email_delivered", "Emails delivered", format_integer(totals["delivered"]))
    with email_kpis[1]:
        selectable_metric("kpi_email_opened", "Emails opened", format_integer(totals["opened"]))
    with email_kpis[2]:
        selectable_metric("kpi_email_open_rate", "Open rate", format_percent(totals["open_rate"]))
    with email_kpis[3]:
        selectable_metric("kpi_email_clicks", "Clicks", format_integer(totals["clicks"]))
    with email_kpis[4]:
        selectable_metric("kpi_email_click_rate", "Click rate", format_percent(totals["click_rate"]))

    has_multiple_email_ad_types = multiple_nonempty_values(email_ads, "ad_type")
    if has_multiple_email_ad_types:
        email_ad_type_col, email_rate_type_col = st.columns(2)
        with email_ad_type_col:
            element_header("Email Metrics by Ad Type", "chart_email_ad_type")
            render_if_selected(
                "chart_email_ad_type",
                lambda: st.altair_chart(email_metrics_by_ad_type_chart(email_ads), use_container_width=True),
            )
        with email_rate_type_col:
            element_header("Email Rates by Ad Type", "chart_email_rates_ad_type")
            render_if_selected(
                "chart_email_rates_ad_type",
                lambda: st.altair_chart(email_rates_by_ad_type_chart(email_ads), use_container_width=True),
            )
    if multiple_dates(email_ads, "placement_date"):
        email_time_col, email_rate_time_col = st.columns(2)
        with email_time_col:
            element_header("Email Metrics Over Time", "chart_email_time")
            render_if_selected(
                "chart_email_time",
                lambda: st.altair_chart(email_metrics_over_time_chart(email_ads), use_container_width=True),
            )
        with email_rate_time_col:
            element_header("Email Rates Over Time", "chart_email_rates_time")
            render_if_selected(
                "chart_email_rates_time",
                lambda: st.altair_chart(email_rates_over_time_chart(email_ads), use_container_width=True),
            )

render_hubspot_email_section(
    "manual_enewsletter",
    "eNewsletter Ads",
    hubspot_enewsletter,
    manual_data,
)
render_hubspot_email_section(
    "manual_custom_email",
    "Custom Email",
    hubspot_custom_email,
    manual_data,
)

st.subheader("Manual Entries")
for manual_element_id in [
    "manual_retargeting",
    "manual_lead_gen",
]:
    render_manual_section(manual_element_id, manual_data)

with st.expander("Source roadmap", expanded=False):
    render_source_status()

selected_pdf_elements = selected_report_elements()
pdf_manual_data = dict(manual_data)
st.markdown('<div class="section-label">PDF Export</div>', unsafe_allow_html=True)
st.caption(f"{len(selected_pdf_elements)} of {len(REPORT_ELEMENTS)} report elements selected.")
try:
    pdf_bytes = build_pdf_report(
        advertiser_name=str(selected["advertiser_name"]),
        start_date=start_date,
        end_date=end_date,
        campaign_name=campaign_name,
        gam_ads=gam_ads,
        webinar_data=webinar_frame,
        creative_assets=image_creatives,
        hubspot_email_data=email_ads,
        manual_data=pdf_manual_data,
        logo_path=LOGO_PATH,
        elements=selected_pdf_elements or ["kpi_impressions"],
    )
    st.download_button(
        "Download PDF report",
        data=pdf_bytes,
        file_name=(
            f"{safe_filename(str(selected['advertiser_name']))}_"
            f"{start_date:%Y%m%d}_{end_date:%Y%m%d}_advertiser_report.pdf"
        ),
        mime="application/pdf",
        use_container_width=False,
    )
except RuntimeError as exc:
    st.warning(str(exc))
