from __future__ import annotations

from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

import pandas as pd


BRAND = {
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


def build_pdf_report(
    advertiser_name: str,
    start_date: date,
    end_date: date,
    campaign_name: str | None,
    gam_ads: pd.DataFrame,
    webinar_data: pd.DataFrame | None = None,
    logo_path: Path | None = None,
    creative_assets: pd.DataFrame | None = None,
    hubspot_email_data: pd.DataFrame | None = None,
    manual_data: dict[str, dict[str, Any]] | None = None,
    sections: list[str] | None = None,
    elements: list[str] | None = None,
) -> bytes:
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import (
            Image,
            KeepTogether,
            PageBreak,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ModuleNotFoundError as exc:
        raise RuntimeError("Install reportlab to enable PDF export: pip install -r requirements.txt") from exc

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.55 * inch,
        leftMargin=0.55 * inch,
        topMargin=0.52 * inch,
        bottomMargin=0.48 * inch,
        title=f"{advertiser_name} Advertiser Report",
    )
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="ReportTitle",
            parent=styles["Title"],
            alignment=TA_CENTER,
            textColor=_color("navy"),
            fontName="Helvetica-Bold",
            fontSize=21,
            leading=25,
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Kicker",
            parent=styles["Normal"],
            alignment=TA_CENTER,
            textColor=_color("charcoal"),
            fontSize=9,
            leading=12,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Section",
            parent=styles["Heading2"],
            textColor=_color("navy"),
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            spaceBefore=14,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="MetricValue",
            parent=styles["Normal"],
            alignment=TA_CENTER,
            textColor=_color("navy"),
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=19,
        )
    )
    styles.add(
        ParagraphStyle(
            name="MetricLabel",
            parent=styles["Normal"],
            alignment=TA_CENTER,
            textColor=_color("charcoal"),
            fontSize=8,
            leading=10,
        )
    )
    styles.add(
        ParagraphStyle(
            name="TableHeader",
            parent=styles["BodyText"],
            textColor=colors.white,
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
        )
    )

    prepared = _prepare_frame(gam_ads)
    webinar_frame = _prepare_webinar_frame(webinar_data)
    email_frame = _prepare_email_frame(hubspot_email_data)
    totals = _totals(prepared)
    campaign_summary = _campaign_summary(prepared)
    creative_summary = _creative_summary(prepared)
    daily_summary = _daily_summary(prepared)
    selected_sections = set(sections or ["kpis", "daily", "campaigns"])
    selected_elements = set(elements or _elements_from_sections(selected_sections))

    story = []
    story.extend(_header(styles, advertiser_name, start_date, end_date, campaign_name, logo_path))
    story.append(Spacer(1, 0.16 * inch))
    metric_keys = [
        key for key in ["kpi_impressions", "kpi_clicks", "kpi_ctr", "kpi_campaigns", "kpi_creatives"]
        if key in selected_elements
    ]
    if metric_keys:
        story.append(Paragraph("Website Ad Metrics", styles["Section"]))
        story.append(_metric_table(styles, totals, metric_keys))
    if "kpi_webinar_registrations" in selected_elements or "table_webinars" in selected_elements:
        story.append(Paragraph("Webinars", styles["Section"]))
    if "kpi_webinar_registrations" in selected_elements:
        story.append(
            _metric_table(
                styles,
                [("kpi_webinar_registrations", "Total registrations", f"{int(webinar_frame['Registrations'].sum()):,}")],
                ["kpi_webinar_registrations"],
            )
        )
    if "table_webinars" in selected_elements:
        story.append(_webinar_table(webinar_frame))
    chart_keys = [
        key for key in [
            "chart_daily_delivery",
            "chart_daily_ctr",
            "chart_campaign_performance",
            "chart_campaign_ctr",
            "chart_creative_performance",
            "chart_creative_ctr",
        ]
        if key in selected_elements
    ]
    if chart_keys:
        story.append(Paragraph("Dashboard Visualizations", styles["Section"]))
        story.extend(_visualization_story(prepared, chart_keys))
    if "image_creatives" in selected_elements:
        story.append(Paragraph("Image Creative Previews", styles["Section"]))
        story.extend(_image_creative_story(styles, creative_assets))

    email_metric_keys = [
        key for key in [
            "kpi_email_delivered",
            "kpi_email_opened",
            "kpi_email_open_rate",
            "kpi_email_clicks",
            "kpi_email_click_rate",
        ]
        if key in selected_elements
    ]
    email_chart_keys = [
        key for key in [
            "chart_email_ad_type",
            "chart_email_rates_ad_type",
            "chart_email_time",
            "chart_email_rates_time",
        ]
        if key in selected_elements
    ]
    email_table_keys = [
        key for key in ["manual_enewsletter", "manual_custom_email"]
        if key in selected_elements
    ]
    if not email_frame.empty and (email_metric_keys or email_chart_keys or email_table_keys):
        story.append(Paragraph("HubSpot Email", styles["Section"]))
        if email_metric_keys:
            story.append(_metric_table(styles, _email_totals(email_frame), email_metric_keys))
        if email_chart_keys:
            story.extend(_email_visualization_story(email_frame, email_chart_keys))
        if email_table_keys:
            story.append(_email_table(email_frame, email_table_keys))

    manual_keys = [
        key for key in [
            "manual_retargeting",
            "manual_lead_gen",
        ]
        if key in selected_elements
    ]
    if manual_keys:
        story.append(Paragraph("Manual Entries", styles["Section"]))
        story.extend(_manual_data_story(styles, manual_data or {}, manual_keys))

    if "table_campaign_detail" in selected_elements or "table_creative_detail" in selected_elements:
        story.append(PageBreak())
    if "table_campaign_detail" in selected_elements:
        story.append(Paragraph("Detailed Performance", styles["Section"]))
        story.append(_summary_table(campaign_summary, ["Campaign", "Impressions", "Clicks", "CTR"], max_rows=40))
    if "table_creative_detail" in selected_elements:
        story.append(Paragraph("Detailed Creative Performance", styles["Section"]))
        story.append(_summary_table(creative_summary, ["Creative", "Impressions", "Clicks", "CTR"], max_rows=40))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()


