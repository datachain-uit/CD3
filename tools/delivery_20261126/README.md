# Script của các sản phẩm giao ngày 26–27/11/2026

Mỗi thư mục là mã của một sản phẩm đã giao ở `Results/cross_task_meta/work_in_progress/`. Các script đã chạy trên máy của đội code với đường dẫn tuyệt đối; để không đưa đường dẫn máy vào repo, **bản commit thay các đường dẫn đó bằng biến môi trường** `TEMPO_REPO_ROOT`, `TEMPO_WORK_ROOT`, `TEMPO_AUDIT44_ROOT`, `TEMPO_DELIVERY_WORK_ROOT` (đặt ở đầu file khi cần, giá trị mặc định `.`) và không đổi logic. Bản đã chạy và bản đã commit vì thế khác nhau ở các dòng đó; cả hai sha256 ghi dưới đây. sha256 của bản đã commit là sha256 của blob (`git show <commit>:<đường dẫn> | sha256sum`), đã đặt `text eol=lf` trong `.gitattributes`.

| Thư mục | Sản phẩm |
|---|---|
| `qa_tables_b2` | B.2: bảng QA01–QA24 của release r2 |
| `qa_extra_qa4` | B.2 bổ sung: QA14, QA17, QA22, QA23 |
| `qa_prediction_audit_qa5` | B.2 bổ sung: QA07, QA11, QA12, QA13, QA21 (kiểm dự đoán và manifest, 36 đơn vị; `qa_fill_*`: bổ sung hai đơn vị LO seed 42 thiếu file ở lượt đầu) |
| `static_layout_radius_b34` | B.3 layout khối tĩnh; B.4 tỷ lệ fallback Radius-SMOTE |
| `slices_per_class_d` | D: gói gộp lát đánh giá và chỉ số theo lớp ba seed |
| `proxy_provenance_p` | P: nguồn gốc ba họ cột `*_catalog_coverage`, cờ proxy, layout, QA23 theo lát, ước lượng ablation |
| `s2_seed44_b4p` | B4′: tập manifest S2 seed 44 |
| `errata_e` | E: hai tệp đính chính của release r2 và overlay QA18/QA19 |

Thư mục bổ sung (27/11/2026): `qa_link_qa5m` (nối thêm 180 run Mantis cho QA11/QA13/QA21 và đọc trường `parent` của manifest), `qa14_views` (các test của QA14 trên view), `qa21_leak_guard` (QA21 năm điều kiện và bảng cột LO của QA23), `qa_tables_v2_v3` (dựng bảng QA bản 2, 3 và 4 và bảng hỗ trợ quyết định QA23), `qa13_checkpoints` (độ phủ checkpoint của 1.836 run cho QA13).

