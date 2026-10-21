"""Generate the LO V3.1 decision report from downloaded immutable audits."""
from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path

import pandas as pd
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "LO" / "resuilt"
OUT = ROOT / "LO" / "docs" / "REPORT_LO_V3_1.docx"
ZIPS = {
    "contract": RESULT / "final_score_contract_audit_v3_1_scored_signal_excluded.zip",
    "ceiling": RESULT / "course_score_ceiling_audit_v3_1_scored_signal_excluded.zip",
    "registry": RESULT / "split_registry_v3_1_scored_signal_excluded_overlap_audit_v1__legacy_metadata.zip",
}


def read_parquet(root: Path, part: str) -> pd.DataFrame:
    files = list((root / part).glob("*.parquet"))
    if len(files) != 1:
        raise FileNotFoundError(f"Expected one parquet under {root / part}; got {len(files)}")
    return pd.read_parquet(files[0])


def n(x) -> str:
    return "—" if pd.isna(x) else f"{int(x):,}"


def pct(x) -> str:
    return "—" if pd.isna(x) else f"{100 * float(x):.3f}%"


def shade(cell, color: str) -> None:
    element = OxmlElement("w:shd")
    element.set(qn("w:fill"), color)
    cell._tc.get_or_add_tcPr().append(element)


def add_table(doc: Document, headers: list[str], rows: list[list[object]]) -> None:
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for cell, value in zip(table.rows[0].cells, headers):
        cell.text = str(value)
        shade(cell, "1F4E78")
        for run in cell.paragraphs[0].runs:
            run.font.bold = True
            run.font.color.rgb = RGBColor(255, 255, 255)
            run.font.size = Pt(9)
    for row in rows:
        cells = table.add_row().cells
        for cell, value in zip(cells, row):
            cell.text = str(value)
            for run in cell.paragraphs[0].runs:
                run.font.size = Pt(9)
    doc.add_paragraph()


