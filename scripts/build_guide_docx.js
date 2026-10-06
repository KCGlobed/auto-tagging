// Builds a Google-Docs-friendly .docx from docs/answer-checking-guide.md
//
// Usage (needs the "docx" npm package: npm install docx):
//   node scripts/build_guide_docx.js docs/answer-checking-guide.md docs/answer-checking-guide.docx
const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell,
  WidthType, ShadingType, BorderStyle, AlignmentType, LevelFormat, Footer, PageNumber,
  PageBreak,
} = require("docx");

const SRC = process.argv[2];
const OUT = process.argv[3];
const md = fs.readFileSync(SRC, "utf8").split("\n");

const FONT = "Arial";
const BRAND = "1F4E79";
const LIGHT = "DEEAF6";
const BOX = "F2F7FC";
const CONTENT_W = 9026; // A4 width minus 1" margins, in DXA

// ---- inline formatting: **bold**, *italic*, `code`, [text](link) ----
function runs(text, base = {}) {
  base = { font: FONT, ...base };
  text = text.replace(/\[([^\]]+)\]\([^)]+\)/g, "$1");
  const out = [];
  const re = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g;
  let last = 0, m;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(new TextRun({ text: text.slice(last, m.index), ...base }));
    const t = m[0];
    if (t.startsWith("**")) out.push(new TextRun({ text: t.slice(2, -2), bold: true, ...base }));
    else if (t.startsWith("`")) out.push(new TextRun({ text: t.slice(1, -1), ...base, font: "Courier New", color: "A31515" }));
    else out.push(new TextRun({ text: t.slice(1, -1), italics: true, ...base }));
    last = m.index + t.length;
  }
  if (last < text.length) out.push(new TextRun({ text: text.slice(last), ...base }));
  return out;
}

const para = (text, opts = {}) => new Paragraph({ children: runs(text), spacing: { after: 120 }, ...opts });

const cellBorder = { style: BorderStyle.SINGLE, size: 4, color: "BFBFBF" };
const borders = { top: cellBorder, bottom: cellBorder, left: cellBorder, right: cellBorder };

function table(rows) {
  const cols = rows[0].length;
  const weights = [...Array(cols).keys()].map(c =>
    Math.min(60, Math.max(24, ...rows.map(r => (r[c] || "").replace(/[*`]/g, "").length))));
  const sum = weights.reduce((a, b) => a + b, 0);
  const widths = weights.map(w => Math.floor((w / sum) * CONTENT_W));
  widths[cols - 1] += CONTENT_W - widths.reduce((a, b) => a + b, 0);
  return new Table({
    width: { size: CONTENT_W, type: WidthType.DXA },
    columnWidths: widths,
    rows: rows.map((r, i) => new TableRow({
      tableHeader: i === 0,
      children: r.map((cell, c) => new TableCell({
        width: { size: widths[c], type: WidthType.DXA },
        borders,
        shading: i === 0 ? { fill: BRAND, type: ShadingType.CLEAR, color: "auto" }
          : i % 2 === 0 ? { fill: "F7F9FC", type: ShadingType.CLEAR, color: "auto" } : undefined,
        margins: { top: 80, bottom: 80, left: 120, right: 120 },
        children: [new Paragraph({
          children: runs(cell, i === 0 ? { bold: true, color: "FFFFFF" } : {}),
        })],
      })),
    })),
  });
}

function callout(lines) {
  return lines.map((l, i) => new Paragraph({
    children: runs(l),
    shading: { fill: "FFF4E5", type: ShadingType.CLEAR, color: "auto" },
    border: { left: { style: BorderStyle.SINGLE, size: 24, color: "F0A020", space: 8 } },
    indent: { left: 200, right: 200 },
    spacing: { after: i === lines.length - 1 ? 200 : 0, before: i === 0 ? 80 : 0 },
  }));
}

// Flow diagram: each step becomes a shaded box with a down arrow between steps.
function flow(lines) {
  const steps = lines.map(l => l.trim()).filter(l => l && l !== "↓");
  const boxBorder = { style: BorderStyle.SINGLE, size: 6, color: "9DC3E6", space: 4 };
  const out = [];
  steps.forEach((s, i) => {
    const [head, detail] = s.split("→").map(x => x && x.trim());
    const children = [new TextRun({ font: FONT, text: head, bold: true, color: BRAND })];
    if (detail) children.push(new TextRun({ font: FONT, text: "  —  " + detail }));
    out.push(new Paragraph({
      children,
      alignment: AlignmentType.CENTER,
      shading: { fill: BOX, type: ShadingType.CLEAR, color: "auto" },
      border: { top: boxBorder, bottom: boxBorder, left: boxBorder, right: boxBorder },
      indent: { left: 900, right: 900 },
      spacing: { before: 40, after: 40 },
    }));
    if (i < steps.length - 1) {
      out.push(new Paragraph({
        children: [new TextRun({ font: FONT, text: "▼", color: "9DC3E6", size: 20 })],
        alignment: AlignmentType.CENTER, spacing: { before: 0, after: 0 },
      }));
    }
  });
  out.push(new Paragraph({ children: [], spacing: { after: 120 } }));
  return out;
}

// ---- parse markdown ----
const body = [];
let i = 0;
let title = "", subtitle = "";
let numberedRef = 0;

while (i < md.length) {
  const line = md[i];
  const t = line.trim();

  if (t.startsWith("# ")) { title = t.slice(2); i++; continue; }
  if (!subtitle && title && t && !t.startsWith("#") && !t.startsWith("---")) { subtitle = t; i++; continue; }
  if (t === "" || t === "---") { i++; continue; }

  if (t.startsWith("## ")) {
    body.push(new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun({ font: FONT, text: t.slice(3) })] }));
    i++; continue;
  }
  if (t.startsWith("### ")) {
    body.push(new Paragraph({ heading: HeadingLevel.HEADING_2, children: runs(t.slice(4)) }));
    i++; continue;
  }
  if (t.startsWith("```")) {
    const block = [];
    i++;
    while (i < md.length && !md[i].trim().startsWith("```")) block.push(md[i++]);
    i++;
    body.push(...flow(block));
    continue;
  }
  if (t.startsWith("|")) {
    const rows = [];
    while (i < md.length && md[i].trim().startsWith("|")) {
      const r = md[i].trim().slice(1, -1).split("|").map(c => c.trim());
      if (!r.every(c => /^-+$/.test(c))) rows.push(r);
      i++;
    }
    body.push(table(rows), new Paragraph({ children: [], spacing: { after: 120 } }));
    continue;
  }
  if (t.startsWith(">")) {
    const block = [];
    while (i < md.length && md[i].trim().startsWith(">")) block.push(md[i++].trim().replace(/^>\s?/, ""));
    body.push(...callout(block.filter(l => l !== "")));
    continue;
  }
  if (/^\d+\.\s/.test(t)) {
    numberedRef++;
    const ref = `num${numberedRef}`;
    while (i < md.length && /^\d+\.\s/.test(md[i].trim())) {
      body.push(new Paragraph({
        children: runs(md[i].trim().replace(/^\d+\.\s/, "")),
        numbering: { reference: ref, level: 0 }, spacing: { after: 80 },
      }));
      i++;
    }
    continue;
  }
  if (/^\s*-\s/.test(line)) {
    while (i < md.length && /^\s*-\s/.test(md[i])) {
      const level = md[i].match(/^\s*/)[0].length >= 2 ? 1 : 0;
      body.push(new Paragraph({
        children: runs(md[i].trim().slice(2)),
        numbering: { reference: "bullets", level }, spacing: { after: 80 },
      }));
      i++;
    }
    continue;
  }
  // FAQ question lines ("**...?**") get a little extra space above
  const isFaqQ = /^\*\*.*\?\*\*$/.test(t);
  if (/^\*[^*].*\*$/.test(t)) {
    body.push(para(t, { spacing: { before: 240 } }));
  } else {
    body.push(para(t, isFaqQ ? { spacing: { before: 200, after: 40 }, keepNext: true } : {}));
  }
  i++;
}

const numberingConfigs = [{
  reference: "bullets",
  levels: [
    { level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
    { level: 1, format: LevelFormat.BULLET, text: "◦", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 1440, hanging: 360 } } } },
  ],
}];
for (let n = 1; n <= numberedRef; n++) {
  numberingConfigs.push({
    reference: `num${n}`,
    levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 720, hanging: 360 } } } }],
  });
}

