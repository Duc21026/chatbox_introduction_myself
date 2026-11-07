# Chatbot giới thiệu bản thân

Chatbot hỏi đáp tiếng Việt giới thiệu hồ sơ học tập của Văn Phú Đức. Giao diện là một ứng dụng React độc lập; backend Python (Flask + LangChain + FAISS + Ollama) được giữ lại tạm thời và phục vụ qua HTTP.

## Kiến trúc

```text
frontend/ (React + Vite + TypeScript)
        │  POST /chat/stream  (SSE, có fallback)
        │  POST /chat         (JSON)
        ▼
backend/ (Flask, giữ tạm thời)
        │
        ├─ khớp mờ qa.txt (RapidFuzz)
        └─ RAG: bge-m3 + FAISS → Qwen2.5 qua Ollama
```

> **Backend tạm thời**: thư mục `backend/` giữ nguyên hành vi trả lời và hợp đồng `POST /chat` hiện có trong giai đoạn chuyển giao. Việc thay thế backend là một hạng mục riêng trong tương lai. Frontend chỉ phụ thuộc vào các hợp đồng HTTP trong `specs/003-react-chat-ui/contracts/`.

## Cấu trúc repository

| Đường dẫn | Vai trò |
|-----------|---------|
| `frontend/` | Giao diện React: chat, Markdown, code copy, theme, cuộc trò chuyện trong phiên |
| `backend/` | Dịch vụ Python tạm thời: API, RAG, quản lý nguồn, đánh giá, kiểm thử |
| `app.py` | Shim tương thích để `python app.py` vẫn chạy backend |
| `specs/` | Đặc tả, kế hoạch, hợp đồng và tasks của từng tính năng |
| `README.md` | Hướng dẫn chạy và kiến trúc |
| `.gitignore` | Quy tắc bỏ qua cho cả frontend và backend |

## Yêu cầu

- Python 3.11 trở lên.
- Node.js 20 trở lên và npm.
- [Ollama](https://ollama.com/) đang chạy cục bộ với model trả lời và `bge-m3`.

## Cài đặt backend

Từ thư mục gốc repository:

```bash
python -m venv backend/.venv
source backend/.venv/bin/activate        # Windows: backend\.venv\Scripts\activate
pip install -r backend/requirements.txt

ollama pull bge-m3
ollama list
```

Sao chép cấu hình mẫu và chỉnh nếu cần:

```bash
cp backend/.env.example backend/.env
```

Ứng dụng không tự đọc `.env`; hãy nạp biến môi trường bằng shell hoặc công cụ quen dùng. Các biến chính:

| Biến | Mặc định | Ý nghĩa |
|------|----------|---------|
| `CHATBOT_ANSWER_MODEL` | `qwen2.5:7b` | Model trả lời |
| `CHATBOT_EMBEDDING_MODEL` | `bge-m3` | Model embedding |
| `CHATBOT_RELEVANCE_THRESHOLD` | `1.0` | Ngưỡng lọc đoạn không liên quan |
| `CHATBOT_FUZZY_CUTOFF` | `80` | Ngưỡng khớp mờ với `backend/qa.txt` |
| `CHATBOT_DATA_DIR` | `backend/data` | Thư mục dữ liệu |
| `CHATBOT_QA_PATH` | `backend/qa.txt` | Tệp câu hỏi đáp |
| `CHATBOT_OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Địa chỉ Ollama |
| `CHATBOT_CHUNK_SIZE` | `500` | Kích thước đoạn |
| `CHATBOT_CHUNK_OVERLAP` | `50` | Độ chồng đoạn |
| `CHATBOT_TOP_K` | `3` | Số đoạn lấy ra mỗi câu hỏi |
| `CHATBOT_QUERY_REWRITE` | `auto` | Sửa chính tả/bổ sung dấu: `auto`, `always`, `off` |

Chạy backend từ thư mục gốc:

```bash
python app.py
# hoặc trực tiếp:
python backend/app.py
```

Mặc định API ở `http://127.0.0.1:5000`.

## Cài đặt frontend

```bash
cd frontend
npm install
cp .env.example .env        # VITE_API_BASE_URL=http://127.0.0.1:5000
npm run dev
```

Mở địa chỉ Vite in ra (thường `http://localhost:5173`). Các lệnh khác:

```bash
npm run build       # kiểm tra kiểu và build production vào frontend/dist/
npm run preview     # xem bản build
npm run test        # Vitest + React Testing Library
npm run lint
npm run typecheck
```

## Chọn cỡ model theo RAM

| RAM còn trống | Model trả lời |
|---------------|---------------|
| Dưới 4 GB | `qwen2.5:1.5b` (nên nâng cấp máy hoặc dùng API ngoài) |
| Khoảng 4 GB | `qwen2.5:3b` |
| 8 GB trở lên | `qwen2.5:7b` |
| 16 GB trở lên | `qwen2.5:14b` |

```bash
python backend/scripts/recommend_model.py
```

## Quản lý tài liệu

Nguồn tài liệu được lưu trong `backend/data/`. Hỗ trợ `.txt`, `.pdf`, `.docx`, `.xlsx`, `.csv`; PDF phải có lớp văn bản.

```bash
python backend/scripts/manage_docs.py add /tmp/nghi-phep.txt --name nghi-phep.txt
python backend/scripts/manage_docs.py replace /tmp/nghi-phep-moi.txt --name nghi-phep.txt
python backend/scripts/manage_docs.py delete nghi-phep.txt
python backend/scripts/manage_docs.py list
python backend/scripts/manage_docs.py ask "nhân viên được nghỉ bao nhiêu ngày phép?" --debug
```

Thao tác ghi dùng tệp tạm rồi thay thế nguyên tử. Chỉ mục FAISS tự phát hiện thay đổi tệp và tạo lại khi cần, không cần khởi động lại Flask. `ask --debug` chỉ dành cho người vận hành; thông tin chẩn đoán không xuất hiện trong API.

## API

### `POST /chat`

```json
{ "message": "GPA hiện tại?" }
```

Trả về:

```json
{ "response": "GPA hiện tại là 8.30" }
```

### `POST /chat/stream` (bổ sung)

Trả về `text/event-stream`:

```text
data: {"type":"chunk","content":"GPA "}

data: {"type":"chunk","content":"hiện tại là 8.30"}

data: {"type":"done"}
```

Lỗi giữa chừng dùng `data: {"type":"error","message":"..."}`. Frontend tự quay về `POST /chat` nếu endpoint stream không khả dụng.

## Kiểm thử

```bash
# Backend, từ thư mục gốc
pytest backend/tests

# Frontend
cd frontend
npm run test
npm run lint
npm run typecheck
npm run build
```

Một số kiểm thử backend cần Ollama và model đã pull; nếu thiếu, chúng được bỏ qua. Kết quả kiểm thử frontend chạy bằng jsdom, không cần backend thật.

## Ghi chú vận hành

- Khi khởi động, backend kiểm tra thư mục dữ liệu, `qa.txt`, kết nối Ollama và sự tồn tại của hai model.
- Bộ câu hỏi đánh giá nằm trong `backend/evaluation/`.
- Lịch sử trò chuyện chỉ nằm trong bộ nhớ trình duyệt cho phiên hiện tại; tải lại trang sẽ bắt đầu không gian làm việc mới. Tùy chọn giao diện được giữ lại.
- Không có đăng nhập, lịch sử phía máy chủ hay đồng bộ đa thiết bị.
