# Contract: Chat HTTP API (v2 — KB Engine)

**Feature**: `004-self-intro-chatbot-api`
**Supersedes**: `specs/003-react-chat-ui/contracts/chat-api.md` (backward compatible — không breaking)

---

## Compatibility rules

- `POST /chat` giữ nguyên: request shape `{ "message": string }` và field `response` trong mọi response variant.
- Thêm các field mới (`type`, `score`, `answer_bullets`, `suggestions`, `topics`, `message`) không phá vỡ client cũ — chúng sẽ bị ignore.
- `POST /chat/stream` giữ nguyên event format; không có thay đổi.
- Không thêm auth, cookies, hay user identifier.
- CORS rule giữ nguyên (xem contract 003).

---

## `POST /chat`

### Request

```http
POST /chat HTTP/1.1
Content-Type: application/json

{ "message": "ban biet ngon ngu gi" }
```

**Validation**:
- `message` bắt buộc, string.
- Sau `.strip()` không rỗng → HTTP 422 nếu rỗng.
- Độ dài sau `.strip()` ≤ 200 ký tự → HTTP 422 nếu vượt.
- Input chứa từ trong profanity list → HTTP 200 với `type: "unknown"` (không log nội dung).

---

### Response variants

#### type: "answer" — khớp đủ cao (hybrid score ≥ 0.78)

```json
{
  "type": "answer",
  "score": 0.91,
  "response": "Python, JavaScript / TypeScript, SQL",
  "answer_bullets": ["Python", "JavaScript / TypeScript", "SQL"]
}
```

- `response`: chuỗi đầy đủ (join bullets bằng `", "` nếu có bullets). Dùng cho backward compat.
- `answer_bullets`: mảng string nếu kb.json mục đó có `answer_bullets`, ngược lại `null`.
- `score`: hybrid score [0.0–1.0], làm tròn 2 chữ số.

#### type: "suggest" — vùng trung gian (0.55 ≤ score < 0.78)

```json
{
  "type": "suggest",
  "response": "Ý bạn có phải là một trong những câu hỏi này không?",
  "suggestions": [
    { "question": "Bạn biết những ngôn ngữ lập trình nào?", "score": 0.68 },
    { "question": "Tech stack của bạn là gì?",               "score": 0.61 }
  ]
}
```

- `suggestions`: 1–3 mục, sắp xếp score giảm dần.
- `response`: thông báo cố định, dùng cho client cũ hiển thị text thuần.

#### type: "unknown" — ngoài phạm vi (score < 0.55) hoặc profanity

```json
{
  "type": "unknown",
  "response": "Mình chưa có thông tin về điều này.",
  "message": "Mình chưa có thông tin về điều này. Bạn có thể hỏi về các chủ đề sau:",
  "topics": ["Ngôn ngữ lập trình", "Học tập", "Dự án", "Liên hệ"]
}
```

- `topics`: danh sách field `topic` từ tất cả KnowledgeItem trong kb.json (không trùng lặp).

---

### Error responses

| Status | Body | Điều kiện |
|--------|------|-----------|
| 400 | `{ "error": "..." }` | JSON không hợp lệ hoặc thiếu field `message` |
| 422 | `{ "error": "..." }` | `message` rỗng hoặc > 200 ký tự |
| 429 | `{ "error": "Rate limit exceeded" }` | Vượt rate limit (60 req/phút/IP) |
| 500 | `{ "error": "..." }` | Lỗi backend / model không khả dụng |

---

## `POST /chat/stream`

Không thay đổi format so với contract 003. KB Engine trả về kết quả đồng bộ (không stream thêm); nếu KB match thì emit 1 `chunk` + `done`. Nếu fallback sang RAG, stream như cũ.

---

## Fallback chain

```
KB Engine (kb.json)
    │  no match (score < 0.55 AND kb không cover topic)
    ▼
RAG pipeline (FAISS + Ollama) — hiện tại
    │  không tìm thấy đoạn liên quan
    ▼
"Tôi không biết" (REFUSAL hiện tại)
```

Khi fallback sang RAG, `type` trong response = `"answer"` (backward compat, giữ nguyên `response` field từ RAG).

---

## kb.json schema (tham chiếu)

Xem `data-model.md` § 1 cho full schema. Điểm quan trọng với client:
- `answer_bullets` present và non-null → frontend NÊN render gạch đầu dòng.
- `suggestions[].question` là string đã có thể gửi thẳng lại `/chat` → client render thành chip bấm được.

---

## Non-goals (feature 004)

- Không thêm conversation history.
- Không thêm `/reload` endpoint (reload qua restart server).
- Không streaming cho KB engine results (đủ nhanh để trả sync).
- Không thay đổi `/chat/stream` event format.
