# Data Model: Thống nhất dữ liệu + dữ liệu mở/động

Các thực thể và quy tắc hợp lệ của feature. Nguồn gốc yêu cầu: `spec.md` (FR-001…FR-025), đặc tả định dạng từ feature 005, quyết định trong `research.md`.

## Tổng quan

```text
chatbot.txt (viết tay) ── kind: qa | doc | fact ──► KB engine / fuzzy / RAG
sources/courses.csv ───────────────────────────────► QA từng môn + số tổng hợp (tự sinh)
sources/aliases.txt + cột aliases ─────────────────► chuẩn hoá bí danh câu hỏi
inbox/* (PDF|DOCX|XLSX|CSV|TXT) ───────────────────► chunk RAG (sau khi vệ sinh)
```

Mọi giá trị học tập **chỉ có một chỗ**:

- Điểm/tín chỉ/xét chuyên ngành từng môn → dòng trong `courses.csv`.
- GPA, tổng TC, số HP, GPA xét CN, môn cao/thấp nhất → **tính ra** từ `courses.csv` (không gõ tay).
- Giá trị đơn lẻ khác (tốt nghiệp, IELTS, ngành…) → bản ghi `fact`, tham chiếu bằng `{{id}}`.

## 1. Fact

| Thuộc tính | Kiểu | Quy tắc |
|---|---|---|
| `id` | chuỗi | Bắt buộc, duy nhất toàn hệ (gồm cả id của qa/doc), khớp `^[a-z0-9][a-z0-9_-]{0,63}$` |
| `label` | chuỗi | Bắt buộc, ≤ 120 ký tự, tên đọc được (ví dụ "GPA tích lũy (thang 10)") |
| `value` | chuỗi | Bắt buộc, không rỗng, ≤ 4.000 ký tự |
| `snapshot` | ngày (YYYY-MM-DD) | Tuỳ chọn, ngày giá trị được chốt (ví dụ 2026-11-07) |
| `source` | chuỗi | Tuỳ chọn, ≤ 300 ký tự (ví dụ `bang-diem.pdf`) |
| `status` | enum | `active` (mặc định) \| `archived` |

- Fact `archived` không được dùng thay placeholder và không được trả lời trực tiếp.
- Trùng `id` trong bất kỳ kind nào → lỗi `E_CONFLICT` kèm số dòng.
- Hai fact cùng `id` khác `value` → lỗi; sửa giá trị nghĩa là sửa đúng một chỗ này.

**Bộ fact ban đầu (mốc 1)** (giá trị từ bảng điểm PDF 07/11/2026 và hồ sơ đã duyệt):

| id | label | value | snapshot | source |
|---|---|---|---|---|
| gpa-10 | GPA tích lũy (thang 10) | 8.51 | 2026-11-07 | bang-diem.pdf |
| gpa-4 | GPA tích lũy (thang 4) | 3.63 | 2026-11-07 | bang-diem.pdf |
| credits | Tổng tín chỉ tích lũy | 87 | 2026-11-07 | bang-diem.pdf |
| courses-count | Số học phần | 24 | 2026-11-07 | bang-diem.pdf |
| ranking | Xếp loại học lực | Giỏi | 2026-11-07 | bang-diem.pdf |
| gpa-major | GPA xét chuyên ngành | 8.55 (21 môn, 79 tín chỉ) | 2026-11-07 | bang-diem.pdf |
| majors | Ngành đào tạo | Khoa học Máy tính và Khoa học Dữ liệu | — | data.txt |
| graduation | Tốt nghiệp dự kiến | tháng 8/2028 | — | data.txt |
| ielts | Mục tiêu IELTS | Academic 6.5 – 7.0, dự kiến thi cuối 2027 hoặc đầu 2028 | — | data.txt |

*(Đích cuối của mốc 2; trước đó các giá trị này vẫn nằm trong câu trả lời viết tay — xem chuyển trạng thái bên dưới.)*

## 2. Course (dòng trong `courses.csv`)

| Cột | Kiểu | Quy tắc |
|---|---|---|
| `code` | chuỗi | Bắt buộc, duy nhất (ví dụ `CSC10006`) |
| `name` | chuỗi | Bắt buộc, duy nhất, tên đầy đủ có dấu |
| `credits` | số nguyên | Bắt buộc, 1 ≤ credits ≤ 20 |
| `score10` | số | Bắt buộc, 0 ≤ score10 ≤ 10, tối đa 4 chữ số thập phân |
| `score4` | số | Tuỳ chọn, 0 ≤ score4 ≤ 4 (nếu thiếu sẽ tính từ score10 theo bảng quy đổi của trường) |
| `letter` | chuỗi | Tuỳ chọn, một trong A+, A, B+, B, C+, C, D+, D, F |
| `counts_major` | enum | Bắt buộc, `yes` \| `no` — có tính vào GPA xét chuyên ngành không |
| `aliases` | chuỗi | Tuỳ chọn, danh sách phân tách `\|`, không trùng nhau (ví dụ `oop\|lập trình hướng đối tượng`) |

Quy tắc bổ sung:

- Trùng `code` hoặc `name` → lỗi `E_CONFLICT` (FR: môn cùng mã khác tên là dữ liệu sai).
- Một dòng sinh ra 3 câu hỏi-đáp tự động: **điểm**, **số tín chỉ**, **có xét chuyên ngành** — câu trả lời đúng định dạng: "Điểm `<name>` là `<score10>` (`<letter>`, `<credits>` tín chỉ)".
- 24 dòng ban đầu khớp từng hàng của bảng điểm PDF; mọi số tổng hợp tính từ bảng này phải khớp dòng tổng kết PDF (dung sai 0.001), lệch → `W_CONFLICT`.

