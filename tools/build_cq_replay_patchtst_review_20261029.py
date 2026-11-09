"""Create a review document from the CQ matched replay receipt and pilot manifests."""
from pathlib import Path
import json
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
receipt_path = ROOT / 'CQ/resuilt/cq_rnn_matched_historical_20261029/paired_replay_equivalence.json'
receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
assert receipt['paired_exact'] and len(receipt['cells']) == 8
pilot_root = ROOT / 'CQ/resuilt/cq_patchtst_v0_seed42_20261023'
pilots = [json.loads((pilot_root / w / 'run_manifest.json').read_text(encoding='utf-8')) for w in ('W1','W2','W3')]
assert all(p['runner_git_commit'].startswith('7886a856') and p['learning_rate'] == 0.001 for p in pilots)
doc = Document()
sec = doc.sections[0]
sec.left_margin = sec.right_margin = Inches(.65)
style = doc.styles['Normal']; style.font.name = 'Arial'; style.font.size = Pt(11)
title = doc.add_heading('BÁO CÁO CQ: REPLAY RNN VÀ PROVENANCE PATCHTST V0', 0)
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
doc.add_paragraph('Bằng chứng seed 42 · 29/10/2026 · tài liệu xin ý kiến đánh giá')

def text(s): doc.add_paragraph(s)
def table(headers, rows):
    t = doc.add_table(rows=1, cols=len(headers)); t.style = 'Table Grid'
    for c, v in zip(t.rows[0].cells, headers): c.text = str(v)
    for values in rows:
        cells = t.add_row().cells
        for c, v in zip(cells, values): c.text = str(v)
    for row in t.rows:
        for cell in row.cells:
            for paragraph in cell.paragraphs:
                for run in paragraph.runs: run.font.name = 'Arial'; run.font.size = Pt(12)

doc.add_heading('1. Mục đích và kết luận cần xem', 1)
text('Tài liệu trả lời hai vấn đề: kết quả replay CQ RNN theo đúng layout lịch sử và khả năng giữ ba run PatchTST V0 cũ khi các cell tiếp theo dùng runner mới. Phần PatchTST là đề xuất xin ý kiến, chưa mở ngoại lệ ingest.')
doc.add_heading('2. CQ/W1/V0/RNN: matched replay', 1)
text('Baseline chạy ngày 20/10/2026 và replay chạy bằng commit 29da3b2. Hai run dùng cùng CQ V2.2, seed 42, batch 2.048 và historical static layout; hash layout b747da1ebe141251d9e6c1c3641c6391ac9fa1becf32cdf229d4e78c3016ad41. Cả hai chọn epoch 2.')
table(['Split','Phase','Enrollment','Nhãn khớp','Dự đoán khớp','Delta xác suất tối đa'], [(c['split'], c['phase'], f"{c['rows']:,}", 'Có' if c['labels_equal'] else 'Không', 'Có' if c['predictions_equal'] else 'Không', c['max_probability_delta']) for c in receipt['cells']])
text('Đối chiếu theo enrollment nguồn: tạo hash bằng salt riêng của từng run, xác nhận khớp đầy đủ và duy nhất, sau đó so nhãn, dự đoán và ba xác suất. Cả 8 cell khớp tuyệt đối. Salt được giữ riêng, không đưa vào báo cáo.')
text('Giới hạn provenance: baseline có timestamp trước commit 044d6c7 nhưng manifest không ghi Git commit chính xác; timestamp và hash runner là bằng chứng hỗ trợ, không được tự gán thành commit. Replay RNN chứng minh kết quả cell này, không chứng minh mọi model/window tương đương.')
doc.add_heading('3. PatchTST V0: ba run đã hoàn thành', 1)
table(['Window','Runner commit','Protocol','LR','Epoch chọn'], [(p['window_id'], p['runner_git_commit'][:8], p.get('run_purpose'), p.get('learning_rate'), p.get('best_epoch')) for p in pilots])
text('Ba run V0 đã có prediction, metrics và audit. Các run này dùng runner 7886a856; code mới hơn có revision khác. Ingest hiện yêu cầu runner thống nhất, nên chưa thể tự ghép ba V0 cũ với 48 cell mới thành một receipt đồng nhất.')
doc.add_heading('4. Thay đổi code và mức độ bằng chứng', 1)
text('Đối chiếu Git 7886a856 → 29da3b2 trong phạm vi model cho thấy model/data.py và model/shared_phase.py thay đổi; kiến trúc PatchTST/attention không đổi. Training loop bổ sung warm-up và gradient clipping; protocol gốc giữ warm-up 0 và không clip. Đường gradient accumulation được sắp xếp lại, do đó cần lưu ý khả năng khác biệt số học. Layout phải so theo file và hash thực tế của từng run.')
text('Replay RNN ở mục 2 hỗ trợ độ tin cậy của loop chung, nhưng không trực tiếp xác nhận đường accumulation PatchTST. D23 là sensitivity pilot; không chọn hyperparameter theo TEST.')
doc.add_heading('5. Phương án đề xuất xin cô xem', 1)
table(['Phương án','Chi phí và hệ quả'], [('A — đề xuất: giữ 3 V0 cũ','Đăng ký ngoại lệ provenance rõ runner từng nhóm; hoàn thành đối chiếu code và contract. Ingest hiện vẫn chặn trộn runner cho đến khi có quyết định và cơ chế kiểm tra ngoại lệ.'),('B — replay W1/V0 trước','Bổ sung bằng chứng runtime riêng PatchTST, giữ input/layout/seed/protocol; tốn khoảng 6 giờ L4 theo pilot cũ. Một cell không tự chứng minh W2/W3.'),('C — chạy lại cả 3 V0','Có thể tạo lưới cùng runner với các cell mới, nhưng tốn khoảng 18 giờ L4 theo ước lượng review.')])
text('Xin ý kiến: có chấp nhận A (giữ ba V0 với ngoại lệ provenance đã kiểm chứng) hay cần B/C trước khi ghép vào lưới? Nếu chấp nhận A, cần định nghĩa ngoại lệ tường minh và lưu receipt; không gỡ kiểm tra runner một cách chung chung.')
doc.add_heading('6. Tài liệu và artefact', 1)
text('Matched replay CQ: CQ/resuilt/cq_rnn_matched_historical_20261029/paired_replay_equivalence.json; baseline: CQ/resuilt/cq_rnn_baseline_drive_20261029; pilot: CQ/resuilt/cq_patchtst_v0_seed42_20261023; review: docs/28102026/Danh_gia_Code_va_Bao_cao_tong_hop_2026-10-28.docx. Chi phí trên là ước lượng lịch sử, không phải cam kết runtime.')
out = ROOT / 'CQ/docs/REPORT_CQ_REPLAY_RNN_VA_PATCHTST_V0_2026-10-29.docx'
doc.save(out)
print(out)
