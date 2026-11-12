# Data Model: Luôn gợi ý & nạp tài liệu đa định dạng

**Feature**: `006-tiered-suggest-ingest` | **Date**: 2026-11-12 | **Spec**: [spec.md](spec.md) | **Research**: [research.md](research.md)

Mọi dữ liệu dưới đây là mô tả logic; không ràng buộc tên lớp Python cụ thể.

---

## 1. KnowledgeItem (mục tri thức soạn sẵn)

Kế thừa `KBItem` từ `source_format.py` / `CHATBOT-SOURCE v1`.

| Field | Kiểu | Bắt buộc | Ràng buộc |
|-------|------|----------|-----------|
| `id` | string | Có | Duy nhất toàn nguồn; `[a-z0-9][a-z0-9_-]{0,63}` |
| `topic` | string | Có | 1–120 ký tự, không rỗng |
| `questions` | string[] | Có | ≥ 1; mỗi câu 1–200 ký tự |
| `answer` | string \| null | Có nếu không có `answer_bullets` | ≤ 4 000 ký tự |
| `answer_bullets` | string[] \| null | Có nếu không có `answer` | Mỗi bullet ≤ 300 ký tự |
| `keywords` | string[] \| null | Không | Không có trong `CHATBOT-SOURCE v1`; nếu thiếu thì suy ra từ `topic` + `questions` |

**Quan hệ**: 1 `KnowledgeItem` chứa N câu hỏi mẫu; N câu hỏi × embedding tạo thành ma trận chấm điểm KB.

**Bất biến**:
- Không tồn tại hai item cùng `id`.
- `id` dùng trong `suggestions[].id` và `shown_ids`.
- Item không có cả `answer` lẫn `answer_bullets` bị loại khỏi KB Engine (log warning, không làm hỏng tệp).

---

## 2. DocumentFile (tệp tài liệu đã nạp)

Lưu trong `doc_index/files.json`, khoá theo `file` (tên tệp tương đối trong `data/`).

