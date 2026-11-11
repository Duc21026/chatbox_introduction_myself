# Quickstart Validation: Unified Text Knowledge Source

**Feature**: `005-unified-text-source` | **Date**: 2026-11-11

Hướng dẫn kiểm chứng feature sau khi triển khai. Không chứa mã triển khai.

## Điều kiện tiên quyết

- Repo tại thư mục gốc.
- Python 3.11+ và đã cài `backend/requirements.txt` (để chạy pytest/CLI).
- Ollama + `bge-m3` + model trả lời nếu muốn kiểm tra RAG end-to-end.
- Hoặc Docker + Docker Compose nếu kiểm tra theo container.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

## Kịch bản 1 — Validate tệp mẫu

```bash
python backend/scripts/manage_docs.py validate \
  --source specs/005-unified-text-source/template.txt
```

**Kỳ vọng**

- Exit code `0`.
- In số bản ghi `qa` và `doc`.
- Không cần Ollama.

## Kịch bản 2 — Chuyển dữ liệu hiện tại sang một tệp

Sao lưu nguồn cũ trước:

```bash
cp backend/qa.txt /tmp/qa.backup.txt
cp backend/kb.json /tmp/kb.backup.json
cp -r backend/data /tmp/data.backup
```

Migrate:

```bash
python backend/scripts/manage_docs.py migrate \
  --to backend/data/chatbot.txt --force
```

**Kỳ vọng**

- Tệp `backend/data/chatbot.txt` được tạo.
- Không sửa `qa.txt`, `kb.json`, hoặc các tệp trong `backend/data/`.
- Output có số lượng `qa` và `doc` khớp với nguồn cũ.
- Chạy lại migrate khi chưa có `--force` phải từ chối ghi đè.

## Kịch bản 3 — Validate tệp vừa migrate

```bash
python backend/scripts/manage_docs.py validate \
  --source backend/data/chatbot.txt --json
```

**Kỳ vọng**

- JSON có `"valid": true`.
- `counts.qa` bằng số item hợp lệ của `kb.json` cộng số dòng `qa.txt` mới (không trùng câu hỏi).
- `counts.doc` bằng số tệp được hỗ trợ trong `backend/data/` (trừ chính `chatbot.txt`).
- Không có `errors`.

## Kịch bản 4 — Chạy backend chỉ với tệp hợp nhất

Tạm thời chuyển nguồn cũ ra khỏi đường dẫn mặc định:

```bash
mkdir -p /tmp/legacy-sources
mv backend/qa.txt /tmp/legacy-sources/
mv backend/kb.json /tmp/legacy-sources/
mv backend/data/*.txt backend/data/*.pdf backend/data/*.docx backend/data/*.xlsx \
   /tmp/legacy-sources/ 2>/dev/null || true
```

Chạy:

```bash
CHATBOT_SOURCE_PATH=backend/data/chatbot.txt python app.py
```

Kiểm tra:

```bash
curl -s http://127.0.0.1:5000/chat \
  -X POST -H 'Content-Type: application/json' \
  -d '{"message":"GPA của bạn là bao nhiêu?"}'
```

**Kỳ vọng**

- Trả về `type: "answer"` với nội dung GPA.
- Hỏi nội dung chỉ có trong một `kind: doc` → trả lời từ đoạn `content` tương ứng.
- Không cần `qa.txt` hay `kb.json`.

Khôi phục nguồn cũ sau khi kiểm tra.

## Kịch bản 5 — Tệp sai phải báo số dòng

Tạo bản sao lỗi:

```bash
cp backend/data/chatbot.txt /tmp/chatbot-bad.txt
printf '\n=== RECORD ===\nkind: qa\nid: broken\ntopic: Test\nquestions:\n- Câu hỏi?\n=== END ===\n' \
  >> /tmp/chatbot-bad.txt
```

Chạy:

```bash
python backend/scripts/manage_docs.py validate --source /tmp/chatbot-bad.txt --json
```

**Kỳ vọng**

- Exit code `2`.
- `errors` chứa `E_ANSWER` (thiếu `answer`/`bullets`) và số dòng tương ứng.
- Không có nội dung nào được nạp.

## Kịch bản 6 — Escaping

Thêm vào tệp tạm:

```text
=== RECORD ===
kind: doc
id: escape-check
topic: Escape
content:
\=== END ===
line bình thường
\# không phải chú thích
=== END ===
```

Validate và chạy `ask`/API với câu hỏi về nội dung này.

**Kỳ vọng**

- `validate` exit `0`.
- `content` chứa literal `=== END ===` và `# không phải chú thích`.
- Không bị cắt bản ghi.

## Kịch bản 7 — Test tự động

```bash
pytest backend/tests
```

**Kỳ vọng**

- Test parser/validator/mapping chạy không cần Ollama.
- Test cần model được skip nếu thiếu Ollama/model, như hành vi hiện tại.
- Không có regression ở `test_chat_api.py`, `test_chat_stream_api.py`, `test_retrieval*.py`, `test_normalization.py`.

## Kịch bản 8 — Docker chỉ mount một tệp

Cập nhật `docker-compose.yml` để chỉ mount tệp hợp nhất:

```yaml
volumes:
  - ./backend/data/chatbot.txt:/app/backend/data/chatbot.txt
environment:
  CHATBOT_SOURCE_PATH: backend/data/chatbot.txt
```

Chạy:

```bash
docker compose up -d --build backend frontend
docker compose ps
curl -s http://localhost:3000/chat \
  -X POST -H 'Content-Type: application/json' \
  -d '{"message":"Bạn là ai?"}'
```

**Kỳ vọng**

- `chatbot-backend` healthy.
- API trả lời đúng dù không mount `qa.txt` hay `kb.json`.
- Sửa `chatbot.txt` rồi gọi lại → câu trả lời phản ánh nội dung mới.

## Kịch bản 9 — Rollback

Bật cờ tương thích ngược:

```bash
CHATBOT_LEGACY_SOURCES=true python app.py
```

**Kỳ vọng**

- Backend đọc `qa.txt` và `kb.json` như trước.
- Có cảnh báo deprecated trong log.
- Tắt cờ → quay lại dùng `chatbot.txt`.

## Checklist hoàn tất

- [ ] Tệp mẫu validate thành công.
- [ ] Migrate không sửa nguồn gốc và tạo đúng số record.
- [ ] Backend chạy chỉ với `chatbot.txt`.
- [ ] Tệp sai bị từ chối kèm số dòng.
- [ ] Escaping hoạt động.
- [ ] Test backend pass hoặc skip đúng.
- [ ] Docker smoke test pass.
- [ ] Rollback bằng `CHATBOT_LEGACY_SOURCES=true` hoạt động.
