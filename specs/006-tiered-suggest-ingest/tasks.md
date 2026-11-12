# Tasks: Luôn gợi ý & nạp tài liệu đa định dạng

**Input**: Design documents from `specs/006-tiered-suggest-ingest/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: Có bao gồm task kiểm thử vì spec mục 8 (`Kiểm thử`), `plan.md` và `quickstart.md` yêu cầu kiểm chứng thang 3 tầng, session, 4 định dạng tài liệu, incremental ingest và hiệu năng. Không bắt buộc TDD cho toàn bộ feature, nhưng test của mỗi story phải được viết trước phần implementation tương ứng.

**Organization**: Task được nhóm theo user story để mỗi story có thể triển khai, kiểm thử và demo độc lập.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Có thể chạy song song (khác file, không phụ thuộc task chưa xong)
- **[Story]**: User story tương ứng (`US1`–`US4`)
- Mọi task đều có đường dẫn file cụ thể

## Path Conventions

- Backend: `backend/`
- Backend tests: `backend/tests/`
- Script vận hành: `backend/scripts/`
- Frontend: `frontend/src/`
- Tài liệu feature: `specs/006-tiered-suggest-ingest/`
- Docker: `docker-compose.yml`, `backend/.env.example`

## User Stories

- **US1 (P1) — MVP**: Mọi câu hỏi đều nhận `answer`/`suggest`/`clarify`; không còn `unknown` hay "không biết"; mọi nhánh không phải `answer` có ít nhất một nút bấm.
- **US2 (P2)**: "Câu hỏi khác" dẫn theo cấp: menu chủ đề → câu chưa hiển thị → mời mô tả tự do; không lặp trong phiên.
- **US3 (P3)**: Nạp offline PDF/DOCX/XLSX/CSV (thêm TXT/MD); trả lời trích xuất kèm nguồn; nạp lại chỉ xử lý phần đổi.
- **US4 (P4)**: Phản hồi nhanh, không gọi LLM trên đường chính; tóm tắt LLM tuỳ chọn, mặc định tắt.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Chuẩn bị cấu hình, ignore và kiểu dữ liệu dùng chung.

- [ ] T001 [P] Thêm `backend/doc_index/` vào `.gitignore` và bổ sung các biến mới (`CHATBOT_SUGGEST_THRESHOLD`, `CHATBOT_DOC_THRESHOLD`, `CHATBOT_AMBIGUITY_GAP`, `CHATBOT_MAX_SUGGESTIONS`, `CHATBOT_DOC_INDEX_DIR`, `CHATBOT_DOC_MAX_BYTES`, `CHATBOT_SESSION_TTL`, `CHATBOT_SESSION_MAX`, `ENABLE_LLM_SUMMARY`) vào `backend/.env.example`.
- [ ] T002 [P] Thêm `FakeEmbedder` (vector deterministic, có `embed_documents`/`embed_query`) và helper tạo PDF/DOCX/XLSX/CSV tối giản vào `backend/tests/helpers.py`.
- [ ] T003 [P] Tạo `frontend/src/lib/chatTypes.ts` chứa union `ChatResponse` (`answer`/`suggest`/`clarify`), `Suggestion` (`id`, `question`, `score`), `Action` (`id`, `label`, `topic?`), `SourceRef` (`file`, `page?`, `sheet?`, `row_start?`, `row_end?`, `heading?`) đúng `data-model.md` mục 8.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Hạ tầng chung bắt buộc cho mọi story: cấu hình, session, response builder, `kb_engine.evaluate`, helper văn bản và interface injectable.

**⚠️ CRITICAL**: Không bắt đầu user story nào trước khi phase này xong.

- [ ] T004 [P] Thêm hàm đọc env và hằng số vào `backend/assistant.py` (thresholds `0.78`/`0.45`, gap `0.05`, max suggestions `4`) và tạo khung `backend/doc_index.py` với `CHATBOT_DOC_INDEX_DIR` (mặc định `backend/doc_index`), `CHATBOT_DOC_THRESHOLD=0.55`, `CHATBOT_DOC_MAX_BYTES=20971520`; sai giá trị → nêu tên biến và giá trị lỗi.
- [ ] T005 [P] Implement `SessionStore` trong `backend/session.py`: dict theo `session_id`, `shown_ids` (tối đa 200, không trùng), `last_query`, `level` (1–3), `last_topics`, `last_candidates`, TTL `CHATBOT_SESSION_TTL=1800` giây, tối đa `CHATBOT_SESSION_MAX=1000` phiên, `threading.Lock`, hàm `get_or_create`, `reset`, `expire`.
- [ ] T006 Implement response builders trong `backend/assistant.py`: `answer_response`, `suggest_response`, `clarify_response`; mọi response có `type`, `session_id`, `response`; `answer` có `score`, `answer_bullets`, `source`, `sources`; `suggest` có `message`, `suggestions`, `actions`; `clarify` có `message`, `topics`, `examples`, `actions`; không tạo `type="unknown"` và không dùng chuỗi "mình không biết"/"chưa biết".
- [ ] T007 Refactor `backend/kb_engine.py`: thêm `evaluate(message, query_vec=None)` trả `norm`, `word_count`, `query_vec`, `top1`, `top2`, `candidates` **toàn bộ mục đã chấm điểm, sắp xếp giảm dần** (mỗi mục có `item_id`, `topic`, `question`, `score`, `source="kb"`), `answer_item`, `embeddings_ready`; dùng một lần embed; bỏ gọi `_try_rewrite` khỏi `evaluate`; giữ `query()` cũ làm wrapper tương thích và giữ hybrid `0.8*cosine + 0.2*WRatio`.
- [ ] T008 [P] Thêm helper thuần Python vào `backend/text_normalization.py`: `tokenize`, `word_count`, `split_sentences` (tách theo `.!?` và xuống dòng), `token_overlap`; dùng `normalize_query` cho câu hỏi và `normalize_text(lowercase=False)` cho tài liệu.
- [ ] T009 Implement dataclass/protocol injectable trong `backend/assistant.py`: `KbEvaluator` (hàm `evaluate`), `DocSearcher` (hàm `search` + `extractive_answer`), `SessionBackend`; `handle()` nhận các dependency này để test không cần Ollama và để US3 gắn chỉ mục tài liệu sau.

**Checkpoint**: Nền tảng sẵn sàng — có thể bắt đầu US1; US2/US3 có thể chạy song song sau khi US1 xong phần `assistant.handle`.

---

## Phase 3: User Story 1 — Mọi câu hỏi đều có bước tiếp theo (Priority: P1) 🎯 MVP

**Goal**: `/chat` và `/chat/stream` chỉ trả `answer`/`suggest`/`clarify`; câu mơ hồ có gợi ý; câu lạc đề/vô nghĩa có menu chủ đề; frontend render được cả ba loại.

**Independent Test**: Gửi lần lượt câu khớp rõ, "mục tiêu", "hôm nay ăn gì", "asdf" → nhận đúng `answer`/`suggest`/`clarify`; không response nào là `unknown`; mọi response `suggest`/`clarify` có ít nhất một nút.

### Tests for User Story 1 (viết trước, phải fail)

- [ ] T010 [P] [US1] Viết `backend/tests/test_assistant.py`: bảng quyết định high `≥0.78` → `answer`; vùng `0.45–0.78`, câu `≤3` từ, hoặc top1−top2 `<0.05` → `suggest`; `<0.45` không có tài liệu → `clarify`; "asdf" → `clarify`; assert không có `type="unknown"` và mọi `suggest`/`clarify` có `actions`.
- [ ] T011 [P] [US1] Cập nhật `backend/tests/test_chat_api.py` và `backend/tests/test_chat_api_contract.py`: `POST /chat` trả `type` hợp lệ, luôn có `session_id`; giữ `response`/`answer_bullets`; validation 400/422 cũ; bỏ kỳ vọng `unknown`.
- [ ] T012 [P] [US1] Viết `frontend/src/components/Message/Message.test.tsx`: render bong bóng `answer`; danh sách nút `suggest` kèm %; chip `clarify` + ví dụ + nút "Câu hỏi khác"/"Hỏi lại cách khác"; không render chuỗi "không biết".
- [ ] T013 [P] [US1] Cập nhật `frontend/src/lib/chatClient.test.ts`: `sendMessage` gọi `POST /chat`, trả `ChatResponse` có `type`/`session_id`; fallback stream khi `/chat` trả 404/405; không mất trường `response` cũ.

### Implementation for User Story 1

- [ ] T014 [US1] Implement `handle()` cơ bản trong `backend/assistant.py`: chuẩn hoá câu hỏi; nếu rỗng → `clarify`; `top1 ≥ 0.78` và không mơ hồ → `answer` từ KB; mơ hồ/vùng `0.45–0.78` → `suggest` từ top ứng viên KB; `top1 < 0.45` → `clarify` menu chủ đề; `action` khác rỗng → tạm dựng `clarify` cấp 1 (US2 mở rộng sau); embedding lỗi → fuzzy trên câu hỏi KB rồi `clarify`; tuyệt đối không trả `unknown`.
- [ ] T015 [US1] Cập nhật `backend/app.py` route `/chat`: gọi `assistant.handle(...)`, nhận/trả `session_id`, giữ validation 400/422/429; bỏ chuỗi `kb_engine.query → ask_ai` và nhánh `unknown`.
- [ ] T016 [US1] Cập nhật `backend/app.py` route `/chat/stream`: `answer` phát `chunk` + `done`; `suggest`/`clarify` phát một event `{"type":"result","data":<response>}` rồi `done`; không phát `unknown`.
- [ ] T017 [US1] Cập nhật `frontend/src/lib/chatClient.ts` và `frontend/src/lib/streamParser.ts`: `sendMessage` mặc định gọi `/chat` và trả `ChatResponse`; thêm kiểu event `result`; giữ `chunk`/`done`/`error` tương thích.
- [ ] T018 [US1] Cập nhật `frontend/src/store/chatStore.ts`: mở rộng `Message` với `responseType`, `sessionId`, `suggestions`, `topics`, `examples`, `actions`, `sources`; tạo `sessionId` cho mỗi `Conversation`; gán response vào message assistant.
- [ ] T019 [US1] Tạo `frontend/src/components/Message/SuggestionList.tsx` và `frontend/src/components/Message/TopicList.tsx`; render trong `frontend/src/components/Message/Message.tsx`; thêm style trong `frontend/src/styles/app.css`; mọi nút `type="button"`, có `aria-label` và focus ring.
- [ ] T020 [US1] Implement `sendAction(action, payload)` trong `frontend/src/store/chatStore.ts`: gửi `{session_id, action, topic?}` tới `sendMessage`; bấm gợi ý gửi câu hỏi đã chọn như tin nhắn mới; bấm "Câu hỏi khác"/"Hỏi lại cách khác" gửi action tương ứng; chặn khi đang streaming.
- [ ] T021 [US1] Cập nhật `backend/tests/test_refusal.py`: câu ngoài phạm vi trả `clarify` có `topics`/`actions`, không còn `"Tôi không biết"`; giữ test validation input rỗng/quá dài.
- [ ] T022 [US1] Chạy `pytest backend/tests/test_assistant.py backend/tests/test_chat_api.py backend/tests/test_chat_api_contract.py backend/tests/test_refusal.py` và `npm test -- --run` trong `frontend/`; sửa lỗi tích hợp.

**Checkpoint**: US1 là MVP — không còn ngõ cụt, API và UI render đủ 3 loại phản hồi.

---

## Phase 4: User Story 2 — Làm rõ theo cấp, không lặp lại (Priority: P2)

**Goal**: Gợi ý theo từ khoá + embedding; "Câu hỏi khác" → menu chủ đề → câu chưa hiển thị → mời mô tả; trạng thái `shown_ids`/`level` giữ theo phiên.

**Independent Test**: Từ "mục tiêu", bấm "Câu hỏi khác" 3 lần liên tiếp: lần 1 ra menu chủ đề, chọn chủ đề ra câu chưa hiển thị, cạn câu ra cấp 3 với ví dụ; không câu nào lặp trong cùng phiên; phiên mới reset.

### Tests for User Story 2 (viết trước, phải fail)

- [ ] T023 [P] [US2] Viết `backend/tests/test_suggestions.py`: gộp keyword/topic + embedding, khử trùng, bỏ `shown_ids`, trả 2–4 gợi ý (mục tiêu 3–4), điểm 0–1; topic menu lấy từ KB + tài liệu (`<file> — <heading>`/tên tệp), tối đa 8, ưu tiên chủ đề nhiều câu/đoạn; thêm bộ ~25 câu ngắn/không dấu/teencode và assert **≥80%** có ít nhất một gợi ý đúng ý định (SC-008).
- [ ] T024 [P] [US2] Viết `backend/tests/test_session.py`: TTL 1800 giây, tối đa 1000 phiên, `shown_ids` tối đa 200, hai phiên không ảnh hưởng nhau, `reset` xoá trạng thái.
- [ ] T025 [P] [US2] Mở rộng `backend/tests/test_chat_api.py`: `action=other` → `clarify` cấp 1; `action=topic` → `suggest` câu chưa hiển thị; cạn câu → `clarify` cấp 3; `action=rephrase` → cấp 3; `action=topic` thiếu `topic` → 400; phiên mới được lặp lại gợi ý.
- [ ] T026 [P] [US2] Cập nhật `frontend/src/store/chatStore.test.ts` và thêm test tương tác cho `SuggestionList`/`TopicList`: gửi đúng `session_id`/`action`/`topic`; không gửi trùng khi đang streaming; `newConversation` tạo `sessionId` mới; nút hiển thị đúng nhãn.

### Implementation for User Story 2

- [ ] T027 [US2] Implement `backend/suggestions.py`: `keyword_score` (overlap token với `topic` + câu hỏi mẫu + `keywords` nếu có, cộng `WRatio`), `embedding_candidates` từ `query_vec` + ma trận câu hỏi, gộp theo câu hỏi, trọng số `0.6*embedding + 0.4*keyword`, khử trùng, bỏ `shown_ids`, lấy tối đa 4; nếu < 2 → báo `clarify`.
- [ ] T028 [US2] Implement quy tắc `suggestions[].id` trong `backend/suggestions.py` đúng `data-model.md`: item 1 câu → `item_id`; nhiều câu → `item_id#<sha1(normalized_question)[:8]>`; câu KB không item → `kb:<sha1(normalized_question)[:12]>`; câu tài liệu → `doc:<file>#<heading>`.
- [ ] T029 [US2] Implement `build_clarify()` trong `backend/suggestions.py`: L1 topics (KB + tài liệu, tối đa 8, ≥3 nếu dữ liệu đủ) + 2–3 `examples` + action `rephrase`; L2 câu thuộc topic chưa hiển thị (topic tài liệu dùng heading làm câu mẫu); L3 `topics=[]`, 2–3 `examples`; không lặp vô hạn.
- [ ] T030 [US2] Tích hợp session vào `backend/assistant.py`: `action=other` → L1; `action=topic` → L2 (xác thực topic trong `last_topics`); `action=rephrase` và cạn câu → L3; `action=retry` → chạy lại `last_query`; cập nhật `shown_ids` (tối đa 200), `level`, `last_query`; tin nhắn mới không phải action → `level=1` nhưng giữ `shown_ids`.
- [ ] T031 [US2] Cập nhật validation `backend/app.py`: `message` bắt buộc khi không có `action`, 1–200 ký tự; `action` chỉ `other|topic|rephrase|retry`; `action=topic` bắt buộc `topic`; `session_id` ≤100 ký tự; giữ 400/422/429.
- [ ] T032 [US2] Cập nhật `frontend/src/store/chatStore.ts`: giữ `sessionId` theo `Conversation`, reset khi `newConversation`; thêm bubble người dùng cho câu đã chọn/chủ đề đã chọn; không gửi action khi đang streaming.
- [ ] T033 [US2] Cập nhật `frontend/src/components/Message/Message.tsx` + `SuggestionList.tsx`/`TopicList.tsx`: nút gợi ý kèm `%`, chip chủ đề, danh sách ví dụ, nút "Câu hỏi khác"/"Hỏi lại cách khác"; gọi `sendAction` đúng `{action, topic?}`; thêm CSS focus/disabled trong `frontend/src/styles/app.css`.
- [ ] T034 [US2] Chạy `pytest backend/tests/test_suggestions.py backend/tests/test_session.py backend/tests/test_chat_api.py` và `npm test -- --run` trong `frontend/`; kiểm tra thủ công kịch bản "mục tiêu" ở `quickstart.md` mục 4.2–4.4.

