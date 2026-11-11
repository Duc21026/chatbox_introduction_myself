# Phase 1 Data Model: Unified Text Knowledge Source

**Feature**: `005-unified-text-source` | **Date**: 2026-11-11

## Tổng quan

Tệp `chatbot.txt` là nguồn gốc duy nhất. Parser tạo `SourceFile` gồm nhiều `SourceRecord`; bước ánh xạ tạo `DerivedSource` phục vụ KB Engine, khớp mờ và RAG. Không entity nào được ghi ngược lại tệp nguồn.

```text
SourceFile 1 ─── * SourceRecord
                    │
                    ├─ kind=qa  ──▶ KBItem + QAPair + RAGDocument
                    └─ kind=doc ──▶ RAGDocument

SourceFile ──▶ SourceSignature ──▶ SourceCache
```

## Entity: SourceFile

| Field | Type | Required | Mô tả |
|---|---|---|---|
| `path` | str | yes | Đường dẫn tuyệt đối tới `chatbot.txt` |
| `version` | str | yes | Luôn là `"1"` từ header `CHATBOT-SOURCE v1` |
| `encoding` | str | yes | Luôn là `"utf-8"`; BOM bị từ chối hoặc bỏ kèm cảnh báo |
| `text` | str | yes | Nội dung đã đọc, NFC, LF |
| `size_bytes` | int | yes | Kích thước tệp, ≤ 20 MB |
| `content_hash` | str | yes | SHA-256 của nội dung |
| `mtime_ns` | int | yes | Dùng cho signature |
| `records` | list[SourceRecord] | yes | Không rỗng |
| `warnings` | list[ValidationIssue] | no | Cảnh báo không chặn nạp |

**Validation**

- `path` phải là file thường, đọc được.
- `size_bytes > 20 * 1024 * 1024` → lỗi `E_SIZE`.
- Header sai/thiếu → `E_HEADER`.
- Không có record nào → `E_EMPTY`.

## Entity: SourceRecord

| Field | Type | Required (`qa`) | Required (`doc`) | Mô tả |
|---|---|---|---|---|
| `kind` | `"qa"` \| `"doc"` | yes | yes | Loại bản ghi |
| `id` | str | yes | yes | Slug duy nhất `[a-z0-9][a-z0-9_-]{0,63}` |
| `topic` | str | yes | yes | 1–120 ký tự |
| `questions` | list[str] | ≥ 1 | 0..n | Mỗi câu 1–200 ký tự, không trùng trong cùng record |
| `answer` | str \| None | yes nếu `bullets` rỗng | no | ≤ 4.000 ký tự |
| `bullets` | list[str] | optional | no | Mỗi bullet ≤ 300 ký tự |
| `content` | str \| None | optional | yes | Nội dung RAG, không rỗng với `doc` |
| `source` | str \| None | optional | optional | Nhãn truy vết, ≤ 300 ký tự |
| `line_start` | int | yes | yes | Dòng bắt đầu `=== RECORD ===` |
| `line_end` | int | yes | yes | Dòng `=== END ===` |

**Validation**

- `id` sai regex → `E_ID_FORMAT`; trùng trong file → `E_DUP_ID`.
- `kind` ngoài `qa|doc` → `E_KIND`.
- `topic` rỗng/quá dài → `E_TOPIC`.
- `qa` không có câu hỏi → `E_QUESTIONS`; câu rỗng/quá dài/trùng → `E_QUESTION_ITEM`.
- `qa` không có `answer` và không có `bullets` → `E_ANSWER`.
- `doc` không có `content` → `E_CONTENT`.
- Thiếu `=== END ===` → `E_RECORD_EOF`, dùng `line_start` để báo.
- Trường lạ → `W_UNKNOWN_FIELD`, bỏ qua.

**State transitions**

```text
parsed ──validate ok──▶ accepted ──map──▶ derived
   │
   └──validate fail──▶ rejected (không đưa vào derived)
```

## Entity: QAPair

| Field | Type | Mô tả |
|---|---|---|
| `question` | str | Câu hỏi gốc từ `questions` |
| `normalized_question` | str | Kết quả `normalize_text(question)` |
| `answer` | str | `answer` hoặc các bullet nối bằng dấu phẩy |
| `record_id` | str | Truy vết về `SourceRecord` |

Dùng để thay thế `backend/qa.txt` trong khớp mờ RapidFuzz.

## Entity: KBItem

Cấu trúc tương thích `kb.json` hiện tại:

| Field | Type | Mô tả |
|---|---|---|
| `id` | str | Từ `SourceRecord.id` |
| `topic` | str | Từ `SourceRecord.topic` |
| `questions` | list[str] | Từ `SourceRecord.questions` |
| `answer` | str \| None | Từ `SourceRecord.answer` |
| `answer_bullets` | list[str] \| None | Từ `SourceRecord.bullets` |

