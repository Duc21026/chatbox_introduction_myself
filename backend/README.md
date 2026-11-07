# Backend tạm thời

Thư mục này chứa dịch vụ Python đang được giữ lại trong giai đoạn chuyển giao sang giao diện React.

- `app.py`: Flask API. `POST /chat` giữ nguyên hợp đồng; `POST /chat/stream` là bổ sung không phá vỡ tương thích.
- `chatbox.py`, `documents.py`, `text_normalization.py`: cấu hình, RAG, quản lý nguồn và chuẩn hóa tiếng Việt.
- `data/`, `qa.txt`: kho dữ liệu và câu hỏi đáp cục bộ.
- `scripts/`, `evaluation/`, `tests/`: vận hành, đánh giá và kiểm thử.

Chạy từ thư mục gốc repository:

```bash
python app.py
pytest backend/tests
```

Backend sẽ được thay thế trong một tính năng riêng. Frontend không được import mã nguồn backend; mọi tương tác đi qua các hợp đồng HTTP trong `specs/003-react-chat-ui/contracts/`.
