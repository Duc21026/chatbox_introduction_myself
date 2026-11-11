# Implementation Plan: Unified Text Knowledge Source

**Branch**: `005-unified-text-source` | **Date**: 2026-11-11 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/005-unified-text-source/spec.md`

## Summary

Thay ba nguồn dữ liệu hiện tại (`backend/data/`, `backend/qa.txt`, `backend/kb.json`) bằng một tệp văn bản duy nhất `backend/data/chatbot.txt`. Tệp dùng định dạng line-oriented có header `CHATBOT-SOURCE v1` và các bản ghi `kind: qa|doc`. Một parser/validator thuần Python chịu trách nhiệm parse, kiểm tra và ánh xạ sang KB Engine, khớp mờ và tài liệu RAG. Backend giữ nguyên API `POST /chat` và `POST /chat/stream`; cấu hình chuyển sang `CHATBOT_SOURCE_PATH`, kèm cờ `CHATBOT_LEGACY_SOURCES` để rollback trong giai đoạn chuyển đổi.

## Technical Context

**Language/Version**: Python 3.11 (backend hiện tại), TypeScript/React không thay đổi.

**Primary Dependencies**: Flask, Flask-CORS, Flask-Limiter, LangChain, `langchain-ollama`, `langchain-text-splitters`, FAISS (`faiss-cpu`), RapidFuzz, numpy, pytest. Không thêm dependency runtime mới.

**Storage**:
- Một tệp nguồn `backend/data/chatbot.txt` (UTF-8, NFC, LF, ≤ 20 MB).
- Chỉ mục FAISS trong bộ nhớ, tái tạo khi signature đổi.
- `backend/embeddings_cache.npz` cho KB Engine.
- Volume `ollama_models` cho model Ollama.
- Bind mount Docker chỉ cần tệp `chatbot.txt` sau khi migrate.

**Testing**: `pytest backend/tests`; test parser/validator/mapping không cần Ollama; test API dùng monkeypatch; test CLI dùng `tmp_path`; smoke test Docker.

**Target Platform**: Linux server / Docker Compose; chạy được trên máy phát triển với Python 3.11.

**Project Type**: Web service (backend Python + frontend React hiện có; feature chỉ tác động backend và dữ liệu).

**Performance Goals**:
- Parse + validate tệp 1 MB < 1 giây trên máy phát triển.
- Không tăng đáng kể độ trễ request hiện tại; cache parsed source theo signature.
- Tái sử dụng embedding cache khi nội dung KB không đổi.

**Constraints**:
- Đúng một tệp nguồn tri thức; không quét nhiều tệp mặc định.
- UTF-8 không BOM, Unicode NFC, LF, tối đa 20 MB.
- Không đổi thuật toán xếp hạng, ngưỡng KB (0.78/0.55) hay mô hình.
- Không phá vỡ API hiện tại.
- Bắt buộc báo lỗi kèm số dòng; không nạp một phần.
- Docker phải chạy được khi chỉ mount `chatbot.txt`.

**Scale/Scope**: Chatbot giới thiệu cá nhân, khoảng 10–30 bản ghi, 1 người dùng đồng thời; tệp dữ liệu vài chục KB đến vài MB.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md` hiện vẫn là template mặc định với các placeholder `[PRINCIPLE_1_NAME]`, `[PROJECT_NAME]`, `[GOVERNANCE_RULES]`; không có nguyên tắc hay gate nào được ratify.

- **Gate result**: PASS (không có gate cụ thể để vi phạm).
- **Ghi chú**: Nên ratify constitution trước khi triển khai dài hạn. Trong phạm vi feature này, kế hoạch tuân theo quy ước sẵn có của repo: Python 3.11, pytest, Flask, Docker Compose, không thêm dependency không cần thiết.
- **Violations**: none.

## Project Structure

### Documentation (this feature)

```text
specs/005-unified-text-source/
├── spec.md              # Đặc tả yêu cầu (đã có)
├── template.txt         # Mẫu tệp nguồn hợp nhất (đã có)
├── plan.md              # File này
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── source-format.md # Hợp đồng định dạng tệp
│   ├── manage-docs-cli.md # Hợp đồng CLI validate/migrate
│   └── http-api.md      # Hợp đồng API không đổi
└── tasks.md             # Phase 2 output (/speckit.tasks - không tạo ở đây)
```

