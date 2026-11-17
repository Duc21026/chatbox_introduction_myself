# Contract — Chat API

**Feature**: `008-vercel-cloudflare-deploy`
**Endpoints**: `POST /api/chat` (Vercel) và `POST /chat` (Docker/legacy)
**Content-Type**: `application/json`

Hai endpoint dùng **cùng handler và cùng schema**. Frontend trên Vercel gọi
`/api/chat` cùng domain; Docker/nginx tiếp tục proxy `/chat`.

---

## Request

| Field | Type | Required | Mô tả |
|-------|------|----------|-------|
| `message` | string | có, trừ khi `action` được đặt | Câu hỏi, tối đa 200 ký tự sau khi trim |
| `session_id` | string | không | ID phiên; server tạo mới nếu thiếu |
| `action` | `other` \| `topic` \| `rephrase` \| `retry` | không | Hành động từ gợi ý/menu |
| `topic` | string | khi `action="topic"` | Chủ đề đã chọn, tối đa 120 ký tự |

Ví dụ:

```json
{
  "message": "GPA của bạn là bao nhiêu?",
  "session_id": "s-123"
}
```

---

## Response — thành công `200`

```json
{
  "type": "answer",
  "session_id": "s-123",
  "score": 0.91,
  "response": "GPA tích lũy của mình là 8.51 / 10 ...",
  "message": null,
  "answer_bullets": null,
  "source": "kb:gpa",
  "sources": [],
  "suggestions": [],
  "topics": [],
  "examples": [],
  "actions": []
}
```

| Field | Type | Mô tả |
|-------|------|-------|
| `type` | `answer` \| `suggest` \| `clarify` | Loại phản hồi; **không bao giờ** `unknown` |
| `session_id` | string | Phiên để client gửi lại |
| `score` | number | Điểm khớp cao nhất (0–1), có thể vắng ở clarify |
| `response` | string | Nội dung chính |
| `message` | string \| null | Câu dẫn cho suggest/clarify |
| `answer_bullets` | string[] \| null | Gạch đầu dòng nếu có |
| `source` | string \| null | Nguồn (ví dụ `kb:gpa`) |
| `sources` | object[] | Nguồn tài liệu (rỗng trong phạm vi qa-only) |
| `suggestions` | object[] | Gợi ý câu hỏi; mỗi mục có `id`, `question`, `score` |
| `topics` | string[] | Menu chủ đề cho clarify |
| `examples` | string[] | Câu hỏi ví dụ |
| `actions` | object[] | Nút hành động, ví dụ `{"id":"other","label":"Câu hỏi khác"}` |

### Bất biến

- `type=suggest` → `suggestions.length >= 2` và luôn có action `other`.
- `type=clarify` → có `topics` hoặc `examples`; action có `rephrase`/`other`.
- Với câu hỏi hợp lệ, lỗi provider embedding **không** được biến thành HTTP 500 hoặc
  response "không biết"; phải rơi về `suggest`/`clarify`.

---

## Lỗi

| Status | Khi nào | Body |
|--------|---------|------|
| `400` | JSON không hợp lệ; `action`/`topic` sai kiểu; thiếu `topic` khi action=`topic` | `{"error": "..."}` |
| `422` | `message` rỗng hoặc > 200 ký tự; `topic` > 120 ký tự | `{"error": "..."}` |
| `429` | Vượt 30 request/60 giây/IP (WAF) hoặc Flask-Limiter | `{"error": "Rate limit exceeded. Thử lại sau."}` |
| `405` | Sai method | — |
| `500` | Lỗi nội bộ không lường trước | `{"error": "..."}` |

**Lưu ý**: `500` chỉ dành cho lỗi thật sự ngoài luồng fallback; test T4 xác nhận provider
lỗi không tạo 500.

---

## Streaming

`POST /api/chat` trong phạm vi này chỉ trả JSON. `POST /chat/stream` (Docker/legacy) vẫn giữ
hợp đồng SSE hiện có; Vercel function không expose stream ở bản này.

---

## Kiểm thử hợp đồng

- `backend/tests/test_chat_api_contract.py` giữ nguyên shape.
- Thêm test cho `api/chat.py`: import app không kéo `langchain`/`faiss`; gọi test client
  với câu hỏi và provider lỗi → `type` thuộc ba giá trị hợp lệ.
- Frontend `chatClient.test.ts` cập nhật URL thành `/api/chat` khi `VITE_API_BASE_URL=/api`.
