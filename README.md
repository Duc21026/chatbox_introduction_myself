# Chatbot giới thiệu bản thân

Chatbot hỏi đáp tiếng Việt giới thiệu hồ sơ học tập của Văn Phú Đức. Toàn bộ hệ thống chạy bằng Docker Compose: giao diện React (nginx), backend Flask + LangChain + FAISS và Ollama cho mô hình ngôn ngữ.

## Kiến trúc Docker

```text
Trình duyệt
    │  http://localhost:3000
    ▼
frontend (nginx)  ──/chat, /chat/stream──▶  backend (Flask :5000)
                                               ├─ chatbot.txt (nguồn duy nhất)
                                               │    ├─ qa  → KB engine + khớp mờ + RAG
                                               │    └─ doc → RAG
                                               ├─ khớp mờ (RapidFuzz)
                                               └─ RAG: bge-m3 + FAISS
                                                        │
                                                        ▼
                                               ollama (:11434) → Qwen2.5
```

| Service | Build / Image | Cổng host | Vai trò |
|---------|---------------|-----------|---------|
| `frontend` | `frontend/Dockerfile` (React + Vite → nginx) | `3000` → `80` | Giao diện, proxy `/chat` sang backend |
| `backend` | `backend/Dockerfile` (Python 3.11) | `5000` | API, KB engine, RAG, quản lý tài liệu |
| `ollama` | `ollama/ollama:latest` | không publish (nội bộ `11434`) | Runtime chạy model trả lời và embedding |

Dữ liệu của Ollama được giữ trong named volume `ollama_models`, nên chỉ cần tải model một lần cho mỗi máy. Cổng `11434` không được publish ra host để tránh xung đột với Ollama cài sẵn trên máy; backend gọi Ollama qua tên service `ollama` trong mạng nội bộ của Compose.

## Yêu cầu

- Docker Engine và Docker Compose v2 (`docker compose version`).
- Khoảng 8 GB RAM trống cho model mặc định `qwen2.5:7b` (xem bảng chọn model bên dưới).
- Kết nối Internet ở lần chạy đầu để tải image và model.
- Tùy chọn: GPU NVIDIA + `nvidia-container-toolkit` để tăng tốc.

## Khởi chạy nhanh

```bash
git clone <repository-url> chatbot
cd chatbot

# 1. Chạy Ollama trước
docker compose up -d ollama

# 2. Tải model (chỉ cần làm một lần)
docker compose exec ollama ollama pull bge-m3
docker compose exec ollama ollama pull qwen2.5:7b

# 3. Build và chạy backend + frontend
docker compose up --build -d
```

Mở giao diện tại **http://localhost:3000**.

> Thứ tự trên rất quan trọng: backend kiểm tra Ollama và sự tồn tại của cả hai model ngay khi khởi động. Nếu model chưa có, backend sẽ khởi động lại liên tục và frontend không được start (do `depends_on: service_healthy`).

Kiểm tra trạng thái và API:

```bash
docker compose ps
docker compose logs -f backend

curl -s http://localhost:5000/chat \
  -X POST -H 'Content-Type: application/json' \
  -d '{"message":"GPA hiện tại?"}'
```

Tùy chỉnh cấu hình (không bắt buộc):

```bash
cp backend/.env.example backend/.env
# sửa backend/.env rồi tạo lại backend:
docker compose up -d --force-recreate backend
```

## Cấu hình

Biến môi trường được đặt trong `backend/.env` hoặc trong mục `environment` của `docker-compose.yml`. Các giá trị mặc định đã có sẵn trong `backend/Dockerfile`.

| Biến | Mặc định | Ý nghĩa |
|------|----------|---------|
| `CHATBOT_ANSWER_MODEL` | `qwen2.5:7b` | Model trả lời |
| `CHATBOT_EMBEDDING_MODEL` | `bge-m3` | Model embedding |
| `CHATBOT_RELEVANCE_THRESHOLD` | `1.0` | Ngưỡng lọc đoạn không liên quan |
| `CHATBOT_FUZZY_CUTOFF` | `80` | Ngưỡng khớp mờ với các bản ghi `qa` |
| `CHATBOT_SOURCE_PATH` | `backend/data/chatbot.txt` | Tệp nguồn tri thức duy nhất |
| `CHATBOT_LEGACY_SOURCES` | `false` | Bật đọc `qa.txt`/`kb.json`/`backend/data/` để rollback tạm thời |
| `CHATBOT_DATA_DIR` | `backend/data` | Thư mục tài liệu cũ (deprecated, chỉ dùng khi legacy) |
| `CHATBOT_QA_PATH` | `backend/qa.txt` | Tệp Q&A cũ (deprecated, chỉ dùng khi legacy) |
| `CHATBOT_OLLAMA_BASE_URL` | `http://ollama:11434` | Địa chỉ Ollama trong mạng Docker |
| `CHATBOT_CHUNK_SIZE` | `500` | Kích thước đoạn |
| `CHATBOT_CHUNK_OVERLAP` | `50` | Độ chồng đoạn |
| `CHATBOT_TOP_K` | `3` | Số đoạn lấy ra mỗi câu hỏi |
| `CHATBOT_QUERY_REWRITE` | `auto` | Sửa chính tả/bổ sung dấu: `auto`, `always`, `off` |
| `CHATBOT_KB_PATH` | `backend/kb.json` | Tệp KB engine |
| `CHATBOT_KB_HIGH_THRESHOLD` | `0.78` | Ngưỡng trả lời trực tiếp từ KB |
| `CHATBOT_KB_MID_THRESHOLD` | `0.55` | Ngưỡng gợi ý câu hỏi gần đúng |
| `CHATBOT_KB_MAX_SUGGESTIONS` | `3` | Số gợi ý tối đa |
| `CHATBOT_QUERY_CACHE_SIZE` | `512` | Kích thước cache truy vấn |
| `CHATBOT_RATE_LIMIT` | `60/minute` | Giới hạn request mỗi IP |
| `CHATBOT_HOST` | `127.0.0.1` (local), `0.0.0.0` (Docker) | Địa chỉ Flask lắng nghe |
| `CHATBOT_PORT` | `5000` | Cổng Flask |