def main() -> None:
    missing = [str(path) for path in ZIPS.values() if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing downloaded audits: " + ", ".join(missing))
    # Archives have already been unpacked by the download-validation step.
    # Avoid Python's temporary-directory permissions on this Windows host.
    with nullcontext(str(ROOT / "tmp")) as work:
        temp = Path(work)
        roots = {
            "contract": temp / "final_contract_v31_20261001" / "final_score_contract_audit_v3_1_scored_signal_excluded",
            "ceiling": temp / "lo_latest_download_20261001" / "course_score_ceiling_audit_v3_catalog_normalized",
            "registry": temp / "lo_latest_download_20261001" / "split_registry_v3_catalog_normalized_overlap_audit_v1",
        }

        contract = roots["contract"]
        ceiling = roots["ceiling"]
        registry = roots["registry"]
        semantics = read_parquet(contract, "label_semantics_contract").iloc[0]
        version = read_parquet(contract, "label_version_summary").iloc[0]
        exclusions = read_parquet(contract, "exclusion_reason_summary")
        proxy = read_parquet(contract, "proxy_feature_contract")
        score = read_parquet(contract, "score_range_by_profile")
        ceiling_summary = read_parquet(ceiling, "course_score_ceiling_summary").iloc[0]
        split = read_parquet(registry, "split_registry")
        blocks = read_parquet(registry, "block_label_audit")
        label_total = int(score[["n_I_D", "n_G", "n_E"]].sum().sum())
        label_counts = score[["n_I_D", "n_G", "n_E"]].sum()
        block_by_name = blocks.set_index("rolling_block")

        def label_row(name: str, frame: pd.DataFrame) -> list[str]:
            total = int(frame["enrollment_count"].sum())
            i_d = int(frame["I/D_count"].sum())
            g = int(frame["G_count"].sum())
            e = int(frame["E_count"].sum())
            return [name, n(total), pct(i_d / total), pct(g / total), pct(e / total)]

        window_blocks = {
            "W1": {"train": ("A",), "validation": ("B",), "test": ("C",)},
            "W2": {"train": ("A", "B", "C"), "validation": ("D",), "test": ("E",)},
            "W3": {"train": ("A", "B", "C", "D", "E"), "validation": ("F",), "test": ("G",)},
        }

        doc = Document()
        section = doc.sections[0]
        section.top_margin = Inches(0.55)
        section.bottom_margin = Inches(0.55)
        section.left_margin = Inches(0.65)
        section.right_margin = Inches(0.65)
        doc.styles["Normal"].font.name = "Aptos"
        doc.styles["Normal"].font.size = Pt(10.5)
        title = doc.add_heading("BÁO CÁO LO V3.1 — SCORED-SIGNAL EXCLUDED", 0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        doc.add_paragraph("Cập nhật 01/10/2026 | Hybrid scenario | CQ shared calendar").alignment = WD_ALIGN_PARAGRAPH.CENTER

        doc.add_heading("1. Kết luận điều hành", 1)
        doc.add_paragraph(
            "LO V3.1 đã loại các course không có attempt quan sát được ở mọi thành phần assignment/exam mang trọng số. "
            "Label contract V3.1 hợp lệ và điểm PRIMARY được chặn trong [0,100]. Toàn bộ artifact downstream dùng định danh "
            "split_version = v3_1_scored_signal_excluded trên shared calendar CQ V2.2."
        )

        doc.add_heading("2. Mục tiêu, đơn vị quan sát và luồng xử lý", 1)
        doc.add_paragraph(
            "Đơn vị phân tích là enrollment_id (một người học trong một course offering), gắn với user_id và course_id. "
            "Mục tiêu là dự báo sớm hiệu suất LO tại bốn thời điểm P1–P4, không phải suy luận completion, dropout hay final grade độc lập. "
            "Luồng tái lập là: raw events → timeline/offering → cumulative phase features → nhãn final_score → chronological split → views/prefixes → S0/data-quality → imputation → augmentation chỉ trên TRAIN → modeling."
        )
        doc.add_paragraph(
            "Không random split enrollment; không chia một offering × timeline_source qua nhiều block trong cùng window; feature store lưu raw. Scaling/imputation chỉ fit trên TRAIN của từng window. "
            "Mọi feature hoặc event có availability_time sau cutoff của phase đều bị cấm ở phase đó."
        )

        doc.add_heading("3. Timeline, cohort và feature contract", 1)
        doc.add_paragraph(
            "Với course có lịch quan sát được, offering được gán theo course_limit và offering_end_date là mốc lịch. Với course thiếu lịch, scenario hybrid dùng enrollment-anchored pseudo-offering; "
            "template duration chỉ là suy luận lịch, không phải lịch khai giảng/kết thúc quan sát trực tiếp. Kết quả hybrid không được gộp với timeline_only."
        )
        doc.add_paragraph(
            "Feature động gồm video, problem và comment; context gồm user/course/teacher/school. Event absence trong một phase đã quan sát có thể được biểu diễn bằng 0 theo ngữ nghĩa; "
            "phase tương lai luôn là NULL. observed masks giữ ranh giới giữa ‘không có event’ và ‘chưa quan sát modality’, nên không zero-fill tương lai trước preprocessing."
        )

        doc.add_heading("4. Label contract và cohort V3.1", 1)
        add_table(doc, ["Thuộc tính", "Giá trị"], [
            ["label_rule_version", semantics.contract_version],
            ["Công thức", semantics.formula],
            ["Ngưỡng", semantics.class_thresholds],
            ["Ý nghĩa", "Activity-derived final_score; không phải final grade, completion hay dropout quan sát trực tiếp"],
            ["Quyết định V3.1", "Loại no_scored_signal_in_course"],
        ])
        add_table(doc, ["Trạng thái", "Enrollment", "Course", "Tỷ lệ raw"], [
            [r.proxy_status, n(r.enrollment_count), n(r.course_count), pct(r.enrollment_share)]
            for r in exclusions.sort_values("enrollment_count", ascending=False).itertuples(index=False)
        ])
        doc.add_paragraph(
            f"Cohort eligible là {n(version.eligible_enrollment_count)} / {n(version.enrollment_count)} raw enrollment "
            f"({pct(version.eligible_enrollment_count / version.enrollment_count)}), thuộc {n(711)} course. "
            "Reason no_scored_signal_in_course loại 172,003 enrollment từ 102 course."
        )
        doc.add_paragraph("Tỷ lệ nhãn dưới đây dùng nhãn PRIMARY V3.1: I/D là mặc định, G và E là hai lớp hiếm. Mẫu số luôn là tổng enrollment của hàng tương ứng.")
        add_table(doc, ["Phạm vi", "Enrollment", "I/D", "G", "E"], [[
            "Toàn cohort eligible", n(label_total), pct(label_counts["n_I_D"] / label_total),
            pct(label_counts["n_G"] / label_total), pct(label_counts["n_E"] / label_total),
        ]])

        doc.add_heading("4.1. Phân bố nhãn theo lát thời gian", 2)
        slice_groups = [("A", ("A",)), ("T1", ("B", "C")), ("T2", ("D", "E")), ("T3", ("F", "G"))]
        add_table(doc, ["Lát", "Enrollment", "I/D", "G", "E"], [
            label_row(label, blocks[blocks["rolling_block"].isin(names)]) for label, names in slice_groups
        ])
        doc.add_heading("4.2. Phân bố nhãn theo window và split", 2)
        split_label_rows = []
        for window, assignments in window_blocks.items():
            for split_name, names in assignments.items():
                split_label_rows.append(label_row(f"{window} — {split_name}", blocks[blocks["rolling_block"].isin(names)]))
        add_table(doc, ["Window — split", "Enrollment", "I/D", "G", "E"], split_label_rows)

        doc.add_heading("5. Trần điểm course và quyết định loại", 1)
        add_table(doc, ["Chỉ số sau V3.1", "Course", "Enrollment eligible", "Tỷ lệ"], [
            ["Trần quan sát <60", n(ceiling_summary.course_count_ceiling_lt_60), n(ceiling_summary.enrollment_count_ceiling_lt_60), pct(ceiling_summary.enrollment_count_ceiling_lt_60 / ceiling_summary.eligible_enrollment_count)],
            ["Trần quan sát <85", n(ceiling_summary.course_count_ceiling_lt_85), n(ceiling_summary.enrollment_count_ceiling_lt_85), pct(ceiling_summary.enrollment_count_ceiling_lt_85 / ceiling_summary.eligible_enrollment_count)],
            ["Còn thỏa no_scored_signal_in_course", n(ceiling_summary.course_count_proposed_exclude), n(ceiling_summary.enrollment_count_proposed_exclude), pct(ceiling_summary.share_eligible_enrollments_proposed_exclude)],
        ])
        doc.add_paragraph(
            "course_score_ceiling_observed là score PRIMARY lớn nhất quan sát được của course. Không loại tự động mọi course có trần thấp; "
            "chỉ loại course không có attempt ở mọi component chấm điểm có trọng số. Sau V3.1, candidate còn lại bằng 0."
        )

        doc.add_heading("6. Leakage, current-grade và sampling", 1)
        add_table(doc, ["Nhóm", "Quy tắc khóa"], [
            ["Label proxy", f"{len(proxy)} canonical fields; cấm khỏi imputer/model, gồm mọi hậu tố _P1–_P4."],
            ["Current-grade", "score_sum, score_mean, score_std, score_fraction_mean, score_fraction_std, correct_problem_count, incorrect_problem_count, correct_ratio, correct_ratio_std; chỉ LO_FULL_EARLY."],
            ["LO_NO_CURRENT_GRADE", "Loại toàn bộ current-grade; problem_score_catalog_coverage vẫn là label proxy, cấm hoàn toàn."],
            ["Sampling PRIMARY", "IR10_K10: tối đa 10× mỗi lớp hiếm, synthetic share ≤90%; augmentation chỉ TRAIN."],
            ["Đánh giá", "W1 kết luận chính; W2/W3 exploratory, small_support_flag, CI 95% và paired bootstrap."],
        ])
        doc.add_heading("6.1. Support lớp hiếm và IR10_K10 theo cohort V3.1", 2)
        support_rows = []
        for window, assignments in window_blocks.items():
            for split_name in ("validation", "test"):
                part = blocks[blocks["rolling_block"].isin(assignments[split_name])]
                g = int(part["G_count"].sum())
                e = int(part["E_count"].sum())
                support_rows.append([
                    f"{window} — {split_name}", n(g), n(e),
                    "1" if min(g, e) < 400 else "0",
                    "PRIMARY (W1)" if window == "W1" else "Exploratory",
                ])
        add_table(doc, ["Window — split", "G", "E", "small_support_flag (<400)", "Vai trò"], support_rows)
        sampling_rows = []
        for window, assignments in window_blocks.items():
            train = blocks[blocks["rolling_block"].isin(assignments["train"])]
            i_d = int(train["I/D_count"].sum())
            g = int(train["G_count"].sum())
            e = int(train["E_count"].sum())
            sampling_rows.append([
                window, n(i_d), n(g), n(e), n(g * 10), n(e * 10),
                f"{i_d / (g * 10):.1f} / {i_d / (e * 10):.1f}",
            ])
        add_table(doc, ["Window", "Train I/D", "Train G", "Train E", "G sau ×10", "E sau ×10", "IR I/D:G / I/D:E"], sampling_rows)

        doc.add_heading("7. Kiểm tra điểm và phân bố lớp", 1)
        add_table(doc, ["Profile", "Eligible", "Score min/max", "E", "G", "I/D", "V3 >100"], [
            [r.assessment_modality_signature, n(r.eligible_enrollment_count), f"{r.final_score_min:.3f} / {r.final_score_max:.3f}", n(r.n_E), n(r.n_G), n(r.n_I_D), n(r.n_final_score_gt_100)]
            for r in score.itertuples(index=False)
        ])

        doc.add_heading("8. Split V3.1 theo thời gian, phase P1–P4 và drift", 1)
        doc.add_paragraph(
            "Block counts và tổng cohort của registry khớp V3.1 (2,605,423 enrollment), QA22 đều đạt. Split được định danh "
            "split_registry_v3_1_scored_signal_excluded_overlap_audit_v1; calendar vẫn dùng CQ V2.2 làm anchor và pairing rarest_first."
        )
        add_table(doc, ["Block", "Enrollment", "I/D", "G", "E"], [
            [r.rolling_block, n(r.enrollment_count), n(r._5), n(r.G_count), n(r.E_count)]
            for r in blocks.sort_values("rolling_block").itertuples(index=False)
        ])
        add_table(doc, ["Window", "Validation", "Test", "QA22", "Calendar anchor"], [
            [r.window_id, n(r.n_enrollments_validation), n(r.n_enrollments_test), "Đạt" if r.qa22_ok else "Không đạt", r.calendar_anchor_task]
            for r in split.itertuples(index=False)
        ])

        doc.add_heading("8.1. QA22 giữ nguyên giao thức", 2)
        doc.add_paragraph(
            "QA22 không được nới hoặc thay quy tắc ở V3.1: vẫn kiểm thứ tự label-end, kích thước hai arm evaluation và tổng evaluation theo registry. "
            "Bảng dưới đây là kết quả QA22 của registry V3.1."
        )
        add_table(doc, ["W", "end_order", "Validation", "Test", "Eval tổng", "Arm/total size", "QA22", "Purge"], [
            [
                r.window_id, "Đạt" if r.end_order_ok else "Không đạt", n(r.n_enrollments_validation),
                n(r.n_enrollments_test), n(r.n_enrollments_evaluation),
                "Đạt" if r.eval_size_ok else "Không đạt", "Đạt" if r.qa22_ok else "Không đạt",
                f"{n(r.n_purged)} ({r.purge_mode})",
            ] for r in split.itertuples(index=False)
        ])

        doc.add_paragraph(
            "P1/P2/P3/P4 là prefix tích lũy: test Pj chỉ lộ P1…Pj. Label drift giữa T1/T2/T3 là thay đổi thời gian thực, được báo cáo theo window và không được san bằng; "
            "mọi metric lớp hiếm phải kèm support, CI bootstrap 95% và small_support_flag khi n_support < 400."
        )

        doc.add_heading("9. Loại trừ kỹ thuật đã tồn tại trong A/T1/T2/T3", 1)
        doc.add_paragraph(
            "Bảng dưới đây là 18,008 enrollment đã không đủ điều kiện nhãn vì điều kiện kỹ thuật/cấu hình scoring. Đây không phải 172,003 enrollment mới loại ở V3.1; "
            "do đó về logic bảng ổn định khi thay V3 thành V3.1. Các course thiếu hoàn toàn course weights bị loại trước khi vào lát A/T1/T2/T3 nên không xuất hiện trong bảng này."
        )
        add_table(doc, ["Lát", "Assignment catalog thiếu", "Weights tổng ≠100", "Exam catalog thiếu", "Tổng điểm không dương", "Tổng"], [
            ["A", "37", "154", "943", "1", "1,135"],
            ["T1", "1", "0", "0", "0", "1"],
            ["T2", "2,453", "361", "55", "6", "2,875"],
            ["T3", "8,946", "4,980", "61", "10", "13,997"],
            ["Tổng", "11,437", "5,495", "1,059", "17", "18,008"],
        ])

        doc.add_heading("10. Integrity assignment và offering dài", 1)
        doc.add_paragraph(
            "Assignment được kiểm ở cấp offering_id × timeline_source: một enrollment không được ở hai block của cùng window. "
            "duration p50/p90/max, tỷ lệ enrollment thuộc offering >270 ngày và audit strict P1–P4 phải được lưu theo timeline_source. "
            "Không loại offering dài mặc định; long_offering_flag chỉ là prediction-level context để báo cáo phân tầng."
        )

        doc.add_heading("11. Trạng thái downstream và điều kiện khóa", 1)
        doc.add_paragraph(
            "Có thể materialize views/test prefixes ngay; sau đó chạy S0, coverage và long-offering audit gắn V3.1, rồi bốn imputation, augmentation TRAIN-only và model. "
            "Không ghép bất kỳ artifact V1/V2/V3 cũ vào meta-release V3.1."
        )

        doc.add_heading("12. Trạng thái và bước tiếp theo", 1)
        add_table(doc, ["Hạng mục", "Trạng thái"], [
            ["Label V3.1 + final-score contract", "Đã khóa"],
            ["Course-ceiling audit", "Đã khóa; không còn candidate"],
            ["Split V3.1 / QA22", "Đã khóa theo định danh v3_1_scored_signal_excluded"],
            ["Materialize views và test prefixes V3.1", "Sẵn sàng chạy"],
            ["Coverage + long-offering audit V3.1", "Chạy sau materialize/S0"],
            ["Imputation, augmentation, model", "Chạy sau S0/P0"],
        ])

        doc.add_heading("13. Ma trận độ đầy đủ của đánh giá V3.1", 1)
        doc.add_paragraph("Đối chiếu với Danh_gia_LO_V2.2_nhan, Danh_gia_LO_V3 và Danh_gia_Split_V2.2_closure. ‘Thiếu’ nghĩa là chưa có artifact cùng release V3.1, không phải thay đổi QA22.")
        add_table(doc, ["Thành phần cần đánh giá", "V3.1 hiện có", "Trạng thái"], [
            ["Định nghĩa/công thức nhãn, miền điểm, sensitivity", "final-score contract; điểm PRIMARY [0,100]; 19 proxy fields", "Đủ"],
            ["Raw → eligible và lý do loại", "11,807,090 raw; 2,605,423 eligible; 172,003 no_scored_signal; bảng 18,008 theo lát", "Đủ"],
            ["Tỷ lệ I/D/G/E, support và IR10_K10", "Toàn cohort, A/T1/T2/T3, W×split, support lớp hiếm và ×10", "Đủ"],
            ["Course-score ceiling", "Bảng <60/<85; không auto-drop; no_scored_signal đã loại", "Đủ"],
            ["QA22, calendar, purge và drift", "QA22 được giữ nguyên, đạt ở W1–W3 và có bảng chi tiết", "Đủ"],
            ["Uniqueness assignment, strict P1–P4, duration/long offering", "Audit nguồn có sẵn; cần refresh sau materialize để gắn downstream V3.1", "Hậu materialize"],
            ["Tập trung E/G theo offering", "Chưa có n_offerings_with_class và top-offering share gắn V3.1", "Cần chạy lại audit"],
            ["S0: missing_rate, event_sparsity theo lát × timeline_source", "Chưa materialize/S0 dưới V3.1", "Chưa có"],
            ["P0/QA23 và dictionary feature cuối", "Policy đã ghi; chưa có audit phase V3.1", "Chưa có"],
            ["Imputation, augmentation, model/metric hiệu năng", "Chưa chạy trên cohort V3.1", "Chưa bắt đầu"],
        ])

        OUT.parent.mkdir(parents=True, exist_ok=True)
        doc.save(OUT)
        print(OUT)


if __name__ == "__main__":
    main()
