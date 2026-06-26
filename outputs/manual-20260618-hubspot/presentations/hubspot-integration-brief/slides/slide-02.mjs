import { C, bullet, footer, rect, text, titleBlock } from "./shared.mjs";

export async function slide02(presentation, ctx) {
  const slide = presentation.slides.add();
  rect(ctx, slide, 0, 0, 1280, 720, C.white);
  titleBlock(
    ctx, slide, "Scope & purpose",
    "The project replaces manual source-hopping with one advertiser-level report.",
    "A Streamlit dashboard produces a live preview, client-ready PDF, and Power BI-ready tables."
  );

  bullet(ctx, slide, 62, 226, "One advertiser, one reporting window", "Select the advertiser, campaign, and dates once; connected sources resolve the supporting evidence.", 510);
  bullet(ctx, slide, 62, 330, "Client-facing, not analyst-facing", "The report emphasizes understandable KPIs, charts, creative evidence, and source links rather than raw platform exports.", 510);
  bullet(ctx, slide, 62, 434, "Automation with controlled fallbacks", "GAM and Webinar.net are automated today; manual entry remains only where source access is not yet available.", 510);

  rect(ctx, slide, 636, 216, 570, 388, C.paleBlue);
  text(ctx, slide, "REPORTING FLOW", 662, 238, 300, 22, { fontSize: 13, bold: true, color: C.blue });
  const nodes = [
    ["Source systems", "GAM\nWebinar.net\nHubSpot", 260],
    ["Normalize", "Advertiser\nCampaign\nDate range", 365],
    ["Preview", "KPIs\nCharts\nTables\nCreative", 470],
    ["Deliver", "PDF report\nPower BI export", 575],
  ];
  nodes.forEach(([head, body, y], i) => {
    rect(ctx, slide, 668, y, 500, 78, C.white, `flow-node-${i}`, C.gray, 1);
    rect(ctx, slide, 668, y, 10, 78, i === 0 ? C.orange : i === 3 ? C.lime : C.blue);
    text(ctx, slide, head, 696, y + 12, 150, 24, { fontSize: 17, bold: true, color: C.navy });
    text(ctx, slide, body, 850, y + 10, 285, 56, { fontSize: 15, color: C.charcoal, valign: "middle" });
  });
  footer(ctx, slide, 2, "Current project: Streamlit dashboard + PDF export + Power BI export");
  return slide;
}