| Script | sha256 bản đã chạy | sha256 blob đã commit |
|---|---|---|
| `qa_tables_b2/build_qa_outcomes_csv.py` | `6de868bc7485881d5e5dc90471a8caaabc66848a9bd28e5388f7d394c69a9e0f` | `6de868bc7485881d5e5dc90471a8caaabc66848a9bd28e5388f7d394c69a9e0f` |
| `qa_tables_b2/run_qa_release_r2.py` | `8133868886cdbf3183c16131d1f1720743465318b5f60fcb500ae74bcb29d1a8` | `3402540ee90dbafd5bf33ac9c74e0c0ffaf779575b4a213cad2237e7e17cb2c0` |
| `qa_extra_qa4/build_qa4_results.py` | `ef6748d37c40f33bd94f27f211728859f3628a867f59878264d4d4728a0c06c7` | `ef6748d37c40f33bd94f27f211728859f3628a867f59878264d4d4728a0c06c7` |
| `qa_extra_qa4/qa14.py` | `89c25733e69388133d4e53de072c8a8bdbd530cdf8eb4cddbbfcbf6c76cd02bf` | `89c25733e69388133d4e53de072c8a8bdbd530cdf8eb4cddbbfcbf6c76cd02bf` |
| `qa_extra_qa4/qa17.py` | `04e5d00b6b1bd517cc43b25c72602cb2d948b830948bc6618285a12cf14d3536` | `04e5d00b6b1bd517cc43b25c72602cb2d948b830948bc6618285a12cf14d3536` |
| `qa_extra_qa4/qa22.py` | `0adf94fade4daa434eb0f290a4078c6151c46b42c2baa654180aba40d89eab17` | `0adf94fade4daa434eb0f290a4078c6151c46b42c2baa654180aba40d89eab17` |
| `qa_extra_qa4/qa23.py` | `b2b2656dd9e5ebc0a78c926287d075d38c58d8e1d1a2fb10bc9021051ba47d0f` | `b2b2656dd9e5ebc0a78c926287d075d38c58d8e1d1a2fb10bc9021051ba47d0f` |
| `qa_prediction_audit_qa5/qa_pred_audit.py` | `01324eedf5cb796ad264a256eae6eb13ad4caaa0d29c34df56097535564287bd` | `01324eedf5cb796ad264a256eae6eb13ad4caaa0d29c34df56097535564287bd` |
| `qa_prediction_audit_qa5/run_all_qa5.py` | `14641478523174a8a5ea18d52c64313f16ec4067d8fc12aecf1ee8a387f0f245` | `14641478523174a8a5ea18d52c64313f16ec4067d8fc12aecf1ee8a387f0f245` |
| `qa_prediction_audit_qa5/verify_independent.py` | `22ffd70972ea0b928fc2aca0b7855d72556646292d78005520c1a3c0c9ac6aed` | `22ffd70972ea0b928fc2aca0b7855d72556646292d78005520c1a3c0c9ac6aed` |
| `qa_prediction_audit_qa5/qa_fill_pred_audit.py` | `1762071a548d1af4dd72bd13d183f4dc1ca9ea68c91d4d35a74730f48f985fbe` | `1762071a548d1af4dd72bd13d183f4dc1ca9ea68c91d4d35a74730f48f985fbe` |
| `qa_prediction_audit_qa5/qa_fill_merge.py` | `a44047c5234849464a91deedaaddfc2d7bdbfe790feab5e6f540ac5b43ec7367` | `a44047c5234849464a91deedaaddfc2d7bdbfe790feab5e6f540ac5b43ec7367` |
| `static_layout_radius_b34/build_radius_fallback_class.py` | `8f7c3ccdff6bba63ccf9b98f65e5375cf3c50d028ebc9c3edbb02eed42d32264` | `efd8a41975bdf27a88932212fa6b98b70aec08c7411f28ee0c9269688562c39d` |
| `static_layout_radius_b34/build_static_layout_by_unit.py` | `48bb55b233c01744e259f5c2d27462ceeec223ab23d07041cd5015dbb16cf0e7` | `a6856db996f4c6872a602ac07d9b60fbb9e3cbcb8fe8d7e1f8c5b9e8acda4f49` |
| `static_layout_radius_b34/extract_s2_manifests_seed44.py` | `cbc6cc096e190c17b8f31ff246e71120ad68e2249781bb84dfcb19dbdf33fb9c` | `cbc6cc096e190c17b8f31ff246e71120ad68e2249781bb84dfcb19dbdf33fb9c` |
| `static_layout_radius_b34/verify_layout_in_tar.py` | `14e34419f2a0a5d933761e6356f8936ce0c99130c7365bcbd18180c1ee981507` | `14e34419f2a0a5d933761e6356f8936ce0c99130c7365bcbd18180c1ee981507` |
| `slices_per_class_d/build.py` | `6aff217dc6cf645b9192b577145100382d3457b71e06c95a8d267eb508658e8d` | `1489884588b53adaa0a6746a545f6241b5f0b8fef3fede9ec47a2635d65a5539` |
| `slices_per_class_d/finish.py` | `ddeeafb79973734dc7bb1f76bfbde0ded8780c5b996c75a07d721e95f14eb445` | `7c6eb989e886e544a34d0ae91fa19e5fc62ef8d32f70200e081e04d2bf5c3217` |
| `slices_per_class_d/lo42check.py` | `8331e9c3e93a5681dc5cc966837932857c7d7273764fe9d9483ed90a03310675` | `d2f33392695e9ad0a68786799d56bac8c0d913242d137558ecdd42010ee9ecd5` |
| `slices_per_class_d/readme.py` | `11b8dc9d739a7463ad3ccff09756364f975734781979c745668359fd1d36e41a` | `085bc9ab16eba2cffccf54ca3f4cc4f08da50107132438c67932bd7ca96ae3d9` |
| `slices_per_class_d/registry.py` | `1b0d5232457e8a152c31a6c90b0bdd80a7f10f027b60a5075a7533db710f3eaf` | `554efe4f0dd6b93fadd737f3b12dd8c38acd0b6966dc130a2dee5889974c9e7b` |
| `slices_per_class_d/schemas.py` | `dbfe84803772657d27f6084d36deb67aaf8bf00b775b9654dbae0d19c5a53ea1` | `3e3416a4dc57460742dcc1395aad55a2151e95dbae51055cd723ddb4953cd03c` |
| `slices_per_class_d/survey.py` | `42f3e26f1ed24eb2bb85022c83c596f9e1bd2cbad34cd1255cd5d573754d46ed` | `48cb2140fae379be911c9a0dbccfbd0d60b76796cfa6249bcbec1b9675deeb21` |
| `slices_per_class_d/verify.py` | `168963b9d95622fcfe6cc8b6a1ac75df679ea7f07bf9025722dea10823d057a7` | `6449e702b0636ea7fcc2cb4930805e8fd939f3a68d6845c1824598c2b9b93dcd` |
| `proxy_provenance_p/build_cost_table.py` | `8311c0ab616d1842d7ab8f7fe0b29186ebf32e8dc2b7b5e70324fb4ef503c9b9` | `8311c0ab616d1842d7ab8f7fe0b29186ebf32e8dc2b7b5e70324fb4ef503c9b9` |
| `proxy_provenance_p/build_flag_and_layout.py` | `8ae69593e5c3190f3227cd87c0259d7230379ef104c50b53674bb90d28eb9d60` | `8ae69593e5c3190f3227cd87c0259d7230379ef104c50b53674bb90d28eb9d60` |
| `proxy_provenance_p/build_qa23_detail.py` | `ed04d16d6354e28b1b25b89c9b0dc137d6ec7a4ae5ea5ad8d7298948a8b3e51f` | `ed04d16d6354e28b1b25b89c9b0dc137d6ec7a4ae5ea5ad8d7298948a8b3e51f` |
| `proxy_provenance_p/empirical_prefix_check.py` | `ea23663cc160d12c6605f550eb8c33820e9b5daaa0ff2ea47fbd9ca64bce2289` | `2992773e5cd27484dd2edacaa517aad9b47daedd81629c2f26617e2705e0db23` |
| `proxy_provenance_p/monotone_violation_probe.py` | `0049b7646e236b9b3e1e3c724719c12b04840f8f932664ea732dbb66090c2746` | `0049b7646e236b9b3e1e3c724719c12b04840f8f932664ea732dbb66090c2746` |
| `s2_seed44_b4p/analyze.py` | `f7a78d816ceb625c455c103f89231e20d2a882d4fa3a15419ec7cb97cee90261` | `f7a78d816ceb625c455c103f89231e20d2a882d4fa3a15419ec7cb97cee90261` |
| `s2_seed44_b4p/build_deliverables.py` | `a5cbac2f97efaedf093b08d1c94ebe2143929549fabb500c85862cfcdbc1592f` | `a5cbac2f97efaedf093b08d1c94ebe2143929549fabb500c85862cfcdbc1592f` |
| `s2_seed44_b4p/extract_manifests.py` | `90cbbacdb59fc1966612d353374fba1bdd665a85554e236ba2b7266f00d30f9e` | `90cbbacdb59fc1966612d353374fba1bdd665a85554e236ba2b7266f00d30f9e` |
| `s2_seed44_b4p/hashlocal.py` | `a52d523f270798369bb52c8bc75efbb6c26a89aca5389d7095edc10d79fae0ff` | `a52d523f270798369bb52c8bc75efbb6c26a89aca5389d7095edc10d79fae0ff` |
| `s2_seed44_b4p/hop_extract.py` | `c600a0562d3498f8e003df0b3cb1087d6a740144b5f172ad725649fb4d24b339` | `c600a0562d3498f8e003df0b3cb1087d6a740144b5f172ad725649fb4d24b339` |
| `s2_seed44_b4p/plan.py` | `0de96a58eb5ad7912bc5d2dc7429fcd2494cd03cdeffa6c886b8d19b27a56300` | `0de96a58eb5ad7912bc5d2dc7429fcd2494cd03cdeffa6c886b8d19b27a56300` |
| `errata_e/build_null_errata.py` | `4c8d86658c1eaabb590425cd8cdefc32eb77c8038fb0a6bca986ed42df92f572` | `4c8d86658c1eaabb590425cd8cdefc32eb77c8038fb0a6bca986ed42df92f572` |
| `errata_e/build_roles_errata.py` | `a7a5c155843770b602f598a644b40d284021fe97c4db19a7e4dcbd7fd2607892` | `a7a5c155843770b602f598a644b40d284021fe97c4db19a7e4dcbd7fd2607892` |
| `errata_e/run_overlay_qa18_qa19.py` | `3584ce16d59d84a50445a29fbd6ecee1a4b77c565cbd78aa40bb7cb42d91049c` | `3584ce16d59d84a50445a29fbd6ecee1a4b77c565cbd78aa40bb7cb42d91049c` |

