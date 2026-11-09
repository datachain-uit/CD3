"""Render the 08-Nov evidence reconciliation Markdown report as a Word document."""
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_BREAK
from docx.shared import Inches, Pt


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/08112026/BAO_CAO_DOI_CHIEU_M01_M18_2026-11-08.md"
TARGET = ROOT / "docs/08112026/BAO_CAO_DOI_CHIEU_M01_M18_2026-11-08.docx"


def text(cell, value, bold=False):
    paragraph = cell.paragraphs[0]
    paragraph.clear()
    run = paragraph.add_run(value)
    run.bold = bold
    run.font.size = Pt(8.5)
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER


def add_table(document, rows):
    headers = [part.strip() for part in rows[0].strip().strip("|").split("|")]
    table = document.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for cell, value in zip(table.rows[0].cells, headers):
        text(cell, value, bold=True)
    for line in rows[2:]:
        values = [part.strip() for part in line.strip().strip("|").split("|")]
        row = table.add_row().cells
        for cell, value in zip(row, values):
            text(cell, value)
    document.add_paragraph()


def render(document, source):
    lines = source.read_text(encoding="utf-8").splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        if line.startswith("```"):
            index += 1
            code = []
            while index < len(lines) and not lines[index].startswith("```"):
                code.append(lines[index])
                index += 1
            paragraph = document.add_paragraph()
            paragraph.style = document.styles["No Spacing"]
            run = paragraph.add_run("\n".join(code))
            run.font.name = "Consolas"
            run.font.size = Pt(8.5)
            index += 1
            continue
        if line.startswith("| "):
            table_lines = []
            while index < len(lines) and lines[index].startswith("|"):
                table_lines.append(lines[index])
                index += 1
            add_table(document, table_lines)
            continue
        if line.startswith("# "):
            document.add_heading(line[2:], level=0)
        elif line.startswith("## "):
            document.add_heading(line[3:], level=1)
        elif line.startswith("### "):
            document.add_heading(line[4:], level=2)
        elif line[:2] in ("- ", "* "):
            document.add_paragraph(line[2:], style="List Bullet")
        elif line[0].isdigit() and ". " in line[:4]:
            document.add_paragraph(line.split(". ", 1)[1], style="List Number")
        else:
            paragraph = document.add_paragraph()
            for part in line.split("**"):
                run = paragraph.add_run(part)
                if line.split("**").index(part) % 2:
                    run.bold = True
        index += 1


def main():
    document = Document()
    section = document.sections[0]
    section.top_margin = Inches(0.65)
    section.bottom_margin = Inches(0.65)
    section.left_margin = Inches(0.65)
    section.right_margin = Inches(0.65)
    normal = document.styles["Normal"]
    normal.font.name = "Aptos"
    normal.font.size = Pt(10)
    render(document, SOURCE)
    document.add_paragraph().add_run("Nguồn: artefact local đã kiểm ngày 08/11/2026.").italic = True
    document.save(TARGET)
    print(TARGET)


if __name__ == "__main__":
    main()
