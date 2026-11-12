# Research: Thống nhất dữ liệu + dữ liệu mở/động

Các ẩn số kỹ thuật được giải quyết bằng cách soi mã nguồn hiện có (feature 005/006) và đối chiếu với thiết kế đã duyệt trong spec. Không có NEEDS CLARIFICATION còn sót.

## R1 — Mở rộng ngữ pháp tệp nguồn: `kind: fact`, placeholder, `status`

- **Decision**: Giữ header `CHATBOT-SOURCE v1`, mở rộng **cộng dồn**: thêm `kind: fact` (trường `label`, `value`, `snapshot`, `source`), trường `status: active|archived` cho mọi kind, và placeholder `{{id}}` trong các khối `answer`/`bullets`/`content` với quy tắc thoát `\{{...}}`.
- **Rationale**: Bản dữ liệu mới chủ chatbot đã duyệt vẫn ghi header `v1`; bump `v2` sẽ buộc đổi mọi tệp/test hiện có. Parser 005 đã được thiết kế để "trường lạ bị bỏ qua kèm cảnh báo", nên thêm kind/trường là phát triển tự nhiên; placeholder chỉ có ý nghĩa trong nội dung, không đụng ngữ pháp khung record.
- **Alternatives considered**: (a) Bump `CHATBOT-SOURCE v2` — rõ ràng về version nhưng gây churn tệp dữ liệu đã duyệt; (b) Để placeholder là phép nội suy thời chạy ngoài parser — dễ bỏ sót khi validate offline. Cả hai bị loại.

## R2 — Vị trí và định dạng danh sách môn + bí danh

- **Decision**: `backend/data/sources/courses.csv` (8 cột: `code,name,credits,score10,score4,letter,counts_major,aliases`, aliases phân tách bằng `|`) và `backend/data/sources/aliases.txt` (mỗi dòng `bí-danh | tên-chuẩn` hoặc nhóm `bí-danh1, bí-danh2 | tên-chuẩn`). Đường dẫn ghi đè được bằng biến môi trường `CHATBOT_COURSES_PATH`, `CHATBOT_ALIASES_PATH`; mặc định nằm trong `CHATBOT_DATA_DIR`.
- **Rationale**: CSV là cách dễ sửa bằng tay và dễ so sánh `diff` (tiêu chí NFR-003 của 005); aliases tách file riêng để bí danh **chủ đề/khái niệm** (không chỉ môn) dùng chung một cơ chế với `aliases` của từng dòng môn. Trong `data/` vì thư mục này đã được Docker bind-mount và `CHATBOT_DATA_DIR` đã là điểm vào vận hành hiện tại.
- **Alternatives considered**: (a) Gộp tất cả vào `chatbot.txt` — phá Q16 ("file viết tay duy nhất" không có nghĩa là file duy nhất tuyệt đối; dữ liệu bảng phải tách để tự sinh); (b) JSON — khó gõ/sửa tay hơn CSV.

## R3 — Tính số tổng hợp và đối chiếu

- **Decision**: GPA thang 10 = Σ(score10×credits)/Σcredits; thang 4 tương tự với score4; tổng TC = Σcredits; số HP = số dòng; GPA xét chuyên ngành tính trên các dòng `counts_major=yes`. Kết quả được đối chiếu với giá trị fact `gpa-10`, `gpa-4`, `credits`, `courses` (dung sai 0.001) và với dòng tổng kết của bảng điểm PDF; lệch → `W_CONFLICT` (cảnh báo, kèm hai giá trị) khi nạp, `E_CONFLICT` khi lệnh `add course` tạo ra mâu thuẫn giá trị trùng id.
- **Rationale**: Công thức GPA theo tín chỉ là chuẩn đại học Việt Nam; PDF 07/11/2026 là nguồn sự thật (Q1) nên số tính ra **phải** khớp, sai lệch nghĩa là dữ liệu sai chứ không phải công thức sai → phải cảnh báo rõ, không im lặng.
- **Alternatives considered**: (a) Cảnh báo là lỗi cứng (E) — quá khắt vì làm tròn hiển thị (8.51 vs 8.514) luôn lệch nhẹ; (b) không đối chiếu — phá tiêu chí N2/N3. Đã cân bằng bằng cặp W/E.

## R4 — Bí danh trong chuẩn hoá câu hỏi

- **Decision**: Bí danh được áp dụng ở tầng chuẩn hoá câu hỏi (sau `normalize_query`, trước khi khớp KB/fuzzy/embedding): thay chuỗi bí danh → tên chuẩn rồi nối vào văn bản chuẩn hoá để khớp cả hai chiều. Bản đồ bí danh gộp từ `aliases.txt` + cột `aliases` của từng dòng môn.
- **Rationale**: `normalize_query` đã là điểm vào duy nhất của mọi luồng khớp (KB engine, fuzzy, retrieval) — chèn một bước tại đây cho hiệu lực toàn cục, không phải sửa từng engine. Tránh được việc nhân đôi record `vtp1`/`vi-tich-phan-1` như hiện tại (I22).
- **Alternatives considered**: (a) Thêm câu hỏi giả vào từng record — chính là nguyên nhân record trùng hiện nay; (b) embedding riêng cho bí danh — phình chỉ mục không cần thiết.

## R5 — Quy trình ghi nguyên tử và tự nạp lại

