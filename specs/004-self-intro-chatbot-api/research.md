# Research: Self-Introduction Chatbot API

**Feature**: `004-self-intro-chatbot-api`
**Date**: 2026-11-10

---

## 1. Kiến trúc tổng thể: Mở rộng backend hiện tại vs. tạo service mới

**Decision**: Mở rộng `backend/` hiện có — thêm `kb.json` store, `kb_engine.py` module, và bổ sung 3 kiểu response vào `/chat`.

**Rationale**:
- Backend Flask + FAISS + Ollama đã chạy; contract `POST /chat` và `POST /chat/stream` đã được frontend 003 tiêu thụ.
- Tạo service mới (FastAPI riêng) đồng nghĩa frontend phải trỏ đến 2 URL khác nhau — phức tạp không cần thiết.
- Flask đủ async (via `stream_with_context`) cho usecase này; chỉ endpoint `/chat/stream` cần non-blocking và đã có sẵn.
- Pipeline mới (`kb_engine.py`) sẽ được ưu tiên tra cứu **trước** pipeline RAG FAISS hiện tại, không phá vỡ contract cũ.

**Alternatives considered**:
- FastAPI riêng: clean hơn về type hints, nhưng cần thêm proxy hoặc sửa frontend — không tương xứng lợi ích.
- Thay hoàn toàn `chatbox.py`: rủi ro, kiểm thử hiện tại sẽ hỏng.

---

## 2. Knowledge Base format: kb.json vs. kb.yaml vs. mở rộng qa.txt

**Decision**: `kb.json` với schema có cấu trúc (id, topic, questions[], answer hoặc answer_bullets[]).

**Rationale**:
- `qa.txt` hiện tại dạng `câu hỏi|câu trả lời` đơn giản, không hỗ trợ nhiều cách hỏi cho 1 câu trả lời.
- JSON cho phép `answer_bullets: []` (mảng) để frontend render gạch đầu dòng — không thể biểu diễn trong qa.txt.
- JSON native với Python, không cần thêm thư viện (yaml cần `pyyaml`).
- Được hash bằng `hashlib.md5` để phát hiện thay đổi — cùng pattern với `_source_signature()` hiện tại.

**Alternatives considered**:
- Mở rộng qa.txt với delimiter phức tạp: giòn, khó maintain.
- SQLite: overkill cho < 1000 mục, không cần query phức tạp.

---

## 3. Embedding + similarity: giữ FAISS/bge-m3 hay tính cosine thuần numpy

**Decision**: Dùng `numpy` cosine similarity trực tiếp trên embedding matrix `(N×D)` — **không** tạo FAISS index riêng cho kb.json.

**Rationale**:
- kb.json ≤ 1000 mục câu hỏi mẫu → `N×D` matrix nhỏ (1000 × 1024 float32 ≈ 4 MB RAM); brute-force cosine < 1 ms.
- Tránh duplicate: đã có FAISS index cho tài liệu RAG trong `get_db()`; thêm FAISS thứ hai cho kb.json gây nhầm lẫn.
- Embedding được tính qua `OllamaEmbeddings` hiện có (cùng model `bge-m3`), cache ra `embeddings_cache.npz` (numpy binary).
- Invalidation bằng hash file `kb.json` — cùng pattern với `_index_signature()`.

**Alternatives considered**:
- faiss-cpu IndexFlatIP: dùng được nhưng không cần thiết ở scale này.
- sentence-transformers trực tiếp: thêm dependency nặng; model bge-m3 đã qua Ollama.

---

## 4. Hybrid scoring: trọng số embedding + fuzzy

**Decision**: `score = 0.8 × cosine_sim + 0.2 × (rapidfuzz.fuzz.WRatio / 100)` — tính trên top-20 ứng viên embedding rồi re-rank.

**Rationale**:
- Tính hybrid trên toàn bộ N câu tốn O(N) fuzzy — chấp nhận được với N ≤ 1000.
- WRatio của rapidfuzz xử lý được "ban biet ngon ngu j" vs "bạn biết ngôn ngữ nào" nhờ partial token matching.
- `rapidfuzz` đã có trong `requirements.txt`.
- Trọng số 0.8/0.2 là điểm khởi đầu từ spec; phải chỉnh sau khi có test set thực.

**Alternatives considered**:
- Chỉ embedding: miss lỗi gõ kiểu transposition.
- Chỉ fuzzy: không hiểu ngữ nghĩa, miss paraphrase.
- BM25: thêm thư viện (`rank-bm25`), hoạt động trên token không phải char — ít lợi hơn fuzzy cho typo.

---

## 5. Ngưỡng quyết định và xử lý vùng MID

