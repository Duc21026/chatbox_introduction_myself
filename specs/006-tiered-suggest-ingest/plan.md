# Implementation Plan: Luôn gợi ý & nạp tài liệu đa định dạng

**Branch**: `006-tiered-suggest-ingest` | **Date**: 2026-11-12 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/006-tiered-suggest-ingest/spec.md`

## Summary

Thay toàn bộ nhánh "unknown / không biết" bằng một **bộ điều phối phản hồi 3 tầng** (`answer` → `suggest` → tài liệu → `clarify`) và bổ sung **chỉ mục tài liệu nạp offline** cho PDF, DOCX, XLSX, CSV (thêm TXT/MD). Câu trả lời từ tài liệu là **trích xuất** (không gọi LLM trên đường chính), kèm nguồn file/trang/sheet/dòng. Trạng thái làm rõ (`shown_ids`, `last_query`, `level`) được giữ theo phiên ở phía server; frontend chỉ cần render ba loại phản hồi và gửi lại hành động người dùng bấm.

Giải pháp tái sử dụng tối đa hạ tầng hiện có: chuẩn hoá tiếng Việt trong `text_normalization.py`, chấm điểm hybrid trong `kb_engine.py`, embedding `bge-m3` qua Ollama, và CLI `manage_docs.py`. Chỉ mục tài liệu là **dữ liệu phái sinh** đặt cạnh `chatbot.txt`; không thay đổi định dạng `CHATBOT-SOURCE v1` và không buộc người vận hành chép nội dung PDF/Excel vào tệp văn bản.

## Technical Context

**Language/Version**: Python 3.11 (backend), TypeScript 5.7 + React 18 (frontend)

**Primary Dependencies**:
- Hiện có, dùng lại: Flask + flask-cors + flask-limiter, `langchain-ollama` (`OllamaEmbeddings`), `faiss-cpu`, numpy, RapidFuzz, cachetools, pandas, openpyxl, pypdf, python-docx, pytest.
- Frontend hiện có: React, Zustand, lucide-react, Vitest.
- Không thêm dependency runtime bắt buộc. `libreoffice` chỉ là công cụ ngoài tuỳ chọn cho DOC cũ; `pytesseract`/`pdf2image` nằm ngoài phạm vi v1.

**Storage**:
- `backend/data/chatbot.txt`: nguồn Q&A soạn sẵn (định dạng 005, không đổi).
- `backend/data/*`: tài liệu nguồn PDF/DOCX/XLSX/CSV/TXT/MD do người vận hành bỏ vào.
- `backend/doc_index/files.json`: trạng thái từng tệp (hash SHA-256, chunk ids, thời điểm nạp, lỗi).
- `backend/doc_index/chunks.json`: metadata từng đoạn (file, loại, trang/sheet/dòng, heading, text gốc, hash nội dung).
- `backend/doc_index/vectors.npz`: vector đã chuẩn hoá theo `chunk_id` (float32).
- Chỉ mục FAISS `IndexFlatIP` dựng lại trong RAM lúc khởi động từ `vectors.npz`; không lưu chỉ mục nhị phân FAISS.
- Trạng thái phiên: bộ nhớ trong tiến trình (TTL + giới hạn số phiên); không lưu DB.

**Testing**: `pytest backend/tests`; `npm test`/`npm run typecheck` trong `frontend/`. Unit test dùng embedder giả (deterministic) để không cần Ollama; integration test Ollama được gate bằng `tests/helpers.ollama_ready`.

**Target Platform**: Linux server / Docker Compose; chạy được trên máy phát triển Python 3.11 với Ollama cục bộ.

**Project Type**: Web application (Flask backend + React SPA), kèm CLI vận hành.

**Performance Goals**:
- Tiền xử lý < 1 ms; dựng gợi ý/topics < 5 ms.
- Một lần embed câu hỏi 50–200 ms trên CPU; tra KB + tài liệu < 20 ms với kho ≤ 10 000 đoạn.
- p50 phản hồi không dùng LLM < 300 ms; p95 < 500 ms.
- Nạp lại thư mục không đổi: chỉ đọc hash, không embed lại.

**Constraints**:
- Không gọi LLM trên đường chính; `ENABLE_LLM_SUMMARY=false` mặc định.
- Không còn `type: "unknown"`; mọi phản hồi phải có hành động bấm được ngoài `answer`.
- Giữ tương thích trường `response` và `answer_bullets` để client cũ không vỡ.
- Không phá hợp đồng `POST /chat` hiện tại về mã lỗi 400/422/429; chỉ mở rộng schema.
- Không thay đổi định dạng `CHATBOT-SOURCE v1`; tài liệu nhị phân dùng chỉ mục riêng.
- Kho dữ liệu nhỏ (vài chục tệp, vài nghìn đoạn), một người dùng đồng thời.

**Scale/Scope**: 1 chatbot portfolio, 1 người vận hành, 10–100 tài liệu, ≤ 10 000 đoạn; không cần scale ngang.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md` vẫn là template chưa ratify (các placeholder `[PRINCIPLE_1_NAME]`, `[PROJECT_NAME]`, `[GOVERNANCE_RULES]`), nên không có gate bắt buộc nào. Đối chiếu với nguyên tắc dự án đang áp dụng:

| Gate | Trạng thái | Ghi chú |
|------|------------|---------|
| Đơn giản / YAGNI | PASS | Tái dùng Flask, Ollama embedding, FAISS, pandas, `manage_docs.py`; thêm 4 module nhỏ, không thêm service hay DB. |
| Thư viện/CLI độc lập, test được | PASS | `doc_loaders`, `doc_index`, `suggestions`, `assistant` tách khỏi Flask; CLI thao tác trực tiếp các module này. |
| Test-first (thích ứng) | PASS | Test quyết định 3 tầng, session, chunker, hash tăng dần và API được viết trước khi đổi luồng `app.py`. Test phụ thuộc Ollama được gate. |
| Kiểm thử tích hợp | PASS | Kịch bản: hỏi mơ hồ → gợi ý → "Câu hỏi khác" → chủ đề → mô tả; nạp 4 định dạng → hỏi → nguồn; nạp lại không đổi/đổi. |
| Quan sát được | PASS | `ask --debug` và log nạp hiển thị nguồn, chunk, hash, trạng thái bỏ qua/cập nhật; response có `sources`. |
| Không secret / local-first | PASS | Không thêm dịch vụ cloud, API key hay lưu trữ từ xa; tài liệu và vector ở lại đĩa cục bộ. |

**Kết quả**: PASS — không có vi phạm cần justification.

**Tái kiểm tra sau Phase 1**: PASS — thiết kế giữ nguyên kiến trúc Flask/Ollama/FAISS, không thêm dependency bắt buộc, tách rõ module và không phá API cũ.

### Tương thích với 005 (single source)

005 quy định `chatbot.txt` là nguồn **soạn sẵn** duy nhất và loại trừ xử lý nhị phân phức tạp. 006 giữ nguyên quy định đó cho Q&A, đồng thời bổ sung **chỉ mục phái sinh** từ các tệp tài liệu trong `data/`:

- Người vận hành vẫn chỉ sửa tay `chatbot.txt` cho câu hỏi/đáp.
- PDF/DOCX/XLSX/CSV không bị chép vào `chatbot.txt`; chúng được nạp bằng lệnh `ingest` vào `doc_index/`.
- Nếu cần rollback, xoá `doc_index/` là trở về hành vi 005.

## Project Structure

### Documentation (this feature)

```text
specs/006-tiered-suggest-ingest/
├── plan.md                  # This file
├── spec.md                  # Feature specification
├── research.md              # Phase 0 — decisions & rationale
├── data-model.md            # Phase 1 — entities, validation, state
├── quickstart.md            # Phase 1 — end-to-end validation guide
├── checklists/
│   └── requirements.md      # Spec quality checklist
└── contracts/
    ├── chat-api.md          # POST /chat + /chat/stream (answer/suggest/clarify)
    ├── manage-docs-cli.md   # ingest/list/remove + lệnh cũ
    └── doc-index-schema.md  # files.json/chunks.json/vectors.npz
```

### Source Code (repository root)

```text
backend/
├── app.py                      # SỬA: gọi assistant.handle(); thêm session_id/action; bỏ unknown
├── assistant.py                # MỚI: thang quyết định 3 tầng + dựng response
├── suggestions.py              # MỚI: gợi ý theo topic/keyword + embedding; menu clarify theo cấp
├── session.py                  # MỚI: SessionStore in-memory (TTL, shown_ids, level)
├── doc_index.py                # MỚI: nạp/lưu/tìm chỉ mục đoạn tài liệu; trả lời trích xuất
├── doc_loaders.py              # MỚI: trích + chunk theo định dạng (PDF/DOCX/XLSX/CSV/TXT/MD/DOC)
├── kb_engine.py                # SỬA: tách evaluate() trả top-1/top-2/candidates; giữ query() tương thích
├── chatbox.py                   # SỬA: giữ RAG cũ; thêm retrieve_rag_documents() + helper trích câu
├── documents.py                # GIỮ: lifecycle add/replace/delete/list của 002 (không đổi hành vi)
├── text_normalization.py       # GIỮ: normalize_text/normalize_query dùng chung
├── source_format.py            # GIỮ: parser CHATBOT-SOURCE v1
├── requirements.txt            # Không thêm dependency bắt buộc
│
├── doc_index/                  # SINH RA (gitignored): files.json, chunks.json, vectors.npz
├── data/                       # Nguồn: chatbot.txt + tài liệu nhị phân
├── scripts/
│   └── manage_docs.py          # SỬA: thêm ingest/remove; list hiển thị số đoạn
│
└── tests/
    ├── test_assistant.py        # MỚI: thang 3 tầng, không unknown, fallback
    ├── test_suggestions.py      # MỚI: keyword/embedding, shown_ids, menu cấp
    ├── test_session.py          # MỚI: TTL, tách phiên, reset
    ├── test_doc_loaders.py      # MỚI: 4 định dạng + PDF scan + CSV encoding
    ├── test_doc_index.py        # MỚI: chunk metadata, incremental hash, remove
    ├── test_doc_answers.py      # MỚI: trích câu + nguồn
    ├── test_chat_api.py         # SỬA: answer/suggest/clarify + action/session
    ├── test_chat_api_contract.py# SỬA: bỏ kỳ vọng unknown, giữ trường cũ
    ├── test_refusal.py          # SỬA: ngoài phạm vi → clarify, không "Tôi không biết"
    └── test_source_perf.py      # SỬA: thêm đo p50/p95 với embedder giả

frontend/
├── src/lib/chatClient.ts        # SỬA: gọi /chat, kiểu ChatResponse mới, session/action
├── src/lib/streamParser.ts      # SỬA: nhận event result (giữ chunk/done/error)
├── src/store/chatStore.ts       # SỬA: sessionId, suggestions/topics/actions, sendAction
├── src/components/Message/Message.tsx        # SỬA: render 3 loại phản hồi
├── src/components/Message/SuggestionList.tsx # MỚI
├── src/components/Message/TopicList.tsx      # MỚI
├── src/styles/app.css                        # SỬA: style nút gợi ý/chủ đề
└── src/**/*.test.tsx                         # SỬA/THÊM: tương tác nút, session
```

**Structure Decision**: Giữ nguyên mô hình web app một backend Flask + một SPA React. Luồng hội thoại và chỉ mục tài liệu nằm trong các module Python độc lập, không phụ thuộc Flask để dễ unit test. Frontend chỉ là lớp render/gửi hành động, không tính điểm hay giữ trạng thái làm rõ (trạng thái nằm ở server theo `session_id`).

## Complexity Tracking

Không có vi phạm constitution. Không cần justification.

## Implementation Notes

### 1. Thang quyết định trong `assistant.handle(question, session_id, action, topic)`

```text
normalize → nếu rỗng/không có chữ-số: validation (422 ở app.py)

