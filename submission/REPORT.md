# Báo cáo Day 09 — Dương Quang Chung, 2A202603217

## 1. Kết luận trước
**Hold.** Từ 224 ảnh raw, cửa vào loại 19 ảnh, còn 205 ảnh được xuất thành **bản nháp** `clean_v1`. Sau khi chạy sửa tự động và duyệt mô phỏng 80 ảnh, dataset không còn lỗi bắt buộc nhưng vẫn còn 38/205 ảnh có cảnh báo chưa duyệt (chiếm 18.54% ≥ 10%), nên chưa đủ điều kiện phát hành ([summary](reports/08_summary.json)).

## 2. Lỗi và phân việc
Nguồn: [danh sách v1](reports/02_error_list_v1.csv). Các lỗi cửa vào tính trên toàn bộ 224 ảnh; các lỗi QC tính trên 205 ảnh được nhận. Cột số lượng ghi nhận số bản ghi lỗi (không cộng dồn thành số ảnh vì một ảnh có thể dính nhiều lỗi).

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

Hàng đợi ưu tiên dựa trên tổng trọng số lỗi, tăng dần theo độ tự tin (confidence). `img_0020` đứng đầu (11.524 điểm) do có dòng bị xoá, nghi thiếu box và nhầm lớp; xếp ngay sau là 6 ảnh thiếu file nhãn (10 điểm/ảnh). Trong 125 ảnh chờ, bước mô phỏng đã duyệt 80 ảnh, bao gồm **74/103 ảnh có cảnh báo ngữ nghĩa**, tương ứng **94/123 cảnh báo** ở bản v2. Đây là lượng cảnh báo được đưa qua duyệt chứ chưa phải số lỗi thật đã chốt ([hàng đợi](reports/05_review_queue.csv), [log duyệt](reports/06_review_log.csv)).

## 3. Calibration (2 ngưỡng)

Đo trên 39 ảnh calib bằng `pipeline.calibrate`; số liệu trích từ [calibration.json](calibration/calibration.json) và [bảng sweep](calibration/calibration_report.md). P = precision, R = recall; các chỉ số được làm tròn 3 chữ số thập phân.

| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---|---|---|---|
| `duplicates.phash_dist` | 2 | **4** | Gần trùng: 1.000 / 0.500 → 1.000 / 0.667 | Bắt được 4/6 ca thay vì 3/6, FP = 0 trên calib; mình chọn ngưỡng nhỏ nhất đạt mức này để tránh xoá nhầm ảnh sạch, chấp nhận sót 2/6 ca. |
| `second_opinion.conf` | 0.25 | **0.6** | Thiếu box: 0.500 / 1.000 → 0.571 / 1.000; nhầm lớp: 0.556 / 0.833 → 0.625 / 0.833 | Giữ nguyên TP thiếu box (8/8) và nhầm lớp (5/6), giảm FP tương ứng từ 8→6 và 4→3; chấp nhận giảm khả năng bắt box lỏng. |

Về đánh đổi khi đặt `conf=0.6`: P/R của box lỏng giảm từ **0.286/0.400 → 0.200/0.200**, chỉ bắt được 1/5 ca thay vì 2/5. Box thừa giữ nguyên P/R **0.312/1.000** (TP=5, FP=11) do chạy theo ngưỡng `fp_conf` riêng. Mức ngưỡng này không tối ưu cho mọi loại lỗi nên vẫn cần người kiểm tra bổ sung phần box lỏng. Mình cũng không đẩy lên 0.8 dù precision nhầm lớp đạt 1.000, vì làm vậy recall thiếu box sẽ tụt xuống còn 6/8.

**Lưu ý khi nhìn số liệu calibration:** Trên tập calib, `phash_dist=16` đạt P=1.000, R=5/6 cho ảnh gần trùng, nhưng khi chạy thử trên tập raw lại gộp nhầm `img_0008` (hai người trượt tuyết) với `img_0011` (người chơi tennis). Vì xoá nhầm sẽ làm mất dữ liệu tốt nên mình chốt giữ ngưỡng 4 dù recall trên calib thấp hơn. Ngoài ra, tập calib chỉ có 6 ca gần trùng và không có ca rò rỉ test, nên không thể lấy P/R ở đây để suy rộng cho toàn bộ tập raw.

