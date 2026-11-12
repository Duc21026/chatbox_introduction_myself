# Quickstart & Validation: Luôn gợi ý & nạp tài liệu đa định dạng

**Feature**: `006-tiered-suggest-ingest` | **Date**: 2026-11-12

Hướng dẫn này chứng minh feature hoạt động end-to-end. Chi tiết schema xem [contracts/chat-api.md](contracts/chat-api.md), [contracts/manage-docs-cli.md](contracts/manage-docs-cli.md), [contracts/doc-index-schema.md](contracts/doc-index-schema.md).

---

## 1. Chuẩn bị

```bash
# Từ thư mục gốc repo
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

# Ollama + model embedding (bắt buộc cho tìm kiếm ngữ nghĩa)
ollama serve            # nếu chưa chạy
ollama pull bge-m3
ollama pull qwen2.5:3b  # chỉ cần nếu bật ENABLE_LLM_SUMMARY hoặc RAG cũ

# Frontend
cd frontend
npm install
cd ..
```

Biến môi trường tối thiểu (có thể đặt trong `backend/.env`):

```bash
export CHATBOT_OLLAMA_BASE_URL=http://127.0.0.1:11434
export CHATBOT_EMBEDDING_MODEL=bge-m3
export CHATBOT_SOURCE_PATH=backend/data/chatbot.txt
export CHATBOT_DOC_INDEX_DIR=backend/doc_index
export ENABLE_LLM_SUMMARY=false
```

> Trong Docker dùng `CHATBOT_OLLAMA_BASE_URL=http://ollama:11434`.

---

## 2. Nạp tài liệu

Repo có sẵn vài tệp mẫu trong `backend/data/` (PDF, DOCX, XLSX) và một tệp CSV nếu bạn thêm vào.

```bash
# Nạp cả thư mục
python backend/scripts/manage_docs.py ingest ./backend/data

# Hoặc nạp một tệp
python backend/scripts/manage_docs.py ingest ./backend/data/CV_Data_Science_Vietnamese.docx

# Xem tệp đã nạp + số đoạn
python backend/scripts/manage_docs.py list
```

Kỳ vọng:

- Mỗi tệp hợp lệ xuất hiện với `indexed` và số đoạn > 0.
- PDF scan / tệp lỗi xuất hiện trong mục `lỗi` (hoặc status `failed`), các tệp khác vẫn nạp.
- Chạy lại lệnh `ingest` ngay sau đó: tất cả `bỏ qua`, `Vector đã tính: 0`.

Kiểm tra tính tăng dần:

```bash
# Sửa một tệp CSV/DOCX (thêm 1 dòng) rồi nạp lại
python backend/scripts/manage_docs.py ingest ./backend/data --json
```

Kỳ vọng: `stats.embeddings_computed` chỉ bằng số đoạn mới/đổi, không phải toàn bộ.

Xoá khỏi chỉ mục (không xoá tệp nguồn):

```bash
python backend/scripts/manage_docs.py remove CV_Data_Science_Vietnamese.docx
python backend/scripts/manage_docs.py list
```

---

## 3. Chạy backend

```bash
python backend/app.py
# hoặc: flask --app backend.app run
```

Backend khởi động sẽ:

- Nạp `chatbot.txt` và embedding KB (cache `embeddings_cache.npz`).
- Nạp `doc_index/` vào RAM và dựng lại FAISS.
- Warm-up embedder; nếu Ollama không sẵn sàng, log cảnh báo và hạ cấp (không chết server).

---

## 4. Kiểm tra API bằng curl

### 4.1 Câu khớp rõ → `answer`

```bash
curl -s http://127.0.0.1:5000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"GPA hiện tại của bạn là bao nhiêu?"}' | python -m json.tool
```

Kỳ vọng: `type = "answer"`, `score ≥ 0.78`, `answer_bullets`/`response` có nội dung.

### 4.2 Câu mơ hồ "mục tiêu" → `suggest` + nút

```bash
curl -s http://127.0.0.1:5000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"mục tiêu"}' | tee /tmp/suggest.json | python -m json.tool
```

Kỳ vọng:

