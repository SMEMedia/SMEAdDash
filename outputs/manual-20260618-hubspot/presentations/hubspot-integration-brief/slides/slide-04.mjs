import { C, footer, rect, step, text, titleBlock } from "./shared.mjs";

export async function slide04(presentation, ctx) {
  const slide = presentation.slides.add();
  rect(ctx, slide, 0, 0, 1280, 720, C.white);
  titleBlock(
    ctx, slide, "Attribution contract",
    "Reliable advertiser matching depends on a small naming and link convention.",
    "The API can return totals; the project must determine which email and which clicked URL belong to each advertiser."
  );

  step(ctx, slide, 1, "Find candidate emails", "Filter by published date, email name, campaign name, type, and subject.", 68, 226, 500, C.blue);
  step(ctx, slide, 2, "Match the advertiser", "Preferred: HubSpot campaign/name contains advertiser. Fallback: maintained advertiser-to-email ID mapping.", 68, 344, 500, C.teal);
  step(ctx, slide, 3, "Identify the advertiser link", "Match CLICK event URL to the advertiser destination domain or configured URL pattern.", 68, 462, 500, C.orange);

  rect(ctx, slide, 650, 220, 560, 362, C.navy);
  text(ctx, slide, "MINIMUM DATA CONTRACT", 678, 244, 300, 22, { fontSize: 13, bold: true, color: C.lime });
  const rows = [
    ["Advertiser key", "Canonical advertiser name / ID"],
    ["Email key", "HubSpot email ID + campaign ID"],
    ["Match fields", "Name, subject, campaignName, publishedAt"],
    ["Ad-link rule", "Destination domain or exact URL pattern"],
    ["Creative evidence", "webversion.url or content asset URL"],
  ];
  rows.forEach(([left, right], idx) => {
    const y = 286 + idx * 52;
    text(ctx, slide, left, 680, y, 155, 25, { fontSize: 15, bold: true, color: C.white });
    text(ctx, slide, right, 844, y, 330, 34, { fontSize: 15, color: idx === 3 ? C.lime : C.white });
  });
  rect(ctx, slide, 650, 600, 560, 46, C.paleOrange);
  text(ctx, slide, "Decision needed: confirm the naming convention and destination-link ownership source.", 670, 611, 520, 25, {
    fontSize: 15, bold: true, color: C.charcoal,
  });
  footer(ctx, slide, 4, "CLICK events include the clicked URL; advertiser attribution is an SME business rule.");
  return slide;
}