def _header(styles, advertiser_name, start_date, end_date, campaign_name, logo_path):
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.platypus import Image, Paragraph, Table, TableStyle

    title = Paragraph(advertiser_name, styles["ReportTitle"])
    campaign = f"<br/>Campaign: {campaign_name}" if campaign_name else ""
    subtitle = Paragraph(
        f"Advertiser Performance Report<br/>{start_date:%B %d, %Y} to {end_date:%B %d, %Y}{campaign}",
        styles["Kicker"],
    )
    center = [title, subtitle]

    logo = ""
    if logo_path and logo_path.exists():
        logo = Image(str(logo_path), width=1.2 * inch, height=0.5 * inch, kind="proportional")

    table = Table([["", center, logo]], colWidths=[1.35 * inch, 4.7 * inch, 1.35 * inch])
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (1, 0), (1, 0), "CENTER"),
                ("ALIGN", (2, 0), (2, 0), "RIGHT"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LINEBELOW", (0, 0), (-1, -1), 1.4, _color("lime")),
            ]
        )
    )
    return [table]


def _metric_table(styles, totals, metric_keys: list[str]):
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, Table, TableStyle

    total_map = {key: (label, value) for key, label, value in totals}
    cells = []
    for key in metric_keys:
        label, value = total_map[key]
        cells.append([Paragraph(value, styles["MetricValue"]), Paragraph(label, styles["MetricLabel"])])
    table = Table([cells], colWidths=[6.6 * inch / max(len(cells), 1)] * len(cells))
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), _color("pale_blue")),
                ("BOX", (0, 0), (-1, -1), 0.8, _color("blue")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.white),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    return table


