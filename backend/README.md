# Backend

Dịch vụ Python (Flask + LangChain + FAISS) phục vụ giao diện React.

- `app.py`: Flask API. `POST /chat` trả `answer`/`suggest`/`clarify` kèm `session_id`; `POST /chat/stream` trả SSE (`chunk`, `result`, `done`).
- `assistant.py`: bộ điều phối ba tầng, session state và cache đánh giá; không gọi LLM trên đường chính.
- `kb_engine.py`: chấm điểm KB, trả toàn bộ ứng viên qua `evaluate()`; `suggestions.py`: xếp hạng gợi ý/menu chủ đề.
- `session.py`: TTL, giới hạn số phiên, `shown_ids`, `last_query`, `level`.
- `doc_loaders.py` + `doc_index.py`: trích xuất PDF/DOCX/XLSX/CSV/TXT/MD, chỉ mục tăng dần và trả lời trích xuất kèm nguồn.
- `source_format.py`: phân tích, kiểm tra, ánh xạ và ghi nguồn `chatbot.txt` (`CHATBOT-SOURCE v1`).
- `chatbox.py`, `documents.py`, `text_normalization.py`: cấu hình, RAG dự phòng, quản lý nguồn và chuẩn hóa tiếng Việt.
- `data/chatbot.txt`: nguồn tri thức hợp nhất — `qa` cho KB engine, `doc` cho RAG dự phòng.
- `doc_index/`: dữ liệu phái sinh (đã ignore trong git); không thêm `__init__.py` vào thư mục này.
- `scripts/manage_docs.py`: `add`, `replace`, `delete`, `list`, `ingest`, `remove`, `ask`, `validate`, `migrate`.
- `evaluation/`, `tests/`: đánh giá và kiểm thử.

Chạy từ thư mục gốc repository:

```bash
python app.py
pytest backend/tests
pytest backend/tests/test_source_*.py
```

Kiểm tra nguồn trước khi chạy:

```bash
python backend/scripts/manage_docs.py validate
```

Nạp và quản lý chỉ mục tài liệu:

```bash
python backend/scripts/manage_docs.py ingest backend/data --recursive
python backend/scripts/manage_docs.py list --json
python backend/scripts/manage_docs.py remove old-cv.pdf
```

`ENABLE_LLM_SUMMARY=false` mặc định. Khi bật, chỉ câu trả lời trích xuất từ tài liệu mới được tóm tắt bằng LLM với `num_predict=120`; lỗi LLM sẽ quay về các câu trích. Rollback chỉ mục: dừng backend, xoá `backend/doc_index/`, chạy lại `ingest`.

Đặc tả nguồn: `specs/005-unified-text-source/contracts/source-format.md`. Frontend không import mã nguồn backend; mọi tương tác đi qua HTTP.
