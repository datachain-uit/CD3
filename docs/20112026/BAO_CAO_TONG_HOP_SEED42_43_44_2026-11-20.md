# Báo cáo tổng hợp kết quả seed 42, 43 và 44, cấu hình meta-dataset và meta-model (CQ và LO) — 20/11/2026

Báo cáo gộp kết quả hiệu suất của các mô hình đã chạy xong với ba seed 42, 43 và 44, cho hai tác vụ CQ và LO, ba cửa sổ W1–W3 và 17 pipeline V0–V16, sáu mô hình: F1 (RNN, LSTM, GRU, BILSTM), F2 (PatchTST) và F3 (Mantis V2). Báo cáo mô tả thêm bàn giao seed 44, cấu hình của meta-dataset ba seed và cấu hình, kết quả của meta-model (M-15). Mọi số trong bảng lấy từ release ba seed và từ các tệp nguồn nêu ở mục 8; không số nào được gõ tay.

## 1. Phạm vi và độ phủ

Số ô (cửa sổ × pipeline) có kết quả trên tập kiểm tra, mỗi ô đủ bốn pha P1–P4:

| Task | Họ | Mô hình | Seed 42 | Seed 43 | Seed 44 |
|---|---|---|---|---|---|
| CQ | F1 | RNN | 51 | 51 | 51 |
| CQ | F1 | LSTM | 51 | 51 | 51 |
| CQ | F1 | GRU | 51 | 51 | 51 |
| CQ | F1 | BILSTM | 51 | 51 | 51 |
| CQ | F2 | PATCHTST | 51 | 51 | 51 |
| CQ | F3 | MANTIS_V2 | 51 | 51 | 51 |
| LO | F1 | RNN | 51 | 51 | 51 |
| LO | F1 | LSTM | 51 | 51 | 51 |
| LO | F1 | GRU | 51 | 51 | 51 |
| LO | F1 | BILSTM | 51 | 51 | 51 |
| LO | F2 | PATCHTST | 51 | 51 | 51 |
| LO | F3 | MANTIS_V2 | 51 | 51 | 51 |

Tất cả 36 tổ hợp (task × mô hình × seed) trên 36 đều đủ 51 ô, mỗi ô 8 dòng ở mức seed (2 tập × 4 pha) nên mỗi tổ hợp có 408 dòng. Số trong các bảng dưới đây là **trung bình trên tập TEST**, lấy trung bình bốn pha P1–P4 của mỗi ô, rồi trung bình trên 51 ô.

## 2. Hiệu suất mô hình

### 2.1 Chỉ số chính theo task, mô hình và seed

| Task | Họ | Mô hình | Seed | F1 macro | Balanced acc | Kappa | G-mean | Log loss | Brier | ECE | AccTEMPO M3 cal (= M4) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| CQ | F1 | RNN | 42 | 0.7129 | 0.7005 | 0.6597 | 0.6256 | 0.1556 | 0.0658 | 0.0330 | 0.7423 |
| CQ | F1 | RNN | 43 | 0.7119 | 0.6969 | 0.6593 | 0.6197 | 0.1647 | 0.0668 | 0.0338 | 0.7416 |
| CQ | F1 | RNN | 44 | 0.7108 | 0.6957 | 0.6587 | 0.6181 | 0.1644 | 0.0667 | 0.0324 | 0.7412 |
| CQ | F1 | LSTM | 42 | 0.7138 | 0.6987 | 0.6602 | 0.6236 | 0.1534 | 0.0651 | 0.0330 | 0.7422 |
| CQ | F1 | LSTM | 43 | 0.7105 | 0.6931 | 0.6579 | 0.6157 | 0.1615 | 0.0660 | 0.0332 | 0.7406 |
| CQ | F1 | LSTM | 44 | 0.7098 | 0.6929 | 0.6564 | 0.6144 | 0.1651 | 0.0673 | 0.0362 | 0.7402 |
| CQ | F1 | GRU | 42 | 0.7164 | 0.7005 | 0.6622 | 0.6280 | 0.1525 | 0.0648 | 0.0323 | 0.7432 |
| CQ | F1 | GRU | 43 | 0.7147 | 0.6979 | 0.6623 | 0.6218 | 0.1631 | 0.0662 | 0.0349 | 0.7425 |
| CQ | F1 | GRU | 44 | 0.7134 | 0.6961 | 0.6606 | 0.6187 | 0.1643 | 0.0666 | 0.0353 | 0.7418 |
| CQ | F1 | BILSTM | 42 | 0.7129 | 0.6974 | 0.6597 | 0.6215 | 0.1535 | 0.0651 | 0.0304 | 0.7419 |
| CQ | F1 | BILSTM | 43 | 0.7129 | 0.6958 | 0.6600 | 0.6175 | 0.1622 | 0.0660 | 0.0323 | 0.7417 |
| CQ | F1 | BILSTM | 44 | 0.7117 | 0.6943 | 0.6587 | 0.6162 | 0.1657 | 0.0672 | 0.0346 | 0.7410 |
| CQ | F2 | PATCHTST | 42 | 0.7088 | 0.6860 | 0.6477 | 0.6129 | 0.1572 | 0.0659 | 0.0251 | 0.7382 |
| CQ | F2 | PATCHTST | 43 | 0.7093 | 0.6885 | 0.6484 | 0.6136 | 0.1610 | 0.0666 | 0.0280 | 0.7385 |
| CQ | F2 | PATCHTST | 44 | 0.7134 | 0.6892 | 0.6517 | 0.6164 | 0.1515 | 0.0651 | 0.0227 | 0.7401 |
| CQ | F3 | MANTIS_V2 | 42 | 0.6674 | 0.6659 | 0.6138 | 0.5777 | 0.2152 | 0.0821 | 0.0409 | 0.7221 |
| CQ | F3 | MANTIS_V2 | 43 | 0.6704 | 0.6672 | 0.6173 | 0.5806 | 0.2076 | 0.0800 | 0.0374 | 0.7235 |
| CQ | F3 | MANTIS_V2 | 44 | 0.6719 | 0.6677 | 0.6194 | 0.5846 | 0.1899 | 0.0799 | 0.0383 | 0.7240 |
| LO | F1 | RNN | 42 | 0.4165 | 0.5223 | 0.2518 | 0.2159 | 0.1762 | 0.0746 | 0.0347 | 0.5754 |
| LO | F1 | RNN | 43 | 0.4266 | 0.5317 | 0.2687 | 0.2134 | 0.1700 | 0.0734 | 0.0333 | 0.5808 |
| LO | F1 | RNN | 44 | 0.4217 | 0.5277 | 0.2591 | 0.2210 | 0.1728 | 0.0742 | 0.0342 | 0.5780 |
| LO | F1 | LSTM | 42 | 0.4187 | 0.5180 | 0.2537 | 0.1730 | 0.1736 | 0.0724 | 0.0335 | 0.5757 |
| LO | F1 | LSTM | 43 | 0.4116 | 0.5112 | 0.2548 | 0.1375 | 0.1667 | 0.0714 | 0.0329 | 0.5737 |
| LO | F1 | LSTM | 44 | 0.4168 | 0.5184 | 0.2595 | 0.1711 | 0.1646 | 0.0716 | 0.0333 | 0.5762 |
| LO | F1 | GRU | 42 | 0.4271 | 0.5326 | 0.2669 | 0.2750 | 0.1828 | 0.0733 | 0.0334 | 0.5811 |
| LO | F1 | GRU | 43 | 0.4218 | 0.5248 | 0.2621 | 0.2151 | 0.1816 | 0.0745 | 0.0339 | 0.5785 |
| LO | F1 | GRU | 44 | 0.4234 | 0.5302 | 0.2691 | 0.2354 | 0.1732 | 0.0723 | 0.0327 | 0.5806 |
| LO | F1 | BILSTM | 42 | 0.4126 | 0.5146 | 0.2474 | 0.1833 | 0.1674 | 0.0715 | 0.0323 | 0.5734 |
| LO | F1 | BILSTM | 43 | 0.4143 | 0.5174 | 0.2544 | 0.1635 | 0.1630 | 0.0715 | 0.0322 | 0.5751 |
| LO | F1 | BILSTM | 44 | 0.4167 | 0.5195 | 0.2582 | 0.1771 | 0.1789 | 0.0735 | 0.0327 | 0.5763 |
| LO | F2 | PATCHTST | 42 | 0.4190 | 0.5377 | 0.2695 | 0.2404 | 0.1609 | 0.0672 | 0.0290 | 0.5812 |
| LO | F2 | PATCHTST | 43 | 0.4185 | 0.5438 | 0.2637 | 0.2564 | 0.1683 | 0.0701 | 0.0298 | 0.5813 |
| LO | F2 | PATCHTST | 44 | 0.4145 | 0.5442 | 0.2633 | 0.2003 | 0.1645 | 0.0715 | 0.0309 | 0.5803 |
| LO | F3 | MANTIS_V2 | 42 | 0.3716 | 0.4116 | 0.1488 | 0.0448 | 0.2351 | 0.0867 | 0.0541 | 0.5335 |
| LO | F3 | MANTIS_V2 | 43 | 0.3703 | 0.4232 | 0.1486 | 0.0317 | 0.2316 | 0.0874 | 0.0581 | 0.5352 |
| LO | F3 | MANTIS_V2 | 44 | 0.3666 | 0.4019 | 0.1418 | 0.0276 | 0.2464 | 0.0799 | 0.0431 | 0.5300 |