def _summary_table(frame: pd.DataFrame, headings: list[str], max_rows: int):
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, Table, TableStyle

    styles = getSampleStyleSheet()
    header_style = ParagraphStyle(
        "SummaryTableHeader",
        parent=styles["BodyText"],
        textColor=colors.white,
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
    )
    body = frame.head(max_rows).copy()
    rows = [[Paragraph(str(heading), header_style) for heading in headings]]
    for _, row in body.iterrows():
        rows.append([Paragraph(str(value), styles["BodyText"]) for value in row.tolist()])

    col_widths = [2.9 * inch, 1.15 * inch, 1.0 * inch, 0.85 * inch]
    table = Table(rows, colWidths=col_widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _color("blue")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.35, _color("gray")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _color("pale_blue")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _webinar_table(frame: pd.DataFrame):
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, Table, TableStyle
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet

    styles = getSampleStyleSheet()
    header_style = ParagraphStyle(
        "WebinarTableHeader",
        parent=styles["BodyText"],
        textColor=colors.white,
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
    )
    rows = [[Paragraph("Webinar", header_style), Paragraph("Registrations", header_style), Paragraph("URL", header_style)]]
    if frame.empty:
        rows.append([Paragraph("No matched webinars.", styles["BodyText"]), "0", ""])
    else:
        for _, row in frame.head(20).iterrows():
            rows.append(
                [
                    Paragraph(str(row.get("Webinar", "")), styles["BodyText"]),
                    Paragraph(f"{int(row.get('Registrations', 0)):,}", styles["BodyText"]),
                    Paragraph(str(row.get("URL", "")), styles["BodyText"]),
                ]
            )

    table = Table(rows, colWidths=[3.1 * inch, 1.1 * inch, 2.3 * inch], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _color("blue")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.35, _color("gray")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _color("pale_blue")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _email_table(frame: pd.DataFrame, table_keys: list[str]):
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, Table, TableStyle

    styles = getSampleStyleSheet()
    header_style = ParagraphStyle(
        "EmailTableHeader",
        parent=styles["BodyText"],
        textColor=colors.white,
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
    )
    selected_types = []
    if "manual_enewsletter" in table_keys:
        selected_types.append("eNewsletter Ad")
    if "manual_custom_email" in table_keys:
        selected_types.append("Custom Email")
    body = frame[frame["report_type"].isin(selected_types)].copy() if selected_types else frame.copy()
    rows = [
        [
            Paragraph("Type", header_style),
            Paragraph("Date", header_style),
            Paragraph("Ad Type", header_style),
            Paragraph("Delivered", header_style),
            Paragraph("Opened", header_style),
            Paragraph("Clicks", header_style),
            Paragraph("Open Rate", header_style),
            Paragraph("Click Rate", header_style),
        ]
    ]
    for _, row in body.head(24).iterrows():
        rows.append(
            [
                Paragraph(escape(str(row.get("report_type", ""))), styles["BodyText"]),
                Paragraph(escape(str(row.get("placement_date_label", ""))), styles["BodyText"]),
                Paragraph(escape(str(row.get("ad_type", ""))), styles["BodyText"]),
                Paragraph(f"{int(float(row.get('delivered', 0))):,}", styles["BodyText"]),
                Paragraph(f"{int(float(row.get('opened', 0))):,}", styles["BodyText"]),
                Paragraph(f"{int(float(row.get('clicks', 0))):,}", styles["BodyText"]),
                Paragraph(f"{float(row.get('open_rate', 0)):.2%}", styles["BodyText"]),
                Paragraph(f"{float(row.get('click_rate', 0)):.2%}", styles["BodyText"]),
            ]
        )

    table = Table(rows, colWidths=[0.9 * inch, 0.75 * inch, 1.15 * inch, 0.8 * inch, 0.75 * inch, 0.65 * inch, 0.75 * inch, 0.75 * inch], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _color("blue")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("GRID", (0, 0), (-1, -1), 0.35, _color("gray")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _color("pale_blue")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def _image_creative_story(styles, creative_assets: pd.DataFrame | None):
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.platypus import Image, Paragraph, Spacer, Table, TableStyle

    if creative_assets is None or creative_assets.empty:
        return [Paragraph("No image creative assets were found for this report.", styles["BodyText"])]

    story = []
    for _, creative in creative_assets.head(6).iterrows():
        image_url = str(creative.get("image_url", "") or "")
        image = _image_from_url(image_url, width=1.35 * inch)
        stats = Paragraph(
            "<b>{name}</b><br/>"
            "Type: {creative_type}<br/>"
            "Impressions: {impressions}<br/>"
            "Clicks: {clicks}<br/>"
            "CTR: {ctr}<br/>"
            "Size: {width} x {height}".format(
                name=str(creative.get("creative_name", "")),
                creative_type=str(creative.get("creative_type", "Image")),
                impressions=f"{int(float(creative.get('ad_impressions', 0))):,}",
                clicks=f"{int(float(creative.get('ad_clicks', 0))):,}",
                ctr=f"{float(creative.get('ctr', 0)):.2%}",
                width=str(creative.get("width", "") or "Unknown"),
                height=str(creative.get("height", "") or "Unknown"),
            ),
            styles["BodyText"],
        )
        table = Table([[image or "", stats]], colWidths=[1.55 * inch, 4.95 * inch])
        table.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.5, _color("blue")),
                    ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                    ("LEFTPADDING", (0, 0), (-1, -1), 7),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ]
            )
        )
        story.extend([table, Spacer(1, 0.1 * inch)])
    return story


