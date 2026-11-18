# Báo cáo Day 09 — Dương Quang Chung, 2A202603217

## 1. Kết luận trước
**Hold.** Từ 224 ảnh raw, cửa vào loại 19 ảnh, còn 205 ảnh được xuất thành **bản nháp** `clean_v1`. Sau sửa tự động và duyệt mô phỏng 80 ảnh, không còn lỗi bắt buộc nhưng còn 38/205 ảnh có cảnh báo chưa duyệt (18.54% ≥ 10%); chưa đủ điều kiện phát hành ([summary](reports/08_summary.json)).

## 2. Lỗi và phân việc
Nguồn: [danh sách v1](reports/02_error_list_v1.csv). Các lỗi cửa vào tính trên 224 ảnh; các lỗi QC tính trên 205 ảnh được nhận. Cột số lượng là số bản ghi lỗi, không cộng thành số ảnh vì một ảnh có thể có nhiều lỗi.

| Mã lỗi | Số bản ghi; số ảnh | Ai sửa | Vì sao |
|---|---:|---|---|
| CORRUPT_IMAGE / BAD_SIZE | 2; 2 / 3; 3 (trên 224) | Máy ở cửa vào | Không đọc được / cạnh ngắn <250px |
| DUP_IMAGE_EXACT / DUP_IMAGE_NEAR / LEAK_TEST | 8; 8 / 2; 2 / 4; 4 (trên 224) | Máy ở cửa vào | Loại trùng và nghi rò rỉ |
| BAD_FORMAT / BAD_CLASS_ID / BOX_ZERO / DUP_BOX | 3; 3 / 6; 6 / 4; 4 / 7; 7 | Máy | Xoá dòng lỗi, giữ log trước–sau |
| BOX_OUT_OF_IMAGE | 8; 8 | Máy | Cắt box, xoá nếu không còn diện tích |
| BAD_CLASS_NAME | 2; cấp dataset | Máy | Chuẩn hoá tên lớp trong YAML |
| MISSING_LABEL_FILE | 6; 6 | Người mô phỏng | Máy không tự bịa nhãn |
| EMPTY_LABEL | 12; 12 | Người | Phân biệt ảnh nền và bỏ sót nhãn |
| BOX_TINY / BOX_HUGE | 6; 4 / 3; 3 | Người | Cần đánh giá đối tượng thực tế |
| CLASS_RARE | 4; cấp dataset | Người | Kiểm phân bố lớp; đếm token kể cả ID lạ |
| POSSIBLE_WRONG_CLASS | 18; 18 | Người | Model có thể nhầm lớp |
| POSSIBLE_MISSING | 53; 52 | Người | Xác nhận vật bị bỏ sót |
| POSSIBLE_LOOSE_BOX | 28; 24 | Người | Xem mức độ sát của box |
| POSSIBLE_FALSE_POS | 29; 27 | Người | Xác nhận box thừa |

Hàng đợi ưu tiên tổng trọng số lỗi, tăng theo confidence. `img_0020` đứng đầu (11.524 điểm) vì có dòng bị xoá, nghi thiếu box và nhầm lớp; tiếp theo là 6 ảnh thiếu file nhãn (10 điểm/ảnh). Trong 125 ảnh chờ, mô phỏng duyệt 80 ảnh, gồm **74/103 ảnh có cảnh báo ngữ nghĩa**, tương ứng **94/123 cảnh báo** ở v2. Đây là số cảnh báo được đưa qua duyệt, không phải số lỗi thật được xác nhận ([hàng đợi](reports/05_review_queue.csv), [log duyệt](reports/06_review_log.csv)).

## 3. Calibration (2 ngưỡng)

Đo trên 39 ảnh calib bằng `pipeline.calibrate`; số liệu lấy từ [calibration.json](calibration/calibration.json) và [bảng sweep](calibration/calibration_report.md). P = precision, R = recall; các giá trị dưới đây làm tròn 3 chữ số.

| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---|---|---|---|
| `duplicates.phash_dist` | 2 | **4** | Gần trùng: 1.000 / 0.500 → 1.000 / 0.667 | Bắt 4/6 ca thay vì 3/6, FP = 0 trên calib; chọn ngưỡng nhỏ nhất đạt mức này để hạn chế loại nhầm. Còn bỏ sót 2/6 ca. |
| `second_opinion.conf` | 0.25 | **0.6** | Thiếu box: 0.500 / 1.000 → 0.571 / 1.000; nhầm lớp: 0.556 / 0.833 → 0.625 / 0.833 | Giữ TP thiếu box 8/8 và nhầm lớp 5/6, giảm FP tương ứng 8→6 và 4→3; chấp nhận giảm khả năng bắt box lỏng. |