Chỉ sinh từ record `kind: qa`.

## Entity: RAGDocument

Đầu vào tương thích `langchain_core.documents.Document` hiện tại:

| Field | Type | Mô tả |
|---|---|---|
| `page_content` | str | `content`, hoặc văn bản suy ra từ `qa` |
| `metadata.source` | str | `source` nếu có, ngược lại `record_id` |
| `metadata.record_id` | str | ID bản ghi |
| `metadata.kind` | str | `qa` hoặc `doc` |
| `metadata.topic` | str | Chủ đề |
| `metadata.page` | int \| None | Chỉ có nếu `source` chứa `#page=N` |

Chunking và metadata `chunk_index` vẫn do `chatbox.get_db()` thực hiện như hiện tại.

## Entity: SourceSignature

| Field | Type | Mô tả |
|---|---|---|
| `path` | str | Đường dẫn tệp |
| `mtime_ns` | int | Thời điểm sửa |
| `size_bytes` | int | Kích thước |
| `content_hash` | str | SHA-256 |
| `embedding_model` | str | `CHATBOT_EMBEDDING_MODEL` |
| `chunk_size` | int | `CHATBOT_CHUNK_SIZE` |
| `chunk_overlap` | int | `CHATBOT_CHUNK_OVERLAP` |
| `normalizer_version` | str | Phiên bản quy tắc chuẩn hoá |

Signature bằng nhau → dùng cache; khác → parse/chunk/embed lại.

## Entity: ValidationIssue

| Field | Type | Mô tả |
|---|---|---|
| `severity` | `error` \| `warning` | Mức độ |
| `code` | str | Mã lỗi/cảnh báo |
| `message` | str | Thông báo tiếng Việt, có gợi ý sửa |
| `line` | int \| None | Số dòng 1-based |
| `record_id` | str \| None | ID bản ghi liên quan |

### Mã lỗi

| Code | Severity | Điều kiện |
|---|---|---|
| `E_FILE_MISSING` | error | Không tìm thấy tệp |
| `E_ENCODING` | error | Không decode được UTF-8 |
| `E_BOM` | error | Tệp có BOM |
| `E_SIZE` | error | > 20 MB |
| `E_HEADER` | error | Thiếu/sai `CHATBOT-SOURCE v1` |
| `E_EMPTY` | error | Không có record |
| `E_RECORD_EOF` | error | Thiếu `=== END ===` |
| `E_FIELD_ORDER` | error | Sai thứ tự/thiếu nhãn trường |
| `E_KIND` | error | `kind` không hợp lệ |
| `E_ID_FORMAT` | error | `id` sai regex |
| `E_DUP_ID` | error | `id` trùng |
| `E_TOPIC` | error | `topic` rỗng/quá dài |
| `E_QUESTIONS` | error | `qa` không có câu hỏi |
| `E_QUESTION_ITEM` | error | Câu hỏi rỗng/quá dài/trùng |
| `E_ANSWER` | error | `qa` thiếu cả `answer` và `bullets` |
| `E_CONTENT` | error | `doc` thiếu `content` |
| `W_UNKNOWN_FIELD` | warning | Trường lạ, bị bỏ qua |
| `W_ESCAPE` | warning | Dùng `\` không cần thiết |

## DerivedSource

| Field | Type | Mô tả |
|---|---|---|
| `source_file` | SourceFile | Nguồn đã parse |
| `qa_pairs` | list[QAPair] | Cho khớp mờ |
| `kb_items` | list[KBItem] | Cho `kb_engine` |
| `rag_documents` | list[RAGDocument] | Cho FAISS |
| `kb_hash` | str | Hash của phần KB để invalidate embedding cache |
| `signature` | SourceSignature | Cache key |

## Quan hệ với code hiện tại

| Thành phần hiện tại | Thay đổi |
|---|---|
| `chatbox._load_documents()` | Thay bằng đọc `DerivedSource.rag_documents` |
| `chatbox._load_qa_data()` | Thay bằng `DerivedSource.qa_pairs` |
| `chatbox._source_signature()` | Thay bằng `SourceSignature` của tệp hợp nhất |
| `kb_engine._load_kb()` | Nhận `DerivedSource.kb_items` thay vì đọc `kb.json` |
| `kb_engine._kb_hash()` | Dùng `DerivedSource.kb_hash` |
| `documents.extract_segments()` | Giữ lại cho bước migrate một lần |
| `manage_docs.py` | Thêm `validate`, `migrate` |