**Mẫu 3 dòng (từ plan đã duyệt):**

```csv
code,name,credits,score10,score4,letter,counts_major,aliases
CSC10004,Cấu trúc dữ liệu và giải thuật,4,5.4,2.2,C,yes,ctdl|dsa
CSC10003,Phương pháp lập trình hướng đối tượng,4,6.9,2.95,B,yes,oop|pplt hđt
BAA00004,Pháp luật đại cương,3,8.6,3.8,A,no,pháp luật
```

## 3. Alias (bí danh)

- Nguồn: `sources/aliases.txt` (mỗi dòng: `bí-danh | tên-chuẩn`; nhiều bí danh cùng đích phân tách bằng dấu phẩy) **cộng** cột `aliases` của từng dòng course.
- Áp dụng tại `normalize_query` trước khi khớp: `vtp2` → `vi tích phân 2`, `oop` → `phương pháp lập trình hướng đối tượng`, `xstk` → `xác suất thống kê`, `hđh` → `hệ điều hành`, `knm` → `kỹ năng mềm`…
- Bí danh trùng nhau hoặc trùng `code`/`name` → lỗi khi validate.
- Thay thế hoàn toàn các cặp record trùng hiện tại (`vtp1`/`vi-tich-phan-1`, `ky-nang-mem`/`ki-nang-mem`, `vat-ly`/`vat-li`).

## 4. QA record & Doc record (mở rộng từ feature 005)

Giữ nguyên hợp đồng của 005, bổ sung:

- Trường `status: active|archived` cho mọi kind; `archived` không xuất hiện trong KB/fuzzy/RAG/gợi ý, vẫn giữ trong tệp để khôi phục.
- Khối `answer`/`bullets`/`content` có thể chứa placeholder `{{id-fact}}`; parser thay thế bằng giá trị fact khi trả lời; tham chiếu fact không tồn tại → `E_PLACEHOLDER_UNKNOWN` kèm số dòng, tệp không nạp.
- Thoát: `\{{...}}` hiểu là chuỗi theo nghĩa đen.
- Mốc 2 di trú: xoá toàn bộ record `diem-*` và `*-xet-chuyen-nganh` viết tay (đã được sinh tự động từ `courses.csv`); record `doc` chỉ do `ingest` sinh từ tệp gốc (mỗi tệp → 1+ record, số trang từ 1, nguồn ghi tên tệp + trang/sheet/dòng).

## 5. Inbox file

| Thuộc tính | Quy tắc |
|---|---|
| Định dạng | `.pdf`, `.docx`, `.xlsx`, `.csv`, `.txt` (kế thừa loader 006) |
| Dấu vân tay | SHA-256 nội dung; nạp lại chỉ khi hash thay đổi |
| Vệ sinh trước chunk | bỏ `nan`/`Unnamed*`/`about:blank`; làm tròn số nhiễu; bỏ header/footer lặp; trang từ 1 |
| Từ chối | nội dung còn `[...]` → `E_PLACEHOLDER`; còn `nan`/`Unnamed`/`about:blank` → `E_NOISE`; tệp bị từ chối giữ nguyên trong inbox kèm báo lỗi vị trí |
| Kết quả | 1+ record `doc` (chunk hoá khi nạp) + mục trong chỉ mục RAG; không ghi vào `chatbot.txt` |

## 6. Chuyển trạng thái và vòng đời

```text
[soạn/sửa] ─► validate ─ lỗi ─► báo vị trí, không ghi
                  │
                  └─ sạch ─► ghi tạm + os.replace ─► reload signature ─► request kế tiếp dùng mới
                                                                              │
                        ┌─────────────────────────────────────────────────────┘
                        ▼
            [thay đổi nguồn] ─► validate lại ─ lỗi ─► giữ nguyên index cũ đang chạy

record: active ◄─┬─► archived (khôi phục bất cứ lúc nào; không bị trả lời khi archived)
```

Quy tắc ghi (áp dụng mọi lệnh ghi): đọc toàn bộ → áp thay đổi trên bản sao → validate đầy đủ → ghi tệp tạm cùng thư mục → `os.replace()` → tự nạp lại. Bất kỳ bước lỗi → dừng, không ghi.

## 7. Chuẩn hoá dữ liệu mốc 1 (danh sách đối soát)

| Chỉ tiêu | Giá trị duy nhất | Ghi chú |
|---|---|---|
| GPA thang 10 | 8.51 (≈ 8.5) | gốc 8.514 |
| GPA thang 4 | 3.63 | gốc 3.634; CV ghi 3.63/4.0 |
| Tổng tín chỉ | 87 | |
| Số học phần | 24 | |
| Xếp loại | Giỏi | |
| Điểm OOP | 6.9 (B, 4 TC) | tên đầy đủ "Phương pháp lập trình hướng đối tượng" |
| GPA xét CN | 8.55 (21 môn, 79 TC) | loại Kỹ năng mềm, Pháp luật đại cương, Kinh tế đại cương |
| Ngành | Khoa học Máy tính và Khoa học Dữ liệu | |
| Chuyên ngành dự kiến | Máy tính, Trí tuệ nhân tạo (AI), Kỹ thuật phần mềm | |
| Tốt nghiệp | tháng 8/2028 | |
| GDQP | archived | 7.1 không có trên PDF |
| data.xlsx | cách ly | không nạp |
| Liên hệ | gỡ record | chờ dữ liệu thật |
