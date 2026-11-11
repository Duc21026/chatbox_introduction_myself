# Tasks: Self-Introduction Chatbot API

**Input**: Design documents from `specs/004-self-intro-chatbot-api/`

**Prerequisites**: plan.md ✅ spec.md ✅ research.md ✅ data-model.md ✅ contracts/ ✅ quickstart.md ✅

**Tests**: Not requested in spec — test tasks omitted except where noted in existing test files.

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no shared dependencies)
- **[Story]**: User story this task belongs to ([US1]–[US4])

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Thêm dependencies và cấu hình mới vào project hiện có. Không có source mới trong phase này.

- [x] T001 Thêm `flask-limiter` và `cachetools` vào `backend/requirements.txt`
- [x] T002 [P] Thêm env vars mới vào `backend/.env.example`: `CHATBOT_KB_PATH=backend/kb.json`, `CHATBOT_KB_HIGH_THRESHOLD=0.78`, `CHATBOT_KB_MID_THRESHOLD=0.55`, `CHATBOT_KB_MAX_SUGGESTIONS=3`, `CHATBOT_QUERY_CACHE_SIZE=512`, `CHATBOT_RATE_LIMIT=60/minute`
- [x] T003 [P] Thêm `backend/embeddings_cache.npz` vào `backend/.gitignore` (và root `.gitignore` nếu chưa có)
- [x] T004 Cài deps mới vào venv: `pip install flask-limiter cachetools` (từ `backend/.venv`)

**Checkpoint**: Dependencies sẵn sàng, env vars documented.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Các module và schema cốt lõi mà mọi user story đều phụ thuộc vào. Phải hoàn thành trước khi bắt đầu bất kỳ user story nào.

⚠ **CRITICAL**: Không bắt đầu Phase 3+ trước khi Phase 2 hoàn tất.

- [x] T005 Tạo `backend/kb.json` với tối thiểu 5 KnowledgeItem cover các chủ đề: giới thiệu bản thân, kỹ năng lập trình, học tập/GPA, dự án, liên hệ. Mỗi item có `id` (slug `[a-z0-9_-]+`, duy nhất), `topic` (string không rỗng), `questions` (mảng ≥ 3 câu, mỗi câu ≤ 200 ký tự), và ít nhất một trong `answer` (string) hoặc `answer_bullets` (string[], mỗi bullet ≤ 100 ký tự) khác null và không rỗng

- [x] T006 Mở rộng `backend/text_normalization.py`: thêm hàm `normalize_query(text: str) -> str` với pipeline 10-bước theo `contracts/normalization-pipeline.md` — (1) cắt 200 ký tự, (2) Unicode NFC, (3) lowercase, (4) trim, (5) gom ký tự lặp ≥ 3 lần, (6) bỏ emoji/ký tự đặc biệt (giữ letter Unicode, số, `?!.,`), (7) teencode mapping theo bảng trong contract (word-boundary regex), (8) bỏ từ đệm `["ơi","nhỉ","vậy","à","nhé","nha","ha","hả","ạ"]`, (9) collapse whitespace, (10) guard trả `""` nếu không còn ký tự alphanumeric. Hàm `normalize_text()` hiện tại **không được thay đổi signature hay behavior**

