# -*- coding: utf-8 -*-
"""QA21 muc D / QA23 cho LO: bang qa23_lo_review_candidates.csv (11 co so chua duoc xem xet + 4 co so nhom diem hien hanh).
Chi doc: qa4/qa23_fullrows/qa23_audit_by_feature.csv (toan bo dong TRAIN, 24 lat) + ma LO trong repo (so dong lay bang tay, kiem lai bang grep).
Env: QA21_OUT, QA4_DIR (thu muc qa4), REPO (repo)."""
import os, re, hashlib
import pandas as pd

OUT = os.environ['QA21_OUT']; QA4 = os.environ['QA4_DIR']; REPO = os.environ['REPO']
FEAT = 'LO/Feature_extraction_LO/features/build_scenario_phase_features.py'
LAB = 'LO/Feature_extraction_LO/labels/build_lo_labels.py'
SEL = f'{FEAT}:196-204 (select_events_until_cutoff: availability_time >= enroll_time va <= cutoff_time)'
SEL_VIDEO = SEL + '; video availability_time = event_time (dong 406-408, 446)'
SEL_PROB = SEL + '; problem availability_time = submit_time (dong 409-411, 447)'
BEH = 'behavioural_prefix_observed (not a label component)'
COMP = 'label_component_or_normalised_version_of_label_component'

