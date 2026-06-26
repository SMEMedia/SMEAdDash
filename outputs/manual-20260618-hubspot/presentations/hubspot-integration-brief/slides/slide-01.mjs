import { C, footer, line, logo, rect, text } from "./shared.mjs";

export async function slide01(presentation, ctx) {
  const slide = presentation.slides.add();
  rect(ctx, slide, 0, 0, 1280, 720, C.white, "background");
  rect(ctx, slide, 0, 0, 30, 720, C.navy, "left-band");
  rect(ctx, slide, 30, 0, 10, 720, C.lime, "left-accent");
  await logo(ctx, slide, 1030, 40, 190, 72);

  text(ctx, slide, "HUBSPOT INTEGRATION BRIEF", 78, 74, 520, 28, {
    fontSize: 15, bold: true, color: C.blue,
  });
  text(ctx, slide, "Close the email reporting gap with one controlled data connection.", 78, 126, 920, 150, {
    fontSize: 52, bold: true, color: C.navy, typeface: ctx.fonts.title,
  });
  text(ctx, slide, "Advertiser Dashboard Automation", 80, 292, 650, 34, {
    fontSize: 23, color: C.charcoal,
  });

  line(ctx, slide, 80, 360, 1120, 2, C.gray);
  const labels = [
    ["LIVE", "Google Ad Manager", C.blue],
    ["LIVE", "Webinar.net", C.teal],
    ["NEXT", "HubSpot email data", C.orange],
  ];
  labels.forEach(([status, name, color], index) => {
    const x = 80 + index * 355;
    rect(ctx, slide, x, 398, 325, 100, index === 2 ? C.paleOrange : C.paleBlue);
    text(ctx, slide, status, x + 18, 414, 72, 22, { fontSize: 13, bold: true, color });
    text(ctx, slide, name, x + 18, 446, 288, 34, { fontSize: 22, bold: true, color: C.navy });
  });

  rect(ctx, slide, 80, 548, 1120, 74, C.navy);
  text(ctx, slide, "MEETING OUTCOME", 102, 563, 190, 20, { fontSize: 13, bold: true, color: C.lime });
  text(ctx, slide, "Approve access, confirm attribution rules, and assign implementation owners.", 300, 557, 860, 36, {
    fontSize: 23, bold: true, color: C.white, valign: "middle",
  });
  footer(ctx, slide, 1, "Prepared for HubSpot access and implementation discussion | June 2026");
  return slide;
}
