import { C, footer, line, rect, text, titleBlock } from "./shared.mjs";

export async function slide05(presentation, ctx) {
  const slide = presentation.slides.add();
  rect(ctx, slide, 0, 0, 1280, 720, C.white);
  titleBlock(
    ctx, slide, "Implementation plan",
    "A five-stage read-only pipeline can reach production in controlled increments.",
    "Each stage has a testable output before the dashboard or PDF is changed."
  );

  const stages = [
    ["1", "Connect", "Private app token\nSecret storage\nConnection test", C.orange],
    ["2", "Inventory", "List emails\nDate filters\nCampaign metadata", C.blue],
    ["3", "Measure", "Delivered / opens\nRatios\nCLICK events by URL", C.teal],
    ["4", "Attribute", "Advertiser mapping\nLink ownership\nCreative / web version", C.navy],
    ["5", "Publish", "Dashboard elements\nPDF selections\nPower BI tables", C.lime],
  ];
  stages.forEach(([num, head, body, color], idx) => {
    const x = 54 + idx * 238;
    rect(ctx, slide, x, 238, 210, 320, idx === 4 ? C.paleLime : C.paleBlue, `stage-${num}`);
    rect(ctx, slide, x, 238, 210, 12, color);
    text(ctx, slide, num, x + 18, 270, 44, 44, { fontSize: 32, bold: true, color });
    text(ctx, slide, head, x + 18, 325, 176, 34, { fontSize: 23, bold: true, color: C.navy });
    text(ctx, slide, body, x + 18, 380, 176, 110, { fontSize: 16, color: C.charcoal });
    if (idx < stages.length - 1) line(ctx, slide, x + 210, 390, 28, 3, C.gray);
  });

  rect(ctx, slide, 54, 584, 1162, 62, C.navy);
  text(ctx, slide, "API CALLS", 76, 601, 105, 20, { fontSize: 12, bold: true, color: C.lime });
  text(
    ctx, slide,
    "GET /marketing/emails/2026-03  ·  GET /marketing/emails/2026-03/statistics/list  ·  GET /email/public/v1/events",
    194, 596, 990, 30,
    { fontSize: 15, color: C.white, typeface: ctx.fonts.mono, valign: "middle" }
  );
  footer(ctx, slide, 5, "Validation: reconcile 3 known emails against HubSpot UI before enabling client reports.");
  return slide;
}