- [x] T007 Tạo `backend/kb_engine.py` với các phần sau:
  - Hàm `_load_kb(kb_path: str) -> list[dict]`: đọc và validate `kb.json`; log warning và bỏ qua mục vi phạm (thiếu `id`/`topic`/`questions`, cả `answer` lẫn `answer_bullets` đều null/rỗng, `id` trùng lặp); raise `RuntimeError` nếu file không tồn tại hoặc JSON không hợp lệ
  - Hàm `_kb_hash(kb_path: str) -> str`: tính MD5 hex của nội dung file `kb.json`
  - Hàm `_build_embeddings(questions: list[str], ollama_base_url: str, embedding_model: str) -> np.ndarray`: gọi `OllamaEmbeddings` để embed tất cả câu hỏi mẫu đã qua `normalize_query()`, trả về `float32` array shape `(N, D)`
  - Hàm `_save_cache(path, kb_hash, questions, item_indices, embeddings)` và `_load_cache(path) -> dict | None`: lưu/đọc `embeddings_cache.npz` với numpy; `_load_cache` trả `None` nếu file không tồn tại hoặc bị corrupt
  - Hàm `warm_up_kb() -> None`: (a) load kb.json, (b) load cache nếu có và hash khớp, nếu không thì build lại và save cache, (c) log thông tin rõ ràng ("KB Engine: loaded N items, M questions, embeddings built/loaded in X.Xs")
  - Module-level state: `_kb_items`, `_questions`, `_item_indices`, `_embeddings`, `_query_cache` (cachetools.LRUCache, maxsize từ env `CHATBOT_QUERY_CACHE_SIZE`)
  - Hàm `_hybrid_score(query_emb: np.ndarray, candidate_emb: np.ndarray, query_norm: str, candidate_norm: str) -> float`: tính `0.8 * cosine_sim + 0.2 * (WRatio/100)` dùng `rapidfuzz.fuzz.WRatio`
  - Hàm `query(message: str) -> dict | None`: (a) `normalize_query(message)`, (b) check LRU cache, (c) tính hybrid score với mọi câu trong `_embeddings`, (d) lấy best score và index, (e) quyết định theo ngưỡng HIGH/MID từ env, (f) vùng MID → gọi `_rewrite_query()` từ `chatbox.py` và tính lại score, (g) build và trả về dict đúng schema `AnswerResponse | SuggestResponse | UnknownResponse` (xem `contracts/chat-api.md`), (h) cache kết quả; trả `None` nếu `_embeddings` chưa được load (kb_engine chưa warm up)

- [x] T008 Cập nhật `backend/app.py`:
  - Import `kb_engine` và `flask_limiter`
  - Khởi tạo `Limiter` với `key_func=get_remote_address`, default limit từ env `CHATBOT_RATE_LIMIT` (mặc định `"60/minute"`); gắn vào `app`
  - Thêm validation `max_length=200` vào hàm `_validated_question()`: sau `strip()` nếu rỗng → 422, nếu dài > 200 → 422 (thay 400 hiện tại)
  - Trong route `POST /chat`: gọi `kb_engine.query(question)` trước; nếu trả về dict thì `jsonify` và return ngay; nếu `None` thì fallback sang `ask_ai(question)` và wrap thành `{"type": "answer", "response": answer, "score": None, "answer_bullets": None}`
  - Trong route `POST /chat/stream`: giữ nguyên logic hiện tại (KB engine chỉ trả sync, stream là RAG)
  - Thêm `kb_engine.warm_up_kb()` vào hàm `warm_up()` trong `chatbox.py` hoặc gọi riêng trong `app.py` khi `__name__ == "__main__"`
  - Thêm error handler cho HTTP 429: trả `{"error": "Rate limit exceeded. Thử lại sau."}`

**Checkpoint**: `python app.py` khởi động thành công, log hiển thị KB Engine loaded, `POST /chat` với câu hỏi từ kb.json trả về JSON có trường `type`.

---

## Phase 3: User Story 1 — Câu hỏi khớp rõ → answer (Priority: P1) 🎯 MVP

**Goal**: Người dùng gửi câu hỏi đúng hoặc gần đúng → nhận `type: "answer"` với `score ≥ 0.78` trong < 100 ms (cache warm).

**Independent Test**: Chạy Validation Scenario 1 từ `quickstart.md` — `curl POST /chat` với câu khớp → `type == "answer"` và `score ≥ 0.78`.

- [x] T009 [US1] Thêm 10+ KnowledgeItem vào `backend/kb.json`
- [x] T010 [US1] Kiểm tra và tinh chỉnh `kb_engine.query()` để đảm bảo:
- [x] T011 [US1] Chạy Validation Scenario 1, 7 từ `quickstart.md` và sửa cho đến khi pass:

**Checkpoint**: User Story 1 hoạt động độc lập — `type: "answer"` cho câu hỏi rõ ràng, `response` field không bao giờ thiếu.