Trong Docker, không đặt `CHATBOT_OLLAMA_BASE_URL=http://127.0.0.1:11434` vì `127.0.0.1` là chính container backend. Dùng tên service `http://ollama:11434`.

`VITE_API_BASE_URL` của frontend được nhúng lúc build. `docker-compose.yml` đặt giá trị rỗng để trình duyệt gọi `/chat` cùng origin, sau đó nginx chuyển tiếp tới backend. Muốn đổi giá trị này phải build lại frontend:

```bash
docker compose up -d --build frontend
```

## Chọn cỡ model theo RAM

| RAM còn trống | Model trả lời |
|---------------|---------------|
| Dưới 4 GB | `qwen2.5:1.5b` (nên nâng cấp máy hoặc dùng API ngoài) |
| Khoảng 4 GB | `qwen2.5:3b` |
| 8 GB trở lên | `qwen2.5:7b` |
| 16 GB trở lên | `qwen2.5:14b` |

Ví dụ đổi sang `qwen2.5:3b`:

```bash
docker compose exec ollama ollama pull qwen2.5:3b
echo 'CHATBOT_ANSWER_MODEL=qwen2.5:3b' >> backend/.env
docker compose up -d --force-recreate backend
```

Gợi ý cấu hình theo máy:

```bash
docker compose exec backend python backend/scripts/recommend_model.py
```

## GPU NVIDIA (tùy chọn)

Mở khối `deploy` trong service `ollama` của `docker-compose.yml`, sau đó:

```bash
docker compose up -d --force-recreate ollama
docker compose exec ollama nvidia-smi   # nếu có GPU
```

## Quản lý nguồn tri thức

Backend đọc một tệp nguồn duy nhất `backend/data/chatbot.txt`, được bind mount vào container:

```text
backend/data/chatbot.txt → /app/backend/data/chatbot.txt
```

Sửa tệp trên máy host có hiệu lực ngay: backend tự phát hiện thay đổi và tạo lại chỉ mục khi cần, không cần khởi động lại. Nếu tệp mới không hợp lệ, backend giữ nguyên nguồn tốt gần nhất và ghi cảnh báo.

Định dạng rút gọn:

```text
CHATBOT-SOURCE v1

=== RECORD ===
kind: qa
id: gpa
topic: Học tập
questions:
- GPA hiện tại của bạn là bao nhiêu?
answer:
GPA hiện tại là 8.30/10.0.
bullets:
- GPA xét chuyên ngành: 8.31/10.0
=== END ===
```

`kind: qa` được dùng cho KB engine, khớp mờ và RAG; `kind: doc` chỉ dùng cho RAG. Đặc tả đầy đủ ở `specs/005-unified-text-source/contracts/source-format.md`.

Kiểm tra và chuyển đổi dữ liệu cũ:

```bash
docker compose exec backend python backend/scripts/manage_docs.py validate
docker compose exec backend python backend/scripts/manage_docs.py migrate \
  --from-data backend/data --qa backend/qa.txt --kb backend/kb.json \
  --to backend/data/chatbot.txt
```

Thêm, thay thế, xóa hoặc hỏi thử:

```bash
docker cp /tmp/nghi-phep.txt chatbot-backend:/tmp/nghi-phep.txt
docker compose exec backend python backend/scripts/manage_docs.py add /tmp/nghi-phep.txt --name nghi-phep.txt

docker compose exec backend python backend/scripts/manage_docs.py list
docker compose exec backend python backend/scripts/manage_docs.py delete nghi-phep.txt
docker compose exec backend python backend/scripts/manage_docs.py ask "nhân viên được nghỉ bao nhiêu ngày phép?" --debug
```

Thao tác ghi dùng tệp tạm rồi thay thế nguyên tử. `ask --debug` chỉ dành cho người vận hành. Để rollback tạm thời về nguồn cũ, đặt `CHATBOT_LEGACY_SOURCES=true` rồi tạo lại backend.