**Checkpoint**: US2 hoàn tất — mọi nút "Câu hỏi khác" dẫn tới một bước tiếp theo, không lặp gợi ý trong phiên.

---

## Phase 5: User Story 3 — Nạp PDF / DOCX / XLSX / CSV & trả lời kèm nguồn (Priority: P3)

**Goal**: Nạp offline 4 định dạng (thêm TXT/MD), lưu chunk có metadata, tìm kiếm ngữ nghĩa, trả lời trích xuất kèm nguồn; nạp lại chỉ xử lý phần đổi.

**Independent Test**: Nạp thư mục mẫu có PDF/DOCX/XLSX/CSV → hỏi 3 câu/định dạng → trả đúng nội dung + `sources` đúng file/trang/sheet/dòng; nạp lại không đổi → `skipped` và `embeddings_computed=0`.

### Tests for User Story 3 (viết trước, phải fail)

- [ ] T035 [P] [US3] Viết `backend/tests/test_doc_loaders.py`: PDF trả `page` 1-based; DOCX giữ `heading` và bảng thành dòng `cột: giá trị`; XLSX đọc **tất cả sheet**, `row_start`/`row_end` 1-based tính header; CSV thử `utf-8-sig`/`utf-8`/`cp1258`/`latin-1`; PDF scan → lỗi `E_NO_TEXT`; TXT/MD đọc UTF-8 và heading `#`; tệp > 20 MB bị từ chối.
- [ ] T036 [P] [US3] Viết `backend/tests/test_doc_index.py`: chunk có đủ `chunk_id`, `file`, `type`, `page`/`sheet`/`row_start`/`row_end`, `heading`, `text`, `embed_text`, `content_hash`, `char_count`; tệp không đổi → `skipped`; tệp đổi → chỉ embed đoạn mới/đổi, tái dùng hash trùng; xoá tệp → chunk/vector biến mất; tệp lỗi không làm hỏng chỉ mục; manifest lệch model/chuẩn hoá/chunk → yêu cầu `ingest --full`.
- [ ] T037 [P] [US3] Viết `backend/tests/test_doc_answers.py`: trả lời trích xuất lấy top 1–2 chunk ≥0.55, chọn 3–5 câu, khử trùng, giữ thứ tự, tối đa ~600 ký tự; `source`/`sources` khớp `page`/`sheet`/`row_start`/`row_end`; không gọi LLM.
- [ ] T038 [P] [US3] Viết `backend/tests/test_doc_cli.py`: `ingest` thư mục/tệp, `list` hiện `indexed|not-indexed|failed` + số đoạn, `remove` chỉ xoá chỉ mục không xoá tệp nguồn, `--json` đúng `IngestReport`, exit code 0/1/2, `--recursive`, `--full`.