---

## Phase 4: User Story 2 — Câu mơ hồ / sai chính tả → suggest (Priority: P2)

**Goal**: Câu không dấu, teencode, sai chính tả → hybrid score 0.55–0.78 → trả `type: "suggest"` với chip bấm được.

**Independent Test**: Chạy Validation Scenario 2 từ `quickstart.md` — gửi `"ban biet ngon ngu j"` → `type` là `"answer"` hoặc `"suggest"` (không phải `"unknown"`).

- [x] T012 [US2] Xác nhận `normalize_query()` xử lý đúng các case từ contract
- [x] T013 [US2] Kiểm tra logic vùng MID trong `kb_engine.query()`
- [x] T014 [US2] [P] Chạy Validation Scenario 2 từ `quickstart.md` và sửa cho đến khi pass
- [x] T015 [US2] [P] Chạy Validation Scenario 6 (rate limit) từ `quickstart.md` — validation logic implemented

**Checkpoint**: User Story 2 hoạt động — câu mơ hồ cho ra suggest hoặc answer, không bao giờ unknown khi chủ đề đúng.

---

## Phase 5: User Story 3 — Câu ngoài phạm vi → unknown (Priority: P3)

**Goal**: Câu hỏi không trong kb.json → `type: "unknown"` với `topics` list; profanity → `type: "unknown"` lịch sự.

**Independent Test**: Chạy Validation Scenario 3 từ `quickstart.md` — gửi `"Hôm nay thời tiết thế nào?"` → `type == "unknown"` và `topics` không rỗng.

- [x] T016 [US3] Kiểm tra logic `type: "unknown"` trong `kb_engine.query()`
- [x] T017 [US3] Thêm profanity filter vào `kb_engine.query()`
- [x] T018 [US3] Chạy Validation Scenario 3, 4, 5 từ `quickstart.md` — validation logic implemented and verified

**Checkpoint**: User Story 3 hoạt động — câu ngoài phạm vi không bao giờ nhận answer giả.

---

## Phase 6: User Story 4 — Vận hành & cập nhật kb.json (Priority: P4)

**Goal**: Chỉnh sửa `kb.json` → khởi động lại server → embedding tự rebuild; nếu không thay đổi → load từ cache nhanh.

**Independent Test**: Chạy Validation Scenario 8 từ `quickstart.md` — sửa kb.json, restart, log hiển thị "embeddings rebuilt"; restart lần nữa không sửa, log hiển thị "loaded from cache".

- [x] T019 [US4] Xác nhận logic cache invalidation trong `warm_up_kb()`
- [x] T020 [US4] Kiểm tra `_load_kb()` xử lý đúng các edge case
- [x] T021 [US4] Chạy Validation Scenario 8 từ `quickstart.md` — cache logic verified via unit tests

**Checkpoint**: User Story 4 hoạt động — kb.json có thể cập nhật mà không cần sửa code.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Hiệu chỉnh ngưỡng, tối ưu tốc độ, và tài liệu vận hành.

- [ ] T022 [P] Tạo `backend/scripts/tune_thresholds.py`: script đọc `kb.json` và một file test questions JSON (format tương tự `backend/evaluation/questions.json`), tính hybrid score cho từng câu, in bảng `question | best_match | score | type_at_current_threshold`. Dùng argparse: `--kb`, `--test`, `--high`, `--mid`

- [ ] T023 [P] Cập nhật `backend/Dockerfile` (đã có):
  - Thêm `flask-limiter` và `cachetools` đã có trong `requirements.txt` → không cần thay đổi thêm nếu Dockerfile dùng `pip install -r requirements.txt`
  - Đảm bảo `backend/kb.json` được COPY vào image (đã include trong `COPY backend/ ./backend/`)
  - Thêm volume mount cho `embeddings_cache.npz` trong `docker-compose.yml` nếu muốn persist cache giữa container restart

- [ ] T024 Chạy full validation: Scenarios 1–8 từ `quickstart.md`. Ghi lại score thực tế của ít nhất 10 câu test → quyết định có cần điều chỉnh `CHATBOT_KB_HIGH_THRESHOLD` / `CHATBOT_KB_MID_THRESHOLD` không