### Source Code (repository root)

```text
backend/
├── source_format.py        # MỚI: parser, validator, mapping → DerivedSource
├── chatbox.py              # SỬA: dùng DerivedSource cho RAG + khớp mờ; signature
├── kb_engine.py            # SỬA: nhận KB items từ DerivedSource
├── documents.py            # GIỮ: loader trích xuất dùng cho migrate
├── text_normalization.py   # GIỮ: thêm NORMALIZER_VERSION
├── app.py                  # SỬA: warm-up KB/RAG từ nguồn hợp nhất
├── scripts/
│   └── manage_docs.py      # SỬA: thêm validate, migrate
└── tests/
    ├── test_source_format.py       # MỚI: parse/validate/escaping
    ├── test_source_mapping.py      # MỚI: qa/doc → KB/QA/RAG
    ├── test_source_cli.py          # MỚI: validate/migrate
    └── (các test hiện có)          # GIỮ, cập nhật fixture nếu cần

app.py                      # SỬA: gọi warm_up_kb() khi chạy shim
docker-compose.yml          # SỬA: chỉ mount chatbot.txt
backend/Dockerfile          # SỬA nếu cần biến môi trường mới
```

**Structure Decision**: Giữ cấu trúc single-backend hiện có. Toàn bộ logic định dạng mới tập trung trong `backend/source_format.py`; `chatbox.py` và `kb_engine.py` chỉ thay nguồn dữ liệu đầu vào, không đổi thuật toán. Frontend không thay đổi.

## Phase 0 — Research (hoàn tất)

Đã tạo `research.md` với 10 quyết định, bao gồm:

- Định dạng line-oriented thay vì YAML/JSON.
- Parser một lượt, validate toàn bộ trước khi sinh derived index.
- Ánh xạ `qa` → KB + QA + RAG; `doc` → RAG.
- Cấu hình `CHATBOT_SOURCE_PATH`, legacy flag.
- Signature gồm content hash + model + chunk params + normalizer version.
- Mở rộng `manage_docs.py` với `validate`/`migrate`.
- Chiến lược rollback khi tệp đổi nhưng sai.

## Phase 1 — Design & Contracts (hoàn tất)

Đã tạo:

- `data-model.md`: `SourceFile`, `SourceRecord`, `QAPair`, `KBItem`, `RAGDocument`, `SourceSignature`, `ValidationIssue`, `DerivedSource`.
- `contracts/source-format.md`: grammar và escaping normative.
- `contracts/manage-docs-cli.md`: schema, exit code, JSON output cho `validate`/`migrate`.
- `contracts/http-api.md`: xác nhận API không đổi.
- `quickstart.md`: 9 kịch bản kiểm chứng end-to-end.

## Phase 1 — Re-evaluate Constitution Check

Sau thiết kế, không phát sinh nguyên tắc vi phạm. Không thêm dependency runtime, không đổi API, không mở rộng phạm vi sang frontend. **PASS**.

## Implementation Sequence (tham khảo cho `/speckit.tasks`)

1. `source_format.py`: parse header/record/field, escaping, validation codes, mapping.
2. `text_normalization.py`: thêm `NORMALIZER_VERSION`.
3. `chatbox.py`: nhận `DerivedSource`, thay `_load_documents`/`_load_qa_data`/`_source_signature`.
4. `kb_engine.py`: nhận `kb_items`/`kb_hash` từ `DerivedSource`.
5. `app.py` (root shim): gọi `kb_engine.warm_up_kb()` để Docker dùng KB Engine.
6. `manage_docs.py`: thêm `validate`, `migrate`.
7. Cấu hình Docker: `CHATBOT_SOURCE_PATH`, chỉ mount `chatbot.txt`.
8. Tests: parser, mapping, CLI, API regression, Docker smoke.
9. Migrate dữ liệu thật và cập nhật README.

## Complexity Tracking

Không có vi phạm constitution cần justify.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Không có | — | — |