**Tên chỉ số composite.** Cột `acctempo_m3_cal` của meta-dataset (AccTEMPO_M3^(cal)) là cùng một đại lượng với cột `acctempo_m4` trong các gói facts và các báo cáo trước (phiên bản M4): hai cột có giá trị trùng nhau (chênh lệch tuyệt đối lớn nhất 0.0 trên 408 dòng CQ PatchTST seed 44), công thức S_perf^0,6 × S_san+_v2^0,4 với mỗi thành phần kẹp dưới 1e-3. Bộ lắp meta-dataset đổi tên `acctempo_m4` thành `acctempo_m3_cal`; báo cáo này dùng tên `acctempo_m3_cal` và ghi "= M4" khi cần nối với báo cáo cũ.

Trung bình và độ lệch chuẩn giữa ba seed của chỉ số chính (F1 macro):

| Task | Họ | Mô hình | F1 macro (trung bình 3 seed) | Độ lệch chuẩn | AccTEMPO M3 cal (trung bình) | Độ lệch chuẩn |
|---|---|---|---|---|---|---|
| CQ | F1 | RNN | 0.7118 | 0.0011 | 0.7417 | 0.0006 |
| CQ | F1 | LSTM | 0.7114 | 0.0021 | 0.7410 | 0.0011 |
| CQ | F1 | GRU | 0.7148 | 0.0015 | 0.7425 | 0.0007 |
| CQ | F1 | BILSTM | 0.7125 | 0.0007 | 0.7416 | 0.0005 |
| CQ | F2 | PATCHTST | 0.7105 | 0.0025 | 0.7389 | 0.0010 |
| CQ | F3 | MANTIS_V2 | 0.6699 | 0.0023 | 0.7232 | 0.0010 |
| LO | F1 | RNN | 0.4216 | 0.0051 | 0.5781 | 0.0027 |
| LO | F1 | LSTM | 0.4157 | 0.0037 | 0.5752 | 0.0013 |
| LO | F1 | GRU | 0.4241 | 0.0027 | 0.5800 | 0.0014 |
| LO | F1 | BILSTM | 0.4146 | 0.0020 | 0.5749 | 0.0015 |
| LO | F2 | PATCHTST | 0.4173 | 0.0025 | 0.5809 | 0.0005 |
| LO | F3 | MANTIS_V2 | 0.3695 | 0.0026 | 0.5329 | 0.0026 |

### 2.2 V0 (không can thiệp) so với V1–V16 (imputation và cân bằng lớp)

Mười bảy pipeline gồm ba nhóm: **V0** (không can thiệp); **imputation thuần** V1 (median), V5 (mean), V9 (ExtraTrees), V13 (MICE), balancer = NONE; **imputation cộng cân bằng lớp** (12 pipeline còn lại, mỗi imputer đi với CDSMOTE, SASMOTE hoặc RADIUS_SMOTE). Vì vậy V1–V16 không đồng nghĩa với "có tăng cường": bốn pipeline trong số đó chỉ là imputation. Bảng tách ba nhóm, và tách tác động của cân bằng lớp (mỗi pipeline cân bằng trừ pipeline imputation thuần cùng imputer, cùng cửa sổ):

