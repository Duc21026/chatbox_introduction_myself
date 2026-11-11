# Tasks: Unified Text Knowledge Source

**Input**: Design documents from `specs/005-unified-text-source/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: Có bao gồm task kiểm thử vì `plan.md` và `quickstart.md` yêu cầu kiểm chứng parser, CLI, API regression và Docker smoke. Không bắt buộc TDD cho toàn bộ feature.

**Organization**: Task được nhóm theo user story để mỗi story có thể triển khai và kiểm thử độc lập.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Có thể chạy song song (khác file, không phụ thuộc task chưa xong)
- **[Story]**: User story tương ứng (`US1`–`US4`)
- Mọi task đều có đường dẫn file cụ thể

## Path Conventions

- Backend: `backend/`
- Test: `backend/tests/`
- Script vận hành: `backend/scripts/`
- Tài liệu feature: `specs/005-unified-text-source/`
- Docker: `docker-compose.yml`, `backend/Dockerfile`

## User Stories

- **US1 (P1) — MVP**: Một tệp `chatbot.txt` cung cấp dữ liệu cho KB Engine, khớp mờ và RAG; `/chat` trả lời như hiện tại.
- **US2 (P2)**: Người vận hành validate tệp, nhận lỗi kèm số dòng, không nạp một phần.
- **US3 (P3)**: Migrate `kb.json`, `qa.txt`, `backend/data/` sang tệp hợp nhất mà không sửa nguồn gốc.
- **US4 (P4)**: Tự làm mới chỉ mục khi tệp đổi, rollback legacy, Docker chỉ mount một tệp.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Tạo khung module, hằng số và cấu hình chung.

- [X] T001 Tạo `backend/source_format.py` với docstring, import chuẩn và các dataclass `SourceFile`, `SourceRecord`, `QAPair`, `KBItem`, `RAGDocument`, `SourceSignature`, `ValidationIssue`, `DerivedSource` đúng field trong `data-model.md`.
- [X] T002 [P] Thêm `NORMALIZER_VERSION = "1"` và xuất hằng này trong `backend/text_normalization.py`.
- [X] T003 [P] Thêm đọc `CHATBOT_SOURCE_PATH` (mặc định `backend/data/chatbot.txt`) và `CHATBOT_LEGACY_SOURCES` (mặc định `false`) vào `load_config()` trong `backend/chatbox.py`.
- [X] T004 [P] Thêm `CHATBOT_SOURCE_PATH=backend/data/chatbot.txt` và `CHATBOT_LEGACY_SOURCES=false` vào ENV mặc định trong `backend/Dockerfile`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Parser, validator và mapping dùng chung cho mọi user story.

**⚠️ CRITICAL**: Không bắt đầu user story nào trước khi phase này xong.

- [X] T005 Implement kiểm tra encoding/header/size trong `backend/source_format.py`: UTF-8 không BOM, Unicode NFC, LF, header `CHATBOT-SOURCE v1`, kích thước `≤ 20 MB`; trả `E_ENCODING`, `E_BOM`, `E_SIZE`, `E_HEADER`.
- [X] T006 Implement quét record và field trong `backend/source_format.py`: nhận diện `=== RECORD ===`/`=== END ===`, thứ tự `kind, id, topic, questions, answer, bullets, content, source`, escaping `\` ở cột 0, báo `E_RECORD_EOF` và `E_FIELD_ORDER`.
- [X] T007 Implement validation record trong `backend/source_format.py`: `kind` chỉ `qa|doc`; `id` khớp `^[a-z0-9][a-z0-9_-]{0,63}$` và duy nhất; `topic` 1–120 ký tự; `qa` có ≥ 1 câu, mỗi câu 1–200 ký tự và không trùng; `answer` ≤ 4.000 ký tự; mỗi bullet ≤ 300 ký tự; `qa` phải có `answer` hoặc `bullets`; `doc` phải có `content` không rỗng; `source` ≤ 300 ký tự. Trả các mã `E_KIND`, `E_ID_FORMAT`, `E_DUP_ID`, `E_TOPIC`, `E_QUESTIONS`, `E_QUESTION_ITEM`, `E_ANSWER`, `E_CONTENT`, `W_UNKNOWN_FIELD`.
- [X] T008 Implement ánh xạ `SourceRecord` → `DerivedSource` trong `backend/source_format.py`: `qa` sinh `QAPair`, `KBItem`, `RAGDocument`; `doc` chỉ sinh `RAGDocument`; RAG text của `qa` lấy `content` nếu có, ngược lại từ `topic + questions + answer/bullets`; parse `#page=N` trong `source` thành metadata `page`.
- [X] T009 Implement `load_source(path)` và `validate_source(path)` trong `backend/source_format.py`: parse toàn bộ, validate toàn bộ, không gọi Ollama, không nạp một phần khi có error.
- [X] T010 Implement `SourceSignature` trong `backend/source_format.py`: gồm `mtime_ns`, `size_bytes`, SHA-256 nội dung, `embedding_model`, `chunk_size`, `chunk_overlap`, `NORMALIZER_VERSION`; cung cấp hàm so sánh signature.
- [X] T011 [P] Viết test parser/validator trong `backend/tests/test_source_format.py`: header sai, BOM, quá 20 MB (dùng file giả lập kích thước), record thiếu `END`, `id` sai/trùng, `kind` sai, thiếu `answer`/`content`, câu hỏi quá dài, escaping `\=== END ===`.
- [X] T012 [P] Viết test mapping trong `backend/tests/test_source_mapping.py`: `qa` vào KB+QA+RAG, `doc` chỉ RAG, `content` fallback, metadata `source`, `record_id`, `kind`, `topic`, `page`.

