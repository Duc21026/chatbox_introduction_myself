# Data Model: Self-Introduction Chatbot API

**Feature**: `004-self-intro-chatbot-api`
**Date**: 2026-11-10

---

## 1. KnowledgeItem — đơn vị kiến thức trong kb.json

```text
KnowledgeItem
├── id            : string         — unique slug, e.g. "skills", "gpa"
├── topic         : string         — tên chủ đề hiển thị, e.g. "Kỹ năng lập trình"
├── questions     : string[]       — 3–5 cách hỏi khác nhau (tiếng Việt tự nhiên)
├── answer        : string | null  — câu trả lời ngắn (dùng khi answer_bullets rỗng)
└── answer_bullets: string[] | null — danh sách ý (dùng khi câu trả lời có nhiều ý)
```

**Validation rules**:
- `id`: bắt buộc, slug `[a-z0-9_-]+`, duy nhất trong file.
- `topic`: bắt buộc, không rỗng.
- `questions`: bắt buộc, ≥ 1 phần tử, mỗi câu ≤ 200 ký tự.
- `answer` hoặc `answer_bullets` phải có ít nhất một cái không rỗng.
- Mỗi bullet trong `answer_bullets` ≤ 100 ký tự (≤ 15 từ).

**File**: `backend/kb.json` (ví dụ):

```json
[
  {
    "id": "languages",
    "topic": "Ngôn ngữ lập trình",
    "questions": [
      "Bạn biết những ngôn ngữ lập trình nào?",
      "Tech stack của bạn là gì?",
      "Bạn dùng ngôn ngữ gì?"
    ],
    "answer": null,
    "answer_bullets": ["Python", "JavaScript / TypeScript", "SQL"]
  },
  {
    "id": "gpa",
    "topic": "Học tập",
    "questions": [
      "GPA của bạn là bao nhiêu?",
      "Điểm trung bình của bạn?",
      "Kết quả học tập?"
    ],
    "answer": "GPA hiện tại là 8.30 / 10 (62 tín chỉ tích lũy).",
    "answer_bullets": null
  }
]
```

---

## 2. EmbeddingCache — cache embedding tính sẵn

```text
EmbeddingCache (file: backend/embeddings_cache.npz)
├── kb_hash       : string (MD5 hex)  — hash của nội dung kb.json
├── questions     : string[]          — danh sách câu hỏi mẫu đã chuẩn hóa
├── item_indices  : int[]             — index KnowledgeItem tương ứng mỗi câu
└── embeddings    : float32[N × D]    — ma trận embedding (numpy)
```

**Invalidation**: Khi khởi động, tính MD5 của `kb.json`. Nếu khác `kb_hash` trong cache → build lại toàn bộ.

**File**: `backend/embeddings_cache.npz` (numpy compressed binary, không commit vào git).

---

## 3. QueryCache — LRU cache response

```text
QueryCache (in-process, cachetools.LRUCache)
├── key   : string   — câu hỏi đã qua normalize_query() (lowercase, NFC, teencode)
└── value : ChatResponse — response JSON đã tính
```

**Capacity**: mặc định 512 mục, cấu hình qua `CHATBOT_QUERY_CACHE_SIZE`.

---

## 4. ChatRequest — đầu vào API

```text
ChatRequest
└── message : string   — câu hỏi người dùng, 1–200 ký tự (sau strip)
```

**Validation**:
- Phải là string.
- Sau `.strip()` không được rỗng (HTTP 422).
- Độ dài sau strip ≤ 200 ký tự (HTTP 422).

---

## 5. ChatResponse — đầu ra API (union of 3 variants)

### 5a. AnswerResponse

```text
AnswerResponse
├── type           : "answer"
├── score          : float          — hybrid score [0.0–1.0]
├── response       : string         — câu trả lời đầy đủ (backward compat)
└── answer_bullets : string[] | null — danh sách ý nếu có
```

### 5b. SuggestResponse

```text
SuggestResponse
├── type        : "suggest"
├── response    : string        — thông báo ngắn ("Ý bạn có phải là…?") cho client cũ
└── suggestions : Suggestion[]  — top 1–3 gợi ý
```

```text
Suggestion
├── question : string   — câu hỏi mẫu gốc (chưa normalize)
└── score    : float    — hybrid score của gợi ý này
```

### 5c. UnknownResponse

```text
UnknownResponse
├── type     : "unknown"
├── response : string    — thông báo lịch sự cho client cũ
├── message  : string    — thông báo chi tiết hơn (giống response, có thể khác)
└── topics   : string[]  — danh sách topic từ kb.json (field `topic`)
```

---

## 6. State transitions — luồng xử lý một request

```text
ChatRequest.message
        │
        ▼
[1] Validation (độ dài, không rỗng, profanity filter)
        │  invalid → HTTP 422
        ▼
[2] normalize_query()
    (NFC, lowercase, teencode, emoji strip, từ đệm)
        │
        ▼
[3] QueryCache lookup
        │  HIT  → return cached ChatResponse
        │  MISS ↓
        ▼
[4] KB Engine: hybrid_score(query) for each question in kb.json
        │
        ├─ score ≥ HIGH (0.78) ──────────────────► AnswerResponse  → cache → return
        │
        ├─ MID ≤ score < HIGH (0.55–0.78)
        │       │
        │       ▼
        │   [4a] _rewrite_query() via Qwen (sửa chính tả)
        │       │
        │       ▼
        │   [4b] hybrid_score(rewritten_query)
        │       │
        │       ├─ score ≥ HIGH ────────────────► AnswerResponse  → cache → return
        │       └─ score < HIGH ───────────────► SuggestResponse (top 3) → cache → return
        │
        └─ score < MID (0.55) ──────────────────► UnknownResponse → cache → return
```

---

## 7. File layout — nguồn dữ liệu runtime

| File | Mô tả | Git |
|---|---|---|
| `backend/kb.json` | Danh sách Q&A có cấu trúc | ✅ commit |
| `backend/embeddings_cache.npz` | Embedding matrix tính sẵn | ❌ gitignore |
| `backend/qa.txt` | Q&A đơn giản hiện tại (giữ nguyên) | ✅ commit |
