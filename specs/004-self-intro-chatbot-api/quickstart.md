# Quickstart & Validation Guide

**Feature**: `004-self-intro-chatbot-api`
**Date**: 2026-11-10

---

## Prerequisites

1. Ollama đang chạy với 2 model đã pull:
   ```bash
   ollama pull bge-m3
   ollama pull qwen2.5:3b    # hoặc 1.5b/7b tùy RAM
   ```
2. Python virtual env đã kích hoạt và deps đã install:
   ```bash
   source backend/.venv/bin/activate
   pip install -r backend/requirements.txt
   ```
3. `backend/kb.json` đã tồn tại với ít nhất 2 KnowledgeItem (xem [kb-schema.md](contracts/kb-schema.md)).
4. `backend/.env` đã cấu hình (copy từ `.env.example` nếu chưa có).

---

## Khởi động server

```bash
# Từ repo root
python app.py
```

Expected output:
```
 * Running on http://127.0.0.1:5000
 * KB Engine: loaded 15 items, 42 questions, embeddings built in 8.3s
 * Warm-up complete (embed + LLM)
```

---

## Validation Scenario 1 — Câu khớp rõ (type: answer)

```bash
curl -s -X POST http://127.0.0.1:5000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Bạn biết những ngôn ngữ lập trình nào?"}'
```

**Expected**:
```json
{
  "type": "answer",
  "score": 0.95,
  "response": "Python, JavaScript / TypeScript, SQL",
  "answer_bullets": ["Python", "JavaScript / TypeScript", "SQL"]
}
```

✅ `type == "answer"` và `score >= 0.78`.

---

## Validation Scenario 2 — Không dấu + teencode (type: answer hoặc suggest)

```bash
curl -s -X POST http://127.0.0.1:5000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "ban biet ngon ngu j"}'
```

**Expected** (nếu hybrid score ≥ 0.78 sau normalize):
```json
{ "type": "answer", "score": 0.82, "response": "...", "answer_bullets": [...] }
```

**Expected** (nếu 0.55–0.78, cần Qwen sửa):
```json
{
  "type": "suggest",
  "response": "Ý bạn có phải là một trong những câu hỏi này không?",
  "suggestions": [
    { "question": "Bạn biết những ngôn ngữ lập trình nào?", "score": 0.68 }
  ]
}
```

✅ `type` là `"answer"` hoặc `"suggest"` (không phải `"unknown"`).

---

## Validation Scenario 3 — Ngoài phạm vi (type: unknown)

```bash
curl -s -X POST http://127.0.0.1:5000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hôm nay thời tiết thế nào?"}'
```

**Expected**:
```json
{
  "type": "unknown",
  "response": "Mình chưa có thông tin về điều này.",
  "message": "Mình chưa có thông tin về điều này. Bạn có thể hỏi về các chủ đề sau:",
  "topics": ["Giới thiệu bản thân", "Kỹ năng lập trình", "Học tập", "Dự án", "Liên hệ"]
}
```

✅ `type == "unknown"` và `topics` không rỗng.

---

## Validation Scenario 4 — Input rỗng (HTTP 422)

```bash
curl -s -X POST http://127.0.0.1:5000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "   "}'
```

**Expected**: HTTP 422 với body `{ "error": "..." }`.

---

## Validation Scenario 5 — Input quá dài (HTTP 422)

```bash
# Tạo chuỗi 201 ký tự
python -c "print('a'*201)" | xargs -I{} curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://127.0.0.1:5000/chat \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"$(python -c 'print(\"a\"*201)')\"}"
```

**Expected**: HTTP 422.

---

## Validation Scenario 6 — Rate limit (HTTP 429)

```bash
# Gửi 61 request liên tiếp
for i in $(seq 1 61); do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -X POST http://127.0.0.1:5000/chat \
    -H "Content-Type: application/json" \
    -d '{"message": "GPA của bạn?"}'
done | tail -5
```

**Expected**: 1–2 dòng cuối hiện `429`.

---

## Validation Scenario 7 — Backward compatibility (client cũ)

```bash
# Client cũ chỉ đọc "response" field
curl -s -X POST http://127.0.0.1:5000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "GPA của bạn?"}' | python -c "import sys,json; d=json.load(sys.stdin); print(d['response'])"
```

**Expected**: In ra chuỗi không rỗng (không có KeyError).

---

## Validation Scenario 8 — Embedding cache reload

```bash
# Kiểm tra cache build
ls -la backend/embeddings_cache.npz   # phải tồn tại sau lần chạy đầu

# Sửa kb.json (thêm 1 mục), restart, kiểm tra rebuild
# Log phải in: "KB Engine: embeddings rebuilt (kb.json changed)"
```

---

## Hiệu chỉnh ngưỡng (tùy chọn)

Sau khi có test set thực:

```bash
python backend/scripts/tune_thresholds.py \
  --kb backend/kb.json \
  --test backend/evaluation/questions.json
```

Script in ra bảng score cho từng câu → chọn HIGH/MID sao cho:
- Câu đúng ≥ 95% nằm trên HIGH.
- Câu ngoài chủ đề ≥ 95% nằm dưới MID.

Cập nhật env var:
```bash
CHATBOT_KB_HIGH_THRESHOLD=0.78  # mặc định
CHATBOT_KB_MID_THRESHOLD=0.55   # mặc định
```

---

## Tham chiếu

- Schema kb.json: [contracts/kb-schema.md](contracts/kb-schema.md)
- API contract: [contracts/chat-api.md](contracts/chat-api.md)
- Pipeline chuẩn hoá: [contracts/normalization-pipeline.md](contracts/normalization-pipeline.md)
- Data model: [data-model.md](data-model.md)