| Task | Họ | Mô hình | Seed | F1 macro V0 | F1 macro imputation thuần (4 pipeline) | F1 macro imputation + cân bằng (12) | Imputation thuần − V0 | Imputation + cân bằng − V0 | Riêng cân bằng lớp (so với pipeline cha) | Ô cân bằng hơn pipeline cha |
|---|---|---|---|---|---|---|---|---|---|---|
| CQ | F1 | RNN | 42 | 0.7194 | 0.7097 | 0.7134 | -0.0098 | -0.0060 | 0.0038 | 58% |
| CQ | F1 | RNN | 43 | 0.7084 | 0.7117 | 0.7122 | 0.0033 | 0.0038 | 0.0005 | 69% |
| CQ | F1 | RNN | 44 | 0.7103 | 0.7139 | 0.7097 | 0.0036 | -0.0006 | -0.0041 | 44% |
| CQ | F1 | LSTM | 42 | 0.7184 | 0.7121 | 0.7140 | -0.0063 | -0.0044 | 0.0019 | 53% |
| CQ | F1 | LSTM | 43 | 0.7061 | 0.7074 | 0.7120 | 0.0013 | 0.0059 | 0.0046 | 69% |
| CQ | F1 | LSTM | 44 | 0.7100 | 0.7084 | 0.7103 | -0.0016 | 0.0002 | 0.0019 | 64% |
| CQ | F1 | GRU | 42 | 0.7169 | 0.7136 | 0.7172 | -0.0033 | 0.0003 | 0.0036 | 61% |
| CQ | F1 | GRU | 43 | 0.7191 | 0.7146 | 0.7144 | -0.0045 | -0.0046 | -0.0002 | 50% |
| CQ | F1 | GRU | 44 | 0.7056 | 0.7147 | 0.7136 | 0.0091 | 0.0080 | -0.0011 | 47% |
| CQ | F1 | BILSTM | 42 | 0.7111 | 0.7107 | 0.7137 | -0.0003 | 0.0027 | 0.0030 | 61% |
| CQ | F1 | BILSTM | 43 | 0.7163 | 0.7131 | 0.7126 | -0.0032 | -0.0037 | -0.0005 | 58% |
| CQ | F1 | BILSTM | 44 | 0.7063 | 0.7138 | 0.7115 | 0.0075 | 0.0051 | -0.0023 | 50% |
| CQ | F2 | PATCHTST | 42 | 0.7107 | 0.6955 | 0.7131 | -0.0152 | 0.0024 | 0.0176 | 92% |
| CQ | F2 | PATCHTST | 43 | 0.7192 | 0.6997 | 0.7116 | -0.0195 | -0.0076 | 0.0119 | 72% |
| CQ | F2 | PATCHTST | 44 | 0.6998 | 0.7123 | 0.7148 | 0.0126 | 0.0151 | 0.0025 | 75% |
| CQ | F3 | MANTIS_V2 | 42 | 0.6565 | 0.6555 | 0.6723 | -0.0009 | 0.0158 | 0.0167 | 69% |
| CQ | F3 | MANTIS_V2 | 43 | 0.6969 | 0.6630 | 0.6707 | -0.0339 | -0.0263 | 0.0076 | 56% |
| CQ | F3 | MANTIS_V2 | 44 | 0.6577 | 0.6716 | 0.6731 | 0.0139 | 0.0155 | 0.0016 | 56% |
| LO | F1 | RNN | 42 | 0.4035 | 0.4234 | 0.4153 | 0.0199 | 0.0117 | -0.0081 | 28% |
| LO | F1 | RNN | 43 | 0.4267 | 0.4275 | 0.4264 | 0.0008 | -0.0003 | -0.0011 | 28% |
| LO | F1 | RNN | 44 | 0.4146 | 0.4090 | 0.4264 | -0.0056 | 0.0118 | 0.0174 | 39% |
| LO | F1 | LSTM | 42 | 0.3979 | 0.4068 | 0.4244 | 0.0088 | 0.0265 | 0.0177 | 47% |
| LO | F1 | LSTM | 43 | 0.4019 | 0.3981 | 0.4169 | -0.0038 | 0.0150 | 0.0188 | 53% |
| LO | F1 | LSTM | 44 | 0.4124 | 0.4015 | 0.4223 | -0.0109 | 0.0099 | 0.0208 | 61% |
| LO | F1 | GRU | 42 | 0.4263 | 0.4212 | 0.4292 | -0.0051 | 0.0029 | 0.0080 | 36% |
| LO | F1 | GRU | 43 | 0.4227 | 0.4123 | 0.4249 | -0.0104 | 0.0022 | 0.0126 | 44% |
| LO | F1 | GRU | 44 | 0.4177 | 0.4271 | 0.4226 | 0.0095 | 0.0049 | -0.0046 | 28% |
| LO | F1 | BILSTM | 42 | 0.4011 | 0.3914 | 0.4207 | -0.0097 | 0.0196 | 0.0293 | 50% |
| LO | F1 | BILSTM | 43 | 0.3944 | 0.3992 | 0.4210 | 0.0048 | 0.0266 | 0.0218 | 56% |
| LO | F1 | BILSTM | 44 | 0.3929 | 0.4020 | 0.4236 | 0.0091 | 0.0307 | 0.0216 | 42% |
| LO | F2 | PATCHTST | 42 | 0.4319 | 0.4280 | 0.4149 | -0.0039 | -0.0170 | -0.0131 | 17% |
| LO | F2 | PATCHTST | 43 | 0.3967 | 0.4351 | 0.4148 | 0.0384 | 0.0181 | -0.0202 | 19% |
| LO | F2 | PATCHTST | 44 | 0.4398 | 0.4129 | 0.4129 | -0.0268 | -0.0269 | -0.0000 | 19% |
| LO | F3 | MANTIS_V2 | 42 | 0.3310 | 0.3569 | 0.3798 | 0.0259 | 0.0488 | 0.0229 | 69% |
| LO | F3 | MANTIS_V2 | 43 | 0.3581 | 0.3398 | 0.3815 | -0.0183 | 0.0235 | 0.0418 | 61% |
| LO | F3 | MANTIS_V2 | 44 | 0.3511 | 0.3396 | 0.3768 | -0.0115 | 0.0257 | 0.0372 | 75% |

Gộp V1–V16 (không tách nhóm) so với V0 cho F1 macro và AccTEMPO M3 cal nằm trong `tables/summary_V0_vs_V1V16.csv`, kèm tỉ lệ ô V1–V16 hơn V0 trong `tables/delta_V0_vs_V1V16_macro_f1.csv`. Các chênh lệch trong bảng là mô tả, không có kiểm định.

### 2.3 Theo cửa sổ (F1 macro)

| Task | Họ | Mô hình | Cửa sổ | Seed 42 | Seed 43 | Seed 44 |
|---|---|---|---|---|---|---|
| CQ | F1 | RNN | W1 | 0.7039 | 0.7041 | 0.7033 |
| CQ | F1 | RNN | W2 | 0.6533 | 0.6541 | 0.6510 |
| CQ | F1 | RNN | W3 | 0.7815 | 0.7774 | 0.7779 |
| CQ | F1 | LSTM | W1 | 0.7037 | 0.7046 | 0.7035 |
| CQ | F1 | LSTM | W2 | 0.6519 | 0.6468 | 0.6483 |
| CQ | F1 | LSTM | W3 | 0.7858 | 0.7802 | 0.7777 |
| CQ | F1 | GRU | W1 | 0.7054 | 0.7056 | 0.7052 |
| CQ | F1 | GRU | W2 | 0.6614 | 0.6598 | 0.6576 |
| CQ | F1 | GRU | W3 | 0.7823 | 0.7788 | 0.7772 |
| CQ | F1 | BILSTM | W1 | 0.7029 | 0.7036 | 0.7026 |
| CQ | F1 | BILSTM | W2 | 0.6527 | 0.6549 | 0.6504 |
| CQ | F1 | BILSTM | W3 | 0.7830 | 0.7803 | 0.7821 |
| CQ | F2 | PATCHTST | W1 | 0.7028 | 0.7025 | 0.7037 |
| CQ | F2 | PATCHTST | W2 | 0.6528 | 0.6642 | 0.6668 |
| CQ | F2 | PATCHTST | W3 | 0.7708 | 0.7611 | 0.7697 |
| CQ | F3 | MANTIS_V2 | W1 | 0.6541 | 0.6570 | 0.6585 |
| CQ | F3 | MANTIS_V2 | W2 | 0.6592 | 0.6588 | 0.6675 |
| CQ | F3 | MANTIS_V2 | W3 | 0.6890 | 0.6954 | 0.6897 |
| LO | F1 | RNN | W1 | 0.3220 | 0.3221 | 0.3222 |
| LO | F1 | RNN | W2 | 0.3486 | 0.3478 | 0.3492 |
| LO | F1 | RNN | W3 | 0.5788 | 0.6099 | 0.5935 |
| LO | F1 | LSTM | W1 | 0.3235 | 0.3237 | 0.3237 |
| LO | F1 | LSTM | W2 | 0.3486 | 0.3491 | 0.3489 |
| LO | F1 | LSTM | W3 | 0.5841 | 0.5620 | 0.5779 |
| LO | F1 | GRU | W1 | 0.3230 | 0.3231 | 0.3237 |
| LO | F1 | GRU | W2 | 0.3543 | 0.3514 | 0.3518 |
| LO | F1 | GRU | W3 | 0.6041 | 0.5911 | 0.5946 |
| LO | F1 | BILSTM | W1 | 0.3239 | 0.3241 | 0.3239 |
| LO | F1 | BILSTM | W2 | 0.3482 | 0.3485 | 0.3483 |
| LO | F1 | BILSTM | W3 | 0.5658 | 0.5704 | 0.5778 |
| LO | F2 | PATCHTST | W1 | 0.3311 | 0.3320 | 0.3235 |
| LO | F2 | PATCHTST | W2 | 0.3529 | 0.3557 | 0.3542 |
| LO | F2 | PATCHTST | W3 | 0.5728 | 0.5679 | 0.5657 |
| LO | F3 | MANTIS_V2 | W1 | 0.3244 | 0.3220 | 0.3230 |
| LO | F3 | MANTIS_V2 | W2 | 0.3385 | 0.3390 | 0.3369 |
| LO | F3 | MANTIS_V2 | W3 | 0.4517 | 0.4499 | 0.4398 |