### Implementation for User Story 3

- [ ] T039 [US3] Implement `backend/doc_loaders.py` `extract_blocks(path)`: PDF dùng `pypdf` theo trang (1-based, trang không có text → `E_NO_TEXT`); DOCX dùng `python-docx` giữ `Heading 1..6`, bảng → dòng `cột: giá trị`; DOC cũ chuyển bằng `libreoffice --headless` nếu có, thiếu → lỗi rõ; XLSX dùng `pandas.read_excel(sheet_name=None)`; CSV dùng `pandas.read_csv` với danh sách encoding; TXT/MD UTF-8.
- [ ] T040 [US3] Implement `backend/doc_loaders.py` `chunk_blocks`: mục tiêu **300–500 ký tự**, `chunk_size` tối đa 500, `chunk_overlap=50`; tiền tố `[file > heading > trang/sheet]`; `text` gốc không tiền tố, `embed_text` đã chuẩn hoá; `content_hash=sha256(embed_text)`; `chunk_id=sha1(file|page|sheet|row_start|row_end|heading|content_hash)`; bảng gộp 5–10 dòng ngắn đến ~500 ký tự; bỏ dòng rỗng/header lặp.
- [ ] T041 [US3] Implement `backend/doc_index.py` persistence: `manifest.json` (`schema_version=1`, `embedding_model`, `normalizer_version`, `chunk_size`, `chunk_overlap`, `file_count`, `chunk_count`, `vector_dim`), `files.json` (status `indexed|skipped|failed|removed`, `file_hash` SHA-256, `chunk_ids`), `chunks.json`, `vectors.npz` (`chunk_ids`, `vectors` float32 L2-normalized); ghi atomic `os.replace`; kiểm tra toàn vẹn khi `load()`; lỗi không xoá dữ liệu cũ.
- [ ] T042 [US3] Implement `backend/doc_index.py` ingest tăng dần: `file_hash` trùng → `skipped`; tệp đổi → so `content_hash` từng đoạn, tái dùng vector cũ cho hash trùng, embed đoạn mới/đổi, xoá đoạn mất; `--full` bỏ cache; tệp lỗi giữ nguyên bản ghi thành công trước đó; dựng lại `faiss.IndexFlatIP` + `IndexIDMap2` trong RAM.
- [ ] T043 [US3] Implement `backend/doc_index.py` `search(query_vec, k=5)` (cosine, lọc `≥0.55`), `extractive_answer(hits)`, `list_documents()`, `remove_document(name)`; `extractive_answer` chấm câu bằng `0.6*overlap + 0.4*fuzzy`, chọn 3–5 câu, không gọi LLM.
- [ ] T044 [US3] Tích hợp trong `backend/assistant.py` và `backend/app.py`: khởi tạo `DocIndex` một lần lúc startup (nạp sẵn chỉ mục vào RAM, không xử lý lại tài liệu); khi `top1 < 0.45` gọi `doc_searcher.search`; có hit `≥0.55` → `answer` trích xuất + `sources`; không có → gọi `chatbox.retrieve_rag_documents` cho bản ghi `kind: doc` của 005; vẫn không có → `clarify`.
- [ ] T045 [US3] Thêm `retrieve_rag_documents(question, k=5)` vào `backend/chatbox.py`: dùng `get_db()` + `similarity_search_with_score`, chuyển L2 distance trên vector chuẩn hoá thành cosine `max(0, 1 - d²/2)`, lọc `≥0.55`, trả excerpt + metadata `source`/`page`/`chunk_index`; không gọi LLM.
- [ ] T046 [US3] Mở rộng `backend/scripts/manage_docs.py`: thêm `ingest [PATH]` (`--data-dir`, `--index-dir`, `--recursive`, `--full`, `--json`), `remove SOURCE` (`--index-dir`, `--json`), mở rộng `list` hiển thị `indexed|not-indexed|failed` + số đoạn; `IngestReport`/`--json` phải có `added`, `updated`, `skipped`, `failed`; giữ nguyên `add/replace/delete/validate/migrate/ask`; exit code 0/1/2 đúng `contracts/manage-docs-cli.md`.
- [ ] T047 [US3] Cập nhật `docker-compose.yml` mount `./backend/data:/app/backend/data:ro` và `./backend/doc_index:/app/backend/doc_index`, thêm `CHATBOT_DOC_INDEX_DIR`; cập nhật `README.md` và `backend/.env.example` với quy trình `ingest/list/remove`.
- [ ] T048 [US3] Cập nhật `frontend/src/components/Message/Message.tsx` + `frontend/src/lib/chatTypes.ts`: render `sources` dạng `file, trang N` hoặc `file, sheet X, dòng A–B`; thêm CSS trong `frontend/src/styles/app.css`; nguồn không được bịa, chỉ lấy từ response.
- [ ] T049 [US3] Chạy `pytest backend/tests/test_doc_loaders.py backend/tests/test_doc_index.py backend/tests/test_doc_answers.py backend/tests/test_doc_cli.py`; chạy `ingest` trên `backend/data/` mẫu và hỏi 3 câu/định dạng theo `quickstart.md` mục 4.7.

