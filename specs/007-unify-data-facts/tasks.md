---

description: "Task list for feature implementation"
---

# Tasks: Thống nhất dữ liệu đầu vào + dữ liệu mở/động

**Input**: Design documents from `/specs/007-unify-data-facts/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Bao gồm (repo đã có bộ pytest 27 tệp và plan.md chỉ định tệp test mới).

**Organization**: Nhóm theo user story; mỗi story triển khai và nghiệm thu độc lập. Hai mốc theo plan: **Mốc 1** (US1 — thuần dữ liệu, không code) chạy được song song với **Mốc 2** (engine, US2–US5).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Chạy song song được (khác tệp, không phụ thuộc task chưa xong)
- **[Story]**: User story tương ứng (US1…US5)
- Đường dẫn tệp chính xác trong mỗi mô tả

---

## Phase 1: Setup (Chuẩn bị nền)

**Purpose**: Thư mục dữ liệu mới, biến môi trường, bản sao lưu trạng thái cũ.

- [X] T001 Tạo thư mục `backend/data/sources/` và `backend/data/inbox/` (kèm tệp `.gitkeep` trong mỗi thư mục).
- [X] T002 [P] Thêm cấu hình môi trường `CHATBOT_COURSES_PATH`, `CHATBOT_ALIASES_PATH`, `CHATBOT_INBOX_DIR` (mặc định lần lượt là `<CHATBOT_DATA_DIR>/sources/courses.csv`, `<CHATBOT_DATA_DIR>/sources/aliases.txt`, `<CHATBOT_DATA_DIR>/inbox`) vào `backend/chatbox.py` (hàm `load_config`) và khai báo tương ứng trong `docker-compose.yml` (services `backend`).
- [X] T003 [P] Sao lưu trạng thái hiện tại: tạo `backend/data/archive/` và copy `chatbot.txt`, `data.txt`, `CV_Data_Science_Vietnamese.docx`, `data.xlsx` vào đó trước khi sửa (giữ lịch sử ngoài git).

---

## Phase 2: User Story 1 - Mọi câu hỏi về hồ sơ trả một giá trị duy nhất (Priority: P1) 🎯 MVP

**Goal**: Mọi giá trị hồ sơ khớp bảng điểm PDF 07/11/2026 (GPA 8.51/3.63, 87 TC, 24 HP, Giỏi); không còn số cũ ở bất kỳ nguồn nào. Thuần dữ liệu — không phụ thuộc Phase 3.

**Independent Test**: `python backend/scripts/manage_docs.py validate` sạch; `ask "gpa bao nhiêu"` → 8.51; `ask "điểm oop"` → 6.9; `ask "mục tiêu"` → ≥ 2 gợi ý; grep N1 (8.30/62/17/3.7) = 0 kết quả trong `backend/data/chatbot.txt`.

### Implementation for User Story 1

- [X] T004 [US1] Thay toàn bộ nội dung `backend/data/chatbot.txt` bằng bản `CHATBOT-SOURCE v1` mới đã duyệt (nội dung trong mô tả feature): `intro`/`university` ghi ngành đào tạo "Khoa học Máy tính và Khoa học Dữ liệu"; `gpa` ghi 8.51/10 (≈ 8.5; thang 4: 3.63), 87 tín chỉ, 24 học phần, Giỏi; `best-subjects` 3 môn 10.0 + Cơ sở dữ liệu 9.8; `skills` gộp đủ 8 nhóm; `projects` thêm Vietnam Air Quality & Weather Analytics Platform; `greeting`/`hi`/`van-phu-duc` ngôi thứ nhất "mình"; đủ 24 record `diem-*` đúng điểm PDF (OOP = 6.9); record mục tiêu (học bổng Đức/TUHH, IELTS Academic 6.5–7.0 thi cuối 2027/đầu 2028, tốt nghiệp 8/2028, định hướng AI Engineer/ML/CS Research, phong cách học); `gpa-chuyen-nganh` = 8.55 (21 môn, 79 TC); `du-an-air-quality`.
- [X] T005 [US1] Trong `backend/data/chatbot.txt`: xoá record `contact` (liên hệ ví dụ `vanphuduc@example.com`, `github.com/vanphuduc`); gỡ record Giáo dục quốc phòng (7.1) — tạm đánh dấu bằng dòng chú thích `# archived: gdqp` ngoài record cho đến khi parser hỗ trợ `status` (mốc 2).
- [X] T006 [US1] Trong `backend/data/chatbot.txt`: xoá 5 record `kind: doc` cũ mang số liệu lệch (62 TC / 17 môn / 8.30) — gồm `bang-diem-hoc-tap-van-phu-duc-page-1`, `cv-data-science-vietnamese`, `data` và các doc rác xlsx (nội dung sẽ do `ingest` sinh lại ở mốc 2 từ tệp gốc).
- [X] T007 [P] [US1] Tạo `backend/data/sources/courses.csv` đủ 24 dòng từ bảng điểm PDF 07/11/2026 theo `specs/007-unify-data-facts/contracts/courses-csv.md`: mã môn theo PDF (ví dụ `CSC10014` Tư duy tính toán, `CSC10012` Cơ sở lập trình); cột `counts_major` = `no` cho Kỹ năng mềm, Pháp luật đại cương, Kinh tế đại cương, còn lại `yes` (Triết học và Kinh tế chính trị Mác - Lênin vẫn tính); `score10`/`score4`/`letter` đúng từng hàng PDF; `aliases` theo mẫu contract.
- [X] T008 [P] [US1] Tạo `backend/data/sources/aliases.txt` theo contract: `vtp1 | vi tích phân 1`, `vtp2 | vi tích phân 2`, `ctdl, dsa | cấu trúc dữ liệu và giải thuật`, `oop, pplt hđt | phương pháp lập trình hướng đối tượng`, `knm, kĩ năng mềm | kỹ năng mềm`, `dstt | đại số tuyến tính`, `trr | toán rời rạc`, `mmt | mạng máy tính`, `xstk | xác suất thống kê`, `hđh | hệ điều hành`, `csdl | cơ sở dữ liệu`, `csai | cơ sở trí tuệ nhân tạo`, `ktct | kinh tế chính trị mác - lênin`.
- [X] T009 [US1] Sửa `backend/data/data.txt`: xoá các mục "Tổng quan học tập", "Các môn nổi bật", "Điểm cần cải thiện" (nay do `courses.csv` sinh); giữ mục tiêu dài hạn, IELTS, tốt nghiệp (8/2028), định hướng nghề nghiệp, phong cách học; sửa "Ngành đào tạo" thành hai ngành "Khoa học Máy tính" + "Khoa học Dữ liệu" và giữ "Chuyên ngành dự kiến" tách riêng.
- [X] T010 [US1] Sửa `backend/data/CV_Data_Science_Vietnamese.docx`: họ tên "Văn Phú Đức" (xóa placeholder `[HỌ VÀ TÊN]`); GPA `3.63/4.0`; ngành "Khoa học Máy tính và Khoa học Dữ liệu"; "Dự kiến tốt nghiệp: tháng 8/2028"; bỏ mọi chuỗi `[...]` còn lại (điện thoại/email/GitHub để trống hoặc xóa dòng — không giữ placeholder).
- [X] T011 [US1] Cách ly `backend/data/data.xlsx` (tên "Kim Oanh", mã môn cũ `CSC10144`/`CSC10112`): chuyển vào `backend/data/archive/data.xlsx`; đảm bảo không còn nằm trong thư mục được nạp.
- [X] T012 [US1] Chạy `python backend/scripts/manage_docs.py validate` và sửa đến khi hết lỗi; chạy kiểm tra N1: `grep -rEn "8\.30|8\.3 |62 tín chỉ|62 TC|17 môn|3\.7/4\.0" backend/data/chatbot.txt` = 0 kết quả; chạy `ask` các câu mẫu ("gpa bao nhiêu", "điểm oop", "mục tiêu", "xin chào") và đối chiếu kỳ vọng ở quickstart mục B.