Với cấu hình đã chọn, [báo cáo cửa vào](reports/01_intake.csv) ghi nhận loại 19/224 ảnh: 2 ảnh hỏng, 3 ảnh quá nhỏ, 8 trùng byte, 2 gần trùng và 4 ảnh nghi rò rỉ từ kho test/val. Mình đã mở kiểm tra trực tiếp 2 cặp gần trùng (`img_0042`–`img_0076`, `img_0037`–`img_0143`) cùng 3 cặp trùng byte thì chưa thấy ca nào bị loại oan; toàn bộ 8 cặp trùng byte cũng đã đối chiếu khớp mã SHA-256. Tuy nhiên đây chỉ là bước kiểm tra mẫu xác suất, không đảm bảo 100% trường hợp đều chuẩn xác.

Chạy thử pipeline cho kết quả **Hold**: hàng đợi 125 ảnh, người duyệt mô phỏng xử lý xong 80 ảnh; sau cùng còn 38/205 ảnh có cảnh báo chưa duyệt (18.54% ≥ 10%), không còn lỗi bắt buộc ([summary](reports/08_summary.json)). Mình giữ nguyên cấu hình, không cố tình tăng `conf` để ép đạt Release; bản xuất ra hiện tại chỉ dừng ở mức nháp.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
Mình chạy một thí nghiệm tách biệt để kiểm tra cửa chặn, không làm ảnh hưởng đến báo cáo và dataset chính:

```powershell
.\.venv\Scripts\python.exe -m pipeline.run --budget 0 --work work/run_nb --reports submission/reports/gate_no_review --export-dir work/exp_nb
```

Kết quả trả về: **Rework, mã thoát 20**, còn tồn 6 lỗi `MISSING_LABEL_FILE` trên 205 ảnh; thư mục `work/exp_nb/clean_v1` không được tạo. Chi tiết xem tại [summary thí nghiệm](reports/gate_no_review/08_summary.json), [mã thoát và kiểm tra export](reports/gate_no_review/proof.json), và [log chạy](reports/gate_no_review/run.log). Cờ `needs_label` chỉ đẩy tác vụ sang cho người gán chứ không tự sinh file nhãn rỗng.

Có hai điểm mù lộ rõ khi đo trên calib: (1) box lỏng chỉ bắt được **1/5**, bỏ sót **4/5** ở cấu hình hiện tại; (2) ảnh gần trùng chỉ bắt **4/6**, sót **2/6**. Bên cạnh đó, lỗi nhầm lớp vẫn sót **1/6**. Những ca khó này bắt buộc phải có người rà soát thủ công, không thể thấy checker im lặng mà mặc định nhãn đã đúng. Các quy tắc cú pháp cũng bó tay trước những ca thuộc về ngữ cảnh ảnh—ví dụ người mặc quân phục chưa được gắn box trong `img_0001` mà mình phát hiện khi soi ảnh ở bước chuẩn bị.

## 5. Train: raw vs clean