**Checkpoint**: US3 hoàn tất — 4 định dạng nạp được, trả lời kèm nguồn, ingest tăng dần đúng.

---

## Phase 6: User Story 4 — Trả lời nhanh, không phụ thuộc LLM (Priority: P4)

**Goal**: p50 < 300 ms, p95 < 500 ms khi tắt tóm tắt; 0% nội dung do LLM sinh; tóm tắt LLM tuỳ chọn, mặc định tắt; hạ cấp khi embedding lỗi.

**Independent Test**: Chạy 50+ lượt qua 3 nhánh với embedder giả hoặc Ollama đã warm → p50 < 300 ms, p95 < 500 ms; `ENABLE_LLM_SUMMARY=false` → không gọi LLM khi trả lời; tắt Ollama → vẫn nhận `suggest`/`clarify`.

### Tests for User Story 4 (viết trước, phải fail)

- [ ] T050 [P] [US4] Mở rộng `backend/tests/test_source_perf.py`: gọi `assistant.handle` 50+ lượt cho `answer`/`suggest`/`clarify` với embedder giả; assert tiền xử lý < 1 ms, tra cứu < 20 ms, dựng gợi ý < 5 ms, p50 < 0.300 s, p95 < 0.500 s; assert không gọi LLM.
- [ ] T051 [P] [US4] Viết `backend/tests/test_llm_summary.py`: `ENABLE_LLM_SUMMARY=false` → không gọi `get_llm`; `true` → gọi với context chỉ gồm câu đã trích, `num_predict ≤ 120`; lỗi LLM → quay về trích xuất; `/chat` trả một lần, `/chat/stream` stream.