def _manual_data_story(styles, manual_data: dict[str, dict[str, Any]], manual_keys: list[str]):
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

    story = []
    for key in manual_keys:
        section = manual_data.get(key, {})
        title = section.get("title", key.replace("_", " ").title())
        rows = section.get("rows", [])
        table_rows = [
            [Paragraph("Metric", styles["TableHeader"]), Paragraph("Value", styles["TableHeader"])]
        ]
        for metric, value in rows:
            display_value = str(value or "-").strip() or "-"
            table_rows.append(
                [
                    Paragraph(escape(str(metric)), styles["BodyText"]),
                    Paragraph(escape(display_value).replace("\n", "<br/>"), styles["BodyText"]),
                ]
            )
        if len(table_rows) == 1:
            table_rows.append(["No values entered.", ""])

        table = Table(table_rows, colWidths=[2.1 * inch, 4.4 * inch], repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), _color("blue")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.35, _color("gray")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _color("pale_blue")]),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.extend([Paragraph(escape(str(title)), styles["Section"]), table, Spacer(1, 0.1 * inch)])
    return story


def _image_from_url(url: str, width):
    if not url:
        return None
    try:
        import requests
        from PIL import Image as PILImage
        from reportlab.platypus import Image

        response = requests.get(url, timeout=10)
        response.raise_for_status()
        image_buffer = BytesIO(response.content)
        with PILImage.open(image_buffer) as pil_image:
            pil_image.load()
            image_width, image_height = pil_image.size
            normalized = BytesIO()
            pil_image.save(normalized, format="PNG")
        normalized.seek(0)
        height = width * image_height / image_width if image_width else width
        return Image(normalized, width=width, height=height)
    except Exception:
        return None

def _visualization_story(frame: pd.DataFrame, chart_keys: list[str]):
    from reportlab.lib.units import inch
    from reportlab.platypus import Image, Spacer

    if frame.empty:
        return []

    charts = []
    delivery = _delivery_chart_image(frame) if "chart_daily_delivery" in chart_keys else None
    if delivery:
        charts.extend([Image(delivery, width=6.4 * inch, height=2.7 * inch), Spacer(1, 0.12 * inch)])

    daily_ctr = _daily_ctr_chart_image(frame) if "chart_daily_ctr" in chart_keys else None
    if daily_ctr:
        charts.extend([Image(daily_ctr, width=6.4 * inch, height=2.7 * inch), Spacer(1, 0.12 * inch)])

    campaign = _campaign_chart_image(frame) if "chart_campaign_performance" in chart_keys else None
    if campaign:
        charts.extend([Image(campaign, width=6.4 * inch, height=2.9 * inch), Spacer(1, 0.12 * inch)])

    campaign_ctr = _campaign_ctr_chart_image(frame) if "chart_campaign_ctr" in chart_keys else None
    if campaign_ctr:
        charts.extend([Image(campaign_ctr, width=6.4 * inch, height=2.9 * inch), Spacer(1, 0.12 * inch)])

    creative = _creative_chart_image(frame) if "chart_creative_performance" in chart_keys else None
    if creative:
        charts.extend([Image(creative, width=6.4 * inch, height=2.9 * inch), Spacer(1, 0.12 * inch)])

    creative_ctr = _creative_ctr_chart_image(frame) if "chart_creative_ctr" in chart_keys else None
    if creative_ctr:
        charts.extend([Image(creative_ctr, width=6.4 * inch, height=2.9 * inch), Spacer(1, 0.12 * inch)])

    return charts


def _email_visualization_story(frame: pd.DataFrame, chart_keys: list[str]):
    from reportlab.lib.units import inch
    from reportlab.platypus import Image, Spacer

    charts = []
    metrics_ad_type = _email_metrics_by_ad_type_chart_image(frame) if "chart_email_ad_type" in chart_keys else None
    if metrics_ad_type:
        charts.extend([Image(metrics_ad_type, width=6.4 * inch, height=2.8 * inch), Spacer(1, 0.12 * inch)])

    rates_ad_type = _email_rates_by_ad_type_chart_image(frame) if "chart_email_rates_ad_type" in chart_keys else None
    if rates_ad_type:
        charts.extend([Image(rates_ad_type, width=6.4 * inch, height=2.8 * inch), Spacer(1, 0.12 * inch)])

    metrics_time = _email_metrics_over_time_chart_image(frame) if "chart_email_time" in chart_keys else None
    if metrics_time:
        charts.extend([Image(metrics_time, width=6.4 * inch, height=2.8 * inch), Spacer(1, 0.12 * inch)])

    rates_time = _email_rates_over_time_chart_image(frame) if "chart_email_rates_time" in chart_keys else None
    if rates_time:
        charts.extend([Image(rates_time, width=6.4 * inch, height=2.8 * inch), Spacer(1, 0.12 * inch)])
    return charts


