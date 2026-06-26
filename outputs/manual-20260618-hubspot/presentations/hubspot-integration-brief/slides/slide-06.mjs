import { C, footer, line, rect, text, titleBlock } from "./shared.mjs";

export async function slide06(presentation, ctx) {
  const slide = presentation.slides.add();
  rect(ctx, slide, 0, 0, 1280, 720, C.white);
  titleBlock(
    ctx, slide, "Exact permission request",
    "Approve a dedicated private app with the minimum scope required for email reporting.",
    "The app reads marketing-email content and events; it does not modify contacts, lists, workflows, or sends."
  );

  rect(ctx, slide, 58, 218, 755, 370, C.white, "permission-table", C.gray, 1);
  rect(ctx, slide, 58, 218, 755, 52, C.navy);
  text(ctx, slide, "ACCESS ITEM", 78, 234, 215, 22, { fontSize: 13, bold: true, color: C.white });
  text(ctx, slide, "REQUEST", 300, 234, 165, 22, { fontSize: 13, bold: true, color: C.white });
  text(ctx, slide, "WHY", 475, 234, 310, 22, { fontSize: 13, bold: true, color: C.white });
  const rows = [
    ["Creator role", "Super admin action", "A super admin must create/access the private app."],
    ["Private app", "Dedicated app", "Isolates token, scopes, logs, and rotation from other integrations."],
    ["Required scope", "content", "Required by Marketing Emails statistics/retrieval and Email Events endpoints."],
    ["Token delivery", "Access token", "Stored only in local .env and Streamlit Secrets; never committed."],
    ["Optional scope", "files", "Only if private File Manager assets must be downloaded for creative evidence."],
  ];
  rows.forEach((row, idx) => {
    const y = 270 + idx * 63;
    if (idx % 2 === 1) rect(ctx, slide, 58, y, 755, 63, C.paleBlue);
    text(ctx, slide, row[0], 78, y + 15, 205, 34, { fontSize: 15, bold: true, color: C.navy });
    text(ctx, slide, row[1], 300, y + 15, 160, 34, {
      fontSize: 14, bold: true, color: idx === 2 ? C.orange : C.charcoal, typeface: idx === 2 ? ctx.fonts.mono : ctx.fonts.body,
    });
    text(ctx, slide, row[2], 475, y + 10, 315, 44, { fontSize: 14, color: C.charcoal });
  });

  rect(ctx, slide, 850, 218, 366, 370, C.paleOrange);
  text(ctx, slide, "NOT REQUESTED", 874, 240, 250, 24, { fontSize: 14, bold: true, color: C.orange });
  const no = [
    "No contact read/write scopes",
    "No company or deal scopes",
    "No list or workflow scopes",
    "No email publishing or sending",
    "No HubSpot user login credentials",
    "No recipient-level data stored",
  ];
  no.forEach((item, idx) => {
    rect(ctx, slide, 876, 284 + idx * 46, 10, 10, C.orange);
    text(ctx, slide, item, 900, 278 + idx * 46, 286, 28, { fontSize: 16, color: C.charcoal });
  });
  footer(ctx, slide, 6, "Official HubSpot docs: private apps, scopes, Marketing Emails API, Email Events API");
  return slide;
}