### Implementation for User Story 4

- [ ] T052 [US4] Thêm nhánh tóm tắt tuỳ chọn trong `backend/assistant.py` (và helper stream trong `backend/chatbox.py`): chỉ dùng khi `ENABLE_LLM_SUMMARY=true`, chỉ cho `answer` từ tài liệu, giới hạn `num_predict ≤ 120`, lỗi → fallback extractive; mặc định tắt.
- [ ] T053 [US4] Đặt `CHATBOT_QUERY_REWRITE` mặc định `off` trong `backend/chatbox.py`; bảo đảm `backend/assistant.py` không gọi `_rewrite_query`/Qwen trên đường chính; ghi cảnh báo deprecated cho `CHATBOT_KB_MID_THRESHOLD`, đọc alias `CHATBOT_KB_MAX_SUGGESTIONS` cho `CHATBOT_MAX_SUGGESTIONS`.
- [ ] T054 [US4] Thêm cache assessment LRU trong `backend/assistant.py` (key = câu chuẩn hoá) cho `top1/top2/candidates/query_vec`; response cuối vẫn dựng theo session/`shown_ids`; giới hạn cache bằng `CHATBOT_QUERY_CACHE_SIZE=512`; không cache kết quả phụ thuộc phiên.
- [ ] T055 [US4] Đo p50/p95 theo `quickstart.md` mục 7, tinh chỉnh ngưỡng nếu cần; cập nhật `backend/.env.example`, `README.md`, `docker-compose.yml` với `ENABLE_LLM_SUMMARY`, `CHATBOT_QUERY_REWRITE=off` và ngân sách hiệu năng.
- [ ] T056 [US4] Chạy `pytest backend/tests/test_source_perf.py backend/tests/test_llm_summary.py backend/tests/test_assistant.py -k "fallback or perf or summary"`; xác nhận nhánh Ollama lỗi vẫn trả `suggest`/`clarify`, không 500/`unknown`.