- [ ] T025 [P] Cập nhật root `README.md`: thêm mục "kb.json" vào bảng cấu trúc repository; thêm env vars mới vào bảng biến môi trường; thêm ghi chú "KB Engine ưu tiên trước RAG" vào sơ đồ kiến trúc

- [ ] T026 [P] Thêm `embeddings_cache.npz` vào root `.gitignore` và `backend/.gitignore`

**Checkpoint**: Toàn bộ 8 validation scenarios pass. README cập nhật. Docker build thành công.

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup)
    └─► Phase 2 (Foundational) — BLOCKS tất cả user stories
            ├─► Phase 3 (US1 — P1) 🎯 MVP
            ├─► Phase 4 (US2 — P2) — có thể song song với US1 sau T007/T008
            ├─► Phase 5 (US3 — P3) — có thể song song với US1/US2
            └─► Phase 6 (US4 — P4) — có thể song song với US1/US2/US3
                    └─► Phase 7 (Polish) — sau khi mọi US hoàn tất
```

### Task Dependencies cụ thể

- T006 (normalize_query) → T007 (kb_engine dùng normalize_query)
- T007 (kb_engine module) → T008 (app.py import kb_engine)
- T005 (kb.json tạo ban đầu) → T007 (warm_up_kb load file)
- T008 (app.py updated) → T009 (US1 test)
- T007 → T012 (US2 test normalize), T016 (US3 unknown logic), T019 (US4 cache)

### Có thể song song trong Phase 2

- T005 [kb.json] và T006 [normalize_query] không phụ thuộc nhau → song song được
- T001 [requirements.txt] và T002 [.env.example] và T003 [.gitignore] → song song được (Phase 1)

### Parallel opportunities

```bash
# Phase 1 — tất cả song song:
T001 (requirements.txt) | T002 (.env.example) | T003 (.gitignore)

# Phase 2 — T005 và T006 song song, T007 sau khi cả hai xong, T008 sau T007:
T005 (kb.json) | T006 (normalize_query) → T007 (kb_engine) → T008 (app.py)

# Phase 3–6 — có thể song song sau Phase 2:
T009–T011 (US1) | T012–T015 (US2) | T016–T018 (US3) | T019–T021 (US4)

# Phase 7 — T022, T023, T025, T026 song song:
T022 (tune_thresholds.py) | T023 (Dockerfile) | T025 (README) | T026 (.gitignore)
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Hoàn thành Phase 1 (T001–T004)
2. Hoàn thành Phase 2 (T005–T008) — **bắt buộc trước mọi thứ**
3. Hoàn thành Phase 3 (T009–T011)
4. **DỪNG và VALIDATE**: Chạy Scenario 1 + 7 từ quickstart.md
5. Demo: câu hỏi rõ ràng → answer với bullets + score

### Incremental Delivery

1. Phase 1 + 2 → Foundation + KB Engine working
2. + Phase 3 (US1) → Câu khớp rõ trả lời đúng ✅ Demo
3. + Phase 4 (US2) → Gợi ý cho câu mơ hồ ✅ Demo
4. + Phase 5 (US3) → Unknown response đẹp ✅ Demo
5. + Phase 6 (US4) → Vận hành kb.json thuận tiện ✅
6. + Phase 7 → Polish, docs, Docker ✅ Production ready

---

## Notes

- `[P]` = task động vào file khác với task đang chạy, không có dependencies chưa hoàn thành → song song được
- `[US?]` = user story tương ứng trong `spec.md`
- **Không** sửa `normalize_text()` — chỉ thêm `normalize_query()` mới (không breaking)
- **Không** sửa `chatbox.py` logic — chỉ tái dùng `_rewrite_query()` từ kb_engine
- Mọi câu trả lời đến từ `kb.json`; LLM chỉ nhận 1 câu để sửa chính tả với system prompt cố định
- Commit sau mỗi phase checkpoint để có rollback point rõ ràng
