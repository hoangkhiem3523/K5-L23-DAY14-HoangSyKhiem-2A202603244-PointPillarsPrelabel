# Báo cáo Day 14 — Hoàng Sỹ Khiêm — 2A202603244

> File báo cáo cá nhân (sao chép từ `MSSV_HoTen.md`).

- Mã học viên dùng với `--student`: `2A202603244`
- `seed_tag` trong `frames_A.txt`: `393590736f`

## 1. Dự đoán trước sweep (bước 5b)

- Tham số tôi nghĩ giảm công sửa nhiều nhất: tăng **`score_thr`** (từ `0.1` lên khoảng `0.3–0.4`), có thể kết hợp **`min_points = 5`**.
- Vì sao (nhìn ảnh BEV tập A: box thừa nhiều hay box sót nhiều?): Nhìn 3 ảnh `d14_2A202603244/png_A/` (`s03f03`, `s04f09`, `s05f24`) và kết quả đo bước 5 (dự đoán `80` hộp so với `52` hộp tham chiếu: **xóa 39**, **thêm 11**, **sửa 5**, tổng chi phí `25.2`), tỷ lệ **box thừa chiếm gần một nửa** số dự đoán (chủ yếu là các hộp confidence thấp nhận nhầm hàng rào công trình, dải phân cách vàng, cột biển báo và dãy xe đạp dựng bên vỉa hè ở `s05f24`). Riêng phần xóa đã chiếm `39 × 0.3 = 11.7` điểm chi phí. Do đó tăng `score_thr` vừa phải (và lọc các hộp rất ít điểm bằng `min_points`) sẽ cắt được nhiều box rác mà không làm mất quá nhiều xe thật — tuy nhiên không nên tăng quá mạnh vì theo công thức chi phí, mỗi hộp thật bị lọc sót tốn `1.0` điểm, đắt gấp `3,3` lần một hộp thừa (`0.3` điểm).

## 2. Tập A: sửa tay và tune

| Cấu hình | Xóa | Thêm | Sửa | Chi phí |
|---|---:|---:|---:|---:|
| Gốc | | | | |
| `best_config.json` | | | | |

- Tham số đã đổi trong `best_config.json`: ...
- Kết quả leave-one-out (dán các dòng `scripts/pp_sweep.py` in ra): ...
- Cấu hình có ổn định trên từng frame không? Vì sao tôi vẫn chọn (hoặc không chọn) nó: ...

## 3. Trước/sau (bước 8)

![so sánh](../../d14_2A202603244/compare/<frame>.jpg)

- `scripts/pp_compare.py` báo giảm (hoặc tăng) ...% công sửa trên tập A.
- Dự đoán ở mục 1 đúng hay sai? Giải thích bằng số box xóa/thêm/sửa: ...

## 4. Tập B

Số đo từ `scripts/pp_prelabel.py --frames d14_2A202603244/frames_B.txt --config d14_2A202603244/best_config.json --gt d14_2A202603244/ref_B.json`:

| Xóa | Thêm | Sửa | Chi phí |
|---:|---:|---:|---:|
| | | | |

- Loại box tốn công sửa nhất ở tập B: ...

## 5. Giới hạn

- Nêu ít nhất 2 giới hạn (ví dụ: chỉ 3 frame tune; model KITTI không có Truck/Bus; chi phí là công thức, chưa phải thời gian sửa thật): ...