**Checkpoint**: US4 hoàn tất — phản hồi nhanh, không LLM mặc định, có đường tóm tắt tuỳ chọn.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Tài liệu, dọn mã cũ, kiểm tra toàn bộ và xác nhận quickstart.

- [ ] T057 [P] Cập nhật `README.md` và `backend/README.md`: schema `answer/suggest/clarify`, `session_id`, action buttons, CLI `ingest/list/remove`, biến môi trường mới, quy trình nạp tài liệu và rollback bằng cách xoá `backend/doc_index/`.
- [ ] T058 [P] Rà soát `.gitignore`, `backend/.env.example`, `docker-compose.yml`: không commit `backend/doc_index/`, không chứa khoá/mật khẩu/PII; xác nhận mount chỉ đọc cho `backend/data`.
- [ ] T059 Chạy toàn bộ `pytest backend/tests -q`; sửa regression ở `backend/app.py`, `backend/chatbox.py`, `backend/kb_engine.py`, `backend/assistant.py`.
- [ ] T060 Chạy `npm test`, `npm run typecheck`, `npm run lint` trong `frontend/`; sửa lỗi TypeScript/ESLint.
- [ ] T061 Chạy checklist `specs/006-tiered-suggest-ingest/quickstart.md` mục 4–7 bằng curl và UI; ghi lại kết quả p50/p95 và các tiêu chí SC-001–SC-010.
- [ ] T062 Rà soát mã nguồn để bảo đảm không còn `_build_unknown_response`, `type="unknown"` hay chuỗi "Tôi không biết"/"Mình không biết" trên đường phản hồi; xoá code chết hoặc giữ trong nhánh legacy có ghi chú rõ.
- [ ] T063 Chạy smoke test Docker: `docker compose up -d --build`, `ingest` trong container, `POST /chat` qua nginx cho `answer`/`suggest`/`clarify`, kiểm tra `doc_index/` được mount bền vững.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Không phụ thuộc; bắt đầu ngay.
- **Foundational (Phase 2)**: Phụ thuộc Setup; **chặn toàn bộ user story**.
- **US1 (Phase 3)**: Phụ thuộc Foundational; là MVP, mở khóa UI/API 3 loại phản hồi.
- **US2 (Phase 4)**: Phụ thuộc US1 (đã có `suggest`/`clarify` và `sendAction`); có thể làm song song US3 nếu đủ người.
- **US3 (Phase 5)**: Phụ thuộc Foundational + `assistant.handle` của US1; **không** phụ thuộc US2.
- **US4 (Phase 6)**: Phụ thuộc US1 + US3 (cần trả lời tài liệu để đo và tóm tắt tuỳ chọn).
- **Polish (Phase 7)**: Phụ thuộc tất cả story mong muốn hoàn tất.