| `qa_link_qa5m/qa5m_link_extension.py` | `8b75f64b145895e36b7a306d6875f65cdb240e31e3d31647806c7820e94999e2` | `8b75f64b145895e36b7a306d6875f65cdb240e31e3d31647806c7820e94999e2` |
| `qa_link_qa5m/qa5m_declared_parent.py` | `e5aa2dbab3c67d260865b900e1ac9eef165abe8b4161bde562b86370588b0186` | `e5aa2dbab3c67d260865b900e1ac9eef165abe8b4161bde562b86370588b0186` |
| `qa14_views/qa14_run.py` | `270c981683f9a79b6a3493286812e9ae6517b46cd33a515745fdf120452a6656` | `270c981683f9a79b6a3493286812e9ae6517b46cd33a515745fdf120452a6656` |
| `qa21_leak_guard/qa21_ab_keys_labels.py` | `6ba0e1953df43e91ef9ff30efabe668923e2548056bc5439547d287e6f53d2d1` | `6ba0e1953df43e91ef9ff30efabe668923e2548056bc5439547d287e6f53d2d1` |
| `qa21_leak_guard/qa21_b2_overlap_share.py` | `31bd6d336892a0d6a1d60c4640c07cb509c479b5a320c24b3511cbd752cf1628` | `31bd6d336892a0d6a1d60c4640c07cb509c479b5a320c24b3511cbd752cf1628` |
| `qa21_leak_guard/qa21_c_grade_group_info.py` | `02f8f450664e8e7e946e3c529861618fbb33ced769991184972b93906cfadd89` | `0856ef5a8e8d86a25b3d45b77c7207bc95b7dcc3e7b1cc58be04e13925c4c54a` |
| `qa21_leak_guard/qa21_c_predictors_vs_proxy.py` | `e2e2588ce66c695c4cf54f0fd8186738905231d1198d43ecf4dd5aa7467ee114` | `a2c38150c721e5ce442ea24dfd3e40d2aea27451862ad0a90db95ab6685f5b0a` |
| `qa21_leak_guard/qa21_c_safe_inspect_joblib.py` | `2a8a8aa14cbd34236adae5bebd66aaf065e1d478ec7553a515a0fc4b6cefd224` | `ce74fbe603fe40a852e1d3ece219fc29df9872162ab45ade16d8fda3354a2eb9` |
| `qa21_leak_guard/qa21_d_lo_review_candidates.py` | `ba18193491be916649f82bebb410fff08a76f68579b15c656dcb3a469a702474` | `7e4c7a48759296db2baa536efcb806b487e5bd3b20c049a2c33fef655e20d715` |
| `qa21_leak_guard/qa21_c_fetch.sh` | `d527feb5d62f3b19cc6bd09b62e5f6a983a9b5539f066141bea4dc43d9cc56de` | `4ceff221587b42ea4a3972b206b7c6c571a5aba8f19f23e499aa9eaea5a1c2dc` |
| `qa_tables_v2_v3/build_qa_v2.py` | `7e5538e053c1c90ef3c6a334a6fd6c1a1de2b1e9c0b002d958236da11951611a` | `7e5538e053c1c90ef3c6a334a6fd6c1a1de2b1e9c0b002d958236da11951611a` |
| `qa_tables_v2_v3/build_qa_v3.py` | `8066d6a46a60a7aff86554c05659f1dedb0dd9e81064e3afe9723a4f64d594b0` | `8066d6a46a60a7aff86554c05659f1dedb0dd9e81064e3afe9723a4f64d594b0` |
| `qa_tables_v2_v3/build_qa23_decision_support.py` | `96b66b905b9084323f17c01e4703f3f906cb5166ae5ca8f33307667c3e8ee08f` | `96b66b905b9084323f17c01e4703f3f906cb5166ae5ca8f33307667c3e8ee08f` |
| `qa13_checkpoints/s1_pick_sources.py` | `acb5535690044712703dc123e437241b6b4e3728a968006e3756047dd4af57b4` | `acb5535690044712703dc123e437241b6b4e3728a968006e3756047dd4af57b4` |
| `qa13_checkpoints/s2_scan_tars.py` | `371e6b228d0e1e1f5c686256177117e9918e3262e6e239ed0408697cc326a501` | `371e6b228d0e1e1f5c686256177117e9918e3262e6e239ed0408697cc326a501` |
| `qa13_checkpoints/s2b_rescan_errors.py` | `b0f4a699c1fb5ce55d8b6357d2b52746a14cec1c40f05c834bc05ffe117ae44e` | `b0f4a699c1fb5ce55d8b6357d2b52746a14cec1c40f05c834bc05ffe117ae44e` |
| `qa13_checkpoints/s3_build_coverage.py` | `8d697ac8274c4761105e3e9b942475bf94507f9af7dee6f91581e800ef94190d` | `8d697ac8274c4761105e3e9b942475bf94507f9af7dee6f91581e800ef94190d` |
| `qa13_checkpoints/tarlist.py` | `9c77f331caf0422a56bb7cfa3533c7b5d2bddfaddd2617ffddc38bd7bb57d1f6` | `9c77f331caf0422a56bb7cfa3533c7b5d2bddfaddd2617ffddc38bd7bb57d1f6` |
| `qa_tables_v2_v3/build_qa_v4.py` | `f189f9cf3dd14d4dc4ea61ad21666ef91097ce741e0ce1c614eb4425960ee083` | `f189f9cf3dd14d4dc4ea61ad21666ef91097ce741e0ce1c614eb4425960ee083` |
| `qa_tables_v2_v3/build_qa_v5.py` | `fc7348500d1be6052d6d2a77c7f4136483847bb7bd068e577fba9f43e8dc3885` | `fc7348500d1be6052d6d2a77c7f4136483847bb7bd068e577fba9f43e8dc3885` |