**Checkpoint**: Parser/validator/mapping hoạt động độc lập, test chạy không cần Ollama.

---

## Phase 3: User Story 1 — Một nguồn dữ liệu cho chatbot (Priority: P1) 🎯 MVP

**Goal**: `/chat` và `/chat/stream` trả lời từ `chatbot.txt`; KB Engine, khớp mờ và RAG dùng chung nguồn.

**Independent Test**: Chỉ tạo tệp `chatbot.txt` tạm có một `qa` và một `doc`, gọi `POST /chat` cho câu hỏi KB và câu hỏi chỉ có trong `doc`; cả hai trả lời đúng, không cần `qa.txt`/`kb.json`.

### Tests for User Story 1

- [X] T013 [P] [US1] Viết API regression test trong `backend/tests/test_source_api.py`: tạo `chatbot.txt` tạm với `qa` + `doc`, set `CHATBOT_SOURCE_PATH`, gọi `/chat` với câu hỏi KB và câu hỏi RAG, assert `type == "answer"` và nội dung đúng; gọi `/chat` khi chỉ có nguồn hợp nhất.

### Implementation for User Story 1

- [X] T014 [US1] Thêm loader cache `get_source()` trong `backend/chatbox.py`: dùng `source_format.load_source`, cache theo `SourceSignature`, trả `DerivedSource`.
- [X] T015 [US1] Thay `_load_documents()`, `_load_qa_data()`, `_source_signature()` trong `backend/chatbox.py` để lấy `rag_documents`, `qa_pairs`, `signature` từ `get_source()`; giữ nguyên chunking 500/50 và `FAISS.from_documents`.
- [X] T016 [US1] Cập nhật `backend/kb_engine.py`: `warm_up_kb()` nhận `DerivedSource.kb_items`, `_kb_hash()` dùng `DerivedSource.kb_hash`, giữ nguyên threshold 0.78/0.55 và hybrid score 0.8*cosine + 0.2*WRatio.
- [X] T017 [US1] Cập nhật `backend/app.py` để warm-up KB và RAG từ nguồn hợp nhất; đảm bảo lỗi nguồn không làm API trả lời bằng index rỗng.
- [X] T018 [US1] Cập nhật `app.py` (root shim) gọi thêm `backend.kb_engine.warm_up_kb()` trước `warm_up()` để Docker dùng KB Engine.
- [X] T019 [US1] Chạy regression `pytest backend/tests/test_chat_api.py backend/tests/test_chat_stream_api.py backend/tests/test_retrieval.py backend/tests/test_retrieval_normalization.py` và sửa tương thích trong `backend/chatbox.py`.

**Checkpoint**: US1 là MVP: một tệp duy nhất phục vụ toàn bộ pipeline trả lời.

---

## Phase 4: User Story 2 — Validate và báo lỗi theo số dòng (Priority: P2)

**Goal**: Người vận hành kiểm tra tệp trước khi chạy, nhận lỗi rõ ràng và an toàn.

**Independent Test**: Chạy `validate` trên tệp mẫu → exit 0; trên tệp thiếu `answer` → exit 2, JSON có `E_ANSWER` và `line` đúng; server không nạp tệp sai.

### Tests for User Story 2

- [X] T020 [P] [US2] Viết CLI test trong `backend/tests/test_source_cli.py`: `validate` tệp hợp lệ exit 0, tệp lỗi exit 2, `--json` có `valid`, `counts`, `errors`, `warnings`, số dòng chính xác.

### Implementation for User Story 2