def _email_metrics_by_ad_type_chart_image(frame: pd.DataFrame):
    summary = (
        frame.groupby("ad_type", dropna=False)[["delivered", "opened", "clicks"]]
        .sum()
        .sort_values("delivered", ascending=False)
    )
    if summary.empty:
        return None
    fig, ax = _figure(height=3.0)
    summary.plot(kind="bar", ax=ax, color=[BRAND["navy"], BRAND["teal"], BRAND["gold"]])
    ax.set_title("Email Metrics by Ad Type", color=BRAND["navy"], weight="bold")
    ax.set_xlabel("")
    ax.set_ylabel("Count")
    ax.tick_params(axis="x", rotation=25)
    ax.legend(["Delivered", "Opened", "Clicks"], frameon=False)
    return _fig_to_buffer(fig)


def _email_rates_by_ad_type_chart_image(frame: pd.DataFrame):
    summary = (
        frame.groupby("ad_type", dropna=False)[["delivered", "opened", "clicks"]]
        .sum()
        .reset_index()
        .sort_values("delivered", ascending=False)
    )
    if summary.empty:
        return None
    summary["open_rate"] = summary["opened"] / summary["delivered"].replace(0, pd.NA)
    summary["click_rate"] = summary["clicks"] / summary["delivered"].replace(0, pd.NA)
    summary[["open_rate", "click_rate"]] = summary[["open_rate", "click_rate"]].fillna(0)
    fig, ax = _figure(height=3.0)
    summary.set_index("ad_type")[["open_rate", "click_rate"]].plot(kind="bar", ax=ax, color=[BRAND["deep_teal"], BRAND["red"]])
    ax.set_title("Email Rates by Ad Type", color=BRAND["navy"], weight="bold")
    ax.set_xlabel("")
    ax.set_ylabel("Rate")
    ax.tick_params(axis="x", rotation=25)
    ax.yaxis.set_major_formatter(lambda value, _: f"{value:.0%}")
    ax.legend(["Open rate", "Click rate"], frameon=False)
    return _fig_to_buffer(fig)


def _email_metrics_over_time_chart_image(frame: pd.DataFrame):
    summary = (
        frame.dropna(subset=["placement_date"])
        .groupby("placement_date", dropna=False)[["delivered", "opened", "clicks"]]
        .sum()
        .sort_index()
    )
    if summary.empty:
        return None
    fig, ax = _figure(height=3.0)
    ax.plot(summary.index, summary["delivered"], color=BRAND["navy"], marker="o", label="Delivered")
    ax.plot(summary.index, summary["opened"], color=BRAND["teal"], marker="o", label="Opened")
    ax.plot(summary.index, summary["clicks"], color=BRAND["gold"], marker="o", label="Clicks")
    ax.set_title("Email Metrics Over Time", color=BRAND["navy"], weight="bold")
    ax.set_ylabel("Count")
    ax.tick_params(axis="x", rotation=35)
    ax.legend(frameon=False)
    return _fig_to_buffer(fig)


def _email_rates_over_time_chart_image(frame: pd.DataFrame):
    summary = (
        frame.dropna(subset=["placement_date"])
        .groupby("placement_date", dropna=False)[["delivered", "opened", "clicks"]]
        .sum()
        .reset_index()
        .sort_values("placement_date")
    )
    if summary.empty:
        return None
    summary["open_rate"] = summary["opened"] / summary["delivered"].replace(0, pd.NA)
    summary["click_rate"] = summary["clicks"] / summary["delivered"].replace(0, pd.NA)
    summary[["open_rate", "click_rate"]] = summary[["open_rate", "click_rate"]].fillna(0)
    fig, ax = _figure(height=3.0)
    ax.plot(summary["placement_date"], summary["open_rate"], color=BRAND["deep_teal"], marker="o", label="Open rate")
    ax.plot(summary["placement_date"], summary["click_rate"], color=BRAND["red"], marker="o", label="Click rate")
    ax.set_title("Email Rates Over Time", color=BRAND["navy"], weight="bold")
    ax.set_ylabel("Rate")
    ax.tick_params(axis="x", rotation=35)
    ax.yaxis.set_major_formatter(lambda value, _: f"{value:.0%}")
    ax.legend(frameon=False)
    return _fig_to_buffer(fig)