| Field | Kiểu | Bắt buộc | Ràng buộc |
|-------|------|----------|-----------|
| `file` | string | Có | Tên tệp đơn, không chứa `/`, `\`, `..`, `:` |
| `type` | enum | Có | `pdf`, `docx`, `xlsx`, `csv`, `txt`, `md`, `doc` |
| `file_hash` | string | Có | SHA-256 hex của toàn bộ bytes |
| `size_bytes` | integer | Có | 0 < size ≤ `CHATBOT_DOC_MAX_BYTES` |
| `status` | enum | Có | `indexed`, `skipped`, `failed`, `removed` |
| `chunk_ids` | string[] | Có | Danh sách chunk thuộc tệp; rỗng nếu `failed` |
| `ingested_at` | ISO-8601 string | Có | Lần nạp thành công gần nhất |
| `error` | string \| null | Không | Chỉ khi `failed` |
| `mtime_ns` | integer | Có | Thời điểm sửa tệp lúc nạp (hỗ trợ chẩn đoán) |

**Bất biến**:
- `file_hash` trùng với lần nạp trước → `status = skipped`, không đọc lại nội dung.
- Mọi `chunk_id` trong `chunk_ids` phải tồn tại trong `chunks.json` và `vectors.npz`.
- Xoá tệp khỏi chỉ mục → xoá `DocumentFile` + toàn bộ `DocumentChunk` tương ứng.

---

## 3. DocumentChunk (đoạn tài liệu)

Lưu trong `doc_index/chunks.json`; vector tương ứng trong `vectors.npz`.

| Field | Kiểu | Bắt buộc | Ràng buộc |
|-------|------|----------|-----------|
| `chunk_id` | string | Có | Ổn định; `sha1(file + vị trí + content_hash)` |
| `file` | string | Có | Trỏ tới `DocumentFile.file` |
| `type` | enum | Có | Như `DocumentFile.type` |
| `page` | integer \| null | Không | 1-based với PDF |
| `sheet` | string \| null | Không | Tên sheet với XLSX/CSV |
| `row_start` | integer \| null | Không | Dòng bắt đầu (1-based, tính cả header) |
| `row_end` | integer \| null | Không | Dòng kết thúc |
| `heading` | string \| null | Không | Heading gần nhất (DOCX/MD/PDF nếu có) |
| `text` | string | Có | Văn bản gốc để hiển thị; không chứa tiền tố ngữ cảnh |
| `embed_text` | string | Có | `normalize_text(text, lowercase=False)` + tiền tố ngữ cảnh |
| `content_hash` | string | Có | SHA-256 của `embed_text` sau chuẩn hoá |
| `char_count` | integer | Có | Độ dài `text`; dùng cho thống kê |

**Ví dụ**:

```json
{
  "chunk_id": "cv_pdf_p2_c3_9f2a1b",
  "file": "CV.pdf",
  "type": "pdf",
  "page": 2,
  "sheet": null,
  "row_start": null,
  "row_end": null,
  "heading": "Kinh nghiệm",
  "text": "2022–nay: Backend developer tại Công ty A...",
  "embed_text": "[CV.pdf > Kinh nghiệm > trang 2] 2022–nay: Backend developer tại Công ty A...",
  "content_hash": "9f2a1b...",
  "char_count": 412
}
```

**Bất biến**:
- `text` không rỗng; chunk rỗng bị loại.
- `chunk_id` duy nhất toàn chỉ mục.
- `(file, page, sheet, row_start, heading)` phải phản ánh đúng vị trí thực tế để trích dẫn.

### Quan hệ

```text
DocumentFile 1 ─── N DocumentChunk
DocumentChunk 1 ─── 1 vector trong vectors.npz
DocumentChunk N ─── 1 DocumentFile (qua file)
```

---

## 4. DocumentIndex (kho phái sinh)

| Field | Kiểu | Mô tả |
|-------|------|-------|
| `files` | map<string, DocumentFile> | Trạng thái từng tệp |
| `chunks` | map<string, DocumentChunk> | Metadata đoạn |
| `vectors` | map<string, float32[] L2-normalized> | Vector theo `chunk_id` |
| `index` | in-memory FAISS `IndexFlatIP` | Dựng lại khi khởi động hoặc sau ingest |
| `loaded_at` | timestamp | Lần nạp gần nhất |

**Bất biến**:
- Ba tập khoá `files`/`chunks`/`vectors` luôn đồng bộ sau mỗi thao tác ghi.
- Nếu một tệp lỗi, các tệp khác và chỉ mục cũ vẫn nguyên vẹn.
- Chỉ mục không chứa chunk của tệp `failed`/`removed`.

---

## 5. MatchCandidate (ứng viên khớp)

| Field | Kiểu | Mô tả |
|-------|------|-------|
| `source` | enum | `kb`, `doc` hoặc `rag` (bản ghi `kind: doc` của 005) |
| `ref_id` | string | `item_id` (KB) hoặc `chunk_id` (tài liệu) |
| `display` | string | Câu hỏi (KB) hoặc đoạn trích (tài liệu) |
| `score` | float 0–1 | Điểm tổng hợp |
| `cosine` | float \| null | Thành phần ngữ nghĩa |
| `fuzzy` | float \| null | Thành phần chuỗi |
| `topic` | string \| null | Chủ đề (KB) |
| `meta` | object | `file/page/sheet/row/heading` với tài liệu |

---

## 6. QueryEvaluation (kết quả chấm một câu hỏi)

| Field | Kiểu | Mô tả |
|-------|------|-------|
| `norm` | string | Câu hỏi đã chuẩn hoá; rỗng nếu không tìm được chữ-số |
| `word_count` | integer | Số token sau chuẩn hoá |
| `query_vec` | float32[] \| null | Vector câu hỏi; null nếu embedding lỗi |
| `top1` | float | Điểm cao nhất |
| `top2` | float | Điểm cao thứ hai |
| `candidates` | MatchCandidate[] | Ứng viên KB, sắp giảm dần |
| `ambiguous` | boolean | Theo luật D1/spec |
| `answer_item` | KnowledgeItem \| null | Item tương ứng top1 nếu đủ ngưỡng |
| `doc_hits` | MatchCandidate[] | Ứng viên tài liệu (chỉ khi cần) |
| `rag_hits` | MatchCandidate[] | Ứng viên `kind: doc` từ 005 (chỉ khi `doc_hits` không đạt) |

**Luật `ambiguous`** (thoả một):
1. `word_count ≤ 3`, hoặc
2. `top1 - top2 < CHATBOT_AMBIGUITY_GAP`, hoặc
3. `CHATBOT_SUGGEST_THRESHOLD ≤ top1 < CHATBOT_KB_HIGH_THRESHOLD`.

---

## 7. ChatRequest

```json
{
  "message": "mục tiêu",
  "session_id": "s-3f1c...",
  "action": "other | topic | rephrase | retry | null",
  "topic": "Kỹ năng"
}
```

| Field | Bắt buộc | Ràng buộc |
|-------|----------|-----------|
| `message` | Có nếu không có `action` | Chuỗi, 1–200 ký tự sau trim; không rỗng |
| `session_id` | Không | Chuỗi ≤ 100 ký tự; server tạo mới nếu thiếu/không hợp lệ |
| `action` | Không | Một trong `other`, `topic`, `rephrase`, `retry` |
| `topic` | Có nếu `action = topic` | Nhãn topic có trong menu gần nhất của phiên |

**Lỗi**:
- `400`: body không phải JSON object; thiếu `message` khi không có `action`; `action = topic` thiếu `topic`.
- `422`: `message` rỗng/toàn khoảng trắng hoặc > 200 ký tự.
- `429`: vượt rate limit.

---

## 8. ChatResponse (union)

Mọi response có:

| Field | Kiểu | Ghi chú |
|-------|------|---------|
| `type` | `answer` \| `suggest` \| `clarify` | Không có `unknown` |
| `session_id` | string | Luôn trả về |
| `response` | string | Chuỗi hiển thị tương thích client cũ |
| `score` | float \| null | Chỉ `answer` |
| `answer_bullets` | string[] \| null | Chỉ `answer` |
| `source` | string \| null | Nhãn nguồn, ví dụ `kb:gpa` hoặc `CV.pdf, trang 2` |
| `sources` | SourceRef[] | Nguồn tài liệu chi tiết |
| `message` | string \| null | Câu dẫn cho `suggest`/`clarify` |
| `suggestions` | Suggestion[] | Chỉ `suggest` |
| `topics` | string[] | Chỉ `clarify` cấp 1/2 |
| `examples` | string[] | Chỉ `clarify` cấp 3 (và có thể cấp 1) |
| `actions` | Action[] | Nút hành động; bắt buộc với `suggest`/`clarify` |

### 8.1 AnswerResponse

```json
{
  "type": "answer",
  "session_id": "s-...",
  "score": 0.91,
  "response": "GPA hiện tại là 8.30/10.",
  "answer_bullets": ["GPA 8.30/10"],
  "source": "kb:gpa",
  "sources": [],
  "actions": []
}
```

- Nguồn KB: `source = "kb:<item_id>"`.
- Nguồn tài liệu: `source = "<file>, trang <page>"` hoặc `"<file>, sheet <sheet>, dòng <a>–<b>"`; `sources` chứa cấu trúc.
- `score` là điểm top1; với tài liệu là điểm chunk cao nhất.

### 8.2 SuggestResponse

```json
{
  "type": "suggest",
  "session_id": "s-...",
  "message": "Bạn muốn hỏi về mục tiêu nào?",
  "response": "Bạn muốn hỏi về mục tiêu nào?",
  "suggestions": [
    {"id": "goal_career", "question": "Mục tiêu nghề nghiệp của bạn là gì?", "score": 0.82},
    {"id": "goal_bot", "question": "Mục tiêu của chatbot này là gì?", "score": 0.74}
  ],
  "actions": [{"id": "other", "label": "Câu hỏi khác"}]
}
```

- 2–4 suggestions, không trùng `id`, không nằm trong `shown_ids` của phiên.
- Luôn có action `other`.

### 8.3 ClarifyResponse

```json
{
  "type": "clarify",
  "session_id": "s-...",
  "message": "Mình chưa chắc bạn muốn hỏi phần nào. Bạn chọn một mục bên dưới, hoặc mô tả thêm giúp mình nhé:",
  "response": "Mình chưa chắc bạn muốn hỏi phần nào...",
  "topics": ["Giới thiệu", "Kỹ năng", "Dự án"],
  "examples": ["Mục tiêu nghề nghiệp 3 năm tới", "Bạn muốn làm vị trí nào?"],
  "actions": [{"id": "rephrase", "label": "Hỏi lại cách khác"}]
}
```

- Cấp 1: có `topics` (≥ 3 nếu dữ liệu đủ), `examples`, action `rephrase`.
- Cấp 2: có `topics` (topic đang chọn + quay lại) hoặc chỉ `suggestions` thuộc topic.
- Cấp 3: `topics = []`, `examples` 2–3 câu mẫu, action `rephrase`.

### 8.4 Cấu trúc con

**Suggestion**: `{ "id": string, "question": string, "score": float }`
- `id`: định danh **theo từng câu hỏi** để `shown_ids` không ẩn oan câu khác cùng item:
  - item có đúng 1 câu → `item_id` (ví dụ `goal_career`);
  - item có nhiều câu → `item_id#<sha1(normalized_question)[:8]>`;
  - câu KB không gắn item → `kb:<sha1(normalized_question)[:12]>`;
  - câu sinh từ tài liệu → `doc:<file>#<heading>`.
