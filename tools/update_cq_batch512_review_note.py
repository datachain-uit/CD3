"""Append the 17 October review's verified batch/provenance clarification."""
from pathlib import Path
import shutil
from docx import Document


def main():
    path = Path("CQ/docs/REPORT_CQ_FULL_E2E_SEED42_2026-10-16.docx")
    backup = path.with_name(path.stem + "_PRE_REVIEW_20261018.docx")
    if backup.exists():
        raise FileExistsError(backup)
    doc = Document(path)
    doc.add_heading("Làm rõ batch và provenance CQ VastAI — 18/10/2026", level=1)
    doc.add_paragraph("Đã kiểm tra 153 run_manifest.json trong bundle CQ VastAI: toàn bộ 51 LSTM, "
                      "51 GRU và 51 BiLSTM đều ghi batch_size=512. Tên bundle có chữ batch2048 không "
                      "phải bằng chứng cấu hình train. Các manifest lịch sử được kiểm tra không ghi "
                      "micro_batch_size hoặc accumulation_steps; không tự suy các trường này.")
    doc.add_paragraph("LSTM/GRU và BiLSTM thuộc các runner provenance khác nhau. Giữ riêng lineage "
                      "khi so sánh; chưa khẳng định hai runner tương đương nếu chưa đối chiếu mã và môi trường. "
                      "Quyết định giữ batch 512 hay chạy lại với batch 2048 chưa được chốt.")
    doc.add_paragraph("Các manifest lịch sử mẫu không có energy_null_reason; không xác định nguyên nhân "
                      "thiếu telemetry chỉ từ số bản ghi năng lượng bằng 0. Không suy ra năng lượng hoặc CO₂.")
    shutil.copy2(path, backup)
    doc.save(path)
    print(f"updated {path}; backup {backup}")


if __name__ == "__main__":
    main()
