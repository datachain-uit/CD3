"""Repair section ordering after XML-level append of the RNN appendix."""
from __future__ import annotations

from pathlib import Path

from docx import Document


REPORT = Path(__file__).resolve().parents[1] / "CQ" / "docs" / "REPORT_CQ_V1.docx"


def text(element) -> str:
    return "".join(element.itertext())


def main() -> None:
    doc = Document(REPORT)
    body = doc.element.body
    children = list(body)
    section_index = next(index for index, node in enumerate(children) if node.tag.endswith("sectPr"))
    final_index = next(index for index, node in enumerate(children) if "PHẦN C — ĐÁNH GIÁ CUỐI" in text(node))
    source_index = next(index for index, node in enumerate(children)
                        if "Phạm vi: vòng sàng lọc đầu tiên cho CQ" in text(node))

    # RNN source was appended after sectPr by the previous merge. Move it back
    # into the document body first, preserving its internal order.
    for node in children[section_index + 1:]:
        body.remove(node)
        body.insert(body.index(body.sectPr), node)

    # Then move the final assessment block after the RNN source, before sectPr.
    children = list(body)
    final_index = next(index for index, node in enumerate(children) if "PHẦN C — ĐÁNH GIÁ CUỐI" in text(node))
    source_index = next(index for index, node in enumerate(children)
                        if "Phạm vi: vòng sàng lọc đầu tiên cho CQ" in text(node))
    final_block = children[final_index:source_index]
    for node in final_block:
        body.remove(node)
    for node in final_block:
        body.insert(body.index(body.sectPr), node)
    doc.save(REPORT)
    print(REPORT)


if __name__ == "__main__":
    main()