- `score`: 0–1, làm tròn 2 chữ số.

**Action**: `{ "id": "other" | "rephrase" | "topic" | "retry", "label": string, "topic"?: string }`

**SourceRef**: `{ "file": string, "page"?: int, "sheet"?: string, "row_start"?: int, "row_end"?: int, "heading"?: string }`

---

## 9. SessionState

Lưu trong bộ nhớ, khoá theo `session_id`.

| Field | Kiểu | Ràng buộc |
|-------|------|-----------|
| `session_id` | string | Duy nhất; do client hoặc server tạo |
| `shown_ids` | string[] | Tối đa 200; không trùng; dùng để loại gợi ý lặp |
| `last_query` | string \| null | Câu hỏi gần nhất (đã chuẩn hoá hoặc gốc) |
| `level` | integer | `1`, `2`, `3` |
| `last_topics` | string[] | Menu gần nhất, để xác thực `action = topic` |
| `last_candidates` | string[] | Ứng viên gần nhất (id) để phục vụ "Câu hỏi khác" |
| `touched_at` | timestamp | Dùng cho TTL |

### State machine

```text
                 ┌──────────────┐
suggest ──other──►│ clarify L1   │
                 └──────┬───────┘
                        │ chọn topic
                        ▼
                 ┌──────────────┐
                 │ clarify L2   │──chọn câu──► answer
                 └──────┬───────┘
                        │ cạn câu / other
                        ▼
                 ┌──────────────┐
                 │ clarify L3   │──mô tả mới──► (quay lại thang chính)
                 └──────────────┘
```

