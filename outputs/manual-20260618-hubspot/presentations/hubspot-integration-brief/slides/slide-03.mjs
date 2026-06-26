import { C, footer, line, rect, text, titleBlock } from "./shared.mjs";

export async function slide03(presentation, ctx) {
  const slide = presentation.slides.add();
  rect(ctx, slide, 0, 0, 1280, 720, C.white);
  titleBlock(
    ctx, slide, "HubSpot's role",
    "HubSpot supplies the email evidence clients cannot get from GAM or Webinar.net.",
    "The integration covers both recurring eNewsletter placements and dedicated custom emails."
  );

  const cols = [
    {
      x: 56, color: C.blue, title: "eNewsletter Ads",
      items: [
        ["Delivery", "Delivered, opened, open rate"],
        ["Ad response", "Clicks on the advertiser's destination URL"],
        ["Evidence", "Ad creative + most recent newsletter web version"],
        ["Breakdown", "Performance by email and advertiser link"],
      ],
    },
    {
      x: 652, color: C.orange, title: "Custom Email",
      items: [
        ["Delivery", "Delivered, opened, open rate"],
        ["Engagement", "Total clicks, click rate, CTR"],
        ["Evidence", "Rendered screenshot or web-version link"],
        ["Breakdown", "Performance by send, campaign, and date"],
      ],
    },
  ];
  cols.forEach((col) => {
    rect(ctx, slide, col.x, 220, 572, 390, C.white, undefined, C.gray, 1);
    rect(ctx, slide, col.x, 220, 572, 54, col.color);
    text(ctx, slide, col.title, col.x + 20, 232, 530, 32, { fontSize: 24, bold: true, color: C.white });
    col.items.forEach(([label, detail], idx) => {
      const y = 298 + idx * 72;
      text(ctx, slide, label.toUpperCase(), col.x + 22, y, 130, 18, { fontSize: 12, bold: true, color: col.color });
      text(ctx, slide, detail, col.x + 160, y - 2, 380, 42, { fontSize: 17, color: C.charcoal });
      if (idx < col.items.length - 1) line(ctx, slide, col.x + 22, y + 52, 526, 1, C.gray);
    });
  });
  footer(ctx, slide, 3, "HubSpot Marketing Emails API: email metadata, stats, content, and webversion fields");
  return slide;
}
