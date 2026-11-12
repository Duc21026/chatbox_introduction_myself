# Contract: Chat HTTP API (answer / suggest / clarify)

**Feature**: `006-tiered-suggest-ingest` | **Version**: 2 | **Supersedes**: 005 `http-api.md` (chỉ phần response types)

## 1. Nguyên tắc

- `POST /chat` là endpoint chuẩn, trả đầy đủ cấu trúc để client render nút.
- Không còn `type: "unknown"`. Mọi phản hồi là `answer`, `suggest` hoặc `clarify`.
- Giữ các trường `response` và `answer_bullets` để client cũ không vỡ.
- Mọi response có `session_id`; client gửi lại `session_id` ở request sau để giữ trạng thái `shown_ids`/`level`.
- Mã lỗi 400/422/429/500 giữ nguyên như 005.

## 2. `POST /chat`

### Request

```http
POST /chat
Content-Type: application/json
```

```json
{
  "message": "mục tiêu",
  "session_id": "s-3f1c9a",
  "action": null,
  "topic": null
}
```

| Field | Bắt buộc | Mô tả |
|-------|----------|-------|
| `message` | Có nếu không có `action` | Câu hỏi, 1–200 ký tự sau trim |
| `session_id` | Không | Nếu thiếu/không hợp lệ, server tạo mới |
| `action` | Không | `other` \| `topic` \| `rephrase` \| `retry` |
| `topic` | Có nếu `action = topic` | Nhãn topic từ response `clarify` gần nhất |

**Hành động**:

| `action` | Ý nghĩa | Server trả |
|---|---|---|
| `other` | "Câu hỏi khác" / "Không đúng ý tôi" | `clarify` cấp 1 (menu chủ đề) |
| `topic` + `topic` | Chọn chủ đề | `suggest` các câu chưa hiển thị trong chủ đề; cạn → `clarify` cấp 3 |
| `rephrase` | "Hỏi lại cách khác" | `clarify` cấp 3 với ví dụ |
| `retry` | Gửi lại câu hỏi gần nhất | Chạy lại thang chính với `last_query` |

### Response chung

| Field | Kiểu | Có ở |
|-------|------|------|
| `type` | `answer` \| `suggest` \| `clarify` | Tất cả |
| `session_id` | string | Tất cả |
| `response` | string | Tất cả (bong bóng chữ) |
| `score` | number \| null | `answer` |
| `answer_bullets` | string[] \| null | `answer` |
| `source` | string \| null | `answer` |
| `sources` | SourceRef[] | `answer` (tài liệu) |
| `message` | string \| null | `suggest`, `clarify` |
| `suggestions` | Suggestion[] | `suggest` |
| `topics` | string[] | `clarify` |
| `examples` | string[] | `clarify` |
| `actions` | Action[] | `suggest`, `clarify` |

### 2.1 `answer`

```json
{
  "type": "answer",
  "session_id": "s-3f1c9a",
  "score": 0.91,
  "response": "GPA hiện tại là 8.30/10.",
  "answer_bullets": ["GPA 8.30/10"],
  "source": "kb:gpa",
  "sources": [],
  "actions": []
}
```

Trả lời từ tài liệu:

```json
{
  "type": "answer",
  "session_id": "s-3f1c9a",
  "score": 0.71,
  "response": "- 2022–nay: Backend developer tại Công ty A\n- Xây dựng API với Python, FastAPI",
  "answer_bullets": [
    "2022–nay: Backend developer tại Công ty A",
    "Xây dựng API với Python, FastAPI"
  ],
  "source": "CV.pdf, trang 2",
  "sources": [
    {"file": "CV.pdf", "page": 2, "heading": "Kinh nghiệm"}
  ],
  "actions": []
}
```

**Điều kiện**:
- `score ≥ 0.78` từ KB, hoặc `score ≥ 0.55` từ đoạn tài liệu (kể cả bản ghi `kind: doc` của 005).
- Nội dung lấy nguyên văn từ KB/tài liệu; không do LLM sinh khi `ENABLE_LLM_SUMMARY=false`.
- `answer_bullets` có thể null nếu câu trả lời là một đoạn.

### 2.2 `suggest`

```json
{
  "type": "suggest",
  "session_id": "s-3f1c9a",
  "message": "Bạn muốn hỏi về mục tiêu nào?",
  "response": "Bạn muốn hỏi về mục tiêu nào?",
  "suggestions": [
    {"id": "goal_career", "question": "Mục tiêu nghề nghiệp của bạn là gì?", "score": 0.82},
    {"id": "goal_bot", "question": "Mục tiêu của chatbot này là gì?", "score": 0.74}
  ],
  "actions": [{"id": "other", "label": "Câu hỏi khác"}]
}
```

**Điều kiện**:
- 2–4 suggestions, không trùng `id`, không có trong `shown_ids`.
- Luôn có action `other`.
- Nếu không đủ 2 suggestions → trả `clarify` thay vì `suggest`.

### 2.3 `clarify`

Cấp 1 — menu chủ đề:

```json
{
  "type": "clarify",
  "session_id": "s-3f1c9a",
  "message": "Mình chưa chắc bạn muốn hỏi phần nào. Bạn chọn một mục bên dưới, hoặc mô tả thêm giúp mình nhé:",
  "response": "Mình chưa chắc bạn muốn hỏi phần nào...",
  "topics": ["Giới thiệu", "Kỹ năng", "Kinh nghiệm", "Dự án", "Liên hệ", "Tài liệu"],
  "examples": ["Mục tiêu nghề nghiệp 3 năm tới"],
  "actions": [{"id": "rephrase", "label": "Hỏi lại cách khác"}]
}
```

Cấp 3 — mời mô tả:

```json
{
  "type": "clarify",
  "session_id": "s-3f1c9a",
  "message": "Bạn thử mô tả cụ thể hơn nhé, ví dụ:",
  "response": "Bạn thử mô tả cụ thể hơn nhé, ví dụ:",
  "topics": [],
  "examples": [
    "Mục tiêu nghề nghiệp 3 năm tới",
    "Bạn muốn làm vị trí nào?"
  ],
  "actions": [{"id": "rephrase", "label": "Hỏi lại cách khác"}]
}
```

**Điều kiện**:
- Cấp 1: ≥ 3 topics nếu dữ liệu đủ; topics lấy từ KB + heading/tên tài liệu.
- Cấp 3: `topics = []`, 2–3 `examples`.
- Luôn có action `rephrase`.
- Không có câu "Mình không biết"/"chưa biết" trong `message`/`response`.

### 2.4 Cấu trúc con

**Suggestion**

```json
{"id": "goal_career", "question": "Mục tiêu nghề nghiệp của bạn là gì?", "score": 0.82}
```

- `id`: định danh theo từng câu hỏi (dùng cho `shown_ids`):
  - item có đúng 1 câu → `item_id`;
  - item có nhiều câu → `item_id#<sha1(normalized_question)[:8]>`;
  - câu KB không gắn item → `kb:<sha1(normalized_question)[:12]>`;
  - câu từ tài liệu → `doc:<file>#<heading>`.
- `score`: 0–1, làm tròn 2 chữ số.

**Action**

```json
{"id": "other", "label": "Câu hỏi khác"}
{"id": "rephrase", "label": "Hỏi lại cách khác"}
{"id": "topic", "label": "Kỹ năng", "topic": "Kỹ năng"}
```

**SourceRef**

```json
{"file": "CV.pdf", "page": 2, "sheet": null, "row_start": null, "row_end": null, "heading": "Kinh nghiệm"}
```

### 2.5 Ví dụ luồng "mục tiêu"

```http
POST /chat
{"message": "mục tiêu"}
```

```json
{
  "type": "suggest",
  "session_id": "s-abc",
  "message": "Bạn muốn hỏi về mục tiêu nào?",
  "response": "Bạn muốn hỏi về mục tiêu nào?",
  "suggestions": [
    {"id": "goal_career", "question": "Mục tiêu nghề nghiệp của bạn là gì?", "score": 0.82},
    {"id": "goal_bot", "question": "Mục tiêu của chatbot này là gì?", "score": 0.74}
  ],
  "actions": [{"id": "other", "label": "Câu hỏi khác"}]
}
```

```http
POST /chat
{"session_id": "s-abc", "action": "other"}
```

```json
{
  "type": "clarify",
  "session_id": "s-abc",
  "message": "Bạn muốn hỏi về mảng nào?",
  "response": "Bạn muốn hỏi về mảng nào?",
  "topics": ["Giới thiệu", "Kỹ năng", "Kinh nghiệm", "Dự án", "Liên hệ", "Tài liệu"],
  "examples": ["Mục tiêu nghề nghiệp 3 năm tới"],
  "actions": [{"id": "rephrase", "label": "Hỏi lại cách khác"}]
}
```

```http
POST /chat
{"session_id": "s-abc", "action": "topic", "topic": "Kỹ năng"}
```

```json
{
  "type": "suggest",
  "session_id": "s-abc",
  "message": "Các câu hỏi về Kỹ năng:",
  "response": "Các câu hỏi về Kỹ năng:",
  "suggestions": [
    {"id": "skills_languages", "question": "Bạn biết những ngôn ngữ lập trình nào?", "score": 0.80}
  ],
  "actions": [{"id": "other", "label": "Câu hỏi khác"}]
}
```

## 3. `POST /chat/stream`

Giữ `text/event-stream`. Event:

| Event | Khi nào | Payload |
|-------|---------|---------|
| `chunk` | `answer` dạng văn bản (tương thích) | `{"type":"chunk","content":"..."}` |
| `result` | `suggest`/`clarify` hoặc khi client cần cấu trúc đầy đủ | `{"type":"result","data":<ChatResponse>}` |
| `done` | Kết thúc | `{"type":"done"}` |
| `error` | Lỗi giữa chừng | `{"type":"error","message":"..."}` |

- Với `suggest`/`clarify`, server PHẢI phát `result` rồi `done`.
- Với `answer`, server PHẢI phát ít nhất một `chunk` hoặc `result`, rồi `done`.
- Không phát event `unknown`.

Ví dụ:

```text
data: {"type":"result","data":{"type":"suggest","session_id":"s-abc","suggestions":[...],"actions":[{"id":"other","label":"Câu hỏi khác"}]}}

data: {"type":"done"}
```

## 4. Lỗi

| HTTP | Điều kiện | Body |
|------|-----------|------|
| `400` | Body không phải JSON object; thiếu `message` khi không có `action`; `topic` thiếu khi `action=topic` | `{"error": "..."}` |
| `422` | `message` rỗng/toàn khoảng trắng hoặc > 200 ký tự | `{"error": "..."}` |
| `429` | Vượt rate limit | `{"error": "Rate limit exceeded. Thử lại sau."}` |
| `500` | Lỗi nội bộ không hạ cấp được | `{"error": "..."}` |

**Lưu ý**: Lỗi embedding/chỉ mục KHÔNG được trả 500; phải hạ cấp về `suggest`/`clarify` (xem research D13).

## 5. Tương thích

- Client cũ đọc `response` vẫn hoạt động với cả ba loại.
- Client cũ hiểu `type: "unknown"` sẽ không gặp lại; cần cập nhật để render `clarify`.
- `answer_bullets` giữ nguyên dạng mảng chuỗi hoặc null.
- `score` giữ nguyên kiểu number hoặc null.
