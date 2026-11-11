# Backend

Dịch vụ Python (Flask + LangChain + FAISS) phục vụ giao diện React.

- `app.py`: Flask API. `POST /chat` trả `{type, score, response, answer_bullets}`; `POST /chat/stream` trả SSE.
- `source_format.py`: phân tích, kiểm tra, ánh xạ và ghi nguồn `chatbot.txt` (`CHATBOT-SOURCE v1`).
- `chatbox.py`, `documents.py`, `text_normalization.py`: cấu hình, RAG, quản lý nguồn và chuẩn hóa tiếng Việt.
- `data/chatbot.txt`: nguồn tri thức hợp nhất duy nhất — `qa` cho KB engine + khớp mờ + RAG, `doc` cho RAG.
- `scripts/manage_docs.py`: `add`, `replace`, `delete`, `list`, `ask`, `validate`, `migrate`.
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

Đặc tả nguồn: `specs/005-unified-text-source/contracts/source-format.md`. Frontend không import mã nguồn backend; mọi tương tác đi qua HTTP.