### 2.4 Độ lệch giữa ba seed (cùng ô)

Với mỗi cặp seed, trên cùng 51 ô: độ lệch tuyệt đối trung bình của F1 macro, hệ số Pearson giữa các ô, và hệ số Spearman của thứ hạng 17 pipeline (theo trung bình mỗi pipeline):

| Task | Họ | Mô hình | Cặp seed | |chênh| trung bình | Pearson (ô) | Spearman (pipeline) | Pipeline tốt nhất (hai seed) |
|---|---|---|---|---|---|---|---|
| CQ | F1 | RNN | 42–43 | 0.0078 | 0.974 | 0.233 | V10 / V9 |
| CQ | F1 | RNN | 42–44 | 0.0082 | 0.970 | -0.221 | V10 / V13 |
| CQ | F1 | RNN | 43–44 | 0.0067 | 0.980 | 0.520 | V9 / V13 |
| CQ | F1 | LSTM | 42–43 | 0.0071 | 0.987 | 0.522 | V11 / V3 |
| CQ | F1 | LSTM | 42–44 | 0.0087 | 0.985 | 0.341 | V11 / V16 |
| CQ | F1 | LSTM | 43–44 | 0.0070 | 0.984 | 0.311 | V3 / V16 |
| CQ | F1 | GRU | 42–43 | 0.0051 | 0.992 | 0.551 | V6 / V6 |
| CQ | F1 | GRU | 42–44 | 0.0060 | 0.988 | 0.449 | V6 / V6 |
| CQ | F1 | GRU | 43–44 | 0.0062 | 0.983 | 0.150 | V6 / V6 |
| CQ | F1 | BILSTM | 42–43 | 0.0058 | 0.987 | 0.431 | V3 / V15 |
| CQ | F1 | BILSTM | 42–44 | 0.0073 | 0.984 | 0.583 | V3 / V15 |
| CQ | F1 | BILSTM | 43–44 | 0.0059 | 0.986 | 0.654 | V15 / V15 |
| CQ | F2 | PATCHTST | 42–43 | 0.0161 | 0.887 | 0.333 | V10 / V11 |
| CQ | F2 | PATCHTST | 42–44 | 0.0128 | 0.918 | 0.331 | V10 / V11 |
| CQ | F2 | PATCHTST | 43–44 | 0.0136 | 0.883 | 0.142 | V11 / V11 |
| CQ | F3 | MANTIS_V2 | 42–43 | 0.0165 | 0.816 | 0.821 | V4 / V1 |
| CQ | F3 | MANTIS_V2 | 42–44 | 0.0140 | 0.823 | 0.833 | V4 / V4 |
| CQ | F3 | MANTIS_V2 | 43–44 | 0.0176 | 0.678 | 0.694 | V1 / V4 |
| LO | F1 | RNN | 42–43 | 0.0202 | 0.961 | 0.017 | V8 / V9 |
| LO | F1 | RNN | 42–44 | 0.0203 | 0.949 | 0.230 | V8 / V8 |
| LO | F1 | RNN | 43–44 | 0.0204 | 0.943 | -0.047 | V9 / V8 |
| LO | F1 | LSTM | 42–43 | 0.0159 | 0.977 | 0.426 | V14 / V11 |
| LO | F1 | LSTM | 42–44 | 0.0169 | 0.966 | 0.424 | V14 / V6 |
| LO | F1 | LSTM | 43–44 | 0.0136 | 0.978 | 0.571 | V11 / V6 |
| LO | F1 | GRU | 42–43 | 0.0110 | 0.986 | 0.495 | V11 / V11 |
| LO | F1 | GRU | 42–44 | 0.0156 | 0.972 | 0.314 | V11 / V14 |
| LO | F1 | GRU | 43–44 | 0.0149 | 0.973 | 0.270 | V11 / V14 |
| LO | F1 | BILSTM | 42–43 | 0.0158 | 0.958 | 0.275 | V14 / V6 |
| LO | F1 | BILSTM | 42–44 | 0.0146 | 0.968 | 0.608 | V14 / V8 |
| LO | F1 | BILSTM | 43–44 | 0.0114 | 0.969 | 0.603 | V6 / V8 |
| LO | F2 | PATCHTST | 42–43 | 0.0178 | 0.964 | 0.299 | V5 / V1 |
| LO | F2 | PATCHTST | 42–44 | 0.0218 | 0.921 | 0.449 | V5 / V6 |
| LO | F2 | PATCHTST | 43–44 | 0.0254 | 0.907 | -0.074 | V1 / V6 |
| LO | F3 | MANTIS_V2 | 42–43 | 0.0148 | 0.925 | 0.657 | V8 / V7 |
| LO | F3 | MANTIS_V2 | 42–44 | 0.0174 | 0.886 | 0.542 | V8 / V7 |
| LO | F3 | MANTIS_V2 | 43–44 | 0.0120 | 0.953 | 0.814 | V7 / V7 |

Tóm tắt: giá trị theo ô khá ổn định giữa các seed (Pearson trung bình CQ 0.934, LO 0.953; độ lệch tuyệt đối trung bình CQ 0.010, LO 0.017), nhưng thứ hạng 17 pipeline theo trung bình kém ổn định (Spearman trung bình CQ 0.427, LO 0.382); pipeline tốt nhất giữ nguyên giữa hai seed ở 33% (CQ) và 17% (LO) số cặp. Đây là lý do meta-model được huấn luyện trên ba seed.

### 2.5 s_leak

`s_leak` của cả ba seed được chép từ bảng tham chiếu đã đăng ký (`s_leak_source = REFERENCE_TABLE_COPY_NO_REFIT`), không fit lại đầu dò. Chênh lệch lớn nhất của `s_leak` giữa ba seed trên mọi (task, cửa sổ, tập, pha) là 1.11e-16. `probe_seed` ghi 42 (seed của lần fit tham chiếu) ở các gói seed 44.

| Task | Số tổ hợp (cửa sổ, tập, pha) | Nhỏ nhất | Lớn nhất | Chênh lớn nhất giữa seed |
|---|---|---|---|---|
| CQ | 24 | 0.0190 | 0.5558 | 1.11e-16 |
| LO | 24 | 0.0262 | 0.4111 | 1.11e-16 |

## 3. Seed 44: bàn giao và vận hành

### 3.1 Bàn giao

- **Sáu gói facts** (định dạng `_r2`, mỗi gói đủ 51 ô × 4 pha × 2 tập = 408 dòng mỗi mô hình): `CQ|LO/L2_facts/fact_exports/…seed44_…`; bản `staging_incoming` giống hệt; đã đối chiếu từng byte với Drive (biên nhận chuyển giao và ingest L2 đạt, hai gói Mantis kèm nhãn Q-32).
- **M-18 seed 44**: 612 ô (12 tổ hợp × 51), 6,027 dòng epoch; best epoch khớp manifest ở 612/612 ô; 7 ô có hai nguồn đều có history khớp nhau.
- **Commit runner**: 510/510 ô F1 và PatchTST ghi `runner_git_commit = 5ba982958c9ce50ac6be6a28ff9c812e0f17b31e` lúc chạy; 102 ô Mantis không ghi commit trong manifest và dùng bằng chứng hồi tố (commit `6a69b7f6240a2b70ec7e6e478a446cecc2be1ec3`, khớp nội dung file với tar mã).
- **Sửa sau đợt 29**: tiêu đề README theo seed, `probe_seed` = 42 (seed của lần fit tham chiếu), ghi commit dựng gói (`7c24981…`); bản trước khi sửa lưu ở `fact_exports_superseded_20261119`.