- **Decision**: Mọi lệnh ghi (`add fact|qa|course`, sửa `chatbot.txt` bằng tay, `ingest inbox/`) đi qua một đường: đọc toàn bộ trạng thái → áp thay đổi vào bản sao → validate (cú pháp, placeholder, trùng id, mâu thuẫn, chuỗi rác) → nếu sạch thì ghi tệp tạm cùng thư mục rồi `os.replace()` (nguyên tử trên cùng filesystem). Server nhận biết thay đổi bằng signature đã có từ feature 005 (`mtime`/kích thước/hash) mở rộng thêm cho `courses.csv`/`aliases.txt`/`inbox/`, và tự dựng lại chỉ mục cho request kế tiếp; tệp mới sai → giữ nguyên trạng thái cũ (hành vi đã có: tệp sai không nạp một phần).
- **Rationale**: `os.replace` là cách ghi nguyên tử chuẩn POSIX, không cần thư viện mới; signature-based reload đã được chứng minh trong `test_source_reload.py` nên chỉ cần mở rộng nguồn đầu vào.
- **Alternatives considered**: (a) SQLite thay cho tệp — phá mục tiêu "đọc được bằng mắt, diff được"; (b) ghi trực tiếp không tạm — có cửa sổ tệp hỏng khi ghi giữa chừng.

## R6 — Lọc rác khi nạp tài liệu

- **Decision**: Thêm bước vệ sinh trong `doc_loaders.py` (mọi định dạng): bỏ dòng/cột rỗng và tên cột `Unnamed*` (xlsx), thay `nan`/`None` thành ô trống rồi bỏ, xoá chuỗi `about:blank X/Y` ở đuôi trang PDF, làm tròn số thực về tối đa 4 chữ số thập phân (9.300000000000001 → 9.3), đánh số trang PDF từ 1 (hiện `pypdf` trả index 0). Nếu **sau** vệ sinh vẫn còn `[...]` hoặc "(ví dụ)" → `E_PLACEHOLDER`/`E_NOISE` và từ chối tệp.
- **Rationale**: Các chuỗi này là đặc trưng của thư viện trích xuất (pandas/openpyxl/pypdf), nên vệ sinh phải nằm ở tầng loader trước khi chunking; phần `[...]`/"(ví dụ)" là lỗi nội dung thật của chủ chatbot nên phải chặn, không tự bỏ.
- **Alternatives considered**: (a) Bỏ lọc, chỉ cảnh báo — phá N8 (0 chuỗi rác); (b) tự xoá `[...]` — che giấu placeholder chưa điền của CV, trái Q11.

## R7 — Lệnh vận hành mới

- **Decision**: Mở rộng CLI hiện có `backend/scripts/manage_docs.py` (không tạo CLI mới): `add fact --id --label --value [--snapshot --source]`, `add qa --topic --q --a [--bullets]`, `add course --code --name --credits --score10 [--score4 --letter --counts-major --aliases]`, `ingest inbox/…` (mặc định nạp cả thư mục inbox), `validate` (mở rộng kiểm tra fact/placeholder/courses/aliases). Tất cả trả exit code khác 0 khi lỗi và in vị trí lỗi.
- **Rationale**: CLI đã có sẵn cơ chế subcommand/validate và người dùng đã quen; thêm subcommand nhỏ hơn là tạo công cụ mới.
- **Alternatives considered**: Trang admin web — đã thống nhất là ngoài phạm vi (Q15).

## R8 — Trình tự triển khai hai mốc

- **Decision**: Mốc 1 (dữ liệu) đi trước và độc lập với mốc 2 (engine): thay nội dung `chatbot.txt` bằng bản đã duyệt (giữ nguyên header v1, chưa có fact/placeholder), tạo `sources/courses.csv` + `aliases.txt` (được engine đọc sau này), cách ly `data.xlsx`. Mốc 2 bật engine rồi **di trú tiếp**: xoá record `diem-*`/`*-xet-chuyen-nganh` viết tay (thay bằng QA sinh từ courses.csv) và chuyển giá trị lặp sang fact + placeholder.
- **Rationale**: Khớp lộ trình đã duyệt (bước 2 làm ngay không cần code → dữ liệu thống nhất sớm; bước 3–5 mới làm engine). Người dùng có thể dùng chatbot đúng số liệu ngay trong khi engine vẫn đang xây.
- **Alternatives considered**: Engine trước, dữ liệu sau — chatbot tiếp tục trả số cũ trong suốt thời gian làm engine, trái mục tiêu N1.

## Quyết định tổng hợp

| # | Chủ đề | Quyết định |
|---|---|---|
| R1 | Định dạng tệp | `CHATBOT-SOURCE v1` mở rộng cộng dồn: `kind: fact`, `status`, `{{placeholder}}` |
| R2 | Dữ liệu mở | `data/sources/courses.csv` + `aliases.txt`; biến môi trường riêng, mặc định trong `CHATBOT_DATA_DIR` |
| R3 | Số tổng hợp | Tính từ courses.csv; đối chiếu fact/PDF, lệch → `W_CONFLICT`/`E_CONFLICT` |
| R4 | Bí danh | Mở rộng `normalize_query`; nguồn gộp từ aliases.txt + cột aliases |
| R5 | Ghi & reload | validate → ghi tạm + `os.replace` → signature-reload 3 nguồn; sai giữ index cũ |
| R6 | Rác khi nạp | Vệ sinh tầng loader; `[...]`/"(ví dụ)" còn sót → từ chối tệp |
| R7 | CLI | Mở rộng `manage_docs.py`: `add fact|qa|course`, `ingest inbox/`, `validate` |
| R8 | Trình tự | Mốc 1 dữ liệu → Mốc 2 engine → di trú record viết tay sang sinh tự động |
