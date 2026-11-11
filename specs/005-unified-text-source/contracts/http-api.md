# Contract: Chat HTTP API (unchanged)

**Feature**: `005-unified-text-source` | **Version**: 1

Feature này không thay đổi endpoint, request hay response. Chỉ nguồn dữ liệu phía sau thay đổi.

## `POST /chat`

Request:

```http
POST /chat
Content-Type: application/json
```

```json
{ "message": "GPA hiện tại?" }
```

Response thành công (KB hoặc RAG):

```json
{
  "type": "answer",
  "score": 0.91,
  "response": "GPA hiện tại là 8.30 / 10.",
  "answer_bullets": null
}
```

Các `type` hiện có vẫn giữ nguyên:

- `answer`: có câu trả lời.
- `suggest`: gợi ý câu hỏi gần đúng.
- `unknown`: ngoài phạm vi, kèm `topics`.

Lỗi validation:

| HTTP | Điều kiện |
|---|---|
| `400` | Body không phải JSON object hoặc thiếu `message` |
| `422` | `message` rỗng hoặc > 200 ký tự |
| `429` | Vượt rate limit |
| `500` | Lỗi xử lý nội bộ |

## `POST /chat/stream`

Giữ nguyên `text/event-stream`:

```text
data: {"type":"chunk","content":"GPA "}

data: {"type":"done"}
```

Lỗi giữa chừng:

```text
data: {"type":"error","message":"Không thể tạo câu trả lời. Vui lòng thử lại."}
```

## Điều kiện dữ liệu

- API MUST trả lời từ cùng logic KB → khớp mờ → RAG như trước.
- Nếu tệp nguồn hợp nhất không hợp lệ lúc khởi động, backend MUST không phục vụ request và báo lỗi trong log.
- Nếu tệp nguồn đổi và không hợp lệ khi đang chạy, backend MUST giữ index cũ và ghi log lỗi; API không trả về nội dung từ tệp sai.