### User Story Dependencies

- **US1 (P1)**: Không phụ thuộc story khác; cần Phase 2.
- **US2 (P2)**: Cần US1; độc lập với US3.
- **US3 (P3)**: Cần US1; độc lập với US2.
- **US4 (P4)**: Cần US1 + US3; không cần US2.

### Within Each User Story

- Test (T010–T013, T023–T026, T035–T038, T050–T051) phải viết trước và fail trước implementation tương ứng.
- Response builder/session/KB evaluate thuộc Phase 2, hoàn tất trước mọi story.
- Trong US1: `assistant.handle` → `app.py` → frontend client/store → component render.
- Trong US2: `suggestions.py` → session integration → API validation → frontend action UI.
- Trong US3: loaders/chunker → persistence → incremental → search/extractive → assistant/CLI/frontend.
- Trong US4: performance tests → optional summary → remove Qwen → cache → đo/tinh chỉnh.

### Parallel Opportunities

- Setup: T001, T002, T003 chạy song song.
- Foundational: T004, T005, T007, T008 chạy song song; T006/T009 sau T004.
- US1 tests T010–T013 chạy song song; component T019 và store T018 có thể song song sau T017.
- US2 tests T023–T026 chạy song song.
- US3 tests T035–T038 chạy song song; T039/T040 tuần tự trong `doc_loaders.py`; T041–T043 tuần tự trong `doc_index.py`.
- US4 tests T050/T051 chạy song song.
- US2 và US3 có thể chạy song song sau khi US1 xong (khác file chính: `suggestions.py`/UI vs `doc_loaders.py`/`doc_index.py`).

