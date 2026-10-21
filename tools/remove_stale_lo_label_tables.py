"""Remove V2.2 pre-source-faithful label/split tables from REPORT_LO_V1."""
from pathlib import Path

from docx import Document


REPORT = Path(__file__).resolve().parents[1] / "LO" / "docs" / "REPORT_LO_V1.docx"
STALE_MARKERS = (
    "88,732", "15,853", "9,256", "3,611", "28,720", "29,098",
    "98.917% | 0.267% | 0.817%", "27.212% | 95.599% | 2.454%",
)


def delete_table(table) -> None:
    element = table._element
    element.getparent().remove(element)


def main() -> None:
    doc = Document(REPORT)
    stale = []
    for table in doc.tables:
        contents = " | ".join(cell.text for row in table.rows for cell in row.cells)
        if any(marker in contents for marker in STALE_MARKERS):
            stale.append(table)
    for table in stale:
        delete_table(table)
    doc.save(REPORT)
    print(f"removed={len(stale)} report={REPORT}")


if __name__ == "__main__":
    main()
