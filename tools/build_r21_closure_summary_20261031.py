"""Create a scoped R21 evidence and replay report from staged artifacts."""
from pathlib import Path
import json
from docx import Document
from docx.shared import Pt, Inches

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'CQ/resuilt/input/results/R21_evidence_20261031'
OUT=ROOT/'CQ/docs/BAO_CAO_TONG_HOP_R21_CQ_LO_2026-10-31.docx'
def table(doc,headers,rows):
    t=doc.add_table(rows=1,cols=len(headers)); t.style='Table Grid'
    for c,v in zip(t.rows[0].cells,headers): c.text=str(v)
    for row in rows:
        for c,v in zip(t.add_row().cells,row): c.text=str(v)
def main():
    manifest=json.loads((BASE/'manifest.json').read_text(encoding='utf8'))
    ledger=json.loads((BASE/'CQ/S2_seed42/ledger_inventory.json').read_text(encoding='utf8'))
    replay=json.loads((BASE/'CQ/replay/rnn_matched.json').read_text(encoding='utf8'))
    patch=json.loads((BASE/'CQ/replay/patchtst_current_epoch1.json').read_text(encoding='utf8'))
    assert len(manifest['files'])==151 and len(ledger['entries'])==36 and replay['paired_exact'] and patch['pass']
    d=Document(); s=d.sections[0]; s.left_margin=s.right_margin=Inches(.7)
    d.styles['Normal'].font.name='Calibri'; d.styles['Normal'].font.size=Pt(11)
    d.add_heading('BÁO CÁO TỔNG HỢP REVIEW R21 — CQ VÀ LO',0)
    d.add_paragraph('Evidence, quyết định V0 và replay · 31/10/2026')
    d.add_heading('1. Kết luận và quyết định',1)
    d.add_paragraph('CQ F2 dùng ba run PatchTST V0 mới W1–W3, seed 42, cùng cấu hình hiện hành; ba pilot cũ được giữ làm lịch sử và không ghép vào lưới mới. Đây là quyết định của người dùng, không mặc định là chữ ký phê chuẩn của người review. Chưa chạy 48 ô CQ F2 còn lại theo evidence hiện có.')
    d.add_paragraph('Replay matched CQ RNN W1/V0 khớp nhãn, dự đoán và xác suất trên validation/test P1–P4. Baseline lịch sử không ghi commit training loop; ghi rõ giới hạn provenance, không yêu cầu run cũ xuất lại trường chưa từng được lưu. Replay PatchTST W1/V0 hiện hành khớp ba metric ở epoch đầu; không suy rộng sang toàn bộ run.')
    d.add_heading('2. Evidence đã kiểm tra',1)
    table(d,['Hạng mục','Trạng thái'],[
        ['Gói input/results','151 file đã sao chép và đối chiếu SHA-256 với nguồn; manifest ghi đường dẫn và hash.'],
        ['CQ R4 và QA23','Có facts R4 và 68 file QA23 summary/dictionary/predictors; audit QA23 chi tiết chưa được đưa đầy đủ vào gói.'],
        ['LO bốn họ','RNN, LSTM, GRU, BiLSTM: 51 run/họ; sáu bảng audit/họ có số dòng khớp manifest.'],
        ['S2 CQ seed 42','36/36 ledger và manifest có trên Drive; đã tính SHA-256 ledger và lập inventory; ledger không được sao chép vào ổ D.'],
        ['D23','Đã đóng gói train_history W2 và W3; pilot là sensitivity, không tự chọn protocol bằng TEST.'],
        ['CQ label','3.192.206 enrollment trong artifact; 2.684.090 đủ điều kiện, 308.116 không quan sát đầy đủ, 200.000 bị loại theo chính sách zero-activity warning.']])
    d.add_heading('3. Replay CQ matched RNN',1)
    table(d,['Tập','Phase','Enrollment','Nhãn / dự đoán','Delta xác suất tối đa'],[[x['split'],x['phase'],f"{x['rows']:,}",'Khớp' if x['labels_equal'] and x['predictions_equal'] else 'Không khớp',x['max_probability_delta']] for x in replay['cells']])
    d.add_paragraph('Hai phía cùng chọn epoch 2. Hash runner baseline trong metadata khớp biểu diễn CRLF của một phiên bản Git có commit timestamp sau thời điểm run; điều đó không xác định commit baseline hay nội dung toàn bộ training loop. Kết quả chứng minh cell được đối chiếu tái lập prediction, không tự chứng minh mọi run hoặc revision tương đương.')
    d.add_heading('4. Replay PatchTST V0 hiện hành',1)
    table(d,['Metric epoch 1','Run','Replay'],[[k,repr(v['current']),repr(v['replay'])] for k,v in patch['metrics'].items()])
    d.add_paragraph('Layout hash, dữ liệu, runner, seed, batch và môi trường trong receipt khớp. Không phải replay toàn bộ prediction, không phải phép so pilot 12 cột cũ với layout hiện hành.')
    d.add_heading('5. Nội dung còn mở',1)
    d.add_paragraph('48 ô CQ F2 chưa nằm trong kết quả đã kiểm tra. Closure archive, LO replay receipt và toàn bộ dữ liệu QA23 chi tiết chưa được xác nhận đầy đủ trong gói; ledger chỉ được ánh xạ trên Drive. S2 seed 43/44 và đánh giá ổn định đa seed là công việc tiếp theo nếu thực hiện. Không khẳng định phê chuẩn bên ngoài hay ingest chính thức chỉ từ gói local.')
    d.add_heading('6. Nguồn',1)
    d.add_paragraph('Gói: CQ/resuilt/input/results/R21_evidence_20261031; manifest.json chứa đường dẫn nguồn, kích thước và SHA-256. Ledger inventory: CQ/S2_seed42/ledger_inventory.json. Báo cáo hiệu suất PatchTST V0 riêng: CQ/docs/BAO_CAO_CQ_PATCHTST_V0_HIEU_SUAT_REPLAY_2026-10-31.docx.')
    OUT.parent.mkdir(parents=True,exist_ok=True); d.save(OUT); print(OUT)
if __name__=='__main__': main()