action == "other"  → clarify cấp 1 (topics)
action == "topic"  → suggest câu chưa hiển thị trong topic
action == "rephrase" → clarify cấp 3 (ví dụ mô tả)

evaluate KB:
  norm, query_vec = embed một lần
  top1, top2, candidates = kb_engine.evaluate(norm, query_vec)

ambiguous = (số từ ≤ 3) or (top1 - top2 < 0.05) or (0.45 ≤ top1 < 0.78)

nếu top1 ≥ 0.78 và không ambiguous → answer từ KB
nếu ambiguous hoặc 0.45 ≤ top1 < 0.78:
    suggestions = suggestions.build(...)  # topic/keyword + embedding, bỏ shown_ids
    nếu ≥ 2 suggestions → suggest + action "other"
    nếu < 2 → clarify cấp 1
nếu top1 < 0.45:
    hits = doc_index.search(query_vec, k=5)
    nếu top hit ≥ 0.55 → answer trích xuất + sources
    nếu không → hits = chatbox.retrieve_rag_documents(...)  # kind: doc trong chatbot.txt (005)
                 nếu hit ≥ 0.55 → answer trích xuất + sources
                 nếu không → clarify cấp 1
```

- Không có nhánh trả `unknown`; lỗi nội bộ cũng hạ cấp về `clarify`.
- Nếu embedding lỗi: dùng fuzzy thuần trên câu hỏi KB (`normalize_query` + RapidFuzz) để tạo `suggest`; nếu vẫn không có → `clarify`. Không gọi LLM.
- `chatbox.retrieve_rag_documents` chỉ đọc chỉ mục RAG 005 (`kind: doc` trong `chatbot.txt`), trả excerpt + metadata, **không gọi LLM**. Đây là đường tương thích để nội dung doc đã migrate ở 005 không bị mất.

### 2. Response schema (mở rộng, giữ tương thích)

Mọi response có `type`, `session_id`, `response` (chuỗi để client cũ hiển thị) và tối thiểu một hành động nếu không phải `answer`.

```json
{
  "type": "answer",
  "session_id": "s-...",
  "score": 0.91,
  "response": "GPA hiện tại là 8.30/10.",
  "answer_bullets": ["GPA 8.30/10"],
  "source": "kb:gpa",
  "sources": []
}
```

```json
{
  "type": "suggest",
  "session_id": "s-...",
  "message": "Bạn muốn hỏi về mục tiêu nào?",
  "response": "Bạn muốn hỏi về mục tiêu nào?",
  "suggestions": [
    {"id": "goal_career", "question": "Mục tiêu nghề nghiệp của bạn là gì?", "score": 0.82}
  ],
  "actions": [{"id": "other", "label": "Câu hỏi khác"}]
}
```

```json
{
  "type": "clarify",
  "session_id": "s-...",
  "message": "Mình chưa chắc bạn muốn hỏi phần nào. Bạn chọn một mục bên dưới, hoặc mô tả thêm giúp mình nhé:",
  "response": "Mình chưa chắc bạn muốn hỏi phần nào...",
  "topics": ["Giới thiệu", "Kỹ năng", "Dự án"],
  "examples": ["Mục tiêu nghề nghiệp 3 năm tới"],
  "actions": [{"id": "rephrase", "label": "Hỏi lại cách khác"}]
}
```

- Request bổ sung tuỳ chọn: `session_id`, `action` (`other|topic|rephrase|retry`), `topic`.
- Khi có `action`, `message` được phép thiếu; khi không có `action`, giữ validation cũ (`message` bắt buộc, ≤ 200 ký tự).
- `source` là nhãn hiển thị; `sources` chứa cấu trúc `{file, page, sheet, row_start, row_end}` cho tài liệu.
- `suggestions[].id` là mã mục/câu hỏi ổn định để ghi `shown_ids`; không dùng nội dung câu làm khoá.

### 3. Phiên & nút "Câu hỏi khác"

- `SessionStore` dict `session_id → {shown_ids, last_query, level, touched_at}`; TTL mặc định 30 phút, tối đa 1 000 phiên, khoá `threading.Lock`.
- `session_id` do client tạo theo cuộc hội thoại và gửi kèm; server tạo nếu thiếu và luôn trả lại.
- Cấp 1: topics = chủ đề KB (duy nhất) + chủ đề tài liệu (`<file> — <heading>` hoặc tên tệp) nếu có; tối đa 8, ưu tiên chủ đề có nhiều câu/đoạn; khử trùng nhãn.
- Cấp 2: câu hỏi thuộc topic chưa có trong `shown_ids`; nếu topic là tài liệu, dùng heading làm câu mẫu. Khi chọn, đánh dấu đã hiển thị.
- Cấp 3: sau khi cạn hoặc bấm "Hỏi lại cách khác", trả 2–3 ví dụ mô tả tự do; không lặp vô hạn.
- `shown_ids` giới hạn 200 mục/phiên; phiên mới reset.

### 4. Chỉ mục tài liệu

- `doc_loaders.extract_blocks(path)` trả block có `text`, `page`, `sheet`, `row_start`, `row_end`, `heading`, `type`:
  - PDF: pypdf theo trang (giữ tương thích dependency); nếu trang không có text → báo scan. PyMuPDF là phương án thay thế nếu chất lượng trích kém.
  - DOCX: python-docx, gom paragraph theo `Heading 1..6`; bảng → dòng `cột: giá trị`; DOC cũ chuyển bằng LibreOffice nếu có.
  - XLSX: pandas + openpyxl, đọc **tất cả sheet**, header dòng đầu; mỗi dòng → câu `Sheet "X" | Cột: giá trị; ...`; gộp 5–10 dòng ngắn đến ~500 ký tự.
  - CSV: pandas; thử `utf-8-sig`, `utf-8`, `cp1258`, `latin-1`; lỗi → báo tên tệp và bỏ qua tệp.
  - TXT/MD: UTF-8; MD chia theo heading.
- `doc_loaders.chunk_blocks`: tiền tố `[tên-tệp > heading > trang/sheet]` + nội dung; cỡ 500/50; giữ text gốc để hiển thị, text chuẩn hoá để embed.
- `doc_index`:
  - `ingest_path(path)`: hash tệp; nếu trùng hash đã lưu → `skipped`; nếu đổi → so hash từng đoạn, tái dùng vector cho đoạn trùng, chỉ embed đoạn mới/đổi; ghi file tạm rồi `os.replace` cả ba tệp JSON/NPZ.
  - `search(query_vec, k)`: cosine trên vector chuẩn hoá; trả chunk + score; ngưỡng tài liệu 0.55.
  - `extractive_answer(hits)`: lấy top 1–2 chunk, tách câu, chấm mỗi câu bằng overlap token + RapidFuzz với câu hỏi, chọn 3–5 câu, khử trùng, giữ thứ tự xuất hiện; cắt tối đa ~600 ký tự.
  - `list_documents()`, `remove_document(name)`, `load()` khi khởi động.
- Chunk id ổn định: `sha1(file + vị trí + hash nội dung)`; lưu trong `chunks.json`.

### 5. API & frontend

- `app.py` thay chuỗi `kb_engine.query → ask_ai` bằng `assistant.handle(...)`.
- `/chat` trả JSON đầy đủ như trên. `/chat/stream` vẫn hỗ trợ: với `answer` phát `chunk` + `done`; với `suggest`/`clarify` phát `{"type":"result","data":<response>}` rồi `done`. Tương thích event cũ.
- `chatClient.sendMessage` gọi `/chat` (không stream) để nhận cấu trúc; giữ hàm stream làm fallback khi cờ `VITE_CHAT_STREAM=true` hoặc server trả 404/405.
- `chatStore`: thêm `sessionId` vào `Conversation`, `sendAction(action, payload)`; gán `suggestions/topics/examples/actions/sources` vào message assistant; bấm gợi ý gửi câu hỏi đã chọn như tin nhắn mới, bấm "Câu hỏi khác"/"Hỏi lại cách khác" gửi action tương ứng.
- `Message.tsx` render: bong bóng markdown (answer), danh sách nút kèm % (suggest), chip chủ đề + ví dụ (clarify); tất cả nút có `type="button"`, focus ring, `aria-label`.
- Không hiển thị câu "Mình không biết"; fallback cuối luôn là `clarify`.

### 6. CLI vận hành

```bash
python backend/scripts/manage_docs.py ingest ./backend/data
python backend/scripts/manage_docs.py ingest ./backend/data/cv.pdf
python backend/scripts/manage_docs.py list
python backend/scripts/manage_docs.py remove cv.pdf
```

- `ingest` nhận tệp hoặc thư mục; mặc định quét không đệ quy, thêm `--recursive` nếu cần. `--full` buộc embed lại toàn bộ (đổi model/chuẩn hoá/chunk).
- `list` giữ danh sách nguồn hiện có, bổ sung cột trạng thái chỉ mục + số đoạn.
- `remove` chỉ xoá khỏi chỉ mục; `delete` (002) vẫn xoá tệp nguồn.
- `--json` cho kết quả máy đọc; exit code 0 khi mọi tệp xử lý xong (kể cả skipped), 1 khi có lỗi vận hành, 2 khi có tệp lỗi trích xuất.

### 7. Cấu hình mới (mặc định)

| Biến | Mặc định | Ý nghĩa |
|------|----------|---------|
| `CHATBOT_KB_HIGH_THRESHOLD` | `0.78` | Trả lời trực tiếp từ KB |
| `CHATBOT_SUGGEST_THRESHOLD` | `0.45` | Sàn vùng gợi ý; dưới ngưỡng này mới tìm tài liệu |
| `CHATBOT_DOC_THRESHOLD` | `0.55` | Ngưỡng khớp đoạn tài liệu |
| `CHATBOT_AMBIGUITY_GAP` | `0.05` | Chênh top1–top2 bị coi là mơ hồ |
| `CHATBOT_MAX_SUGGESTIONS` | `4` | Số gợi ý tối đa |
| `CHATBOT_DOC_INDEX_DIR` | `backend/doc_index` | Nơi lưu chỉ mục tài liệu |
| `CHATBOT_DOC_MAX_BYTES` | `20971520` | Giới hạn mỗi tệp (20 MB) |
| `CHATBOT_SESSION_TTL` | `1800` | TTL phiên (giây) |
| `CHATBOT_SESSION_MAX` | `1000` | Số phiên tối đa |
| `ENABLE_LLM_SUMMARY` | `false` | Bật tóm tắt LLM tuỳ chọn |
| `CHATBOT_QUERY_REWRITE` | `off` | Qwen sửa chính tả chỉ khi bật rõ ràng |

`CHATBOT_KB_MID_THRESHOLD` cũ (0.55) không còn điều khiển vùng gợi ý; nếu biến này được đặt, ghi cảnh báo deprecated và bỏ qua để tránh vô tình thu hẹp vùng gợi ý. `CHATBOT_KB_MAX_SUGGESTIONS` cũ được đọc làm alias cho `CHATBOT_MAX_SUGGESTIONS` nếu biến mới không đặt.

### 8. Docker & vận hành

- `docker-compose.yml`: mount `./backend/data:/app/backend/data:ro` và `./backend/doc_index:/app/backend/doc_index`; thêm `CHATBOT_DOC_INDEX_DIR`.
- Nạp tài liệu trên host trước khi `docker compose up`, hoặc chạy `docker compose exec backend python backend/scripts/manage_docs.py ingest /app/backend/data`.
- `Dockerfile` không cần đổi nếu `backend/` đã được copy; chỉ cần đảm bảo `doc_index/` được tạo khi ingest.
- `.env.example` và README cập nhật bảng biến + quy trình nạp.

### 9. Thứ tự triển khai

1. `session.py` + `suggestions.py` + refactor `kb_engine.evaluate` + `assistant.py`; test thang 3 tầng.
2. Nối `app.py` + schema API + frontend structured rendering; test API/UI.
3. `doc_loaders.py` + `doc_index.py` + CLI `ingest/remove`; test 4 định dạng + incremental.
4. `extractive_answer` + nguồn; test câu trả lời tài liệu.
5. Đo p50/p95, chỉnh ngưỡng, cập nhật Docker/README.
