# Chatbot giới thiệu bản thân

Chatbot hỏi đáp tiếng Việt giới thiệu hồ sơ học tập của Văn Phú Đức. Hệ thống kết hợp tra cứu câu hỏi có sẵn, tìm kiếm ngữ nghĩa trên tài liệu cá nhân (RAG) và mô hình ngôn ngữ chạy cục bộ qua Ollama.

## Tính năng

- Trả lời câu hỏi về GPA, điểm môn học, trường, mục tiêu, thế mạnh.
- Khớp câu hỏi có sẵn trong `qa.txt` bằng so khớp mờ (fuzzy matching).
- Tìm đoạn tài liệu liên quan bằng embedding `bge-m3` và FAISS.
- Sinh câu trả lời tiếng Việt ngắn gọn bằng Qwen2.5, chỉ dùng dữ liệu được cung cấp.
- Từ chối trả lời (`Tôi không biết`) khi câu hỏi ngoài phạm vi dữ liệu.
- Bộ 15 câu hỏi đánh giá và bảng so sánh trước/sau khi đổi model.

## Kiến trúc

```text
Người dùng
   │
   ▼
index.html  ──POST /chat──▶  app.py (Flask)
                                 │
                                 ▼
                            chatbox.ask_ai()
                                 │
                 ┌───────────────┴───────────────┐
                 ▼                               ▼
        Khớp mờ qa.txt                  RAG: bge-m3 + FAISS
        (RapidFuzz)                     tìm top-k đoạn liên quan
                 │                               │
                 └───────────────┬───────────────┘
                                 ▼
                    Qwen2.5 qua Ollama (ChatOllama)
                                 │
                                 ▼
                          Câu trả lời tiếng Việt
```

Các thành phần chính:

| Thành phần | Vai trò |
|------------|---------|
| `app.py` | HTTP API `POST /chat`, kiểm tra dữ liệu vào, trả lỗi rõ ràng |
| `chatbox.py` | Đọc tài liệu, chia đoạn, embedding, FAISS, cấu hình, prompt, gọi LLM |
| `documents.py` | Thêm/thay thế/xóa/liệt kê nguồn, ghi nguyên tử, trích xuất PDF |
| `text_normalization.py` | Chuẩn hóa tiếng Việt dùng chung cho tài liệu và câu hỏi |
| `index.html` | Giao diện chat tĩnh |
| `data/` | Kho dữ liệu hồ sơ (`.txt`, `.xlsx`, `.pdf`, `.docx`, `.csv`) |
| `qa.txt` | Cặp câu hỏi – câu trả lời có sẵn |
| `evaluation/` | Bộ câu hỏi, chạy đánh giá, tổng hợp bảng so sánh |
| `scripts/` | Tiện ích, ví dụ gợi ý cỡ model theo RAM |
| `tests/` | Kiểm thử API, truy xuất, câu trả lời và từ chối |

## Yêu cầu