Đánh đổi của `conf=0.6`: box lỏng có P/R giảm **0.286/0.400 → 0.200/0.200**, chỉ bắt 1/5 thay vì 2/5 ca. Box thừa giữ nguyên P/R **0.312/1.000** (TP=5, FP=11), vì dùng ngưỡng `fp_conf` riêng. Không xem ngưỡng đã chọn là tốt nhất cho mọi loại lỗi; cần người kiểm bổ sung box lỏng. Không chọn 0.8 dù precision nhầm lớp đạt 1.000, vì recall thiếu box giảm còn 6/8.

**Calibration có thể gây hiểu nhầm:** trên calib, `phash_dist=16` có P=1.000, R=5/6 cho ảnh gần trùng, nhưng khi thử trên raw lại gộp sai `img_0008` (hai người trượt tuyết) với `img_0011` (người chơi tennis). Vì loại nhầm sẽ làm mất dữ liệu tốt, giữ ngưỡng 4 dù recall calib thấp hơn. Calib chỉ có 6 ca gần trùng và không có ca rò rỉ test; không suy rộng precision/recall của calib thành kết quả trên toàn bộ raw.

Với cấu hình đã chọn, [báo cáo cửa vào](reports/01_intake.csv) ghi loại 19/224 ảnh: 2 hỏng, 3 quá nhỏ, 8 trùng byte, 2 gần trùng, 4 bị báo rò rỉ kho test/val. Trợ lý đã xem 2 cặp gần trùng (`img_0042`–`img_0076`, `img_0037`–`img_0143`) và 3 cặp trùng byte, chưa thấy loại nhầm trong 5 cặp này; toàn bộ 8 cặp trùng byte cũng được đối chiếu SHA-256 bằng nhau. Đây là kiểm tra mẫu, không bảo đảm mọi trường hợp đều đúng.

Chạy thử pipeline cho kết luận **Hold**: hàng đợi 125 ảnh, người duyệt mô phỏng xử lý 80 ảnh; sau đó còn 38/205 ảnh có cảnh báo chưa duyệt (18.54% ≥ 10%), không còn lỗi bắt buộc ([summary](reports/08_summary.json)). Không tăng `conf` chỉ để ép đạt Release; dataset xuất ra là bản nháp.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
Thí nghiệm riêng, giữ nguyên báo cáo và dataset chính:

```powershell
.\.venv\Scripts\python.exe -m pipeline.run --budget 0 --work work/run_nb --reports submission/reports/gate_no_review --export-dir work/exp_nb
```

Kết quả thực đo: **Rework, mã thoát 20**, còn 6 lỗi `MISSING_LABEL_FILE` trên 205 ảnh; `work/exp_nb/clean_v1` không được tạo. Bằng chứng: [summary thí nghiệm](reports/gate_no_review/08_summary.json), [mã thoát và kiểm tra export](reports/gate_no_review/proof.json), [log chạy](reports/gate_no_review/run.log). `needs_label` chỉ chuyển người gán, không tạo nhãn rỗng.

Hai điểm mù được đo trên calib: (1) box lỏng chỉ bắt **1/5**, bỏ sót **4/5** ở cấu hình đã chọn; (2) ảnh gần trùng chỉ bắt **4/6**, bỏ sót **2/6**. Ngoài ra, nhầm lớp còn bỏ sót **1/6**. Cần người xem các trường hợp khó; không coi im lặng của checker là bằng chứng nhãn đúng. Quy tắc cú pháp cũng không xác định được người mặc quân phục chưa có box trong `img_0001`, như quan sát trực quan ở bước chuẩn bị.

## 5. Train: raw vs clean