### 3.2 Thời gian chạy và năng lượng

Hai loại thời gian được tách riêng: **thời gian train** (`time_train_s`) và **tổng thời gian run** (`time_run_total_s`, gồm cả đọc dữ liệu, suy luận và ghi kết quả). Mỗi loại ghi số ô có dữ liệu (mẫu số của tổng và trung bình); ô thiếu giá trị không được tính vào tổng hay trung bình. Cột năng lượng ghi "không có dữ liệu" khi không ô nào có số đo, không có nghĩa là năng lượng bằng 0.

| Task | Họ | Mô hình | Seed | Số ô | Ô có thời gian train | Tổng train (giờ) | Trung bình train (phút/ô) | Ô có tổng thời gian run | Tổng run (giờ) | Trung bình run (phút/ô) | Ô có năng lượng | Năng lượng đo được (kWh, trên các ô có số đo) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CQ | F1 | RNN | 42 | 51 | 51/51 | 3.7 | 4.4 | 51/51 | 5.6 | 6.6 | 51/51 | 0.16 |
| CQ | F1 | RNN | 43 | 51 | 51/51 | 3.5 | 4.1 | 51/51 | 4.9 | 5.8 | 0/51 | không có dữ liệu |
| CQ | F1 | RNN | 44 | 51 | 51/51 | 3.6 | 4.3 | 51/51 | 5.2 | 6.1 | 51/51 | 0.16 |
| CQ | F1 | LSTM | 42 | 51 | 51/51 | 3.6 | 4.2 | 51/51 | 5.6 | 6.5 | 51/51 | 0.16 |
| CQ | F1 | LSTM | 43 | 51 | 51/51 | 3.0 | 3.5 | 51/51 | 4.3 | 5.0 | 0/51 | không có dữ liệu |
| CQ | F1 | LSTM | 44 | 51 | 51/51 | 2.9 | 3.5 | 51/51 | 4.4 | 5.1 | 51/51 | 0.14 |
| CQ | F1 | GRU | 42 | 51 | 51/51 | 3.1 | 3.7 | 51/51 | 4.7 | 5.5 | 51/51 | 0.14 |
| CQ | F1 | GRU | 43 | 51 | 51/51 | 3.0 | 3.5 | 51/51 | 4.4 | 5.2 | 0/51 | không có dữ liệu |
| CQ | F1 | GRU | 44 | 51 | 51/51 | 3.5 | 4.1 | 51/51 | 5.1 | 6.0 | 51/51 | 0.16 |
| CQ | F1 | BILSTM | 42 | 51 | 51/51 | 4.2 | 5.0 | 51/51 | 6.0 | 7.0 | 51/51 | 0.23 |
| CQ | F1 | BILSTM | 43 | 51 | 51/51 | 4.3 | 5.1 | 51/51 | 6.5 | 7.7 | 0/51 | không có dữ liệu |
| CQ | F1 | BILSTM | 44 | 51 | 51/51 | 3.7 | 4.3 | 51/51 | 5.1 | 6.0 | 51/51 | 0.21 |
| CQ | F2 | PATCHTST | 42 | 51 | 51/51 | 420.6 | 494.8 | 51/51 | 433.3 | 509.8 | 51/51 | 30.39 |
| CQ | F2 | PATCHTST | 43 | 51 | 51/51 | 409.2 | 481.5 | 51/51 | 422.0 | 496.4 | 48/51 | 28.29 |
| CQ | F2 | PATCHTST | 44 | 51 | 51/51 | 440.4 | 518.2 | 51/51 | 454.5 | 534.7 | 44/51 | 26.49 |
| CQ | F3 | MANTIS_V2 | 42 | 51 | 51/51 | 29.8 | 35.1 | 48/51 | 101.2 | 126.5 | 45/51 | 5.48 |
| CQ | F3 | MANTIS_V2 | 43 | 51 | 51/51 | 35.6 | 41.9 | 51/51 | 93.8 | 110.4 | 51/51 | 4.81 |
| CQ | F3 | MANTIS_V2 | 44 | 51 | 51/51 | 34.6 | 40.7 | 51/51 | 89.3 | 105.0 | 50/51 | 4.37 |
| LO | F1 | RNN | 42 | 51 | 51/51 | 2.7 | 3.1 | 51/51 | 3.9 | 4.6 | 51/51 | 0.11 |
| LO | F1 | RNN | 43 | 51 | 51/51 | 2.5 | 2.9 | 51/51 | 3.5 | 4.1 | 51/51 | 0.10 |
| LO | F1 | RNN | 44 | 51 | 51/51 | 2.9 | 3.4 | 51/51 | 4.1 | 4.8 | 51/51 | 0.12 |
| LO | F1 | LSTM | 42 | 51 | 51/51 | 2.6 | 3.0 | 51/51 | 3.7 | 4.3 | 51/51 | 0.11 |
| LO | F1 | LSTM | 43 | 51 | 51/51 | 2.3 | 2.7 | 51/51 | 3.2 | 3.8 | 51/51 | 0.10 |
| LO | F1 | LSTM | 44 | 51 | 51/51 | 2.4 | 2.8 | 51/51 | 3.6 | 4.2 | 51/51 | 0.11 |
| LO | F1 | GRU | 42 | 51 | 51/51 | 2.4 | 2.8 | 51/51 | 3.5 | 4.1 | 51/51 | 0.11 |
| LO | F1 | GRU | 43 | 51 | 51/51 | 2.2 | 2.6 | 51/51 | 3.1 | 3.7 | 51/51 | 0.09 |
| LO | F1 | GRU | 44 | 51 | 51/51 | 2.2 | 2.6 | 51/51 | 3.3 | 3.9 | 51/51 | 0.10 |
| LO | F1 | BILSTM | 42 | 51 | 51/51 | 2.9 | 3.5 | 51/51 | 4.0 | 4.8 | 51/51 | 0.16 |
| LO | F1 | BILSTM | 43 | 51 | 51/51 | 3.2 | 3.8 | 51/51 | 4.5 | 5.3 | 51/51 | 0.16 |
| LO | F1 | BILSTM | 44 | 51 | 51/51 | 3.2 | 3.8 | 51/51 | 4.5 | 5.3 | 51/51 | 0.18 |
| LO | F2 | PATCHTST | 42 | 51 | 51/51 | 343.1 | 403.7 | 51/51 | 352.2 | 414.3 | 51/51 | 24.17 |
| LO | F2 | PATCHTST | 43 | 51 | 51/51 | 290.1 | 341.3 | 51/51 | 297.9 | 350.5 | 46/51 | 18.18 |
| LO | F2 | PATCHTST | 44 | 51 | 51/51 | 354.2 | 416.7 | 51/51 | 362.6 | 426.6 | 51/51 | 25.91 |
| LO | F3 | MANTIS_V2 | 42 | 51 | 51/51 | 22.3 | 26.2 | 51/51 | 60.8 | 71.5 | 46/51 | 2.98 |
| LO | F3 | MANTIS_V2 | 43 | 51 | 51/51 | 22.7 | 26.7 | 51/51 | 70.3 | 82.8 | 51/51 | 3.62 |
| LO | F3 | MANTIS_V2 | 44 | 51 | 51/51 | 22.9 | 27.0 | 51/51 | 64.1 | 75.4 | 51/51 | 3.39 |

