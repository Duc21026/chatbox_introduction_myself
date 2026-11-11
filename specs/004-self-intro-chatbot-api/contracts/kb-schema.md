# Contract: kb.json Schema

**Feature**: `004-self-intro-chatbot-api`

---

## Mô tả

`backend/kb.json` là nguồn dữ liệu chính cho KB Engine. File này do chủ nhân chatbot biên soạn thủ công; không có giao diện admin.

---

## JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "array",
  "minItems": 1,
  "items": {
    "type": "object",
    "required": ["id", "topic", "questions"],
    "additionalProperties": false,
    "properties": {
      "id": {
        "type": "string",
        "pattern": "^[a-z0-9_-]+$",
        "description": "Unique slug identifier"
      },
      "topic": {
        "type": "string",
        "minLength": 1,
        "description": "Human-readable topic name shown in 'unknown' response topics list"
      },
      "questions": {
        "type": "array",
        "minItems": 1,
        "maxItems": 10,
        "items": {
          "type": "string",
          "minLength": 3,
          "maxLength": 200
        },
        "description": "Variant phrasings for this Q&A item (3–5 recommended)"
      },
      "answer": {
        "type": ["string", "null"],
        "description": "Short answer string. Required if answer_bullets is null."
      },
      "answer_bullets": {
        "type": ["array", "null"],
        "items": {
          "type": "string",
          "maxLength": 100
        },
        "description": "List answer. Required if answer is null. Frontend renders as bullet list."
      }
    }
  }
}
```

**Constraint không trong schema**: ít nhất một trong `answer` / `answer_bullets` phải khác `null` và không rỗng. KB Engine validate lúc load và log warning cho mục vi phạm.

---

## Ví dụ hợp lệ

```json
[
  {
    "id": "intro",
    "topic": "Giới thiệu bản thân",
    "questions": [
      "Bạn là ai?",
      "Giới thiệu về bản thân đi",
      "Cho mình biết về bạn với"
    ],
    "answer": "Mình là Văn Phú Đức, sinh viên Đại học Khoa học Tự nhiên – ĐHQG TP.HCM.",
    "answer_bullets": null
  },
  {
    "id": "skills",
    "topic": "Kỹ năng lập trình",
    "questions": [
      "Bạn biết những ngôn ngữ lập trình nào?",
      "Tech stack của bạn là gì?",
      "Kỹ năng kỹ thuật của bạn?"
    ],
    "answer": null,
    "answer_bullets": ["Python", "JavaScript / TypeScript", "SQL", "FastAPI, Flask, React"]
  }
]
```

---

## Quy tắc bảo trì

1. `id` phải duy nhất trong toàn file; nếu trùng, KB Engine lấy mục đầu tiên.
2. Mỗi `questions` nên có ≥ 3 cách hỏi để embedding matrix cover đủ variation.
3. Sau khi sửa `kb.json`, khởi động lại server để rebuild embedding cache.
4. `embeddings_cache.npz` được generate tự động — không sửa thủ công, không commit vào git.

---

## Gitignore

```
backend/embeddings_cache.npz
```