def _delivery_chart_image(frame: pd.DataFrame):
    daily = (
        frame.groupby("date", dropna=False)[["ad_impressions", "ad_clicks"]]
        .sum()
        .reset_index()
        .sort_values("date")
    )
    if daily.empty:
        return None
    fig, ax1 = _figure()
    ax1.plot(daily["date"], daily["ad_impressions"], color=BRAND["navy"], marker="o", label="Impressions")
    ax1.set_ylabel("Impressions", color=BRAND["navy"])
    ax1.tick_params(axis="x", rotation=35)
    ax2 = ax1.twinx()
    ax2.plot(daily["date"], daily["ad_clicks"], color=BRAND["gold"], marker="o", label="Clicks")
    ax2.set_ylabel("Clicks", color=BRAND["gold"])
    ax1.set_title("Daily Delivery", color=BRAND["navy"], weight="bold")
    return _fig_to_buffer(fig)


def _daily_ctr_chart_image(frame: pd.DataFrame):
    daily = (
        frame.groupby("date", dropna=False)[["ad_impressions", "ad_clicks"]]
        .sum()
        .reset_index()
        .sort_values("date")
    )
    if daily.empty:
        return None
    daily["ctr"] = daily["ad_clicks"] / daily["ad_impressions"].replace(0, pd.NA)
    daily["ctr"] = daily["ctr"].fillna(0)
    fig, ax = _figure()
    ax.plot(daily["date"], daily["ctr"], color=BRAND["deep_teal"], marker="o")
    ax.set_title("Daily CTR", color=BRAND["navy"], weight="bold")
    ax.set_ylabel("CTR")
    ax.tick_params(axis="x", rotation=35)
    ax.yaxis.set_major_formatter(lambda value, _: f"{value:.1%}")
    return _fig_to_buffer(fig)


def _campaign_chart_image(frame: pd.DataFrame):
    summary = (
        frame.groupby("campaign_name", dropna=False)[["ad_impressions", "ad_clicks"]]
        .sum()
        .reset_index()
        .sort_values("ad_impressions", ascending=True)
        .tail(10)
    )
    if summary.empty:
        return None
    fig, ax = _figure(height=3.2)
    ax.barh(summary["campaign_name"], summary["ad_impressions"], color=BRAND["blue"])
    ax.set_title("Campaign Impressions", color=BRAND["navy"], weight="bold")
    ax.set_xlabel("Impressions")
    return _fig_to_buffer(fig)


def _campaign_ctr_chart_image(frame: pd.DataFrame):
    summary = _rate_summary(frame, "campaign_name")
    if summary.empty:
        return None
    fig, ax = _figure(height=3.2)
    ax.barh(summary["name"], summary["ctr"], color=BRAND["teal"])
    ax.set_title("Campaign CTR", color=BRAND["navy"], weight="bold")
    ax.set_xlabel("CTR")
    ax.xaxis.set_major_formatter(lambda value, _: f"{value:.1%}")
    return _fig_to_buffer(fig)


def _creative_chart_image(frame: pd.DataFrame):
    summary = (
        frame.groupby("creative_name", dropna=False)[["ad_impressions", "ad_clicks"]]
        .sum()
        .reset_index()
        .sort_values("ad_impressions", ascending=True)
        .tail(10)
    )
    if summary.empty:
        return None
    fig, ax = _figure(height=3.2)
    ax.barh(summary["creative_name"], summary["ad_impressions"], color=BRAND["teal"])
    ax.set_title("Creative Impressions", color=BRAND["navy"], weight="bold")
    ax.set_xlabel("Impressions")
    return _fig_to_buffer(fig)


def _creative_ctr_chart_image(frame: pd.DataFrame):
    summary = _rate_summary(frame, "creative_name")
    if summary.empty:
        return None
    fig, ax = _figure(height=3.2)
    ax.barh(summary["name"], summary["ctr"], color=BRAND["deep_teal"])
    ax.set_title("Creative CTR", color=BRAND["navy"], weight="bold")
    ax.set_xlabel("CTR")
    ax.xaxis.set_major_formatter(lambda value, _: f"{value:.1%}")
    return _fig_to_buffer(fig)


def _rate_summary(frame: pd.DataFrame, group_col: str):
    summary = (
        frame.groupby(group_col, dropna=False)[["ad_impressions", "ad_clicks"]]
        .sum()
        .reset_index()
    )
    if summary.empty:
        return summary
    summary["ctr"] = summary["ad_clicks"] / summary["ad_impressions"].replace(0, pd.NA)
    summary["ctr"] = summary["ctr"].fillna(0)
    summary = summary.sort_values("ctr", ascending=True).tail(10)
    return summary.rename(columns={group_col: "name"})


