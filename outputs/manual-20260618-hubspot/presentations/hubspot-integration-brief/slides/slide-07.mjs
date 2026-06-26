import { C, bullet, footer, rect, text, titleBlock } from "./shared.mjs";

export async function slide07(presentation, ctx) {
  const slide = presentation.slides.add();
  rect(ctx, slide, 0, 0, 1280, 720, C.white);
  titleBlock(
    ctx, slide, "Decisions & next steps",
    "The meeting can unlock implementation by resolving four concrete items.",
    "Once access and attribution rules are confirmed, development can proceed without further platform discovery."
  );

  bullet(ctx, slide, 64, 230, "1. Approve the access pattern", "Dedicated HubSpot private app, content scope, named owner, and token-rotation owner.", 530, C.orange);
  bullet(ctx, slide, 64, 344, "2. Provide three validation emails", "One newsletter placement, one custom email, and one email with known advertiser-link clicks.", 530, C.blue);
  bullet(ctx, slide, 64, 458, "3. Confirm attribution rules", "Advertiser naming convention, HubSpot campaign usage, and destination URL/domain mapping.", 530, C.teal);

  rect(ctx, slide, 660, 220, 548, 386, C.navy);
  text(ctx, slide, "ACCEPTANCE CRITERIA", 688, 246, 280, 22, { fontSize: 14, bold: true, color: C.lime });
  const criteria = [
    "Email inventory reconciles to HubSpot",
    "Delivered, opened, and ratios match UI",
    "Advertiser-link clicks match known sample",
    "Latest newsletter web-version link resolves",
    "Creative screenshot renders in dashboard/PDF",
    "No recipient PII persists in exported tables",
  ];
  criteria.forEach((item, idx) => {
    rect(ctx, slide, 690, 294 + idx * 47, 18, 18, C.lime);
    text(ctx, slide, "✓", 690, 289 + idx * 47, 18, 24, { fontSize: 15, bold: true, color: C.navy, align: "center" });
    text(ctx, slide, item, 724, 287 + idx * 47, 450, 30, { fontSize: 16, color: C.white });
  });
  rect(ctx, slide, 64, 596, 544, 48, C.paleLime);
  text(ctx, slide, "Proposed owner split: HubSpot admin grants access; dashboard owner builds and validates.", 82, 607, 508, 26, {
    fontSize: 15, bold: true, color: C.navy,
  });
  footer(ctx, slide, 7, "Requested outcome: access approved, sample emails identified, and attribution convention documented.");
  return slide;
}
