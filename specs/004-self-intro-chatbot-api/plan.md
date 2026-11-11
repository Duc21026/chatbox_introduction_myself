# Implementation Plan: Self-Introduction Chatbot API

**Branch**: `004-self-intro-chatbot-api` | **Date**: 2026-11-10 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/004-self-intro-chatbot-api/spec.md`

---

## Summary

Mở rộng backend Flask hiện có (`backend/`) bằng **KB Engine** mới (`kb_engine.py`) để trả lời câu hỏi từ `kb.json` với hybrid scoring (cosine embedding + fuzzy). KB Engine được đặt trước pipeline RAG FAISS hiện tại trong luồng xử lý. Response `POST /chat` được mở rộng với trường `type` / `answer_bullets` / `suggestions` / `topics` trong khi giữ backward compat qua trường `response` hiện tại.

---

## Technical Context

**Language/Version**: Python 3.11

**Primary Dependencies**:
- Flask + flask-cors (hiện có)
- flask-limiter (thêm mới — rate limiting)
- langchain-ollama + OllamaEmbeddings (hiện có — dùng lại cho KB embed)
- numpy (hiện có transitively — dùng trực tiếp cho cosine matrix)
- rapidfuzz (hiện có — fuzzy scoring)
- cachetools (thêm mới — LRU query cache)

**Storage**: File-based — `backend/kb.json` (nguồn), `backend/embeddings_cache.npz` (cache numpy)

**Testing**: pytest (hiện có); thêm test cho `kb_engine.py` và `normalize_query()`

**Target Platform**: Linux server (local hoặc Docker container)

**Project Type**: web-service (backend REST API)

**Performance Goals**:
- Câu khớp rõ (cache warm, KB hit): < 100 ms
- Câu cần Qwen sửa chính tả (vùng MID): < 1 s

**Constraints**:
- Không breaking change trên `POST /chat` và `POST /chat/stream`
- Không thêm dependency nặng (không sentence-transformers, không vector DB)
- kb.json ≤ 1 000 mục → numpy cosine đủ dùng

**Scale/Scope**: 1 người dùng đồng thời (portfolio chatbot); không yêu cầu scale ngang

---

## Constitution Check

*Constitution file chứa placeholders chưa điền — không có gate cụ thể áp dụng.*

Tự-đánh giá theo nguyên tắc dự án:

| Nguyên tắc | Trạng thái |
|---|---|
| Không phá vỡ contract `POST /chat` hiện tại | ✅ Giữ trường `response`, thêm trường mới |
| Frontend không import mã nguồn backend | ✅ Mọi tương tác qua HTTP |
| Backend tạm thời — thay thế là hạng mục riêng | ✅ Feature này chỉ mở rộng, không tái cấu trúc |
| Không tự bịa câu trả lời | ✅ 100% nội dung từ kb.json; LLM chỉ sửa chính tả |

---

## Project Structure

### Documentation (this feature)

```text
specs/004-self-intro-chatbot-api/
├── plan.md                           # This file
├── spec.md                           # Feature specification
├── research.md                       # Phase 0 — decisions & rationale
├── data-model.md                     # Phase 1 — entities & state machine
├── quickstart.md                     # Phase 1 — validation guide
├── checklists/
│   └── requirements.md               # Spec quality checklist
└── contracts/
    ├── chat-api.md                   # POST /chat extended contract
    ├── kb-schema.md                  # kb.json JSON Schema
    └── normalization-pipeline.md     # normalize_query() pipeline contract
```

### Source Code (repository root)

```text
backend/
├── app.py                  # Existing — orchestrate KB Engine BEFORE RAG fallback
├── chatbox.py              # Existing — RAG pipeline (unchanged)
├── documents.py            # Existing — document ingestion (unchanged)
├── text_normalization.py   # Extended — add normalize_query() (new function)
│
├── kb_engine.py            # NEW — KB Engine: load, embed, score, decide
├── kb.json                 # NEW — knowledge base authored by chatbot owner
├── embeddings_cache.npz    # GENERATED — gitignored, rebuilt on kb.json change
│
├── requirements.txt        # Updated — add flask-limiter, cachetools
├── .env.example            # Updated — add CHATBOT_KB_PATH, KB thresholds, cache size
│
├── data/                   # Existing — RAG documents (unchanged)
├── qa.txt                  # Existing — simple Q&A fallback (unchanged)
│
├── scripts/
│   ├── manage_docs.py      # Existing (unchanged)
│   ├── recommend_model.py  # Existing (unchanged)
│   └── tune_thresholds.py  # NEW — hiệu chỉnh HIGH/MID ngưỡng từ test set
│
└── tests/
    ├── conftest.py          # Existing (may need kb fixture)
    ├── test_chat_api.py     # Existing — extend for new response types
    ├── test_kb_engine.py    # NEW — unit tests for KB Engine
    └── test_normalization.py # NEW — unit tests for normalize_query()
```

**Structure Decision**: Single backend service, mở rộng theo chiều dọc. Không tạo package/service mới. `kb_engine.py` là module độc lập trong `backend/` — không phụ thuộc Flask, dễ test và tái sử dụng.

---

## Complexity Tracking

Không có vi phạm constitution. Không cần justification.

---

## Implementation Notes

### Luồng tích hợp trong `app.py`

```python
# POST /chat handler — sau khi implement KB Engine
def chatbot():
    question, error = _validated_question()   # thêm: max_length=200
    if error: return error

    # 1. KB Engine (mới)
    kb_response = kb_engine.query(question)
    if kb_response is not None:
        return jsonify(kb_response)

    # 2. RAG fallback (hiện tại — không đổi)
    answer = ask_ai(question)
    return jsonify({"type": "answer", "response": answer, "score": None, "answer_bullets": None})
```

### Module `kb_engine.py` — interface chính

```python
def query(message: str) -> dict | None:
    """Return ChatResponse dict nếu KB có câu trả lời, None nếu fallback sang RAG."""

def warm_up_kb() -> None:
    """Load kb.json, build/load embedding cache. Gọi từ warm_up()."""
```

### Env vars mới

| Biến | Mặc định | Ý nghĩa |
|------|----------|---------|
| `CHATBOT_KB_PATH` | `backend/kb.json` | Đường dẫn kb.json |
| `CHATBOT_KB_HIGH_THRESHOLD` | `0.78` | Ngưỡng HIGH → answer |
| `CHATBOT_KB_MID_THRESHOLD` | `0.55` | Ngưỡng MID → suggest |
| `CHATBOT_KB_MAX_SUGGESTIONS` | `3` | Số gợi ý tối đa |
| `CHATBOT_QUERY_CACHE_SIZE` | `512` | LRU cache size |
| `CHATBOT_RATE_LIMIT` | `60/minute` | flask-limiter rule |