Đã train trên [Kaggle Tesla T4](https://www.kaggle.com/code/chungdngquang/day09-autoqc-duong-quang-chung-raw-vs-clean), thay Colab do không được cấp GPU. Cả hai biến thể dùng `yolo26n.pt`, Ultralytics 8.4.214, **20 epoch, batch 16, imgsz 640, seed 0/1**, cùng gold_val 40 ảnh để chọn checkpoint và test 100 ảnh để đo cuối. Đầu vào cố định tại commit `a0d8e07`; JSON gốc do `scripts/train_compare.py` sinh, bảng dưới do `scripts/summarize_results.py` sinh.

| biến thể | #ảnh train | số seed | map50 (TB ± độ lệch) | map50_95 (TB ± độ lệch) | precision (TB ± độ lệch) | recall (TB ± độ lệch) |
|---|---|---|---|---|---|---|
| raw | 224 | 2 | 0.726 ± 0.000 | 0.512 ± 0.004 | 0.764 ± 0.061 | 0.649 ± 0.028 |
| clean | 205 | 2 | 0.700 ± 0.030 | 0.486 ± 0.013 | 0.715 ± 0.073 | 0.615 ± 0.017 |

Chênh mAP50 (clean − raw) = **-0.025**.

224 là số ảnh raw được dựng vào thư mục train, **không phải số thực sự được học**: Ultralytics loại 11 ảnh/nhãn lỗi, còn **213 ảnh**; clean dùng đủ **205 ảnh**, không có ảnh bị bỏ qua. Bằng chứng cache và môi trường trong [training_environment.json](results/training_environment.json).

mAP50 chính xác: raw **0.72575 ± 0.00021**, clean **0.70035 ± 0.03048**. Chênh **−0.02540** nhỏ hơn độ lệch giữa seed của clean (0.03048); hai chênh theo seed là −0.0468 và −0.0040. Clean có trung bình thấp hơn ở thí nghiệm này; **chưa có bằng chứng clean tốt hơn raw**, và chỉ 2 seed/100 ảnh test chưa đủ kết luận tổng quát. AP50 trung bình tăng nhẹ ở car (+0.011), person (+0.005), giảm ở truck (−0.090), bus (−0.028).

Hai giả thuyết cần kiểm, chưa phải nguyên nhân đã chứng minh: (1) raw có 4 ảnh bị báo trùng kho test/val, có thể làm điểm raw cao giả; cần kiểm định lại trên tập đánh giá độc lập không rò rỉ, chưa đo được mức ảnh hưởng hiện tại. (2) clean vẫn Hold với 38/205 ảnh cảnh báo chưa duyệt, lại ít ảnh hơn; nhãn ngữ nghĩa hoặc phân bố car/truck/bus có thể gây giảm điểm. Cần audit các lớp này, đối chiếu số box, rồi làm thí nghiệm kiểm soát và thêm seed trong một vòng được phép; không chỉnh ngưỡng theo điểm test vừa đo.

## 6. Quyết định và ghi chú 
Giữ **Hold**, không phát hành. Muốn Release cần không còn lỗi bắt buộc và ít hơn 10% ảnh còn cảnh báo chưa duyệt: với 205 ảnh, tối đa 20 ảnh, tức cần xử lý thêm ít nhất 18/38 ảnh hiện tại và chạy QC lại. Ngân sách 80 ảnh của lần chạy này đã dùng hết; cần vòng duyệt tiếp theo được cho phép, không tự tăng ngân sách hay sửa ngưỡng gate để đạt Release. Các điểm mù vẫn cần kiểm tra bổ sung.

- **Prompt/chỉ dẫn cho AI:** yêu cầu trợ lý hoàn thiện lần lượt bốn module dựa trên docstring và test có sẵn; đầu vào YOLO/cache, quy tắc và đầu ra `Issue`/log theo đề; giữ nguyên test/dữ liệu/file mẫu, không sửa nhãn ngữ nghĩa tự động. Đây là tóm tắt ngữ cảnh trợ lý đã dùng, không phải một prompt nguyên văn do học viên soạn đủ bốn ý.
- **Cách kiểm:** trợ lý chạy 79/79 test đạt, kiểm thêm dòng nhiều lỗi, dòng trống, nhiều dự đoán, tính lặp lại của sửa; chạy calib, pipeline và thí nghiệm budget=0; xem mẫu ảnh trùng. Học viên cần đọc và hiểu code trước khi nộp; không ghi nhận các kiểm tra này là do học viên tự thực hiện.
- **Một lần AI sai:** ban đầu trợ lý dùng `python` của MSYS2 để tạo venv nhưng lại gọi đường dẫn Windows `.venv/Scripts/python.exe`, nên lệnh thất bại. Đã xác định sai interpreter và tạo lại venv bằng `py -3.13`, sau đó cài thư viện và chạy test thành công.

Phần lõi đã kiểm trên Ubuntu/WSL: **79 test đạt, 0 lỗi, 1 cảnh báo bỏ qua train** ([log](reports/check_core.txt)). Sau train, kiểm đầy đủ bằng `python scripts/check_submission.py`: **79 test đạt, 0 lỗi, 0 cảnh báo, mã thoát 0** ([log đầy đủ](reports/check_full.txt)). Trên Windows, script đề so đường dẫn `pipeline\calibrate.py` với danh sách dùng `/`, nên báo nhầm file calibration được bảo vệ; giữ nguyên script và kiểm trên Linux. Chưa thực hiện phần thưởng CVAT.