- [X] T021 [US2] Thêm subcommand `validate` vào `backend/scripts/manage_docs.py` với `--source`, `--json`; mặc định đọc `CHATBOT_SOURCE_PATH`.
- [X] T022 [US2] In kết quả `validate` dạng người đọc và JSON đúng schema `contracts/manage-docs-cli.md`; exit code 0/2/1.
- [X] T023 [US2] Thêm fail-fast khi khởi động trong `backend/chatbox.py` và `backend/app.py`: lỗi tệp nêu số dòng, `record_id`, mã lỗi tiếng Việt; không tạo index một phần.
- [X] T024 [US2] Khi tệp đổi lúc đang chạy mà không hợp lệ, giữ index cũ và log lỗi trong `backend/chatbox.py`; không thay thế `DerivedSource` hiện tại.

**Checkpoint**: US2 độc lập: validate và fail-fast không phụ thuộc Ollama.

---

## Phase 5: User Story 3 — Migrate dữ liệu cũ (Priority: P3)

**Goal**: Sinh `chatbot.txt` từ ba nguồn hiện tại mà không sửa dữ liệu gốc.

**Independent Test**: Chạy `migrate --to /tmp/chatbot.txt` trên bản sao repo; số record `qa`/`doc` khớp nguồn; `diff` nguồn gốc không đổi; `validate` tệp đích exit 0.

### Tests for User Story 3

- [X] T025 [P] [US3] Viết test migrate trong `backend/tests/test_source_cli.py`: KB + `qa.txt` (có câu trùng) + `backend/data/` mẫu; assert không trùng câu hỏi, thứ tự xác định, `--force` hoạt động.

### Implementation for User Story 3

- [X] T026 [US3] Thêm subcommand `migrate` vào `backend/scripts/manage_docs.py` với `--to`, `--from-data`, `--qa`, `--kb`, `--force`.
- [X] T027 [US3] Implement chuyển `kb.json` → record `kind: qa` trong `backend/scripts/manage_docs.py`, giữ `id`, `topic`, `questions`, `answer`, `answer_bullets` → `bullets`.
- [X] T028 [US3] Implement chuyển `qa.txt` → record `kind: qa` trong `backend/scripts/manage_docs.py`; bỏ qua câu hỏi đã có trong KB.
- [X] T029 [US3] Implement chuyển tài liệu trong `--from-data` → record `kind: doc` bằng `documents.extract_segments`; `source` là tên tệp, PDF thêm `#page=N` khi tách trang; thứ tự theo tên tệp.
- [X] T030 [US3] Ghi tệp đích nguyên tử trong `backend/scripts/manage_docs.py`: tệp tạm cùng thư mục, `fsync`, `os.replace`; in số lượng `qa`/`doc`.
- [X] T031 [US3] Chạy migrate trên bản sao dữ liệu repo và validate `backend/data/chatbot.txt` theo `specs/005-unified-text-source/quickstart.md` kịch bản 2–3.

**Checkpoint**: US3 tạo được tệp hợp nhất từ dữ liệu thật, nguồn cũ nguyên vẹn.

---

## Phase 6: User Story 4 — Reload, rollback và Docker một tệp (Priority: P4)

**Goal**: Tự làm mới khi tệp đổi, rollback legacy, Docker chỉ cần `chatbot.txt`.

**Independent Test**: Sửa nội dung `chatbot.txt` → request tiếp theo trả lời nội dung mới; bật `CHATBOT_LEGACY_SOURCES=true` → đọc `qa.txt`/`kb.json`; Docker chỉ mount `chatbot.txt` vẫn healthy.

### Tests for User Story 4

- [X] T032 [P] [US4] Viết test reload/cache trong `backend/tests/test_source_reload.py`: signature đổi → reload; tệp mới sai → giữ index cũ; cùng signature → không parse lại.

### Implementation for User Story 4

- [X] T033 [US4] Implement nhánh legacy trong `backend/chatbox.py`: khi `CHATBOT_LEGACY_SOURCES=true`, đọc `qa.txt` và `kb.json` theo code cũ, log cảnh báo deprecated.
- [X] T034 [US4] Cập nhật `docker-compose.yml`: chỉ mount `./backend/data/chatbot.txt:/app/backend/data/chatbot.txt`, bỏ mount `qa.txt`/`kb.json`, đặt `CHATBOT_SOURCE_PATH=backend/data/chatbot.txt`.
- [X] T035 [US4] Cập nhật `backend/Dockerfile` để không phụ thuộc `qa.txt`/`kb.json` khi chạy image.
- [X] T036 [US4] Chạy Docker smoke test theo `specs/005-unified-text-source/quickstart.md` kịch bản 8: `docker compose up -d --build backend frontend`, kiểm tra healthy và `POST /chat` qua nginx.

**Checkpoint**: US4 hoàn tất vận hành một tệp và đường rollback.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Tài liệu, hiệu năng, an toàn dữ liệu và kiểm tra cuối.