## API

### `POST /chat`

```bash
curl -s http://localhost:3000/chat \
  -X POST -H 'Content-Type: application/json' \
  -d '{"message":"GPA hiện tại?"}'
```

```json
{ "type": "answer", "score": null, "response": "GPA hiện tại là 8.30", "answer_bullets": null }
```

### `POST /chat/stream`

Trả về `text/event-stream`:

```text
data: {"type":"chunk","content":"GPA "}

data: {"type":"chunk","content":"hiện tại là 8.30"}

data: {"type":"done"}
```

Lỗi giữa chừng dùng `data: {"type":"error","message":"..."}`. Frontend tự quay về `POST /chat` nếu endpoint stream không khả dụng. Nginx đã tắt buffer cho SSE.

## Kiểm thử

Backend không chép thư mục test vào image, nên chạy test trên máy host:

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
pytest backend/tests
```

Một số kiểm thử backend cần Ollama và model đã pull; nếu thiếu, chúng được bỏ qua. Kiểm thử riêng cho nguồn hợp nhất:

```bash
pytest backend/tests/test_source_*.py
```

Frontend (cần Node.js 22.12 trở lên, khớp với `node:22-alpine` trong `frontend/Dockerfile`):

```bash
cd frontend
npm ci
npm run test
npm run lint
npm run typecheck
npm run build
```

Kết quả kiểm thử frontend chạy bằng jsdom, không cần backend thật.

## Vận hành

```bash
docker compose ps                     # trạng thái + health
docker compose logs -f backend        # log backend
docker compose logs -f frontend       # log nginx
docker compose restart backend        # khởi động lại một service

docker compose up -d --build          # build lại sau khi sửa mã nguồn
docker compose down                   # dừng, giữ nguyên volume và dữ liệu
docker compose down -v                # dừng và xóa volume (mất model Ollama)
```

- Frontend chờ backend khỏe mạnh rồi mới start; backend chờ Ollama khỏe mạnh.
- Backend chỉ lắng nghe sau khi `warm_up()` xác nhận nguồn `chatbot.txt`, Ollama, hai model và chỉ mục FAISS.
- Embedding cache `backend/embeddings_cache.npz` được tạo lại tự động khi nội dung nguồn hoặc cấu hình chunking thay đổi.
- Lịch sử trò chuyện chỉ nằm trong bộ nhớ trình duyệt cho phiên hiện tại; tải lại trang sẽ bắt đầu không gian làm việc mới. Không có đăng nhập, lịch sử phía máy chủ hay đồng bộ đa thiết bị.
- Backend dùng Flask development server. Khi triển khai thật, nên chạy sau reverse proxy và thay bằng WSGI server (ví dụ Gunicorn).

## Cấu trúc repository

| Đường dẫn | Vai trò |
|-----------|---------|
| `frontend/` | Giao diện React: chat, Markdown, code copy, theme, cuộc trò chuyện trong phiên |
| `backend/` | Dịch vụ Python: API, KB engine, RAG, quản lý nguồn, đánh giá, kiểm thử |
| `backend/data/chatbot.txt` | Nguồn tri thức hợp nhất duy nhất (`CHATBOT-SOURCE v1`) |
| `backend/Dockerfile` | Image backend Python 3.11 |
| `frontend/Dockerfile` | Build React rồi phục vụ bằng nginx |
| `frontend/nginx.conf` | SPA fallback + proxy `/chat` sang backend |
| `docker-compose.yml` | Định nghĩa ba service, healthcheck, volume và cổng |
| `app.py` | Shim tương thích để `python app.py` vẫn chạy backend |
| `specs/` | Đặc tả, kế hoạch, hợp đồng và tasks của từng tính năng |
| `backend/.env.example` | Mẫu biến môi trường |

## Xử lý sự cố

| Triệu chứng | Cách xử lý |
|-------------|------------|
| Backend restart liên tục, log báo không tìm thấy model | `docker compose exec ollama ollama pull bge-m3` và pull model trả lời |
| Log báo không kết nối được Ollama | Giữ `CHATBOT_OLLAMA_BASE_URL=http://ollama:11434`, không dùng `127.0.0.1` |
| Frontend không start | Xem `docker compose ps` và log backend; frontend chỉ start khi backend healthy |
| Cổng đã bị chiếm | Đổi cổng host trong `docker-compose.yml` (ví dụ `3001:80`, `5001:5000`) |
| Hết RAM hoặc trả lời rất chậm | Chuyển sang model nhỏ hơn ở bảng trên |
| Đổi biến môi trường không có tác dụng | Dùng `docker compose up -d --force-recreate backend` |
| Đổi `VITE_API_BASE_URL` không có tác dụng | Build lại frontend: `docker compose up -d --build frontend` |
| Cần xóa toàn bộ model đã tải | `docker compose down -v` (dung lượng lớn, tải lại sẽ lâu) |
