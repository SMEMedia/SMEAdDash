export const C = {
  navy: "#153254",
  blue: "#5F8BB3",
  lime: "#D6D65E",
  gray: "#E8EDF0",
  mid: "#7E8A92",
  charcoal: "#29333A",
  white: "#FFFFFF",
  orange: "#FF5C35",
  teal: "#00788B",
  paleBlue: "#EEF5F8",
  paleLime: "#F6F8DF",
  paleOrange: "#FFF1EC",
};

export const SME_LOGO =
  "C:/Users/mschneider/OneDrive - SME/Desktop/Playground/Advertizing Dashboards/assets/sme_logo.png";

export function rect(ctx, slide, x, y, width, height, fill, name, lineFill = "#00000000", lineWidth = 0) {
  return ctx.addShape(slide, {
    x, y, width, height, fill, name,
    line: ctx.line(lineFill, lineWidth),
  });
}

export function text(ctx, slide, value, x, y, width, height, options = {}) {
  return ctx.addText(slide, {
    text: value,
    x, y, width, height,
    fontSize: options.fontSize ?? 24,
    color: options.color ?? C.charcoal,
    bold: options.bold ?? false,
    typeface: options.typeface ?? ctx.fonts.body,
    align: options.align ?? "left",
    valign: options.valign ?? "top",
    fill: options.fill ?? "#00000000",
    line: ctx.line(options.lineFill ?? "#00000000", options.lineWidth ?? 0),
    insets: options.insets ?? { left: 0, right: 0, top: 0, bottom: 0 },
    name: options.name,
  });
}

export function line(ctx, slide, x, y, width, height = 2, fill = C.gray, name) {
  return rect(ctx, slide, x, y, width, height, fill, name);
}

export function circle(ctx, slide, x, y, size, fill, name) {
  return ctx.addShape(slide, {
    x, y, width: size, height: size, geometry: "ellipse", fill, name,
    line: ctx.line("#00000000", 0),
  });
}

export function titleBlock(ctx, slide, kicker, title, subtitle = "") {
  circle(ctx, slide, 54, 40, 10, C.lime, "kicker-marker");
  text(ctx, slide, kicker.toUpperCase(), 72, 34, 360, 24, {
    fontSize: 14, bold: true, color: C.blue, valign: "middle", name: "kicker-label",
  });
  text(ctx, slide, title, 54, 72, 1170, 72, {
    fontSize: 38, bold: true, color: C.navy, typeface: ctx.fonts.title,
  });
  if (subtitle) {
    text(ctx, slide, subtitle, 56, 148, 1130, 42, {
      fontSize: 18, color: C.mid,
    });
  }
}

export function footer(ctx, slide, page, source = "") {
  line(ctx, slide, 54, 682, 1172, 1, C.gray, `footer-rule-${page}`);
  if (source) {
    text(ctx, slide, source, 56, 690, 1040, 16, {
      fontSize: 10, color: C.mid,
    });
  }
  text(ctx, slide, String(page).padStart(2, "0"), 1155, 688, 68, 18, {
    fontSize: 11, bold: true, color: C.blue, align: "right",
  });
}

export function bullet(ctx, slide, x, y, label, detail, width = 480, color = C.lime) {
  circle(ctx, slide, x, y + 7, 8, color);
  text(ctx, slide, label, x + 20, y, width - 20, 26, { fontSize: 19, bold: true, color: C.navy });
  text(ctx, slide, detail, x + 20, y + 29, width - 20, 52, { fontSize: 16, color: C.charcoal });
}

export function chip(ctx, slide, label, x, y, width, fill = C.paleBlue, color = C.navy) {
  rect(ctx, slide, x, y, width, 30, fill);
  text(ctx, slide, label, x + 10, y + 4, width - 20, 22, {
    fontSize: 13, bold: true, color, valign: "middle",
  });
}

export function step(ctx, slide, n, title, detail, x, y, width, color) {
  circle(ctx, slide, x, y, 34, color, `step-${n}-marker`);
  text(ctx, slide, String(n), x, y + 2, 34, 28, {
    fontSize: 16, bold: true, color: C.white, align: "center", valign: "middle",
  });
  text(ctx, slide, title, x + 48, y - 2, width - 48, 28, {
    fontSize: 18, bold: true, color: C.navy,
  });
  text(ctx, slide, detail, x + 48, y + 28, width - 48, 58, {
    fontSize: 14, color: C.charcoal,
  });
}

export async function logo(ctx, slide, x = 1072, y = 34, width = 150, height = 58) {
  return ctx.addImage(slide, {
    path: SME_LOGO, x, y, width, height, fit: "contain", alt: "SME logo", name: "sme-logo",
  });
}
