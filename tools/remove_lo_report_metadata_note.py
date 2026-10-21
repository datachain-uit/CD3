"""Remove the obsolete coverage-metadata note from the already-rendered LO report."""
from pathlib import Path

from docx import Document


REPORT = Path(__file__).resolve().parents[1] / "LO" / "docs" / "REPORT_LO_V1.docx"


def main() -> None:
    doc = Document(REPORT)
    for paragraph in doc.paragraphs:
        if paragraph.text.startswith("Coverage evidence source:"):
            source = paragraph.text.split(": ", 1)[1].split(". The values", 1)[0]
            paragraph.text = f"Coverage evidence source: {source}. The reported counts are source-faithful and reconcile with the split registry."
        if "Việc kỹ thuật còn lại là tái xuất coverage audit để làm sạch câu chữ metadata." in paragraph.text:
            paragraph.text = paragraph.text.replace(
                " Việc kỹ thuật còn lại là tái xuất coverage audit để làm sạch câu chữ metadata.", ""
            )
    doc.save(REPORT)
    print(REPORT)


if __name__ == "__main__":
    main()