def _figure(width=7.0, height=3.0):
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(width, height), dpi=160)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="x", color="#E5EBEF", linewidth=0.7)
    return fig, ax


def _fig_to_buffer(fig):
    import matplotlib.pyplot as plt

    buffer = BytesIO()
    fig.tight_layout()
    fig.savefig(buffer, format="png", bbox_inches="tight")
    plt.close(fig)
    buffer.seek(0)
    return buffer


def _prepare_email_frame(frame: pd.DataFrame | None) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame(
            columns=[
                "report_type",
                "placement_date",
                "placement_date_label",
                "ad_type",
                "delivered",
                "opened",
                "clicks",
                "open_rate",
                "click_rate",
            ]
        )
    prepared = frame.copy()
    for column in ["delivered", "opened", "clicks", "open_rate", "click_rate"]:
        if column not in prepared.columns:
            prepared[column] = 0
        prepared[column] = pd.to_numeric(prepared[column], errors="coerce").fillna(0)
    prepared["placement_date"] = pd.to_datetime(prepared.get("placement_date", ""), errors="coerce")
    prepared["placement_date_label"] = prepared["placement_date"].dt.strftime("%Y-%m-%d").fillna("")
    if "placement_ad_type" not in prepared.columns:
        prepared["placement_ad_type"] = ""
    prepared["ad_type"] = prepared["placement_ad_type"].fillna("").astype(str)
    if "report_type" not in prepared.columns:
        prepared["report_type"] = "Email"
    prepared.loc[prepared["ad_type"].str.strip() == "", "ad_type"] = prepared["report_type"].fillna("Email").astype(str)
    return prepared


def _email_totals(frame: pd.DataFrame) -> list[tuple[str, str, str]]:
    delivered = float(frame["delivered"].sum()) if not frame.empty else 0
    opened = float(frame["opened"].sum()) if not frame.empty else 0
    clicks = float(frame["clicks"].sum()) if not frame.empty else 0
    open_rate = opened / delivered if delivered else 0
    click_rate = clicks / delivered if delivered else 0
    return [
        ("kpi_email_delivered", "Emails delivered", f"{int(delivered):,}"),
        ("kpi_email_opened", "Emails opened", f"{int(opened):,}"),
        ("kpi_email_open_rate", "Open rate", f"{open_rate:.2%}"),
        ("kpi_email_clicks", "Clicks", f"{int(clicks):,}"),
        ("kpi_email_click_rate", "Click rate", f"{click_rate:.2%}"),
    ]


def _prepare_frame(frame: pd.DataFrame) -> pd.DataFrame:
    prepared = frame.copy()
    if prepared.empty:
        return prepared
    prepared["date"] = pd.to_datetime(prepared["date"], errors="coerce")
    prepared["campaign_name"] = prepared["campaign_name"].fillna("Unassigned")
    if "creative_id" not in prepared.columns:
        prepared["creative_id"] = pd.NA
    if "creative_name" not in prepared.columns:
        prepared["creative_name"] = "Unassigned"
    prepared["creative_name"] = prepared["creative_name"].fillna("Unassigned")
    prepared["ad_impressions"] = pd.to_numeric(prepared["ad_impressions"], errors="coerce").fillna(0)
    prepared["ad_clicks"] = pd.to_numeric(prepared["ad_clicks"], errors="coerce").fillna(0)
    return prepared


def _prepare_webinar_frame(frame: pd.DataFrame | None) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame(columns=["Webinar", "Registrations", "URL"])
    prepared = frame.copy()
    prepared["registrations"] = pd.to_numeric(prepared["registrations"], errors="coerce").fillna(0).astype(int)
    return prepared.rename(
        columns={
            "webinar_title": "Webinar",
            "registrations": "Registrations",
            "reports_url": "URL",
        }
    )[["Webinar", "Registrations", "URL"]]


def _totals(frame: pd.DataFrame) -> list[tuple[str, str]]:
    impressions = frame["ad_impressions"].sum() if not frame.empty else 0
    clicks = frame["ad_clicks"].sum() if not frame.empty else 0
    ctr = clicks / impressions if impressions else 0
    campaigns = frame["campaign_id"].nunique(dropna=True) if not frame.empty else 0
    creatives = frame["creative_id"].nunique(dropna=True) if not frame.empty and "creative_id" in frame.columns else 0
    return [
        ("kpi_impressions", "Ad impressions", f"{int(impressions):,}"),
        ("kpi_clicks", "Ad clicks", f"{int(clicks):,}"),
        ("kpi_ctr", "CTR", f"{ctr:.2%}"),
        ("kpi_campaigns", "Campaigns", f"{int(campaigns):,}"),
        ("kpi_creatives", "Creatives", f"{int(creatives):,}"),
    ]