# (base, nhom, ho, do gi, dong ma, quan he voi nhan, ten proxy da dang ky co lien quan, phan loai, ghi chu)
B = [
 ('attempts_sum', 'outside_current_grade_group', 'problem', 'Tong cot `attempts` (so lan thu ghi tren moi lan nop) cua cac lan nop den cutoff',
  f'{FEAT}:301 (sum coalesce(attempts,0))', SEL_PROB,
  'khong co trong cong thuc performance_score; nhan dung best_correct_ratio = clip(score/full_score) tren moi problem (labels:209-225, 331-340 (best_correct_ratio dong 213, 219)); trong nhan khong co cot attempts',
  'assignment_attempt_count / exam_attempt_count (dem so dong nop, khac dai luong: tong gia tri cot attempts) la proxy trong LO_LABEL_PROXY_COLUMNS, khong thuoc 19 ten hop dong', BEH,
  'dai luong khac voi attempt_count cua nhan'),
 ('exercise_count', 'outside_current_grade_group', 'problem', 'So exercise_id khac nhau da nop den cutoff', f'{FEAT}:290', SEL_PROB,
  'nhan chi dung exercise de xac dinh tap exam (chuong cuoi cua khoa co exam>0; labels:171-186); khong co trong cong thuc diem', 'khong co', BEH,
  'cung ho voi problem_count (cung nguon su kien nop)'),
 ('first_video_day_from_enroll', 'outside_current_grade_group', 'video', 'So ngay tu luc enroll den su kien video dau tien den cutoff', f'{FEAT}:229 (min days_from_enroll; dong 216 dinh nghia days_from_enroll)', SEL_VIDEO,
  'khong co trong nhan (thanh phan video cua nhan la watch_percent = min(1, watched_videos/video_counts), labels:313, 337)', 'khong co', BEH,
  'dai luong thoi gian, khong phai dem'),
 ('last_video_day_from_enroll', 'outside_current_grade_group', 'video', 'So ngay tu luc enroll den su kien video cuoi cung den cutoff', f'{FEAT}:230', SEL_VIDEO,
  'khong co trong nhan', 'khong co', BEH, 'dai luong thoi gian; tang theo do dai prefix'),
 ('problem_context_count', 'outside_current_grade_group', 'problem', 'So context_id khac nhau da nop den cutoff', f'{FEAT}:291', SEL_PROB,
  'khong co trong cong thuc diem', 'khong co', BEH, 'cung ho voi problem_count'),
 ('problem_count', 'outside_current_grade_group', 'problem', 'So problem_id khac nhau da nop den cutoff (tu so cua problem_catalog_coverage)', f'{FEAT}:289; problem_catalog_coverage = problem_count/course_problem_count tai dong 308-309', SEL_PROB,
  'khong la so hang trong cong thuc diem (nhan dung tong best_correct_ratio / so problem catalog); la tu so cua problem_catalog_coverage (proxy da dang ky) [kiem thuc nghiem: p/empirical_main_view_checks.csv, max|gia tri - problem_count/course_problem_count| = 0]; bang assignment_problem_attempted_count + exam_problem_attempted_count cua nhan, gioi han trong prefix',
  'problem_catalog_coverage (hop dong v3, 19 ten); assignment_/exam_problem_attempted_count (LO_LABEL_PROXY_COLUMNS cua wide_imputation, khong thuoc 19 ten)', BEH,
  'ranh gioi: la tu so cua mot proxy da dang ky; tuong tu problem_count cua CQ trong danh sach quyet dinh 21'),
 ('segment_count', 'outside_current_grade_group', 'video', 'So doan (segment) video den cutoff (so su kien)', f'{FEAT}:224', SEL_VIDEO,
  'khong co trong cong thuc diem; nhan dem resource_id khac nhau (watched_videos), khong dem su kien', 'khong co', BEH,
  'la tu so cua video_events_per_active_day, avg_segment_count_per_video'),
 ('segment_duration_seconds', 'outside_current_grade_group', 'video', 'Tong do dai (end_point - start_point, giay) cua cac doan video den cutoff', f'{FEAT}:221', SEL_VIDEO,
  'khong co trong cong thuc diem; nhan khong dung thoi luong xem', 'khong co', BEH, ''),
 ('session_duration_std', 'outside_current_grade_group', 'video', 'Do lech chuan do dai phien xem (cat phien khi nghi > 30 phut) den cutoff', f'{FEAT}:254-276 (sessions, session_std)', SEL_VIDEO,
  'khong co trong nhan', 'khong co', BEH, 'chi duoc tinh khi co su kien video'),
 ('unique_video_count', 'outside_current_grade_group', 'video', 'So resource_id video khac nhau da xem den cutoff (tu so cua video_catalog_coverage)', f'{FEAT}:227; video_catalog_coverage = unique_video_count/course_video_count tai dong 242', SEL_VIDEO,
  'TRUNG voi watched_videos cua nhan (labels:250-252: countDistinct resource_id) gioi han trong prefix; watched_videos la tu so cua watch_percent, thanh phan video_weight*watch_percent cua performance_score (labels:313, 337); [kiem thuc nghiem: p/empirical_main_view_checks.csv, max|video_catalog_coverage - unique_video_count/video_counts| = 0]',
  'watched_videos, watch_percent, video_catalog_coverage (hop dong v3, 19 ten)', COMP,
  'la phien ban prefix cua thanh phan video cua nhan; chua chuan hoa theo catalog (phien ban chuan hoa la video_catalog_coverage, proxy da dang ky)'),
 ('video_events_per_active_day', 'outside_current_grade_group', 'video', 'segment_count / so ngay co xem video den cutoff', f'{FEAT}:240', SEL_VIDEO,
  'khong co trong nhan; khong chia cho catalog (chia cho so ngay hoat dong)', 'khong co', BEH, ''),
 # ---- nhom diem hien hanh (LOCKED 2026-10-01) ----
 ('score_sum', 'current_grade_group', 'problem', 'Tong diem (score) cua moi lan nop den cutoff (khong lay best theo problem)', f'{FEAT}:292; tu so cua problem_score_catalog_coverage (dong 310)', SEL_PROB,
  'cung dai luong score (diem tren diem toi da) ma nhan dung o dang best_correct_ratio = clip(score/full_score) moi problem; o day la tong diem tho cua moi lan nop, khong clip, khong best-per-problem, chua chia catalog [kiem thuc nghiem: max|problem_score_catalog_coverage - score_sum/course_problem_full_score_sum| = 0]',
  'problem_score_catalog_coverage, assignment_/exam_best_correct_sum (hop dong v3)', COMP, 'ranh gioi: phien ban cap lan nop cua diem; nhom dang ky la current_grade_group'),
 ('score_mean', 'current_grade_group', 'problem', 'Trung binh diem (score) cua cac lan nop den cutoff', f'{FEAT}:293', SEL_PROB,
  'trung binh cap lan nop cua score; khong chia full_score, khong best-per-problem', 'assignment_/exam_best_correct_sum (hop dong v3)', COMP, 'ranh gioi: nhu score_sum'),
 ('score_fraction_mean', 'current_grade_group', 'problem', 'Trung binh score/full_score cua cac lan nop den cutoff', f'{FEAT}:295 (score_fraction dong 285)', SEL_PROB,
  'cung ty le score/full_score ma nhan dung (labels:213); khac: trung binh theo lan nop (khong best-per-problem, khong clip), khong chia so problem catalog',
  'assignment_ratio_catalog, exam_ratio_catalog, assignment_/exam_best_correct_sum (hop dong v3)', COMP, 'ranh gioi: phien ban cap lan nop cua correct_ratio cua nhan'),
 ('correct_problem_count', 'current_grade_group', 'problem', 'So lan nop co is_correct = 1 den cutoff (tong is_correct_clean)', f'{FEAT}:297 (is_correct_clean dong 287)', SEL_PROB,
  'nhan khong doc cot is_correct (chi dung score/full_score); khong la so hang cong thuc diem', 'khong co ten tuong ung trong hop dong 19 ten; thanh vien current_grade_group trong LO_PROXY_CONTRACT', BEH,
  'ranh gioi: thuoc current_grade_group theo dang ky (LOCKED 2026-10-01); duoc xem la BEH vi nhan khong doc is_correct'),
]