- Python 3.11 trở lên.
- [Ollama](https://ollama.com/) đang chạy cục bộ.
- RAM đủ cho cỡ model chọn (xem bảng bên dưới).

## Cài đặt

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

ollama pull bge-m3
\```

Kiểm tra model đã có:

```bash
ollama list
```

## Chọn cỡ model theo RAM

| RAM còn trống | Model trả lời |
|---------------|---------------|
| Dưới 4 GB | `qwen2.5:1.5b` (nên nâng cấp máy hoặc dùng API ngoài) |
| Khoảng 4 GB | `qwen2.5:3b` |
| 8 GB trở lên | `qwen2.5:7b` |
| 16 GB trở lên | `qwen2.5:14b` |

Có GPU rời sẽ nhanh hơn, nhưng RAM/VRAM vẫn quyết định cỡ model. Có thể dùng script:

```bash
python scripts/recommend_model.py
```

## Cấu hình

Ứng dụng đọc biến môi trường. Xem mẫu trong `.env.example`:

| Biến | Mặc định | Ý nghĩa |
|------|----------|---------|
| `CHATBOT_ANSWER_MODEL` | `qwen2.5:7b` | Model trả lời |
| `CHATBOT_EMBEDDING_MODEL` | `bge-m3` | Model embedding |
| `CHATBOT_RELEVANCE_THRESHOLD` | `1.0` | Ngưỡng lọc đoạn không liên quan (cần chỉnh lại sau khi đổi embedding) |
| `CHATBOT_FUZZY_CUTOFF` | `80` | Ngưỡng khớp mờ với `qa.txt` |
| `CHATBOT_DATA_DIR` | `data` | Thư mục dữ liệu |
| `CHATBOT_QA_PATH` | `qa.txt` | Tệp câu hỏi đáp |
| `CHATBOT_OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Địa chỉ Ollama |
| `CHATBOT_CHUNK_SIZE` | `500` | Kích thước đoạn |
| `CHATBOT_CHUNK_OVERLAP` | `50` | Độ chồng đoạn |
| `CHATBOT_TOP_K` | `3` | Số đoạn lấy ra mỗi câu hỏi; tăng lên `5` khi thông tin nằm rải rác |
| `CHATBOT_QUERY_REWRITE` | `auto` | Sửa chính tả/bổ sung dấu cho câu hỏi trước khi tìm kiếm: `auto`, `always`, `off` |

Ứng dụng không tự đọc tệp `.env`; hãy đặt biến trong shell hoặc dùng công cụ nạp `.env`.

```bash
export CHATBOT_ANSWER_MODEL=qwen2.5:3b
export CHATBOT_EMBEDDING_MODEL=bge-m3
export CHATBOT_RELEVANCE_THRESHOLD=1.0
```

Windows PowerShell:

```powershell
$env:CHATBOT_ANSWER_MODEL = "qwen2.5:3b"
$env:CHATBOT_EMBEDDING_MODEL = "bge-m3"
```

## Quản lý tài liệu

Nguồn tài liệu được lưu thành tệp trong `CHATBOT_DATA_DIR` (mặc định `data/`). Tên nguồn là tên tệp và là khóa để thay thế/xóa/liệt kê. Hỗ trợ `.txt`, `.pdf`, `.docx`, `.xlsx`, `.csv`; PDF phải có lớp văn bản (không OCR PDF quét ảnh).

```bash
# Thêm mới (hoặc cập nhật nếu tên đã tồn tại)
python scripts/manage_docs.py add /tmp/nghi-phep.txt --name nghi-phep.txt

# Thay thế bắt buộc nguồn đã tồn tại
python scripts/manage_docs.py replace /tmp/nghi-phep-moi.txt --name nghi-phep.txt

# Xóa và liệt kê
python scripts/manage_docs.py delete nghi-phep.txt
python scripts/manage_docs.py list

# Hỏi thử kèm chẩn đoán truy xuất
python scripts/manage_docs.py ask "nhân viên được nghỉ bao nhiêu ngày phép?" --debug
```

Thao tác ghi dùng tệp tạm rồi thay thế nguyên tử, nên nếu lỗi thì bản cũ vẫn nguyên vẹn. Chỉ mục FAISS tự phát hiện thay đổi tệp và tạo lại khi cần, không cần khởi động lại Flask. `ask --debug` in câu hỏi gốc, dạng chuẩn hóa, dạng đã sửa, nguồn, điểm từng đoạn và kết quả (`answered`, `refused`, `rephrase`). Các thông tin này không xuất hiện trong `POST /chat`.

Không cần thêm gói phụ thuộc: tính năng dùng lại Flask, LangChain, FAISS, Ollama, `pypdf`, `pandas`, `python-docx`, `docx2txt` và `RapidFuzz` đã có.

## Chạy ứng dụng

```bash
python app.py
```

Mở `index.html` trong trình duyệt. Giao diện gửi yêu cầu tới `http://127.0.0.1:5000/chat`.

Khi khởi động, ứng dụng kiểm tra thư mục dữ liệu, tệp `qa.txt`, kết nối Ollama và sự tồn tại của hai model. Nếu thiếu, chương trình dừng với thông báo hướng dẫn.

## API

`POST /chat`

```json
{
  "message": "GPA hiện tại của bạn là bao nhiêu?"
}
```

Phản hồi thành công:

```json
{
  "response": ""
}
```

| Mã | Trường hợp |
|----|------------|
| `200` | Trả lời thành công |
| `400` | JSON không hợp lệ, thiếu `message`, hoặc `message` rỗng |
| `500` | Lỗi model/kết nối; nội dung lỗi nằm trong `error` |

## Đánh giá chất lượng

Bộ câu hỏi cố định: `evaluation/questions.json` (15 câu; gồm đáp án trực tiếp, diễn đạt khác, không dấu, đại từ khác, ngoài chủ đề).

Chạy từng mốc:

```bash
python evaluation/run_eval.py --milestone original
python evaluation/run_eval.py --milestone embedding-changed
python evaluation/run_eval.py --milestone answer-model-changed
```

Tổng hợp bảng so sánh:

```bash
python evaluation/report.py --selected answer-model-changed
```

Kết quả nằm trong `evaluation/results/`. Mỗi câu được chấm thủ công theo bốn tiêu chí: đúng thông tin, biết từ chối, tiếng Việt tự nhiên, tốc độ.

Quy trình khuyến nghị: chạy mốc gốc trước khi đổi model, sau đó đổi embedding → tạo lại chỉ mục → chỉnh ngưỡng → đổi model trả lời. Đổi một thứ mỗi lần để biết cải thiện đến từ đâu.

## Kiểm thử

```bash
pytest tests/
```

Các kiểm thử cần Ollama và model thật sẽ tự bỏ qua nếu môi trường chưa sẵn sàng.

## Cấu trúc dự án

```text
.
├── app.py                    # Flask API
├── chatbox.py                # RAG + cấu hình + gọi model
├── documents.py              # Vòng đời nguồn: thêm/thay thế/xóa/liệt kê
├── text_normalization.py     # Chuẩn hóa tiếng Việt dùng chung
├── index.html                # Giao diện chat
├── qa.txt                    # Câu hỏi đáp có sẵn
├── data/                     # Hồ sơ cá nhân
├── evaluation/
│   ├── questions.json        # Bộ câu hỏi đánh giá
│   ├── run_eval.py           # Chạy đánh giá theo mốc
│   ├── report.py             # Tổng hợp bảng so sánh
│   └── results/              # Kết quả sinh ra
├── scripts/
│   ├── manage_docs.py        # CLI quản lý tài liệu
│   └── recommend_model.py    # Gợi ý cỡ model theo RAM
├── tests/                    # Kiểm thử pytest
├── requirements.txt
└── .env.example
```

## Ghi chú

- Chỉ mục FAISS được tạo lại trong bộ nhớ mỗi lần khởi động và mỗi khi dấu vân tay tệp/cấu hình thay đổi; không lưu vector cũ.
- Câu hỏi và tài liệu dùng chung một pipeline chuẩn hóa tiếng Việt; dạng gốc vẫn được giữ cho câu trả lời và hiển thị.
- Khi đổi model embedding, ngưỡng `CHATBOT_RELEVANCE_THRESHOLD` phải được chỉnh lại vì dải điểm thay đổi.
- Model Qwen3 không thuộc cấu hình của ứng dụng; chương trình sẽ báo lỗi nếu chọn Qwen3.
- Câu trả lời chỉ dựa trên `data/`, `qa.txt`; câu hỏi ngoài phạm vi trả về `Tôi không biết`.

## Xử lý sự cố

| Hiện tượng | Cách xử lý |
|------------|------------|
| `Không kết nối được Ollama` | Chạy `ollama serve` và kiểm tra `CHATBOT_OLLAMA_BASE_URL` |
| `Không tìm thấy model ...` | Chạy `ollama pull <model>` hoặc chọn cỡ nhỏ hơn |
| `Không tìm thấy thư mục dữ liệu` | Kiểm tra `CHATBOT_DATA_DIR` và thư mục `data/` |
| Trả lời `Tôi không biết` quá nhiều | Hạ ngưỡng hoặc kiểm tra lại chỉ mục/embedding |
| Trả lời bịa thông tin | Tăng ngưỡng, kiểm tra prompt và dữ liệu đầu vào |
| Chậm hoặc hết RAM | Dùng cỡ Qwen2.5 nhỏ hơn |