def _elements_from_sections(sections: set[str]) -> list[str]:
    elements: list[str] = []
    if "kpis" in sections or "website_ads" in sections or "Website Ads" in sections:
        elements.extend([
            "kpi_impressions",
            "kpi_clicks",
            "kpi_ctr",
            "kpi_campaigns",
            "kpi_creatives",
        ])
    if "webinars" in sections or "Webinars" in sections:
        elements.extend(["kpi_webinar_registrations", "table_webinars"])
    if "visualizations" in sections or "website_ads" in sections or "Website Ads" in sections:
        elements.extend([
            "chart_daily_delivery",
            "chart_daily_ctr",
            "chart_campaign_performance",
            "chart_campaign_ctr",
            "chart_creative_performance",
            "chart_creative_ctr",
        ])
    if "hubspot_email" in sections or "HubSpot Email" in sections:
        elements.extend([
            "kpi_email_delivered",
            "kpi_email_opened",
            "kpi_email_open_rate",
            "kpi_email_clicks",
            "kpi_email_click_rate",
            "chart_email_ad_type",
            "chart_email_rates_ad_type",
            "chart_email_time",
            "chart_email_rates_time",
            "manual_enewsletter",
            "manual_custom_email",
        ])
    if "detail" in sections:
        elements.append("table_campaign_detail")
    if "creative_detail" in sections:
        elements.append("table_creative_detail")
    if "image_creatives" in sections:
        elements.append("image_creatives")
    return elements


def _campaign_summary(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["Campaign", "Impressions", "Clicks", "CTR"])
    summary = (
        frame.groupby("campaign_name", dropna=False)[["ad_impressions", "ad_clicks"]]
        .sum()
        .reset_index()
        .sort_values("ad_impressions", ascending=False)
    )
    summary["ctr"] = summary["ad_clicks"] / summary["ad_impressions"].replace(0, pd.NA)
    summary["ctr"] = summary["ctr"].fillna(0)
    return pd.DataFrame(
        {
            "Campaign": summary["campaign_name"],
            "Impressions": summary["ad_impressions"].map(lambda value: f"{int(value):,}"),
            "Clicks": summary["ad_clicks"].map(lambda value: f"{int(value):,}"),
            "CTR": summary["ctr"].map(lambda value: f"{float(value):.2%}"),
        }
    )


def _daily_summary(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["Date", "Impressions", "Clicks", "CTR"])
    summary = (
        frame.groupby("date", dropna=False)[["ad_impressions", "ad_clicks"]]
        .sum()
        .reset_index()
        .sort_values("date")
    )
    summary["ctr"] = summary["ad_clicks"] / summary["ad_impressions"].replace(0, pd.NA)
    summary["ctr"] = summary["ctr"].fillna(0)
    return pd.DataFrame(
        {
            "Date": summary["date"].dt.strftime("%Y-%m-%d"),
            "Impressions": summary["ad_impressions"].map(lambda value: f"{int(value):,}"),
            "Clicks": summary["ad_clicks"].map(lambda value: f"{int(value):,}"),
            "CTR": summary["ctr"].map(lambda value: f"{float(value):.2%}"),
        }
    )


def _creative_summary(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["Creative", "Impressions", "Clicks", "CTR"])
    summary = (
        frame.groupby("creative_name", dropna=False)[["ad_impressions", "ad_clicks"]]
        .sum()
        .reset_index()
        .sort_values("ad_impressions", ascending=False)
    )
    summary["ctr"] = summary["ad_clicks"] / summary["ad_impressions"].replace(0, pd.NA)
    summary["ctr"] = summary["ctr"].fillna(0)
    return pd.DataFrame(
        {
            "Creative": summary["creative_name"],
            "Impressions": summary["ad_impressions"].map(lambda value: f"{int(value):,}"),
            "Clicks": summary["ad_clicks"].map(lambda value: f"{int(value):,}"),
            "CTR": summary["ctr"].map(lambda value: f"{float(value):.2%}"),
        }
    )


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(_color("gray"))
    canvas.setFont("Helvetica", 7)
    canvas.drawString(doc.leftMargin, 0.27 * 72, "SME Advertiser Dashboard")
    canvas.drawRightString(doc.pagesize[0] - doc.rightMargin, 0.27 * 72, f"Page {doc.page}")
    canvas.restoreState()


def _color(name: str):
    from reportlab.lib import colors

    return colors.HexColor(BRAND[name])