- `type = "suggest"`.
- `suggestions` có ≥ 2 câu hỏi đầy đủ, mỗi câu có `id` + `score`.
- `actions` chứa `{"id":"other","label":"Câu hỏi khác"}`.
- Ghi lại `session_id` để dùng ở bước sau.

### 4.3 Bấm "Câu hỏi khác" → `clarify` menu chủ đề

```bash
SID=$(python -c 'import json;print(json.load(open("/tmp/suggest.json"))["session_id"])')
curl -s http://127.0.0.1:5000/chat \
  -H 'Content-Type: application/json' \
  -d "{\"session_id\":\"$SID\",\"action\":\"other\"}" | python -m json.tool
```

Kỳ vọng: `type = "clarify"`, `topics` có ≥ 3 mục, `actions` có `rephrase`.

### 4.4 Chọn chủ đề → câu chưa hiển thị

```bash
curl -s http://127.0.0.1:5000/chat \
  -H 'Content-Type: application/json' \
  -d "{\"session_id\":\"$SID\",\"action\":\"topic\",\"topic\":\"Kỹ năng\"}" | python -m json.tool
```

Kỳ vọng: `type = "suggest"`; không câu nào trùng với các câu đã hiển thị trước đó trong phiên.

### 4.5 Gõ vô nghĩa → `clarify`, không "không biết"

```bash
curl -s http://127.0.0.1:5000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"asdf"}' | python -m json.tool
```

Kỳ vọng: `type = "clarify"`; không có chuỗi "không biết"/"unknown" trong `response`/`message`.

### 4.6 Câu không dấu / teencode

```bash
curl -s http://127.0.0.1:5000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"ban biet ngon ngu j"}' | python -m json.tool
```

Kỳ vọng: `answer` hoặc `suggest`; không rơi về lỗi.

### 4.7 Câu có đáp án trong tài liệu → `answer` + nguồn

Chọn một câu có thông tin chỉ nằm trong PDF/DOCX/XLSX/CSV đã nạp, ví dụ tên dự án trong CV:

```bash
curl -s http://127.0.0.1:5000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"Dự án chatbot của bạn dùng công nghệ gì?"}' | python -m json.tool
```

Kỳ vọng:

- `type = "answer"`.
- `sources` có `file` và `page`/`sheet`/`row_start`/`row_end` đúng.
- `response`/`answer_bullets` là trích nguyên văn, không phải văn phong LLM.

### 4.8 Tách phiên

Gửi cùng câu "mục tiêu" với `session_id` mới → các gợi ý đã hiển thị ở phiên cũ có thể xuất hiện lại.

---

## 5. Kiểm tra frontend

```bash
cd frontend
npm run dev
```

Mở URL Vite (mặc định `http://127.0.0.1:5173`) và kiểm tra:

1. Gõ "mục tiêu" → thấy bong bóng câu dẫn + danh sách nút gợi ý kèm %.
2. Bấm "Câu hỏi khác" → thấy các chip chủ đề + nút "Hỏi lại cách khác".
3. Bấm một chủ đề → thấy câu hỏi chưa hiển thị; bấm một câu → nhận câu trả lời.
4. Bấm "Hỏi lại cách khác" → thấy ví dụ mô tả tự do.
5. Gõ "asdf" → vẫn thấy menu chủ đề, không có câu "Mình không biết".
6. Hỏi câu có đáp án trong tài liệu → thấy câu trả lời + dòng nguồn `file, trang/sheet/dòng`.
7. Mở cuộc hội thoại mới → trạng thái gợi ý reset, không lặp từ phiên cũ.
8. Nút bấm được bằng bàn phím (Tab/Enter), có focus ring.

---

## 6. Kiểm thử tự động

```bash
# Backend (không cần Ollama cho phần lớn test)
pytest backend/tests -q

# Chỉ test feature 006
pytest backend/tests/test_assistant.py backend/tests/test_suggestions.py \
       backend/tests/test_session.py backend/tests/test_doc_loaders.py \
       backend/tests/test_doc_index.py backend/tests/test_doc_answers.py -q

# Frontend
cd frontend
npm test
npm run typecheck
npm run lint
```

Ghi chú:

- Test cần Ollama được đánh dấu/gate bằng `tests/helpers.ollama_ready`; nếu Ollama không chạy, chúng bị skip thay vì fail.
- Test tài liệu dùng `tmp_path` + embedder giả; không ghi vào `backend/doc_index/` thật.

---

## 7. Đo hiệu năng (p50/p95)

Yêu cầu: tắt tóm tắt LLM.

```bash
export ENABLE_LLM_SUMMARY=false

# Đo nhanh qua HTTP (cần server đang chạy)
python - <<'PY'
import json, statistics, time, urllib.request

questions = [
    "GPA hiện tại của bạn là bao nhiêu?",   # answer
    "mục tiêu",                              # suggest
    "asdf",                                  # clarify
    "Dự án chatbot dùng công nghệ gì?",      # tài liệu (nếu có)
]
latencies = []
for _ in range(15):
    for question in questions:
        body = json.dumps({"message": question}).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:5000/chat",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        start = time.perf_counter()
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
        latencies.append((time.perf_counter() - start) * 1000)

latencies.sort()
p50 = statistics.median(latencies)
p95 = latencies[int(len(latencies) * 0.95) - 1]
print(f"n={len(latencies)} p50={p50:.0f}ms p95={p95:.0f}ms")
PY
```

Kỳ vọng: p50 < 300 ms, p95 < 500 ms trên máy phát triển (Ollama đã warm, `bge-m3` sẵn sàng). Nếu vượt, kiểm tra:

- Có gọi Qwen trên đường chính không (`CHATBOT_QUERY_REWRITE` phải `off`).
- Embedding có bị tạo lại mỗi request không (phải dùng `evaluate` một lần).
- Chỉ mục tài liệu đã nạp sẵn trong RAM chưa.

---

## 8. Đối chiếu tiêu chí chấp nhận

| Tiêu chí | Cách kiểm tra |
|----------|---------------|
| SC-001 không còn unknown/không biết | 4.2, 4.5; grep response |
| SC-002 "mục tiêu" ≥ 2 gợi ý + nút | 4.2 |
| SC-003 "Câu hỏi khác" → chủ đề → câu chưa hiển thị | 4.3, 4.4 |
| SC-004 mỗi định dạng 3/3 câu đúng + nguồn | `pytest backend/tests/test_doc_answers.py`; thử tay 4.7 |
| SC-005 nạp lại không đổi bỏ qua, đổi chỉ embed phần đổi | mục 2 (`--json` → `embeddings_computed`) |
| SC-006 p50/p95 | mục 7 |
| SC-007 0% nội dung LLM sinh | `ENABLE_LLM_SUMMARY=false`; so khớp nguyên văn |
| SC-008 ≥ 80% truy vấn mơ hồ có gợi ý đúng | `pytest backend/tests/test_suggestions.py` |
| SC-009 không hồi quy khớp rõ | `pytest backend/tests/test_answers.py` (khi Ollama sẵn sàng) |
| SC-010 hạ cấp khi embedding lỗi | `pytest backend/tests/test_assistant.py -k fallback` |

---

## 9. Sự cố thường gặp

| Hiện tượng | Nguyên nhân thường gặp | Cách xử lý |
|-----------|------------------------|------------|
| `ingest` báo `E_NO_TEXT` | PDF scan/ảnh, không có lớp chữ | OCR ngoài phạm vi v1; thay bằng PDF có text |
| `list` hiện `not-indexed` | Chưa chạy `ingest` | Chạy `ingest` đúng đường dẫn |
| Mọi câu trả về `clarify` | Ollama/embedding lỗi, KB rỗng | Kiểm tra `/api/tags`, chạy `ollama pull bge-m3`, xem log |
| Gợi ý lặp lại | Client không gửi `session_id` | Đảm bảo client giữ và gửi `session_id` |
| Câu tài liệu không khớp | Chưa nạp tài liệu hoặc ngưỡng 0.55 quá cao | `list`, `ingest`, hạ `CHATBOT_DOC_THRESHOLD` khi thử |
| Docker không thấy tài liệu | Chưa mount `backend/data`/`backend/doc_index` | Kiểm tra `docker-compose.yml` |