**Checkpoint**: Dữ liệu mốc 1 thống nhất — chatbot trả đúng mọi số mà không cần code mới (chạy được trước/song song với Phase 3+).

---

## Phase 3: Foundational (Engine — chặn mọi user story còn lại)

**Purpose**: Parser hỗ trợ fact/placeholder/status, vệ sinh rác loader, validate mở rộng, ghi nguyên tử, reload đa nguồn. Không có US2–US5 nếu thiếu phase này.

**⚠️ CRITICAL**: US2–US5 đều phụ thuộc Phase 3 (US1 thì không).

- [X] T013 Sửa `backend/source_format.py`: parser chấp nhận `kind: fact` với các trường `label` (bắt buộc, ≤ 120 ký tự), `value` (bắt buộc, không rỗng, ≤ 4000 ký tự), `snapshot` (tuỳ chọn, `YYYY-MM-DD`), `source` (tuỳ chọn, ≤ 300 ký tự); thêm trường `status: active|archived` (mặc định `active`) cho mọi kind — theo `specs/007-unify-data-facts/contracts/chatbot-source-v2.md`.
- [X] T014 Sửa `backend/source_format.py`: placeholder `{{id}}` trong khối `answer`/`bullets`/`content` — resolve sang fact `active`; tham chiếu không tồn tại → issue `E_PLACEHOLDER_UNKNOWN` (severity `error`, kèm số dòng và id record); chuỗi `\{{...}}` hiểu theo nghĩa đen (quy tắc `\` như feature 005).
- [X] T015 Sửa `backend/source_format.py`: bổ sung mã lỗi `E_CONFLICT` (trùng id khác value), `E_MISSING_FIELD` (fact thiếu label/value), `E_FIELD_NOT_ALLOWED` (fact có questions/answer/bullets/content), `E_BAD_ENUM` (status khác active/archived), `E_STALE_VALUE` (giá trị cũ) — theo bảng mã lỗi trong contracts.
- [X] T016 [P] Tạo `backend/tests/test_facts.py`: parse fact hợp lệ; lỗi thiếu trường; resolve placeholder; `{{khong-ton-tai}}` → `E_PLACEHOLDER_UNKNOWN` kèm số dòng; record `archived` bị loại khỏi KB/fuzzy/RAG/gợi ý; thoát `\{{...}}`.
- [X] T017 [P] Mở rộng `backend/tests/test_source_format.py`: kind fact + trường status + placeholder (validate tệp chứa fact không lỗi, tệp lỗi bị từ chối toàn bộ).
- [X] T018 Sửa `backend/chatbox.py` (và `backend/documents.py` nếu cần): nạp facts từ `chatbot.txt` vào bộ nhớ khi khởi động/reload; lọc record `archived` khỏi KB engine, khớp mờ, RAG và menu chủ đề (`suggestions.py build_topics`); mở rộng signature reload (mtime/kích thước/hash) cho cả `courses.csv`, `aliases.txt`, `inbox/`.
- [X] T019 Sửa `backend/doc_loaders.py`: vệ sinh trước chunk — bỏ dòng/cột `nan` và `Unnamed*` (xlsx), bỏ chuỗi `about:blank X/Y` ở đuôi trang PDF, bỏ header/footer lặp, đánh số trang từ 1 (hiện pypdf trả index 0), làm tròn số thực về tối đa 4 chữ số thập phân (9.300000000000001 → 9.3).
- [X] T020 [P] Mở rộng `backend/tests/test_doc_loaders.py`: các ca `nan`/`Unnamed`/`about:blank`/số nhiễu/trang bắt đầu từ 1; sau vệ sinh không còn chuỗi rác trong chunk.
- [X] T021 Sửa `backend/scripts/manage_docs.py` subcommand `validate`: kiểm tra thêm fact hợp lệ, placeholder tồn tại, `status` hợp lệ, trùng id mọi kind, `courses.csv` (header/khoảng giá trị/trùng code-name), `aliases.txt` (cú pháp/trùng) — theo `contracts/manage-docs-cli.md`; `--json` in danh sách issue `{severity, code, line/record_id/file, message}`; exit ≠ 0 khi có error.
- [X] T022 Sửa `backend/scripts/manage_docs.py`: helper ghi nguyên tử — đọc toàn bộ → áp thay đổi trên bản sao → validate đầy đủ → ghi tệp tạm cùng thư mục → `os.replace()`; bất kỳ bước lỗi → dừng, không ghi, in lỗi kèm vị trí ra stderr, exit code ≠ 0.

**Checkpoint**: Nền engine sẵn sàng — US2–US5 có thể bắt đầu (song song nếu đủ người).

---

## Phase 4: User Story 2 - Thêm môn / sửa giá trị không cần code (Priority: P1) 🎯

**Goal**: Chủ chatbot thêm 1 dòng `courses.csv` hoặc sửa 1 fact → ngay request kế tiếp chatbot trả lời được và số tổng hợp tự đổi; không sửa code.

**Independent Test**: `add course` môn giả → `ask "điểm môn học thử nghiệm"` đúng; `ask "tổng tín chỉ bao nhiêu"` tăng đúng; `add fact` đổi giá trị → mọi câu dùng `{{id}}` đổi theo (quickstart mục C).

### Implementation for User Story 2

- [X] T023 [P] [US2] Tạo `backend/courses.py`: đọc `CHATBOT_COURSES_PATH` theo `contracts/courses-csv.md` — header đúng 8 cột `code,name,credits,score10,score4,letter,counts_major,aliases`; validate: `code`/`name` bắt buộc và duy nhất (trùng → `E_CONFLICT`), `credits` nguyên 1–20, `score10` 0–10 tối đa 4 chữ số thập phân, `score4` 0–4 (trống thì tính từ score10), `letter` ∈ {A+, A, B+, B, C+, C, D+, D, F}, `counts_major` ∈ {yes, no}; dataclass `Course`.
- [X] T024 [P] [US2] Tạo `backend/aliases.py`: đọc `CHATBOT_ALIASES_PATH` (dòng `bí-danh[, bí-danh…] | tên-chuẩn`) gộp với cột `aliases` từ `courses.py`; hàm áp dụng bí danh trong chuẩn hoá câu hỏi (mở rộng `backend/text_normalization.py` `normalize_query`): thay bí danh → tên chuẩn trước khi khớp; bí danh trùng nhau hoặc trùng code/name → lỗi khi validate.
- [X] T025 [P] [US2] Tạo `backend/tests/test_courses.py`: parse 24 dòng mẫu; trùng code/name → `E_CONFLICT`; giá trị ngoài khoảng → `E_BAD_VALUE`; thiếu cột/header sai → `E_BAD_CSV`; sinh QA đúng định dạng.
- [X] T026 [P] [US2] Tạo `backend/tests/test_aliases.py`: `vtp2`→vi tích phân 2, `oop`→phương pháp lập trình hướng đối tượng, `ctdl`→cấu trúc dữ liệu và giải thuật, `xstk`→xác suất thống kê; bí danh trùng → lỗi.
- [X] T027 [US2] Trong `backend/courses.py`: tính số tổng hợp — `credits-total`=Σcredits, `courses-count`=số dòng, `gpa-10`=Σ(score10×credits)/Σcredits, `gpa-4`=Σ(score4×credits)/Σcredits, `gpa-major` chỉ dòng `counts_major=yes`, `top-subjects`/`bottom-subject`; đối chiếu với fact tương ứng và dòng tổng kết PDF (dung sai 0.001), lệch → `W_CONFLICT` (warning, in hai giá trị) — theo `data-model.md` mục 2.
- [X] T028 [US2] Trong `backend/courses.py`: sinh 3 mục hỏi-đáp cho mỗi dòng — "điểm `<name>`" → "Điểm `<name>` là `<score10>` (`<letter>`, `<credits>` tín chỉ)."; "`<name>` mấy tín chỉ" → "`<name>` có `<credits>` tín chỉ."; "`<name>` xét chuyên ngành không" → "Có/Không, môn `<name>` được/không được tính khi xét chuyên ngành."
- [X] T029 [US2] Tích hợp vào `backend/chatbox.py`: nạp QA sinh từ `courses.csv` + bí danh vào KB engine và khớp mờ (sau `normalize_query`); xác nhận `build_topics` (`backend/suggestions.py`) tự có chủ đề mới mà không hard-code.
- [X] T030 [US2] Thêm subcommand `add course` vào `backend/scripts/manage_docs.py` (hợp đồng `contracts/manage-docs-cli.md`): `--code --name --credits --score10 [--score4 --letter --counts-major --aliases]`; ghi thêm dòng vào `courses.csv` (qua helper T022), không sửa `chatbot.txt`; trùng code/name → `E_CONFLICT` kèm dòng hiện có; sau ghi tính lại tổng, lệch PDF → in `W_CONFLICT`.
- [X] T031 [US2] Thêm subcommand `add fact` vào `backend/scripts/manage_docs.py`: `--id --label --value [--snapshot --source]`; id đã tồn tại là fact → cập nhật `value`; id đang là record qa/doc → `E_CONFLICT`; sau ghi validate lại toàn tệp (placeholder của nó phải còn hợp lệ).
- [X] T032 [P] [US2] Mở rộng `backend/tests/test_source_cli.py`: `add course` môn mới → hỏi điểm trả đúng, GPA/tổng TC đổi đúng phép tính; `add fact` cập nhật `gpa-10` → câu trả lời chứa `{{gpa-10}}` đổi theo; trùng code → lệnh dừng không ghi.

**Checkpoint**: US1 + US2 hoàn chỉnh — MVP trọn vẹn (dữ liệu đúng + mở rộng được không cần code).

---

## Phase 5: User Story 3 - Thêm chủ đề mới và nạp tệp inbox (Priority: P2)

**Goal**: Thêm record qa chủ đề mới → menu chủ đề tự có; thả tệp vào `inbox/` rồi `ingest` → hỏi-đáp từ nội dung tệp kèm nguồn.

**Independent Test**: `add qa` chủ đề "Sở thích" → menu có chủ đề đó; `ask "mục tiêu"` → ≥ 2 gợi ý + nút "Câu hỏi khác"; `ingest inbox/` tệp sạch → hỏi ra đúng nguồn; tệp không đổi → bỏ qua (quickstart mục B, C).

### Implementation for User Story 3

- [X] T033 [US3] Thêm subcommand `add qa` vào `backend/scripts/manage_docs.py`: `--topic --q [--q …] --a [--bullets …]`; tự sinh `id` slug từ topic (thêm hậu tố số nếu trùng); `--q` 1–5 câu mỗi câu ≤ 200 ký tự; `--a` (nhiều dòng gộp thành khối answer) hoặc `--bullets` (không dùng đồng thời); mặc định `status: active`; ghi qua helper T022.
- [X] T034 [US3] Mở rộng subcommand `ingest` trong `backend/scripts/manage_docs.py`: nạp từ `CHATBOT_INBOX_DIR` (cả thư mục hoặc một tệp PDF/DOCX/XLSX/CSV/TXT); vệ sinh theo T019; tệp còn `[...]` → `E_PLACEHOLDER`, còn `nan`/`Unnamed`/`about:blank` → `E_NOISE` (từ chối tệp đó, tiếp tục tệp khác); SHA-256 — tệp không đổi bỏ qua, đổi thì nạp lại phần thay đổi; ghi chỉ mục RAG, KHÔNG ghi `chatbot.txt`; tổng kết từng tệp: đã nạp / bỏ qua / lỗi (kèm mã).
- [X] T035 [P] [US3] Mở rộng `backend/tests/test_source_cli.py`: `add qa` chủ đề mới → `build_topics`/menu chủ đề có chủ đề đó; `ingest` tệp sạch → hỏi ra đúng nội dung + nguồn; tệp có `[...]` → `E_PLACEHOLDER` và chỉ mục không đổi; tệp không đổi khi nạp lại → bỏ qua.
- [X] T036 [P] [US3] Mở rộng `backend/tests/test_suggestions.py` (hoặc `test_assistant.py`): câu "mục tiêu" → `type: suggest` với ≥ 2 gợi ý (học bổng TUHH, IELTS, nghề nghiệp) và luôn có nút "Câu hỏi khác".

**Checkpoint**: US1–US3 hoạt động độc lập; chủ đề và tài liệu mở rộng được.

---

## Phase 6: User Story 4 - Dữ liệu sai thì hệ thống từ chối (Priority: P2)

**Goal**: Mọi đường thêm/nạp sai (mâu thuẫn, placeholder không tồn tại, tệp rác) bị từ chối kèm vị trí lỗi; chatbot giữ nguyên dữ liệu cũ đang chạy.

**Independent Test**: quickstart mục D — `{{khong-ton-tai}}` → `E_PLACEHOLDER_UNKNOWN` kèm dòng; fact trùng id khác value → dừng không ghi; inbox `[...]` → từ chối; tệp nguồn sửa sai → request kế tiếp vẫn dùng dữ liệu cũ.

### Implementation for User Story 4

- [X] T037 [US4] Mở rộng `validate` trong `backend/scripts/manage_docs.py`: quét `E_STALE_VALUE` — mọi nội dung sẽ phục vụ trả lời (chatbot.txt + courses.csv + chunk inbox) không được chứa `8.30`, `8.3 `, `62 tín chỉ`, `62 TC`, `17 môn`, `3.7/4.0`; đối chiếu số tổng hợp ↔ fact ↔ dòng tổng kết PDF (W_CONFLICT, dung sai 0.001).
- [X] T038 [P] [US4] Mở rộng `backend/tests/test_source_cli.py` các ca từ chối: `add fact` trùng id khác value → dừng, không ghi, exit ≠ 0; record chứa `{{khong-ton-tai}}` → validate báo `E_PLACEHOLDER_UNKNOWN` kèm số dòng; `ingest` tệp có `[...]` → `E_PLACEHOLDER`, có `nan` → `E_NOISE`; `validate --json` trả đúng cấu trúc issue.
- [X] T039 [P] [US4] Mở rộng `backend/tests/test_source_reload.py`: sửa `chatbot.txt` thành sai cú pháp → request kế tiếp vẫn trả lời bằng index cũ; sửa lại đúng → request kế tiếp dùng nội dung mới (không cần khởi động lại).
- [X] T040 [US4] Rà toàn bộ lệnh ghi (`add fact|qa|course`, `ingest`): xác nhận tất cả đi qua helper ghi nguyên tử T022 và trả exit code ≠ 0 khi lỗi; sửa bất kỳ đường ghi nào còn bỏ qua validate.

**Checkpoint**: Mọi đường thêm mới an toàn — không thể làm hỏng trạng thái đang chạy.

---

## Phase 7: User Story 5 - Giọng văn và định dạng đồng nhất (Priority: P3)

**Goal**: Mọi câu trả lời ngôi thứ nhất "mình" (0 chữ "tôi"); điểm môn 1 chữ số thập phân; GPA 2 chữ số kèm ≈; câu trả lời điểm đầy đủ ngữ cảnh; record viết tay trùng/thừa được di trú sang nguồn tự sinh + fact.

**Independent Test**: quickstart mục B (N9) — `ask "xin chào"` đúng mẫu; quét mọi câu trả lời không có "tôi"; `ask "điểm vi tích phân 2"` → "10.0 (A+, 4 tín chỉ)"; `ask "gpa bao nhiêu"` → "8.51 / 10 (≈ 8.5)".

### Implementation for User Story 5

- [X] T041 [US5] Di trú `backend/data/chatbot.txt`: xoá toàn bộ record `diem-*` và `*-xet-chuyen-nganh` viết tay (nay do `courses.csv` sinh); xoá record trùng ý `vi-tich-phan-1` (giữ bí danh `vtp1`), `ki-nang-mem`/`vat-li` (bí danh thay thế); thêm record `kind: fact` cho `gpa-10`, `gpa-4`, `credits`, `courses-count`, `ranking`, `gpa-major`, `majors`, `graduation`, `ielts` theo `data-model.md` mục 1.
- [X] T042 [US5] Chuyển câu trả lời lặp giá trị sang placeholder: `gpa`, `gpa-bao-nhieu`, `diem-trung-binh-hien-tai`, `tong-tin-chi-bao-nhieu`, `hoc-bao-nhieu-mon`, `tot-nghiep` dùng `{{gpa-10}}`, `{{gpa-4}}`, `{{credits}}`, `{{courses-count}}`, `{{graduation}}`… trong `backend/data/chatbot.txt`; chạy `validate` xác nhận không `E_PLACEHOLDER_UNKNOWN`.
- [X] T043 [US5] Chuẩn định dạng điểm ở nguồn sinh (T028) và các câu viết tay còn lại: điểm môn đúng 1 chữ số thập phân (`10.0`, `5.4`), GPA đúng 2 chữ số kèm `(≈ 8.5)`; câu trả lời điểm luôn có dạng "Điểm `<name>` là `<score10>` (`<letter>`, `<credits>` tín chỉ)."
- [X] T044 [US5] Mở rộng `backend/tests/test_answers.py`: quét toàn bộ câu trả lời phục vụ được — 0 câu chứa "tôi", câu hồ sơ dùng "mình"; `greeting` = "Xin chào! Mình là Đức (bản chatbot). Bạn muốn biết gì về mình nào?"; GDQP (archived) không xuất hiện trong gợi ý/menu; định dạng điểm chuẩn cho mọi môn.

**Checkpoint**: US1–US5 hoàn chỉnh — đạt toàn bộ tiêu chí N1–N9.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Tài liệu, nghiệm thu cuối, dọn dẹp.

- [X] T045 [P] Cập nhật `README.md`: mô tả dữ liệu mở/động — fact + placeholder, `courses.csv`, `aliases.txt`, `inbox/`, các lệnh `add fact|qa|course`, `ingest inbox/`, `validate` và bảng mã lỗi mới.
- [X] T046 [P] Cập nhật `PLAN_MASTER.md` (nếu tệp tồn tại ở nơi chủ quản lý — không nằm trong repo này): mục 3 (nguồn `chatbot.txt` thêm fact/placeholder/status, courses, aliases), mục 5.2 (loader: thêm `inbox/`, `sources/`; chunk từ tệp gốc, không ghi đè chatbot.txt), mục 6 (xoá record nhập tay số điểm, sinh từ courses.csv).
- [X] T047 Chạy toàn bộ `specs/007-unify-data-facts/quickstart.md` từ mục A đến E (N1–N9) và sửa mọi kỳ vọng sai cho đến khi pass hết.
- [X] T048 Chạy `cd backend && python -m pytest tests/ -q` — toàn bộ xanh; sửa các test cũ (golden set, mẫu dữ liệu trong `test_source_mapping.py`, `test_doc_cli.py`…) bị ảnh hưởng bởi dữ liệu mới.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Không phụ thuộc — bắt đầu ngay.
- **US1 (Phase 2)**: Chỉ cần Phase 1 — thuần dữ liệu, KHÔNG phụ thuộc Phase 3; chạy song song được với Phase 3.
- **Foundational (Phase 3)**: Cần Phase 1 — CHẶN US2–US5 (US1 không bị chặn).
- **US2 (Phase 4)**: Cần Phase 3 (parser fact + helper ghi) + dữ liệu Phase 2 (courses.csv, aliases.txt để test thật).
- **US3 (Phase 5)**: Cần Phase 3 (loader vệ sinh, ghi nguyên tử) + subcommand nền từ Phase 4 (dùng chung helper).
- **US4 (Phase 6)**: Cần Phase 4 + Phase 5 (mọi lệnh ghi đã tồn tại để áp gating) — chạy cuối trong nhóm engine.
- **US5 (Phase 7)**: Cần Phase 4 (courses sinh QA) + Phase 3 (fact/placeholder); thuần dữ liệu là chính, song song được với Phase 6.
- **Polish (Phase 8)**: Cần mọi phase trước.

### User Story Dependencies

- **US1 (P1)**: Độc lập hoàn toàn với engine — làm được ngay sau Setup.
- **US2 (P1)**: Độc lập với US3–US5; phụ thuộc Foundational.
- **US3 (P2)**: Độc lập với US4/US5; phụ thuộc Foundational (+ helper từ US2).
- **US4 (P2)**: Phụ thuộc US2 + US3 (gia cố các lệnh đã có).
- **US5 (P3)**: Độc lập với US3/US4; phụ thuộc US2 (dữ liệu tự sinh).

### Within Each User Story

- Test trước khi triển khai (viết test → chạy thất bại → cài đặt → xanh).
- Model (courses/aliases) trước service; service trước CLI; CLI trước test end-to-end.
- Hoàn thành story trước khi chuyển sang story ưu tiên kế tiếp.

### Parallel Opportunities

- Phase 1: T002, T003 song song.
- Phase 2: T007, T008 song song (khác tệp); các task sửa tệp khác nhau cũng song song được.
- Phase 3: T016, T017, T020 song song (3 tệp test khác nhau).
- Phase 4: T023, T024, T025, T026, T032 song song theo nhóm (tệp khác nhau).
- Phase 6: T038, T039 song song.
- Phase 8: T045, T046 song song.
- **Cross-phase**: Phase 2 (US1) và Phase 3 (Foundational) chạy song song hoàn toàn vì không đụng tệp nguồn của nhau (dữ liệu vs code).

---

## Parallel Example: Phase 2 (US1) + Phase 3 (Foundational)

```bash
# Người A — dữ liệu mốc 1 (không cần code):
Task: "T004 Thay nội dung backend/data/chatbot.txt bằng bản đã duyệt"
Task: "T007 Tạo backend/data/sources/courses.csv (24 dòng từ PDF)"

# Người B — engine (song song):
Task: "T013 Parser kind: fact + status trong backend/source_format.py"
Task: "T019 Vệ sinh rác trong backend/doc_loaders.py"
```

---

## Parallel Example: Phase 4 (US2)

```bash
# Cùng lúc:
Task: "T023 backend/courses.py — đọc/validate courses.csv"
Task: "T024 backend/aliases.py — bí danh"
Task: "T025 backend/tests/test_courses.py (test trước)"
Task: "T026 backend/tests/test_aliases.py (test trước)"
# Sau đó tuần tự: T027 → T028 → T029 → T030 → T031 → T032
```

---

## Implementation Strategy

### MVP First (US1 — chỉ dữ liệu)

1. Hoàn thành Phase 1 (Setup) + Phase 2 (US1).
2. **DỪNG và KIỂM TRA**: `validate` sạch, `ask` các câu mẫu đúng số mới, grep N1 = 0.
3. Deploy/demo ngay — chatbot trả đúng mọi số liệu mới mà không cần một dòng code.

### MVP đầy đủ (US1 + US2)

1. Thêm Phase 3 (Foundational) → Phase 4 (US2).
2. Kiểm tra: thêm môn giả → GPA/tổng TC tự đổi; sửa fact → mọi câu `{{id}}` đổi theo.
3. Đây là mốc mang toàn bộ giá trị "dữ liệu mở/động" của feature.

### Incremental Delivery

1. US1 → demo (dữ liệu đúng ngay).
2. US2 → demo (thêm môn không code).
3. US3 → demo (chủ đề mới + nạp inbox).
4. US4 → gia cố (không thể làm hỏng dữ liệu).
5. US5 → hoàn thiện (giọng văn, định dạng, di trú sạch).
6. Polish → nghiệm thu N1–N9 + toàn bộ test xanh.

### Parallel Team Strategy

- Người A: US1 (dữ liệu) song song với người B: Foundational (code).
- Sau Foundational: B làm US2, C làm US3 (song song); sau đó B/C cùng làm US4; US5 có thể giao cho A khi xong US1.

---

## Notes

- [P] = khác tệp, không phụ thuộc task chưa xong.
- [Story] gắn task vào user story để truy vết.
- Mốc 1 (US1) là dữ liệu thuần — chạy `validate` sau mỗi lần sửa tệp.
- Commit sau mỗi task hoặc nhóm task logic; KHÔNG commit `data.xlsx` (cách ly trong archive/).
- Chạy `python backend/scripts/manage_docs.py validate` trước mỗi lần chạy thử `ask`.