Mình chạy huấn luyện trên [Kaggle Tesla T4](https://www.kaggle.com/code/chungdngquang/day09-autoqc-duong-quang-chung-raw-vs-clean) để thay thế cho Colab đang hết hạn mức GPU. Cả hai tập đều train bằng `yolo26n.pt`, Ultralytics 8.4.214, **20 epoch, batch 16, imgsz 640, seed 0/1**, dùng chung tập `gold_val` 40 ảnh để chọn checkpoint và `test` 100 ảnh để đo kết quả cuối. Dữ liệu đầu vào chốt tại commit `a0d8e07`; file JSON gốc sinh ra từ `scripts/train_compare.py`, còn bảng tổng hợp dưới đây xuất từ `scripts/summarize_results.py`.

| biến thể | #ảnh train | số seed | map50 (TB ± độ lệch) | map50_95 (TB ± độ lệch) | precision (TB ± độ lệch) | recall (TB ± độ lệch) |
|---|---|---|---|---|---|---|
| raw | 224 | 2 | 0.726 ± 0.000 | 0.512 ± 0.004 | 0.764 ± 0.061 | 0.649 ± 0.028 |
| clean | 205 | 2 | 0.700 ± 0.030 | 0.486 ± 0.013 | 0.715 ± 0.073 | 0.615 ± 0.017 |

Chênh lệch mAP50 (clean − raw) = **-0.025**.

Lưu ý là 224 chỉ là số ảnh raw đưa vào thư mục đầu vào, **không phải số ảnh thực học**: Ultralytics đã tự động loại bỏ 11 ảnh/nhãn lỗi nên chỉ học trên **213 ảnh**; trong khi đó bản `clean` dùng trọn vẹn **205 ảnh** không rơi rớt ảnh nào. Chi tiết cache và môi trường lưu tại [training_environment.json](results/training_environment.json).

Xét số lẻ chi tiết của mAP50: raw đạt **0.72575 ± 0.00021**, clean đạt **0.70035 ± 0.03048**. Mức chênh **−0.02540** thực tế còn nhỏ hơn độ lệch chuẩn giữa hai lần chạy seed của bản clean (0.03048); chênh lệch cụ thể từng seed lần lượt là −0.0468 và −0.0040. Dù điểm trung bình của clean đang thấp hơn trong lượt chạy này, **chưa đủ cơ sở kết luận clean kém hơn raw**, vì quy mô 2 seed trên 100 ảnh test còn quá mỏng để khái quát hoá. Nhìn sâu vào từng lớp, AP50 trung bình tăng nhẹ ở `car` (+0.011), `person` (+0.005), nhưng tụt ở `truck` (−0.090) và `bus` (−0.028).

Có hai giả thuyết cần kiểm chứng thêm (chưa kết luận nguyên nhân): (1) Tập raw chứa 4 ảnh nghi trùng với kho test/val nên có thể bị đội điểm ảo; cần đo lại trên một tập test độc lập hoàn toàn sạch rò rỉ để biết mức độ nhiễu. (2) Bản clean vẫn đang kẹt trạng thái Hold với 38/205 ảnh cảnh báo chưa duyệt, đồng thời tổng số mẫu học ít hơn; việc sót nhãn ngữ nghĩa hoặc lệch phân bố nhóm `car/truck/bus` có thể kéo điểm xuống. Bước tiếp theo cần audit kỹ các lớp xe này, đối chiếu lại số lượng box, rồi chạy thêm thí nghiệm kiểm soát với nhiều seed hơn—tuyệt đối không tinh chỉnh ngược ngưỡng lọc dựa trên điểm test vừa đo.

## 6. Quyết định và ghi chú 
Chốt giữ trạng thái **Hold**, chưa phát hành. Điều kiện để lên Release là sạch lỗi bắt buộc và tỷ lệ ảnh còn cảnh báo chưa duyệt phải dưới 10%: với 205 ảnh thì tối đa chỉ được phép còn 20 ảnh, nghĩa là cần xử lý dứt điểm thêm ít nhất 18/38 ảnh hiện tại rồi chạy lại QC. Do ngân sách 80 ảnh của lần chạy này đã chạm trần nên cần mở thêm một vòng duyệt mới được cấp phép, không tự ý nới ngân sách hay sửa ngưỡng gate để ép pass. Các điểm mù đã nêu ở trên vẫn cần kiểm tra thủ công bổ sung.

- **Cách dùng AI hỗ trợ:** Mình chia nhỏ công việc và yêu cầu AI hoàn thiện từng module (tổng cộng 4 module) bám sát docstring cùng bộ test có sẵn; quy định rõ đầu vào YOLO/cache, các rule kiểm tra và định dạng xuất `Issue`/log đúng chuẩn đề bài, đồng thời khoá chặt không cho sửa file test, dữ liệu gốc hay tự ý ghi đè nhãn ngữ nghĩa.
- **Tự kiểm thử và rà soát:** Sau khi ghép code, mình chạy toàn bộ 79/79 unit test, tự viết thêm các ca kiểm tra biên như dòng dính nhiều lỗi, file nhãn rỗng, ảnh nhiều dự đoán và kiểm tra tính luỹ đẳng (idempotency) khi chạy sửa lặp lại. Tiếp đó mình trực tiếp chạy sweep calibration, chạy pipeline chính, thử nghiệm kịch bản `budget=0` và mở soi đối chiếu thủ công các cặp ảnh trùng.
- **Sự cố môi trường đã xử lý:** Lúc đầu tạo môi trường ảo bằng lệnh `python` mặc định của MSYS2 nhưng lại gọi đường dẫn kiểu Windows `.venv/Scripts/python.exe`, nên lệnh thất bại. Đã xác định sai interpreter và tạo lại venv bằng `py -3.13`, cài lại dependencies thì mọi lệnh chạy và test đều thông suốt.

Phần lõi đã được kiểm tra trên Ubuntu/WSL: **79 test đạt, 0 lỗi, 1 cảnh báo bỏ qua phần train** ([log](reports/check_core.txt)). Sau train, mình chạy kiểm tra toàn diện bằng `python scripts/check_submission.py`: **79 test đạt, 0 lỗi, 0 cảnh báo, mã thoát 0** ([log đầy đủ](reports/check_full.txt)). Có một lưu ý nhỏ trên Windows: script kiểm tra của đề đang so chuỗi đường dẫn `pipeline\calibrate.py` với danh sách chuẩn dùng dấu `/`, dẫn đến báo nhầm file calibration bị sửa đổi; mình giữ nguyên script của đề và chuyển sang nghiệm thu trên môi trường Linux. Phần bài tập thưởng CVAT mình chưa triển khai.