- `level` tăng khi người dùng bấm "Câu hỏi khác"/"Hỏi lại cách khác".
- Bất kỳ tin nhắn mới không phải action → reset `level = 1`, giữ `shown_ids` (để không lặp trong phiên).
- Phiên hết TTL hoặc `resetSession` → xoá toàn bộ.

---

## 10. IngestReport (kết quả một lần nạp)

| Field | Kiểu | Mô tả |
|-------|------|-------|
| `started_at` | timestamp | Bắt đầu |
| `finished_at` | timestamp | Kết thúc |
| `added` | `FileResult[]` | Tệp mới được thêm |
| `updated` | `FileResult[]` | Tệp thay đổi được cập nhật |
| `skipped` | `FileResult[]` | Tệp không đổi |
| `failed` | `FileResult[]` | Tệp lỗi (kèm `error`) |
| `stats` | object | `files_total`, `chunks_added`, `chunks_reused`, `chunks_removed`, `embeddings_computed` |

**FileResult**: `{ "file": string, "type": string, "status": "added|updated|skipped|failed", "chunks": int, "error"?: string }`

**Bất biến**:
- `embeddings_computed` chỉ đếm chunk thực sự gọi embedder.
- Tệp `skipped` không đóng góp `chunks_reused` (không đọc lại).
- Tệp `failed` không thay đổi `files.json` cũ của chính nó (nếu đã từng nạp thành công).

---

## 11. Luồng trạng thái quyết định (tóm tắt)

```text
request
  │
  ├─ action=other/topic/rephrase ──► session handler ──► suggest/clarify
  │
  └─ message
       ├─ norm rỗng ──► 422 (app.py)
       ├─ top1 ≥ 0.78 và !ambiguous ──► answer (KB)
       ├─ ambiguous hoặc 0.45 ≤ top1 < 0.78
       │     ├─ suggestions ≥ 2 ──► suggest
       │     └─ suggestions < 2 ──► clarify L1
       └─ top1 < 0.45
             ├─ doc_index hit ≥ 0.55 ──► answer (doc + sources)
             ├─ rag 005 hit ≥ 0.55 ──► answer (doc + sources)
             └─ không ──► clarify L1
```
