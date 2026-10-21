"""Synchronize CQ/LO V1 report text with the current full-train experiment."""
from pathlib import Path

from docx import Document
from docx.shared import Pt


ROOT = Path(__file__).resolve().parents[2]
STATUS = (
    "Tiến độ imputation (Modal): S0_RAW đã materialize cho CQ và LO, W1–W3. "
    "Ở W1, V0, Median và Mean đã hoàn tất để làm baseline. Pipeline chung dùng "
    "log phù hợp → impute → RobustScaler; scaler chỉ fit từ observed numeric train. "
    "Median/Mean fit toàn bộ training values. ExtraTrees và MICE hiện được cấu hình "
    "thử nghiệm full-train (dynamic pooled P1–P4 và static train), chạy từng task một "
    "trên worker 192 GiB RAM với timeout 24 giờ; MICE dùng initializer hằng số 0 chỉ cho "
    "vòng chained-regression đầu và RobustScaler nội bộ train-only (inverse-transform trước output scale) "
    "để bảo đảm predictor hữu hạn; NaN predictor thưa còn sót được fallback bằng median train (0 nếu toàn thiếu). "
    "L2 ghi data-quality, distribution/drift, "
    "masked-validation fidelity, wall time, CPU và peak RAM. Chưa khóa imputer cuối cùng "
    "hoặc chạy mô hình dự báo; chỉ chọn sau khi đối chiếu ổn định W1–W3."
)


def update(path: Path) -> None:
    doc = Document(path)
    matches = [p for p in doc.paragraphs if p.text.startswith("Tiến độ imputation (Modal):")]
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one imputation-status paragraph in {path}; found {len(matches)}")
    paragraph = matches[0]
    paragraph.text = STATUS
    for run in paragraph.runs:
        run.font.name = "Times New Roman"
        run.font.size = Pt(13)
    temporary = path.with_name(path.stem + "_updating.docx")
    doc.save(temporary)
    temporary.replace(path)


for report in (ROOT / "CQ/docs/REPORT_CQ_V1.docx", ROOT / "LO/docs/REPORT_LO_V1.docx"):
    update(report)
    print(f"updated {report}")