d = pd.read_csv(f'{QA4}/qa23_fullrows/qa23_audit_by_feature.csv')
l = d[d.task == 'LO'].copy()
l['base'] = l.column_name.str.replace(r'_P[1-4]$', '', regex=True)
l['col_phase'] = l.column_name.str.extract(r'_(P[1-4])$')[0]
rows, slices = [], []
for (base, grp, fam, meas, code, prefix, labrel, proxyname, cls, note) in B:
    s = l[l.base == base]
    assert len(s) == 30, (base, len(s))
    rec = dict(base=base, group=grp, family=fam, measures=meas, source_code=code, uses_only_prefix_events='yes',
               prefix_rule=prefix, relation_to_label_formula=labrel, related_registered_proxy_names=proxyname,
               classification=cls, note=note)
    top = s.loc[s.spearman_abs.idxmax()]
    rec.update(max_abs_rho_all_slices=round(float(top.spearman_abs), 6), max_at_window=top.window_id, max_at_phase_audit=top.phase_id,
               max_at_column=top.column_name, max_n_obs=int(top.n_obs), n_slices_ge_0_5=0)
    for w in ['W1', 'W2', 'W3']:
        for p in ['P1', 'P2', 'P3', 'P4']:
            sl = s[(s.window_id == w) & (s.phase_id == p)]
            m = sl.loc[sl.spearman_abs.idxmax()] if sl.spearman_abs.notna().any() else sl.iloc[0]   # rho NaN (cot hang/het NULL): ghi NaN, n_obs thuc
            slices.append(dict(base=base, group=grp, window=w, phase_audit=p, n_columns_visible=len(sl), max_abs_rho=(round(float(m.spearman_abs), 6) if pd.notna(m.spearman_abs) else None),
                               column_at_max=m.column_name, n_obs_at_max=int(m.n_obs), rho_signed_at_max=(round(float(m.spearman_rho), 6) if pd.notna(m.spearman_rho) else None), nmi_at_max=(round(float(m.nmi), 6) if pd.notna(m.nmi) else None),
                               needs_review_rule_ge_0_5=bool(m.spearman_abs >= 0.5)))
            rec[f'max_abs_rho_{w}_{p}'] = (round(float(m.spearman_abs), 6) if pd.notna(m.spearman_abs) else None); rec[f'n_obs_{w}_{p}'] = int(m.n_obs)
    rec['n_slices_ge_0_5'] = sum(1 for x in slices if x['base'] == base and x['needs_review_rule_ge_0_5'])
    fl = [x['n_obs_at_max'] for x in slices if x['base'] == base and x['needs_review_rule_ge_0_5']]
    rec['min_n_obs_among_slices_ge_0_5'] = min(fl) if fl else None
    rows.append(rec)
c = pd.DataFrame(rows); sl = pd.DataFrame(slices)
c.to_csv(f'{OUT}/qa23_lo_review_candidates.csv', index=False)
sl.to_csv(f'{OUT}/qa23_lo_review_candidates_by_slice.csv', index=False)
print(c[['base', 'group', 'classification', 'max_abs_rho_all_slices', 'max_at_window', 'max_at_phase_audit', 'max_at_column', 'max_n_obs', 'n_slices_ge_0_5']].to_string())
print(c.groupby(['group', 'classification']).size())