---

## Parallel Example: User Story 1

```bash
# Viết test trước, chạy song song
Task: "Viết backend/tests/test_assistant.py cho thang 3 tầng"
Task: "Cập nhật backend/tests/test_chat_api.py + test_chat_api_contract.py"
Task: "Viết frontend/src/components/Message/Message.test.tsx"
Task: "Cập nhật frontend/src/lib/chatClient.test.ts"

# Sau khi assistant.handle + chatClient xong, chạy song song
Task: "Tạo SuggestionList.tsx + TopicList.tsx"
Task: "Mở rộng chatStore.ts với sessionId/response fields"
```

## Parallel Example: User Story 3

```bash
Task: "Viết backend/tests/test_doc_loaders.py"
Task: "Viết backend/tests/test_doc_index.py"
Task: "Viết backend/tests/test_doc_answers.py"
Task: "Viết backend/tests/test_doc_cli.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Hoàn thành Phase 1: Setup.
2. Hoàn thành Phase 2: Foundational (bắt buộc).
3. Hoàn thành Phase 3: US1.
4. **STOP và VALIDATE**: chạy test US1 + quickstart mục 4.1–4.6; xác nhận không còn `unknown`/ngõ cụt.
5. Demo được ngay: mọi câu hỏi có `answer`/`suggest`/`clarify`, có nút bấm.

### Incremental Delivery

1. Setup + Foundational → nền tảng.
2. US1 → test → demo (MVP: không ngõ cụt).
3. US2 → test → demo (làm rõ theo cấp, không lặp).
4. US3 → test → demo (nạp tài liệu, trả lời kèm nguồn).
5. US4 → test → đo hiệu năng, bật/tắt tóm tắt LLM.
6. Polish → full test, quickstart, Docker smoke.

### Parallel Team Strategy

1. Cả nhóm hoàn thành Setup + Foundational.
2. Sau US1:
   - Developer A: US2 (`suggestions.py`, session, UI action).
   - Developer B: US3 (`doc_loaders.py`, `doc_index.py`, CLI).
3. US4 sau khi US1 + US3 xong (perf + tóm tắt tuỳ chọn).
4. Polish chung.

---

## Notes

- [P] tasks = khác file, không phụ thuộc task chưa xong.
- [Story] label dùng để trace task về user story.
- Ưu tiên tuyệt đối: không nhánh nào trả `unknown` hoặc "không biết"; lỗi nội bộ hạ cấp về `clarify`.
- Không gọi LLM trên đường chính; `ENABLE_LLM_SUMMARY=false` mặc định.
- Chunk/ingest dùng chung `normalize_text`/`normalize_query`; không tạo chuẩn hoá thứ hai.
- Không commit `backend/doc_index/`; dữ liệu tài liệu không rời máy cục bộ.
- `backend/doc_index.py` là module mã nguồn; `backend/doc_index/` chỉ là thư mục dữ liệu, **không** thêm `__init__.py` để tránh nhầm với package.