const muted = text => new Paragraph({ children: [new TextRun({ font: FONT, text, color: "595959" })] });

const cover = [
  new Paragraph({ children: [], spacing: { before: 2400 } }),
  new Paragraph({
    children: [new TextRun({ font: FONT, text: title, bold: true, size: 56, color: BRAND })],
    spacing: { after: 240 },
  }),
  new Paragraph({
    children: [new TextRun({ font: FONT, text: subtitle, size: 28, color: "595959" })],
    border: { bottom: { style: BorderStyle.SINGLE, size: 12, color: BRAND, space: 12 } },
    spacing: { after: 480 },
  }),
  new Paragraph({ children: [new TextRun({ font: FONT, text: "Covers", bold: true, size: 24 })], spacing: { after: 120 } }),
  ...["Essay Checker  (/api/essay-verify)", "ACCA Scenario Checker  (/api/scenario-verify)"].map(s =>
    new Paragraph({ children: [new TextRun({ font: FONT, text: s, size: 24 })], numbering: { reference: "bullets", level: 0 } })),
  new Paragraph({ children: [], spacing: { before: 480 } }),
  muted("Audience: tutors, academic staff, product and operations teams"),
  muted(`Updated ${new Date().toLocaleDateString("en-GB", { month: "long", year: "numeric" })}`),
  new Paragraph({ children: [new PageBreak()] }),
];

const doc = new Document({
  creator: "KC Global Ed",
  title,
  styles: {
    default: { document: { run: { font: FONT, size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font: FONT, color: BRAND },
        paragraph: { spacing: { before: 360, after: 160 }, keepNext: true, outlineLevel: 0,
          border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: LIGHT, space: 4 } } } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, font: FONT, color: "2E75B6" },
        paragraph: { spacing: { before: 240, after: 120 }, keepNext: true, outlineLevel: 1 } },
    ],
  },
  numbering: { config: numberingConfigs },
  sections: [{
    properties: {
      page: { margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } },
      titlePage: true,
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [
            new TextRun({ font: FONT, text: `${title}  ·  Page `, color: "808080", size: 18 }),
            new TextRun({ font: FONT, children: [PageNumber.CURRENT], color: "808080", size: 18 }),
          ],
        })],
      }),
    },
    children: [...cover, ...body],
  }],
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(OUT, buf);
  console.log("wrote", OUT, buf.length, "bytes");
});