- [X] T037 [P] Cập nhật `README.md`: định dạng `chatbot.txt`, `CHATBOT_SOURCE_PATH`, `CHATBOT_LEGACY_SOURCES`, lệnh validate/migrate, Docker mount một tệp.
- [X] T038 [P] Cập nhật `backend/README.md`: mô tả `backend/source_format.py` và luồng parse → validate → mapping.
- [X] T039 [P] Thêm test hiệu năng trong `backend/tests/test_source_perf.py`: parse + validate tệp 1 MB dưới 1 giây.
- [X] T040 [P] Rà soát dữ liệu trong `backend/data/chatbot.txt` không chứa bí mật, khoá API, mật khẩu hoặc PII ngoài phạm vi giới thiệu.
- [ ] T041 Chạy toàn bộ `pytest backend/tests` và xử lý regression trong `backend/`.
- [ ] T042 Chạy toàn bộ checklist `specs/005-unified-text-source/quickstart.md`, ghi kết quả vào PR/ghi chú vận hành.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Không phụ thuộc, bắt đầu ngay.
- **Foundational (Phase 2)**: Phụ thuộc Setup, **chặn toàn bộ user story**.
- **US1 (Phase 3)**: Phụ thuộc Foundational; là MVP.
- **US2 (Phase 4)**: Phụ thuộc Foundational (validator); có thể làm song song US1 nếu đủ người.
- **US3 (Phase 5)**: Phụ thuộc Foundational (models/validator) và `documents.extract_segments`; có thể làm song song US1/US2.
- **US4 (Phase 6)**: Phụ thuộc US1 (loader/cache) và US2 (fail-fast).
- **Polish (Phase 7)**: Phụ thuộc tất cả story mong muốn hoàn tất.

### User Story Dependencies

- **US1 (P1)**: Không phụ thuộc story khác; cần Phase 2.
- **US2 (P2)**: Không phụ thuộc US1; chỉ cần parser/validator.
- **US3 (P3)**: Không phụ thuộc US1; dùng parser để ghi/validate.
- **US4 (P4)**: Phụ thuộc US1 và US2.

### Within Each User Story

- Test (nếu có) viết trước và phải fail trước khi implement.
- Parser/model trước service/loader.
- Loader trước endpoint tích hợp.
- Hoàn tất checkpoint trước khi chuyển story ưu tiên tiếp theo.

### Parallel Opportunities

- Setup: T002, T003, T004 chạy song song sau T001.
- Foundational: T011 và T012 chạy song song sau T005–T010.
- US1: T013 chạy song song với T014–T016 nếu test dùng monkeypatch; T019 chạy sau T014–T018.
- US2: T020 chạy song song với T021; T023–T024 sau T021–T022.
- US3: T025 chạy song song với T026; T027–T030 tuần tự trong cùng file.
- US4: T032 chạy song song với T033; T034–T036 sau T033.
- Polish: T037, T038, T039, T040 chạy song song; T041–T042 sau cùng.

---

## Parallel Example: User Story 1

```bash
# Có thể chạy song song:
Task: "Viết API regression test trong backend/tests/test_source_api.py"
Task: "Thêm loader cache get_source() trong backend/chatbox.py"
Task: "Cập nhật backend/kb_engine.py nhận DerivedSource.kb_items"
```

## Parallel Example: User Story 3

```bash
# Có thể chạy song song:
Task: "Viết test migrate trong backend/tests/test_source_cli.py"
Task: "Thêm subcommand migrate vào backend/scripts/manage_docs.py"
```

---

## Implementation Strategy

### MVP First (US1)

1. Hoàn thành Phase 1 (Setup).
2. Hoàn thành Phase 2 (Foundational) — bắt buộc.
3. Hoàn thành Phase 3 (US1).
4. **STOP và VALIDATE**: chạy `backend/tests/test_source_api.py` và quickstart kịch bản 4.
5. Demo chatbot chỉ với `chatbot.txt`.

### Incremental Delivery

1. Setup + Foundational → parser/validator/mapping sẵn sàng.
2. US1 → một nguồn dữ liệu phục vụ `/chat` (MVP).
3. US2 → công cụ validate an toàn cho người vận hành.
4. US3 → migrate dữ liệu thật, không gián đoạn.
5. US4 → reload/Docker một tệp + rollback.
6. Polish → tài liệu, hiệu năng, kiểm tra cuối.

### Parallel Team Strategy

- Sau Phase 2: Developer A làm US1, Developer B làm US2, Developer C làm US3.
- US4 bắt đầu sau khi US1 và US2 xong.
- Polish chia theo file: README, backend README, perf test, security review.

---

## Notes

- `[P]` = khác file, không phụ thuộc task chưa xong.
- `[Story]` dùng để truy vết về user story.
- Không thêm dependency runtime mới.
- Không đổi response schema của `POST /chat` và `POST /chat/stream`.
- Commit sau mỗi task hoặc nhóm logic.
- Dừng ở checkpoint để validate story độc lập.