#### Ô thiếu dữ liệu thời gian hoặc năng lượng và lý do

Bảng liệt kê mọi tổ hợp (task, mô hình, seed) có ô thiếu thời gian hoặc năng lượng; số ô thiếu tính từ release, lý do lấy từ cột `resource_null_reason` của các gói nguồn. Tổ hợp không có trong bảng thì đủ 51/51 ô. Cột năng lượng của LO đã được điền lại ở release 20261120 (mục 4) và khớp 918/918 run với gói nguồn; các ô LO còn thiếu là các ô mà gói nguồn không có số đo.

| Task | Mô hình | Seed | Ô thiếu thời gian train | Ô thiếu tổng thời gian run | Ô thiếu năng lượng | Lý do |
|---|---|---|---|---|---|---|
| CQ | BILSTM | 43 | 0 | 0 | 51 | không đo năng lượng (`ENERGY_NOT_MEASURED`: `energy_measurement_type = UNAVAILABLE`, 0 mẫu). |
| CQ | GRU | 43 | 0 | 0 | 51 | không đo năng lượng (`ENERGY_NOT_MEASURED`: `energy_measurement_type = UNAVAILABLE`, 0 mẫu). |
| CQ | LSTM | 43 | 0 | 0 | 51 | không đo năng lượng (`ENERGY_NOT_MEASURED`: `energy_measurement_type = UNAVAILABLE`, 0 mẫu). |
| CQ | MANTIS_V2 | 42 | 0 | 3 | 6 | V0 gốc không lưu run manifest, thời gian chạy và năng lượng GPU (`NOT_RECORDED`, 3 ô V0 W1–W3); các ô còn lại: thư viện đo công suất không nạp được (`TELEMETRY_UNAVAILABLE: ModuleNotFoundError`). |
| CQ | MANTIS_V2 | 44 | 0 | 0 | 1 | đo công suất không hoạt động (`ENERGY_NOT_MEASURED`); có đề xuất mức năng lượng bên dưới. |
| CQ | PATCHTST | 43 | 0 | 0 | 3 | đo công suất không khả dụng trên máy chạy (`UNAVAILABLE`). |
| CQ | PATCHTST | 44 | 0 | 0 | 7 | đo công suất không hoạt động (`ENERGY_NOT_MEASURED`); có đề xuất mức năng lượng bên dưới. |
| CQ | RNN | 43 | 0 | 0 | 51 | không đo năng lượng (`ENERGY_NOT_MEASURED`: `energy_measurement_type = UNAVAILABLE`, 0 mẫu). |
| LO | MANTIS_V2 | 42 | 0 | 0 | 5 | thư viện đo công suất không nạp được (`TELEMETRY_UNAVAILABLE: ModuleNotFoundError`). |
| LO | PATCHTST | 43 | 0 | 0 | 5 | đo công suất không khả dụng trên máy chạy (`UNAVAILABLE`). |

Đề xuất mức năng lượng cho 8 ô CQ seed 44 (không áp dụng vào gói), tính bằng công suất trung vị của các ô cùng họ nhân thời gian chạy:

| Mô hình | Cửa sổ | Pipeline | Thời gian chạy (giờ) | Công suất cơ sở (W) | Đề xuất (kWh) | Khoảng p5–p95 (kWh) |
|---|---|---|---|---|---|---|
| PATCHTST | W1 | V16 | 6.7 | 71.6 | 0.480 | 0.375–0.482 |
| PATCHTST | W1 | V5 | 5.8 | 71.6 | 0.416 | 0.325–0.418 |
| PATCHTST | W2 | V12 | 5.4 | 71.6 | 0.388 | 0.303–0.390 |
| PATCHTST | W2 | V16 | 6.8 | 71.6 | 0.485 | 0.378–0.487 |
| PATCHTST | W2 | V7 | 6.1 | 71.6 | 0.436 | 0.341–0.439 |
| PATCHTST | W3 | V0 | 20.0 | 71.6 | 1.432 | 1.118–1.439 |
| PATCHTST | W3 | V12 | 15.9 | 71.6 | 1.139 | 0.890–1.145 |
| MANTIS_V2 | W2 | V0 | 2.7 | 44.6 | 0.119 | 0.097–0.168 |

Chi tiết và phương pháp: `cross_task_meta/work_in_progress/energy_proposal_seed44_20261119`.

## 4. Cấu hình meta-dataset (release ba seed)

| Mục | Giá trị |
|---|---|
| Mã phát hành | `meta_release_CQ_LO_full_F1F2F3_seeds42_43_44_20261120_mm026` |
| Phạm vi | F1 (RNN, LSTM, GRU, BILSTM), F2 (PatchTST V0–V16) và F3 (Mantis V2 V0–V16, dòng `EXPLORATORY`) cho CQ và LO; seed 42, 43, 44 |
| `planned_seeds` | [42, 43, 44] |
| Bảng mức seed (`meta_dataset_seed_level`) | 14,688 dòng × 558 cột (7,344 CQ, 7,344 LO) |
| Bảng gộp seed (`meta_dataset_seed_agg`) | 4,896 dòng × 1797 cột; `n_seeds_planned` = 3, `n_seeds_success` = 3 ở mọi dòng |
| Từ điển cột | 558 cột (TARGET 168, X_STATE 98, X_VAL 75, UNASSIGNED 51, DIAG 36, X_CONTEXT 34…) |
| Trạng thái dòng | CQ_V2_2_full_seeds42_43_44: 7,344, LO_V3_1_full_seeds42_43_44: 7,344 |
| Cờ QA (cả hai task) | metric_recompute = 1.0, pairing = 1.0, delta_identity = 1.0, decomposition = 1.0, run_level_invariant = 1.0, leak_probe_identity = 1.0, v0_zero_delta = 1.0 |
| Mã dựng | metamodel 0.2.6 (2026-11-20); registry `registries_rev_2026-11-20b` (`tempo_fix/examples/registries_v1.6`, sha256 `45e78abaa5f3…`) |
| Đầu vào | 70 tệp có băm sha256 trong manifest (R4 CQ, static-v2 LO, PatchTST, Mantis, sáu gói seed 43, sáu gói seed 44, S0 v4, Z_M v2, F0 CQ, bảng tham chiếu `s_leak`, gói bàn giao) |
| S0 / F0 | S0 v4 (tr_inactive_learner_ratio removed, Q-28); F0 tham chiếu: CQ có, LO chưa có |

**Khóa quan sát** (mỗi dòng là một meta-observation): task, nhãn và bộ ngưỡng, chế độ đặc trưng, cửa sổ, seed, pha, cohort, tập đánh giá, trục và giá trị nhóm con, mô hình, pipeline. Mỗi dòng giữ giá trị trước can thiệp (V0), sau can thiệp (V1–V16), chênh lệch và các tham chiếu (imputer-only, F0), ghép cặp theo cùng seed. Bảng gộp seed bỏ trục seed và thêm trung bình, độ lệch chuẩn, trung vị, p90, p95, số seed dương và độ nhất quán dấu của chênh lệch.

