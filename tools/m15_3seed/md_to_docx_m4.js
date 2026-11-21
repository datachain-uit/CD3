// Markdown -> .docx in the layout of BAO_CAO_TONG_HOP_SEED42_43_2026-11-16_M4.docx (A4 landscape, Arial, dark-blue headings, banded tables with a dark header row).
// usage: NODE_PATH=<docxjs>/node_modules node md_to_docx_m4.js <in.md> <out.docx>
const fs = require('fs');
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle,
  HeadingLevel, LevelFormat, AlignmentType, PageOrientation, VerticalAlign, Footer, PageNumber,
} = require('docx');

const SRC = process.argv[2], OUT = process.argv[3];
const md = fs.readFileSync(SRC, 'utf8').replace(/\r\n/g, '\n').split('\n');

const FONT = 'Arial', TEXT = '263445', BLUE = '17365d', HDR = '21496d', BAND = 'f0f5f9';
const PAGE_W = 16838, PAGE_H = 11906, MAR_L = 1020, MAR_R = 1020, TABLE_W = PAGE_W - MAR_L - MAR_R;

function runs(text, base = {}) {
  const out = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let last = 0, m;
  const mk = (t, extra = {}) => new TextRun({ text: t, font: FONT, color: base.color || TEXT, size: base.size || 22, ...extra });
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push(mk(text.slice(last, m.index), base.bold ? { bold: true } : {}));
    const tok = m[0];
    if (tok.startsWith('**')) out.push(mk(tok.slice(2, -2), { bold: true }));
    else out.push(new TextRun({ text: tok.slice(1, -1), font: 'Consolas', color: base.color || TEXT, size: (base.size || 22) - 2, bold: !!base.bold }));
    last = m.index + tok.length;
  }
  if (last < text.length) out.push(mk(text.slice(last), base.bold ? { bold: true } : {}));
  return out;
}

const thin = { style: BorderStyle.SINGLE, size: 4, color: 'AAAAAA' };
const borders = { top: thin, bottom: thin, left: thin, right: thin };
const cellMargins = { top: 60, bottom: 60, left: 100, right: 100 };

function plainLen(s) { return s.replace(/\*\*|`/g, '').length; }

function buildTable(lines) {
  const split = (l) => l.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map((c) => c.trim());
  const head = split(lines[0]);
  const body = lines.slice(2).map(split);
  const n = head.length;
  const weight = head.map((h, i) => Math.max(6, Math.min(48, Math.max(plainLen(h) * 0.8, ...body.map((r) => plainLen(r[i] || '') )))));
  const sum = weight.reduce((a, b) => a + b, 0);
  let widths = weight.map((w) => Math.max(800, Math.round((TABLE_W * w) / sum)));
  const diff = TABLE_W - widths.reduce((a, b) => a + b, 0);
  widths[widths.indexOf(Math.max(...widths))] += diff;
  const cell = (text, i, isHead, band) => new TableCell({
    width: { size: widths[i], type: WidthType.DXA }, borders, margins: cellMargins, verticalAlign: VerticalAlign.CENTER,
    shading: { fill: isHead ? HDR : (band ? BAND : 'FFFFFF'), type: ShadingType.CLEAR, color: 'auto' },
    children: [new Paragraph({ spacing: { before: 20, after: 40, line: 259 }, alignment: AlignmentType.LEFT,
      children: runs(text, isHead ? { color: 'FFFFFF', bold: true, size: 20 } : { color: '253646', size: 20 }) })],
  });
  const rows = [new TableRow({ tableHeader: true, cantSplit: true, children: head.map((h, i) => cell(h, i, true, false)) })];
  body.forEach((r, k) => rows.push(new TableRow({ cantSplit: true, children: head.map((_, i) => cell(r[i] === undefined ? '' : r[i], i, false, k % 2 === 1)) })));
  return new Table({ width: { size: TABLE_W, type: WidthType.DXA }, columnWidths: widths, alignment: AlignmentType.CENTER, rows });
}

const children = [];
for (let i = 0; i < md.length; i++) {
  const line = md[i];
  if (!line.trim()) continue;
  if (line.startsWith('|') && md[i + 1] && /^\|\s*:?-{3}/.test(md[i + 1])) {
    const blk = [];
    while (i < md.length && md[i].startsWith('|')) blk.push(md[i++]);
    i--;
    children.push(buildTable(blk));
    children.push(new Paragraph({ spacing: { after: 120 }, children: [] }));
    continue;
  }
  let m;
  if ((m = line.match(/^# (.*)/))) children.push(new Paragraph({ heading: HeadingLevel.HEADING_1, keepNext: true, spacing: { before: 200, after: 140 }, children: [new TextRun({ text: m[1], bold: true, font: FONT, color: BLUE, size: 48 })] }));
  else if ((m = line.match(/^## (.*)/))) children.push(new Paragraph({ heading: HeadingLevel.HEADING_2, keepNext: true, spacing: { before: 280, after: 140 }, children: [new TextRun({ text: m[1], bold: true, font: FONT, color: BLUE, size: 36 })] }));
  else if ((m = line.match(/^### (.*)/))) children.push(new Paragraph({ heading: HeadingLevel.HEADING_3, keepNext: true, spacing: { before: 200, after: 120 }, children: [new TextRun({ text: m[1], bold: true, font: FONT, color: BLUE, size: 28 })] }));
  else if ((m = line.match(/^- (.*)/))) children.push(new Paragraph({ numbering: { reference: 'bul', level: 0 }, spacing: { after: 80, line: 269 }, children: runs(m[1], { size: 22 }) }));
  else children.push(new Paragraph({ spacing: { before: 0, after: 100, line: 269 }, children: runs(line, { size: 22 }) }));
}

const doc = new Document({
  creator: 'Đội code',
  title: md[0].replace(/^# /, ''),
  styles: { default: { document: { run: { font: FONT, size: 22, color: TEXT } } } },
  numbering: { config: [{ reference: 'bul', levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] }] },
  sections: [{
    properties: { page: { size: { width: PAGE_H, height: PAGE_W, orientation: PageOrientation.LANDSCAPE }, margin: { top: 935, right: MAR_R, bottom: 879, left: MAR_L, header: 708, footer: 708 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ children: ['Trang ', PageNumber.CURRENT, ' / ', PageNumber.TOTAL_PAGES], font: FONT, size: 18, color: '7a8794' })] })] }) },
    children,
  }],
});
Packer.toBuffer(doc).then((b) => { fs.writeFileSync(OUT, b); console.log('written', OUT, b.length, 'bytes;', children.length, 'blocks'); });
