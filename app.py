from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
import altair as alt

from src.config import load_advertisers, load_report_sources
from src.gam_client import GAMClient, GAMConfigError
from src.pdf_report import build_pdf_report
from src.reporting import ReportRequest, build_advertiser_report, export_report_frames


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

REPORT_ELEMENTS = {
    "kpi_impressions": {"label": "KPI: Ad impressions", "section": "KPI summary", "type": "kpi"},
    "kpi_clicks": {"label": "KPI: Ad clicks", "section": "KPI summary", "type": "kpi"},
    "kpi_ctr": {"label": "KPI: CTR", "section": "KPI summary", "type": "kpi"},
    "kpi_campaigns": {"label": "KPI: Campaigns", "section": "KPI summary", "type": "kpi"},
    "kpi_creatives": {"label": "KPI: Creatives", "section": "KPI summary", "type": "kpi"},
    "chart_daily_delivery": {"label": "Chart: Daily delivery", "section": "Visualizations", "type": "visualization"},
    "chart_daily_ctr": {"label": "Chart: Daily CTR", "section": "Visualizations", "type": "visualization"},
    "chart_campaign_performance": {"label": "Chart: Campaign performance", "section": "Visualizations", "type": "visualization"},
    "chart_campaign_ctr": {"label": "Chart: Campaign CTR", "section": "Visualizations", "type": "visualization"},
    "chart_creative_performance": {"label": "Chart: Creative performance", "section": "Visualizations", "type": "visualization"},
    "chart_creative_ctr": {"label": "Chart: Creative CTR", "section": "Visualizations", "type": "visualization"},
    "table_campaign_detail": {"label": "Table: Campaign detail", "section": "Tables", "type": "table"},
    "table_creative_detail": {"label": "Table: Creative detail", "section": "Tables", "type": "table"},
    "image_creatives": {"label": "Image creative previews", "section": "Creative assets", "type": "visualization"},
    "manual_webinars": {"label": "Manual: Webinars", "section": "Manual data", "type": "table"},
    "manual_enewsletter": {"label": "Manual: eNewsletter ads", "section": "Manual data", "type": "table"},
    "manual_retargeting": {"label": "Manual: Retargeting", "section": "Manual data", "type": "table"},
    "manual_custom_email": {"label": "Manual: Custom email", "section": "Manual data", "type": "table"},
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


@st.cache_data
def cached_sources() -> dict:
    return load_report_sources()


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


def format_integer(value: float | int) -> str:
    return f"{int(value):,}"


def format_percent(value: float | int) -> str:
    return f"{float(value):.2%}"


def safe_filename(value: str) -> str:
    cleaned = "".join(char if char.isalnum() else "_" for char in value.lower())
    return "_".join(part for part in cleaned.split("_") if part)


def all_report_element_ids() -> list[str]:
    return list(REPORT_ELEMENTS.keys())


def table_report_element_ids() -> list[str]:
    return [key for key, value in REPORT_ELEMENTS.items() if value["type"] == "table"]


def no_visual_report_element_ids() -> list[str]:
    return [key for key, value in REPORT_ELEMENTS.items() if value["type"] != "visualization"]


def set_report_elements(elements: list[str]) -> None:
    st.session_state["selected_report_elements"] = elements
    selected = set(elements)
    for element_id in all_report_element_ids():
        st.session_state[f"include_{element_id}"] = element_id in selected


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


def element_selected(element_id: str) -> bool:
    return element_id in set(selected_report_elements())


def ensure_report_element_widget_state() -> None:
    selected = set(selected_report_elements())
    for element_id in all_report_element_ids():
        st.session_state.setdefault(f"include_{element_id}", element_id in selected)


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

        st.markdown("**Webinars**")
        webinar_registrations = manual_number("Registrations", "manual_webinar_registrations")
        webinar_reports_url = st.text_input("Webinar.net reports URL", key="manual_webinar_reports_url")

        st.markdown("**eNewsletter Ads**")
        newsletter_delivered = manual_number("Newsletters delivered", "manual_newsletter_delivered")
        newsletter_opened = manual_number("Newsletters opened", "manual_newsletter_opened")
        newsletter_clicks = manual_number("Ad clicks", "manual_newsletter_clicks")
        newsletter_creative = st.text_area("Ad creative notes or URL", key="manual_newsletter_creative")
        newsletter_url = st.text_input(
            "Most recent newsletter URL",
            key="manual_newsletter_url",
        )

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
        lead_list = st.text_area("List of leads received", key="manual_lead_list")

    retargeting_ctr = retargeting_clicks / retargeting_impressions if retargeting_impressions else 0
    email_open_rate = email_opened / email_delivered if email_delivered else 0
    newsletter_open_rate = newsletter_opened / newsletter_delivered if newsletter_delivered else 0
    newsletter_ctr = newsletter_clicks / newsletter_delivered if newsletter_delivered else 0

    return {
        "manual_webinars": {
            "title": "Webinars",
            "rows": [
                ("Registrations", format_integer(webinar_registrations)),
                ("Webinar.net reports URL", webinar_reports_url),
            ],
        },
        "manual_enewsletter": {
            "title": "eNewsletter Ads",
            "rows": [
                ("Newsletters delivered", format_integer(newsletter_delivered)),
                ("Newsletters opened", format_integer(newsletter_opened)),
                ("Open rate", format_percent(newsletter_open_rate)),
                ("Ad clicks", format_integer(newsletter_clicks)),
                ("CTR", format_percent(newsletter_ctr)),
                ("Ad creative", newsletter_creative),
                ("Most recent newsletter URL", newsletter_url),
            ],
        },
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
            "rows": [("List of leads received", lead_list)],
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
    sources = cached_sources().get("categories", {})
    rows = []
    for key, category in sources.items():
        if key == "website_ads":
            status = "Live"
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


with st.sidebar:
    st.header("Report")
    advertiser_source = st.radio("Advertiser source", ["Local CSV", "Google Ad Manager"])
    include_house = st.checkbox("Include house advertisers", value=False)

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

    selected_name = st.selectbox("Advertiser", advertisers["advertiser_name"].tolist())
    selected = advertisers.loc[advertisers["advertiser_name"] == selected_name].iloc[0].to_dict()
    gam_advertiser_id = str(selected.get("gam_advertiser_id") or selected.get("advertiser_id"))

    default_end_date = date.today() - timedelta(days=1)
    start_date = st.date_input("Start date", default_end_date - timedelta(days=29))
    end_date = st.date_input("End date", default_end_date)

    if start_date > end_date:
        st.error("Start date must be before end date.")
        st.stop()

    try:
        with st.spinner("Loading campaigns..."):
            campaigns = cached_campaigns(gam_advertiser_id, start_date, end_date)
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
    output_mode = st.radio("Output", ["Dashboard", "Power BI export"], horizontal=False)
    run_report = st.button("Run report", type="primary", use_container_width=True)

manual_data = collect_manual_data()

report_key = (
    str(selected.get("advertiser_id")),
    str(gam_advertiser_id),
    start_date.isoformat(),
    end_date.isoformat(),
    str(campaign_id or ""),
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
            report = build_advertiser_report(request, allow_empty_ga4=True)
    except GAMConfigError as exc:
        st.error(str(exc))
        st.stop()
    st.session_state["report_key"] = report_key
    st.session_state["report"] = report
    set_report_elements(all_report_element_ids())
else:
    report = st.session_state["report"]

with st.sidebar:
    st.divider()
    st.header("PDF Selection")
    if st.button("Select all", use_container_width=True):
        set_report_elements(all_report_element_ids())
    if st.button("Exclude visuals", use_container_width=True):
        set_report_elements(no_visual_report_element_ids())
    section_options = sorted({value["section"] for value in REPORT_ELEMENTS.values()})
    chosen_sections = st.multiselect(
        "Selection by PDF section",
        section_options,
        default=[],
    )
    if st.button("Apply section selection", use_container_width=True):
        apply_section_selection(chosen_sections)

frames = export_report_frames(report)
gam_ads = prepare_gam_frame(report.gam_ad_performance)

if output_mode == "Power BI export":
    st.subheader("Power BI tables")
    for name, frame in frames.items():
        if name == "ga4_website_performance":
            continue
        st.write(f"**{name}**")
        st.dataframe(frame, use_container_width=True, hide_index=True)
    st.download_button(
        "Download GAM performance CSV",
        data=frames["gam_ad_performance"].to_csv(index=False),
        file_name=f"{selected['advertiser_id']}_gam_ad_performance.csv",
        mime="text/csv",
        use_container_width=True,
    )
    st.stop()

st.subheader("Website Ads")
if gam_ads.empty:
    st.info("No GAM rows returned for this advertiser, campaign, and date range.")
    st.stop()

total_impressions = gam_ads["ad_impressions"].sum()
total_clicks = gam_ads["ad_clicks"].sum()
weighted_ctr = total_clicks / total_impressions if total_impressions else 0
active_campaigns = gam_ads["campaign_id"].nunique(dropna=True)
active_creatives = gam_ads["creative_id"].nunique(dropna=True)

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

campaign_summary = (
    gam_ads.groupby("campaign_name", dropna=False)[["ad_impressions", "ad_clicks"]]
    .sum()
    .reset_index()
)
campaign_summary["ctr"] = campaign_summary["ad_clicks"] / campaign_summary["ad_impressions"].replace(0, pd.NA)
campaign_summary["ctr"] = campaign_summary["ctr"].fillna(0)
campaign_summary = campaign_summary.sort_values("ad_impressions", ascending=False, ignore_index=True)

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

creative_summary = (
    gam_ads.groupby(["creative_id", "creative_name"], dropna=False)[["ad_impressions", "ad_clicks"]]
    .sum()
    .reset_index()
)
creative_summary["ctr"] = creative_summary["ad_clicks"] / creative_summary["ad_impressions"].replace(0, pd.NA)
creative_summary["ctr"] = creative_summary["ctr"].fillna(0)
creative_summary = creative_summary.sort_values("ad_impressions", ascending=False, ignore_index=True)

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
try:
    with st.spinner("Loading creative assets..."):
        creative_assets = cached_creative_assets(creative_ids)
except GAMConfigError as exc:
    st.warning(str(exc))
    creative_assets = pd.DataFrame()

image_creatives = image_creative_stats(gam_ads, creative_assets)

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

st.subheader("Manual Entries")
for manual_element_id in [
    "manual_webinars",
    "manual_enewsletter",
    "manual_retargeting",
    "manual_custom_email",
    "manual_lead_gen",
]:
    render_manual_section(manual_element_id, manual_data)

with st.expander("Source roadmap", expanded=False):
    render_source_status()

selected_pdf_elements = selected_report_elements()
st.markdown('<div class="section-label">PDF Export</div>', unsafe_allow_html=True)
st.caption(f"{len(selected_pdf_elements)} of {len(REPORT_ELEMENTS)} report elements selected.")
try:
    pdf_bytes = build_pdf_report(
        advertiser_name=str(selected["advertiser_name"]),
        start_date=start_date,
        end_date=end_date,
        campaign_name=campaign_name,
        gam_ads=gam_ads,
        creative_assets=image_creatives,
        manual_data=manual_data,
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