**Decision**: Ngưỡng khởi điểm HIGH=0.78, MID=0.55. Vùng MID → gọi Qwen sửa chính tả rồi embed lại một lần.

**Rationale**:
- Giá trị này lấy từ spec và phù hợp với ngưỡng `CHATBOT_RELEVANCE_THRESHOLD` hiện tại (1.0 L2 distance ~ cosine 0.78+).
- Qwen sửa chính tả đã có sẵn trong `_rewrite_query()` của `chatbox.py` — tái sử dụng, không viết lại.
- Giới hạn gọi LLM duy nhất ở vùng MID để đảm bảo < 1 s theo SC-002.

**Lưu ý**: Ngưỡng thực tế phải hiệu chỉnh sau khi có test set 30-50 câu (xem quickstart.md).

---

## 6. Response format và backward compatibility

**Decision**: Thêm trường `type`, `score`, `answer_bullets`, `suggestions`, `topics` vào response JSON. Trường `response` hiện tại vẫn giữ cho backward compat.

**Rationale**:
- Frontend 003 đọc `response.response` (string). Không được xóa trường này.
- Trường `type` mới cho phép frontend phân biệt answer / suggest / unknown và render chip / bullet.
- Nếu `type == "answer"`: `response` = chuỗi đầy đủ (backward compat), `answer_bullets` = mảng (nếu có).
- Nếu `type == "suggest"` hoặc `"unknown"`: `response` = thông báo ngắn gọn để client cũ vẫn hiển thị được.

**Alternatives considered**:
- Breaking change: đổi hoàn toàn response shape → phải sửa frontend 003 — không chấp nhận.
- Versioning endpoint `/v2/chat`: clean nhưng overkill; backward compat trong cùng endpoint đủ dùng.

---

## 7. Rate limiting

**Decision**: Dùng `flask-limiter` (thay `slowapi` đề xuất trong spec vì project dùng Flask, không FastAPI).

**Rationale**:
- `slowapi` là wrapper ASGI/Starlette; không tương thích Flask trực tiếp.
- `flask-limiter` là giải pháp chuẩn cho Flask; memory backend đủ dùng cho single-process.
- Giới hạn mặc định: 60 req/phút/IP — đủ để chặn spam, không ảnh hưởng người dùng thật.

**Alternatives considered**:
- nginx rate limit: clean hơn nhưng thêm infra dependency; Docker setup đã có nginx (feature 004 Docker).
- Không rate limit: rủi ro khi expose public.

---

## 8. Warm-up và cache

**Decision**: Warm-up khi `warm_up()` gọi: (1) build/load embedding cache từ kb.json, (2) gọi 1 lần embed dummy, (3) gọi 1 lần Qwen dummy. LRU cache 512 mục dùng `functools.lru_cache` hoặc `cachetools.LRUCache`.

**Rationale**:
- `warm_up()` hiện tại đã call `get_db()` và `get_llm()` — thêm `warm_up_kb()` vào cùng function.
- `functools.lru_cache` đủ dùng và zero-dependency; `cachetools` cần thêm vào requirements nhưng linh hoạt hơn (expire, maxsize runtime).
- Chọn `cachetools` vì maxsize có thể cấu hình qua env var.

---

## 9. Cấu trúc module mới trong backend/

**Decision**: Tạo `backend/kb_engine.py` chứa toàn bộ logic kb.json (load, embed, score, decide). `backend/app.py` và `backend/chatbox.py` không bị thay đổi cấu trúc lớn.

**Rationale**:
- Separation of concerns: `chatbox.py` = RAG pipeline, `kb_engine.py` = KB pipeline.
- `app.py` orchestrate: gọi `kb_engine` trước, nếu không có kết quả mới gọi `chatbox`.
- Dễ test độc lập: `kb_engine` không phụ thuộc Flask.
- Dễ bật/tắt: thêm env var `CHATBOT_KB_PATH` trỏ đến `kb.json`; nếu file không tồn tại thì bỏ qua KB engine và dùng RAG như cũ.

---

## 10. Tiền xử lý tiếng Việt bổ sung

**Decision**: Mở rộng `text_normalization.py` thêm: teencode dict, từ đệm filter. Giữ nguyên hàm `normalize_text()` hiện tại (không breaking).

**Rationale**:
- `normalize_text()` hiện tại xử lý: NFC, collapse repeated chars, lowercase, collapse punct, whitespace.
- Cần thêm: teencode mapping (`ko→không`, `dc→được`, v.v.), bỏ emoji, bỏ từ đệm.
- Thêm hàm `normalize_query(text)` chạy pipeline đầy đủ (gọi `normalize_text` + thêm bước mới). `normalize_text` giữ nguyên signature để không break tests.

