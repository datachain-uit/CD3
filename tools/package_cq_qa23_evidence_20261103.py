"""Package selected QA23 evidence, retaining original zip provenance."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,shutil,zipfile
ROOT=Path('CQ/resuilt'); ZIP=ROOT/'qa23_v2_2.zip'; OUT=ROOT/'cq_qa23_detail_20261103'
EVIDENCE=ROOT/'input/results/R21_evidence_20261031/CQ'
GROUPS={'feature_dictionary_v1','imputer_predictors_cq_raw_early','qa23_summary'}
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    OUT.mkdir(parents=True,exist_ok=True); counts={}; entries=[]
    with zipfile.ZipFile(ZIP) as z:
        bad=z.testzip()
        if bad:raise ValueError(f'zip CRC failed: {bad}')
        for info in z.infolist():
            path=Path(info.filename);parts=path.parts
            if info.is_dir() or len(parts)!=4 or parts[0]!='qa23_v2_2' or parts[2] not in GROUPS:continue
            if path.is_absolute() or '..' in parts:raise ValueError(f'unsafe zip member {info.filename}')
            target=OUT.joinpath(*parts[1:]);target.parent.mkdir(parents=True,exist_ok=True)
            data=z.read(info);target.write_bytes(data);counts[parts[2]]=counts.get(parts[2],0)+1
            entries.append({'zip_member':info.filename,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
    for phase in ('P1','P2','P3','P4'):
        for group in GROUPS:
            if not list((OUT/f'phase_id={phase}'/group).glob('*.parquet')):raise ValueError(f'missing {phase}/{group}')
    for src,dst in [(EVIDENCE/'prefix_audit/full_scan.json','prefix_audit/full_scan.json'),(EVIDENCE/'labels/label_view_consistency.json','labels/label_view_consistency.json')]:
        target=OUT/dst;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,target)
    summary={'created_at_utc':datetime.now(timezone.utc).isoformat(),'qa23_source_zip':str(ZIP),'qa23_source_sha256':digest(ZIP),'source_crc':'PASS','selected_zip_files_by_group':counts,'selected_zip_files':len(entries),'entries':entries,'scope':'CQ v2.2 QA23 P1–P4; selected original files plus prefix and label/view audit'}
    (OUT/'source_inventory.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf8')
    (OUT/'README.md').write_text('''# CQ QA23 chi tiết — V2.2

Nguồn: qa23_v2_2.zip, trích nguyên văn feature_dictionary_v1, imputer_predictors_cq_raw_early và qa23_summary của P1–P4; zip và từng tệp được kiểm tra CRC/SHA-256. Gói kèm full_scan.json và label_view_consistency.json từ R21. Các kết quả là snapshot audit, không có nghĩa mọi giả định thời điểm sẵn có của metadata đã được chứng minh.

Định nghĩa canonical theo CQ/Feature_extraction/labels/build_cq_labels.py: vector (COELO_personal, AFELO_personal, ACELO_personal); khoảng cách Euclid d tới [1,1,1]; proximity G = 1 - d/sqrt(3). Nhãn warning nếu G < 0,10; average nếu 0,10 ≤ G < 0,30; good nếu G ≥ 0,30. Không quan sát hoặc thành phần không hợp lệ thì null theo lý do loại. Tối đa 200.000 zero-activity warning bị loại theo thứ tự hash xác định. Weighted geometric mean trong code là diagnostic, không thay cho proximity canonical.
''',encoding='utf8')
    fs=sorted(p for p in OUT.rglob('*') if p.is_file() and p.name!='sha256sums.txt');(OUT/'sha256sums.txt').write_text(''.join(digest(p)+'  '+p.relative_to(OUT).as_posix()+'\n' for p in fs),encoding='utf8')
    print(json.dumps({k:v for k,v in summary.items() if k!='entries'},indent=2),flush=True)
if __name__=='__main__':main()