**Đối chiếu với release một seed (`full42`, 12/11):** phần seed 42 của release mới trùng 2.448/2.448 dòng mỗi task. CQ: 58 cột F1 trước đây rỗng nay đã điền (đúng kết luận nghiệm thu metamodel 0.2.4); LO: một cột chẩn đoán `probe_n_iter` khác ở 408 dòng Mantis, giá trị mới khớp tệp nguồn. Đây không phải mục tiêu của meta-model.

**Cột năng lượng và phiên bản lắp.** Release lắp bằng metamodel 0.2.6 (registry `registries_rev_2026-11-20b`) từ cùng 70 đầu vào của bản trước. Tệp tài nguyên LO của seed 42 có sẵn cột `energy_gpu_run_kwh` rỗng; từ 0.2.5 bộ lắp lấy giá trị ước lượng theo từng dòng mà cột chính rỗng, nên cột năng lượng LO đầy đủ (khớp 918/918 run LO với gói nguồn; 10 run không có số đo là Mantis seed 42 (5) và PatchTST seed 43 (5)). So với release 20261120 (bản vá cục bộ của bộ lắp 0.2.4), mọi cột chung trùng tuyệt đối trừ `meta_release_id` và `builder_version`; cột mới: `rec_energy_measured_types` (bảng mức seed) cùng sáu cột (bảng gộp seed) về kích thước lát và kiểu đo năng lượng. Giá trị năng lượng là ước lượng từ lấy mẫu công suất NVML (`NVML_POWER_SAMPLING_ESTIMATE`).

**M-15 và release.** Cả sáu cấu hình chạy trên đúng release này bằng metamodel 0.2.6. Năm cấu hình dùng cơ sở chi phí thời gian cho kết quả trùng bộ chạy trước trên release 20261120 (so từng bảng `mm_*`: không bảng nào khác). `sens_energy` chạy với `--accept-energy-estimates` trên chính release này.

**Cơ sở chi phí của `sens_energy`.** Theo bảng `mm_cost_basis` (12 nhóm mỗi task × mô hình): CQ: 0 nhóm theo năng lượng, 72 nhóm theo thời gian; LO: 56 nhóm theo năng lượng, 16 nhóm theo thời gian. Nhóm thiếu tỉ lệ năng lượng ở một seed tự về cơ sở thời gian. So với `main_cal_time`, `sens_energy` khác ở 170/238 dòng `mm_metrics` (các cột chi phí và Pareto) và 0/6528 khuyến nghị pipeline.

## 5. Cấu hình meta-model (M-15)

### 5.1 Cấu hình chạy

| Mục | Giá trị |
|---|---|
| Đầu vào | `meta_dataset_seed_agg.parquet` của release ba seed (4,896 dòng; sha256 `8fc29ce4…`) |
| Mã | metamodel 0.2.6 (2026-11-20; lệnh `metamodel.cli run`), tempo_fix registry rev 2026-11-20b |
| Giao thức | E1-A (W1→W2), E1-B (W1W2→W3), E2 (CQ→LO, LO→CQ), E3 (giữ lại từng họ F1, F2, F3): 7 fold |
| Meta-learner chính | L1 (elastic net, tương tác can thiệp–trạng thái), L2 (ExtraTrees), L3 (LightGBM hồi quy, learner chính), L4 (LightGBM LambdaRank) |
| Meta-learner phụ | L5 (LightGBM ba lớp HARM/NEUTRAL/BENEFIT), L6 (hai LightGBM cho phần hiệu năng và phần sanity) |
| Tập đặc trưng | FS0–FS5; mỗi learner chính chạy trên cả 6 tập, learner phụ trên tập chính: 4 × 6 + 2 = 26 ô học mỗi fold, 182 ô học mỗi cấu hình |
| Tìm siêu tham số | Optuna TPE 50 lần thử (L1: lưới), vòng trong theo hối tiếc trung bình; 5 seed cho learner |
| Baseline | B0–B7 (8 baseline mỗi fold), kể cả B7 (chẩn đoán TEMPO-DQ); kiểm âm tính MQ08 trên L3-FS3 |
| Cách chạy | Mỗi cấu hình một tiến trình, mỗi tiến trình một luồng (`OMP/OPENBLAS/MKL/NUMEXPR` = 1, `n_jobs` = 1); Python 3.12.1, lightgbm 4.7.0, optuna 5.0.0, pandas 3.1.0 (môi trường ghim của gói 13/11) |

### 5.2 Sáu cấu hình

| Cấu hình | Mục tiêu | Cờ riêng |
|---|---|---|
| `main_cal_time` | AccTEMPO M3 hiệu chuẩn (`PAPER_COMPOSITE_CAL`) | (mặc định); cơ sở chi phí: năng lượng nếu đo thật, ngược lại thời gian |
| `sens_v1` | AccTEMPO M3 v1 (`META_PRIMARY_M3_V1`) | `--objective META_PRIMARY_M3_V1` |
| `sens_energy` | như mặc định | `--accept-energy-estimates` (coi ước lượng NVML là số đo) |
| `sens_conservative` | như mặc định | `--conservative` |
| `obj_perf` | trục hiệu năng S_perf | `--objective PAPER_PERF_AXIS` |
| `obj_macrof1` | F1 macro | `--objective SECONDARY_MACRO_F1` |

### 5.3 Kết quả

Cấu hình đã có kết quả: `main_cal_time`, `sens_v1`, `sens_energy`, `sens_conservative`, `obj_perf`, `obj_macrof1` (6/6).

| Cấu hình | Nguồn kết quả | Dòng registry | Trạng thái | Dùng phương án dự phòng | MQ08 đạt (fold) | Thời gian (giờ) |
|---|---|---|---|---|---|---|
| `main_cal_time` | đội code (mã 0.2.6, một luồng bằng biến môi trường) | 238 | OK 238 | không | 5/7 | 2.35 |
| `sens_v1` | đội code (mã 0.2.6, một luồng bằng biến môi trường) | 238 | OK 238 | không | 4/7 | 2.50 |
| `sens_energy` | đội code (mã 0.2.6, một luồng bằng biến môi trường) | 238 | OK 238 | không | 5/7 | 2.35 |
| `sens_conservative` | đội code (mã 0.2.6, một luồng bằng biến môi trường) | 238 | OK 238 | không | 3/7 | 2.48 |
| `obj_perf` | đội code (mã 0.2.6, một luồng bằng biến môi trường) | 238 | OK 231, SKIPPED: decomposition parts ('s_perf_log_delta_perf_part_mean', 's_perf_log_delta_san_part_mean') absent (objective s_perf) 7 | không | 7/7 | 2.28 |
| `obj_macrof1` | đội code (mã 0.2.6, một luồng bằng biến môi trường) | 238 | OK 231, SKIPPED: decomposition parts ('macro_f1_log_delta_perf_part_mean', 'macro_f1_log_delta_san_part_mean') absent (objective macro_f1) 7 | không | 6/7 | 2.46 |

**Hối tiếc trung bình theo chiến lược, cấu hình `main_cal_time`** (trung bình trên các fold; thấp hơn là tốt hơn):

| Chiến lược | Hối tiếc trung bình | Tỉ lệ có hại | Top-1 trúng |
|---|---|---|---|
| B0 | 0.0000 | 0.000 | 1.000 |
| B1 | 0.0326 | 0.000 | 0.402 |
| B2 | 0.0113 | 0.135 | 0.382 |
| B3 | 0.0161 | 0.147 | 0.363 |
| B4 | 0.0208 | 0.190 | 0.298 |
| B5 | 0.0141 | 0.165 | 0.274 |
| B6 | 0.0126 | 0.042 | 0.574 |
| B7 | 0.0166 | 0.036 | 0.408 |
| L1-FS3 | 0.0123 | 0.170 | 0.400 |
| L2-FS3 | 0.0175 | 0.216 | 0.299 |
| L3-FS3 | 0.0146 | 0.179 | 0.314 |
| L4-FS3 | 0.0183 | 0.179 | 0.292 |
| L5-FS3 | 0.0139 | 0.177 | 0.347 |
| L6-FS3 | 0.0134 | 0.132 | 0.353 |

