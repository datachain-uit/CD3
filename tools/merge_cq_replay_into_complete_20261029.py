"""Merge the reviewed matched replay and PatchTST evidence into the complete CQ report."""
from copy import deepcopy
from pathlib import Path
from docx import Document
from docx.oxml.ns import qn

ROOT = Path(__file__).resolve().parents[1]
base = ROOT / 'CQ/docs/REPORT_CQ_CONSOLIDATED_EVIDENCE_2026-10-28_R20_DAY_DU.docx'
supplement = ROOT / 'CQ/docs/REPORT_CQ_REPLAY_RNN_VA_PATCHTST_V0_2026-10-29.docx'
target = ROOT / 'CQ/docs/REPORT_CQ_DAY_DU_REPLAY_PATCHTST_2026-10-29.docx'
doc = Document(base)
for paragraph in doc.paragraphs:
    if paragraph.text.startswith('PatchTST D23 chỉ là sensitivity pilot:'):
        paragraph.text = ('PatchTST D23 là sensitivity pilot; protocol gốc được nhóm khóa. '
            'CQ/W1/V0/RNN matched replay giữ historical layout và khớp từng enrollment; '
            'baseline không ghi commit Git chính xác. Phương án giữ ba PatchTST V0 cũ chờ ý kiến người duyệt.')
    elif paragraph.text.startswith('D23 audit:'):
        paragraph.text = ('D23 audit: 2 run, bootstrap B=2.000 và 16 sanity rows. W3 chọn epoch 1 và '
            'đường validation không đơn đỉnh; D23 được giữ là sensitivity. Không chọn protocol dựa trên TEST.')
    elif paragraph.text.startswith('Paired replay CQ/W1/V0/RNN seed 42') or paragraph.text.startswith('Paired replay CQ/W1/V0/RNN/seed 42'):
        paragraph.text = ('Matched replay CQ/W1/V0/RNN/seed 42 dùng cùng historical layout, batch 2.048 và cùng chọn epoch 2. '
            'Ghép theo enrollment nguồn bằng salt riêng: cả 8 cell VALIDATION/TEST × P1–P4 có nhãn, prediction và xác suất khớp tuyệt đối. '
            'Baseline có timestamp 20/10/2026 trước commit 044d6c7 nhưng không ghi commit chính xác; không tự suy diễn revision. '
            'Chi tiết và phương án PatchTST V0 nằm ở mục 14.')
    elif paragraph.text.startswith('Facts chính:'):
        paragraph.text += (' Matched replay mới: CQ/resuilt/cq_rnn_matched_historical_20261029/'
                           'paired_replay_equivalence.json.')

# Replace the old 8-cell table: it described an earlier, different replay pair.
heading = next(p for p in doc.paragraphs if p.text == '8. Replay và việc còn mở')
node = heading._p.getnext()
if node is not None and node.tag == qn('w:tbl'):
    node.getparent().remove(node)

doc.add_page_break()
doc.add_heading('14. Bằng chứng replay RNN và phương án PatchTST V0', level=1)
extra = Document(supplement)
copying = False
for element in extra.element.body:
    if element.tag == qn('w:p'):
        text = ''.join(element.itertext())
        if '2. CQ/W1/V0/RNN: matched replay' in text:
            copying = True
    if copying and element.tag != qn('w:sectPr'):
        doc.element.body.insert(-1, deepcopy(element))
for paragraph in doc.paragraphs:
    if paragraph.style.name.startswith('Heading'):
        for old, new in [('2. CQ/W1/V0/RNN:', '14.1. CQ/W1/V0/RNN:'),
                         ('3. PatchTST V0:', '14.2. PatchTST V0:'),
                         ('4. Thay đổi code', '14.3. Thay đổi code'),
                         ('5. Phương án', '14.4. Phương án'),
                         ('6. Tài liệu', '14.5. Tài liệu')]:
            if paragraph.text.startswith(old):
                paragraph.text = paragraph.text.replace(old, new, 1)
                break
    elif paragraph.text.startswith('Replay RNN ở mục 2'):
        paragraph.text = paragraph.text.replace('Replay RNN ở mục 2', 'Replay RNN ở mục 14.1', 1)
doc.save(target)
print(target)
