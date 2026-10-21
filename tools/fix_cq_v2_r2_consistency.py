"""Correct superseded r1 wording after the canonical r2 acceptance export."""
from pathlib import Path

from docx import Document


REPORT = Path(__file__).resolve().parents[1] / "CQ" / "docs" / "REPORT_CQ_V2.2_CLEAN_GRAIN_RNN_SEED42_V2_2026-10-07.docx"


def replace(paragraph, value: str) -> None:
    paragraph.runs[0].text = value
    for run in paragraph.runs[1:]:
        run.text = ""


def main() -> None:
    document = Document(REPORT)
    changed = 0
    for paragraph in document.paragraphs:
        if paragraph.text.startswith("Sanity coverage đạt đủ 204 TEST rows."):
            replace(
                paragraph,
                "Sanity TEST đạt đủ 204 dòng. Theo export r2 canonical, s_eff và s_leak đều có đúng một giá trị "
                "trong mỗi eval_split × window × phase; leakage probe luôn truy về dữ liệu thật của imputer cha.",
            )
            changed += 1
        elif "report_id=RNN_seed42_v2_2_clean_20261007_r1/" in paragraph.text:
            replace(
                paragraph,
                paragraph.text.replace("RNN_seed42_v2_2_clean_20261007_r1", "RNN_seed42_v2_2_clean_20261007_r2"),
            )
            changed += 1
    if changed != 2:
        raise RuntimeError(f"Expected exactly two r1 consistency replacements, got {changed}")
    document.save(REPORT)
    print(REPORT)


if __name__ == "__main__":
    main()