**Hối tiếc trung bình theo chiến lược, cấu hình `obj_perf`** (trung bình trên các fold; thấp hơn là tốt hơn):

| Chiến lược | Hối tiếc trung bình | Tỉ lệ có hại | Top-1 trúng |
|---|---|---|---|
| B0 | 0.0000 | 0.000 | 1.000 |
| B1 | 0.0559 | 0.000 | 0.219 |
| B2 | 0.0192 | 0.125 | 0.247 |
| B3 | 0.0286 | 0.179 | 0.241 |
| B4 | 0.0357 | 0.244 | 0.158 |
| B5 | 0.0236 | 0.210 | 0.116 |
| B6 | 0.0213 | 0.118 | 0.461 |
| B7 | 0.0289 | 0.039 | 0.204 |
| L1-FS3 | 0.0240 | 0.234 | 0.216 |
| L2-FS3 | 0.0300 | 0.226 | 0.186 |
| L3-FS3 | 0.0250 | 0.225 | 0.198 |
| L4-FS3 | 0.0313 | 0.207 | 0.201 |
| L5-FS3 | 0.0241 | 0.126 | 0.402 |

**Giả thuyết H1–H8 (cấu hình `main_cal_time`; ước lượng trung bình trên các fold có phép thử, khoảng tin cậy trung bình):**

| Giả thuyết | Số phép thử | Ước lượng | Cận dưới | Cận trên |
|---|---|---|---|---|
| H1 | 1 | 0.0029 | 0.0006 | 0.0057 |
| H2 | 1 | 0.0010 | -0.0015 | 0.0041 |
| H3 | 1 | 0.0625 | -0.0417 | 0.1875 |
| H4 | 1 | 0.0087 | 0.0019 | 0.0165 |
| H5 | 3 | -0.0031 | -0.0060 | -0.0003 |
| H6 | 1 | -0.3326 | -0.4162 | -0.2525 |
| H7 | 1 | -0.0011 | -0.0016 | -0.0007 |
| H8 | 2 | -0.2378 | -0.6475 | 0.1915 |

## 6. Đối chiếu các mục yêu cầu đợt 29 (16/11)

| Mục | Trạng thái | Ghi chú |
|---|---|---|
| 1. Commit mã, ghi commit vào gói | Xong (commit cục bộ) | Commit `7c24981` và `11941f1`, sau đó đổi đường dẫn tuyệt đối thành biến môi trường; commit dựng gói ghi trong README và `summary.json` của sáu gói seed 44. Chưa đẩy lên `origin/main`. |
| 2. README và `probe_seed` | Xong | Seed 44 đã sửa; seed 43 chỉ ghi chú (không xuất lại): `cross_task_meta/work_in_progress/seed43_package_notes_20261120`. |
| 3. NVML | Có ghi chú | 8 ô seed 44 không có số đo (xem 3.2); ghi chú và đề xuất năng lượng đã lên Drive. |
| 4. Seed 44: facts, M-18, biên nhận | Xong | Sáu gói facts, M-18, bảng kiểm commit, bằng chứng Mantis, biên nhận chuyển giao và ingest L2, cùng cây thư mục như seed 43. |
| 5. M-15 ba seed | Cấu hình xong; kết quả theo mục 5.3 | Release ba seed đã lắp và đã lên Drive; sáu cấu hình chạy một luồng. |
| 6. Ledger M-08 | Chưa xác nhận | Cần đối chiếu từng ô đã giao với lớp định danh trong ledger; không ghi xác nhận khi chưa kiểm. |
| 7. Hai thư mục báo cáo 16/11 | Đã có trên Drive ở chỗ khác | `cross_task_meta/work_in_progress/l2_ingest_receipts_seed43_20261116` và `CQ|LO/L2_facts/receipts_seed43_20261116`. |
| 8. S2 seed 43/44 | Đã trả lời ở phản hồi 13/11 (mục 1.6) | Bản ghi máy chuẩn và các cột thời gian đo thật; các cột còn giá trị cũ của runner Modal đã nêu. |

## 7. Nguồn của từng số

- Bảng mục 2 và 3.2: `meta_release_CQ_LO_full_F1F2F3_seeds42_43_44_20261120_mm026/meta_dataset_seed_level.parquet` (các cột `*_after`, tập TEST, trung bình bốn pha), qua `report_aggregate_3seed.py`; tệp thô trong `tables/`.
- Mục 3.1: gói M-18 seed 44 (`m18_training_history_seed44_20261119`), bảng kiểm commit runner, biên nhận.
- Mục 3.2 (đề xuất năng lượng): `energy_proposal_seed44_20261119`.
- Mục 4: `meta_release_CQ_LO_full_F1F2F3_seeds42_43_44_20261120_mm026/meta_release_manifest.json` và `meta_column_dictionary.csv`.
- Mục 5: `mm_config.json`, `mm_metrics.parquet`, `mm_run_registry.parquet`, `mm_negative_control.parquet`, `mm_hypotheses.parquet` của từng cấu hình.

## 8. Giới hạn của báo cáo

- Chỉ số mục 2 là trung bình trên tập TEST, không có khoảng tin cậy; độ lệch giữa seed và giữa các nhóm pipeline chỉ mang tính mô tả.
- **Meta-dataset chưa theo đúng cách chia của tài liệu gốc**: release hiện chỉ có nhóm con `ALL/ALL` (cohort `FIXED`), chưa có các nhóm con bắt buộc; E1-A và E1-B gộp CQ và LO trong cùng fold (cả train và test chứa hai task), chưa chia E1 theo từng task như tài liệu mô tả. E2 là chuyển task (CQ→LO, LO→CQ) và E3 giữ lại từng họ mô hình.
- **M-15**: số cấu hình có kết quả và nguồn của chúng ghi ở bảng mục 5.3; cấu hình chưa có trong bảng chưa xong tại thời điểm viết. Kết quả chạy mỗi tiến trình một luồng, có thể khác lần 13/11 ở mức nhiễu dấu phẩy động. Kiểm âm tính MQ08 chưa đạt ở một số fold (số fold đạt ở bảng 5.3); không kết luận gì thêm ngoài việc ghi nhận. Thống kê giả thuyết lấy trung bình trên fold, không thay cho phân tích đầy đủ của tác giả.
- `sens_energy` về cơ sở thời gian ở mọi nhóm CQ và ở một phần nhóm LO (PatchTST và 4 nhóm Mantis), vì thiếu tỉ lệ năng lượng ở ít nhất một seed (mục 4); 8 ô CQ seed 44 không có số đo năng lượng (mục 3.2). Đề xuất năng lượng chỉ để báo cáo, không áp dụng vào dữ liệu.
- Mantis chạy ở chế độ thăm dò (`EXPLORATORY`); commit runner của Mantis được ánh xạ hồi tố, việc phía review chấp nhận cho seed 43 và 44 còn chờ.
- Tổng thời gian run của một số tổ hợp tính trên ít ô hơn số ô (bảng 3.2 ghi mẫu số), vì có ô thiếu `time_run_total_s`.
