# Phase 1 Data Model — Vercel + Cloudflare Workers AI

**Feature**: `008-vercel-cloudflare-deploy`
**Date**: 2026-11-17
**Input**: [spec.md](./spec.md), [plan.md](./plan.md), [research.md](./research.md)

Mô hình dữ liệu dưới đây mô tả các thực thể của **feature triển khai**. Nội dung tri thức
(`SourceRecord`, `Fact`, `Course`, `QA`) đã được đặc tả trong
`specs/007-unify-data-facts/spec.md` và `data-model.md`; feature này không định nghĩa lại
mà dùng chúng làm nguồn.

---

## E-001 — CanonicalSource

Nguồn tri thức viết tay duy nhất và dấu vân tay của nó.

| Field | Type | Required | Mô tả |
|-------|------|----------|-------|
| `path` | string | yes | `data/chatbot.txt` |
| `content_sha256` | string (64 hex) | yes | SHA-256 của nội dung tệp |
| `kb_hash` | string (64 hex) | yes | Hash của KB dẫn xuất sau facts/courses/aliases |
| `size_bytes` | integer | yes | Kích thước tệp |
| `mtime_ns` | integer | yes | Thời điểm sửa cuối (không dùng để quyết định hash) |
| `record_count` | integer | yes | Số bản ghi |
| `qa_question_count` | integer | yes | Số câu hỏi `qa` active |
| `validated_at` | ISO-8601 | yes | Lần kiểm tra hợp lệ gần nhất |

**Quan hệ**: 1 `CanonicalSource` → nhiều `SourceRecord`; 1 `CanonicalSource` → 0..1
`VectorIndex` khớp `kb_hash`.

**Quy tắc kiểm tra**:
- `validate_source()` phải trả 0 lỗi trước khi build vector hoặc deploy.
- `content_sha256` và `kb_hash` phải khớp giá trị trong `VectorIndex` thì chỉ mục mới được
  dùng.
- `path` phải nằm trong `data/`, không trỏ về `backend/data/`.

---

## E-002 — SourceRecord (dùng lại từ feature 007)

Bản ghi trong `data/chatbot.txt`.

| Field | Type | Required | Mô tả |
|-------|------|----------|-------|
| `kind` | `qa` \| `doc` \| `fact` | yes | Loại bản ghi |
| `id` | slug | yes | Định danh duy nhất |
| `topic` | string | qa/doc | Chủ đề |
| `questions` | string[] | qa | 3–5 cách hỏi (theo dữ liệu hiện tại) |
| `answer` / `bullets` / `content` | string / string[] | tùy kind | Nội dung trả lời |
| `label` / `value` / `snapshot` | string | fact | Giá trị dùng chung |
| `source` | string | no | Nguồn trích dẫn |
| `status` | `active` \| `archived` | yes | Mặc định `active` |

**Quy tắc cho feature này**:
- Chỉ `kind: qa` và `status: active` được đưa vào `VectorIndex`.
- `doc` và `fact` vẫn được parse/validate nhưng `doc` không được tìm kiếm trong phạm vi
  qa-only của feature này.
- Bản ghi `archived` không xuất hiện trong vector, gợi ý, menu chủ đề.

---

## E-003 — VectorIndex

Chỉ mục vector tính sẵn, lưu tại `data/vectors.json`.

| Field | Type | Required | Mô tả |
|-------|------|----------|-------|
| `schema_version` | integer | yes | Phiên bản schema, hiện tại `1` |
| `model` | string | yes | `@cf/baai/bge-m3` |
| `dim` | integer | yes | Số chiều vector (dự kiến 1024) |
| `normalizer_version` | string | yes | `NORMALIZER_VERSION` dùng khi build |
| `source_sha256` | string (64 hex) | yes | Hash nội dung nguồn |
| `source_kb_hash` | string (64 hex) | yes | Hash KB dẫn xuất |
| `question_count` | integer | yes | Số entry |
| `built_at` | ISO-8601 | yes | Thời điểm build |
| `entries` | VectorEntry[] | yes | Danh sách vector |

**Trạng thái**:

```text
absent ──build──► current ──source changed──► stale ──build──► current
                    │                           │
                    └──────provider error──────► error (giữ current)
```

- `absent`: chưa có tệp → health `vectors_loaded=false`; runtime dùng lexical/fuzzy.
- `current`: metadata khớp nguồn/cấu hình → dùng cosine.
- `stale`: hash lệch → **không dùng** vector cũ; health `source_hash_matches=false`; runtime
  dùng lexical/fuzzy.
- `error`: build lỗi giữa lô → không ghi tệp; giữ bản `current` trước đó.

---

## E-004 — VectorEntry

Một vector cho một câu hỏi.

| Field | Type | Required | Mô tả |
|-------|------|----------|-------|
| `id` | string | yes | `"{item_id}#{index}"` hoặc slug ổn định |
| `item_id` | string | yes | ID bản ghi `qa` |
| `source_type` | `"qa"` | yes | Loại nguồn trong phạm vi này |
| `question` | string | yes | Câu hỏi gốc |
| `norm` | string | yes | Câu hỏi sau `normalize_query` |
| `topic` | string | no | Chủ đề để hiển thị/gợi ý |
| `vector` | number[] | yes | Độ dài đúng `dim`, giá trị hữu hạn, làm tròn 5 chữ số |

**Quy tắc kiểm tra**:
- `len(vector) == dim` cho mọi entry.
- Không có `norm` trùng lặp trong cùng một `item_id`; cảnh báo nếu trùng giữa các item.
- `item_id` phải tồn tại trong nguồn `current`; nếu không → chỉ mục `stale`.
- Không chứa `NaN`, `Infinity`, hoặc vector toàn 0.

---

## E-005 — EmbeddingProvider

Cấu hình và trạng thái của dịch vụ tạo vector.

| Field | Type | Required | Mô tả |
|-------|------|----------|-------|
| `name` | `cloudflare` \| `ollama` \| `none` | yes | Provider đang dùng |
| `account_id` | string | cloudflare | Từ `CF_ACCOUNT_ID`; không bao giờ trả về client |
| `api_token` | secret | cloudflare | Từ `CF_API_TOKEN`; không log/không bundle frontend |
| `model` | string | yes | `@cf/baai/bge-m3` |
| `query_timeout_seconds` | number | yes | Mặc định 3 |
| `build_timeout_seconds` | number | yes | Mặc định 30 |
| `max_retries` | integer | yes | Mặc định 1 |
| `batch_size` | integer | yes | Mặc định 32 (điều chỉnh theo spike) |
| `last_error` | string \| null | no | Thông điệp lỗi đã lọc bí mật, dùng cho log/health |

**Trạng thái**:

```text
available ──error/quota/timeout──► degraded (fallback lexical/fuzzy)
    ▲                                      │
    └──────────── request sau ─────────────┘
```

`none` là trạng thái tắt chủ động (sự cố kéo dài), không phải lỗi.

---

## E-006 — RuntimeConfig

Biến môi trường của function deploy.

| Biến | Bắt buộc | Mặc định | Ghi chú |
|------|----------|----------|---------|
| `CF_ACCOUNT_ID` | cloudflare | — | Bí mật, chỉ server |
| `CF_API_TOKEN` | cloudflare | — | Bí mật, chỉ server |
| `CHATBOT_EMBEDDING_PROVIDER` | no | `cloudflare` (deploy) / `ollama` (local) | `none` để tắt |
| `CHATBOT_SOURCE_PATH` | no | `data/chatbot.txt` | Nguồn chuẩn |
| `CHATBOT_COURSES_PATH` | no | `data/sources/courses.csv` | |
| `CHATBOT_ALIASES_PATH` | no | `data/sources/aliases.txt` | |
| `CHATBOT_VECTORS_PATH` | no | `data/vectors.json` | |
| `CHATBOT_KB_HIGH_THRESHOLD` | no | theo `tune_weights.py` | `HIGH` |
| `CHATBOT_SUGGEST_THRESHOLD` | no | theo `tune_weights.py` | `MID` |
| `CHATBOT_FUZZY_WEIGHT` | no | `0.2` | `FUZZY_W` |
| `CHATBOT_RATE_LIMIT` | no | `60/minute` | Lớp app; WAF là 30/phút/IP |
| `CHATBOT_CORS_ORIGINS` | no | rỗng | Deploy cùng domain không cần CORS |
| `CHATBOT_RUNTIME` | no | `deployment` trên Vercel | `legacy` cho Docker |

**Quy tắc**:
- Thiếu `CF_ACCOUNT_ID`/`CF_API_TOKEN` khi provider `cloudflare` → function vẫn khởi động,
  log cảnh báo, health `embedding_provider: "cloudflare"`, `provider_ready: false`, chạy
  lexical/fuzzy.
- `HIGH` > `MID`, cả hai trong `[0, 1]`; `FUZZY_W` trong `[0, 1]`; sai → dùng mặc định và
  log cảnh báo (không làm sập function).
- Không biến nào chứa bí mật được trả về client hoặc ghi vào frontend.

---

## E-007 — HealthReport

Phản hồi của `GET /api/health`.

| Field | Type | Mô tả |
|-------|------|-------|
| `status` | `ok` \| `degraded` | `degraded` khi vector không dùng được hoặc provider lỗi |
| `vectors_loaded` | boolean | Đã nạp `vectors.json` chưa |
| `vector_count` | integer | Số entry |
| `model` | string | Model của chỉ mục |
| `dim` | integer | Số chiều |
| `normalizer_version` | string | Phiên bản chuẩn hoá |
| `source_hash_matches` | boolean | `source_kb_hash` khớp nguồn hiện tại |
| `embedding_provider` | string | `cloudflare`/`ollama`/`none` |
| `provider_ready` | boolean | Có đủ cấu hình provider không (không gọi mạng) |
| `message` | string | Thông điệp ngắn, không chứa bí mật |

Health MUST NOT gọi Cloudflare.

---

## E-008 — RateLimitRule

| Field | Type | Mô tả |
|-------|------|-------|
| `scope` | `POST /api/chat` | Endpoint áp dụng |
| `limit` | integer | 30 |
| `window_seconds` | integer | 60 |
| `key` | `ip` | Hobby chỉ hỗ trợ IP/JA4 |
| `action` | `429` | Too Many Requests |
| `published` | boolean | Chỉ rule đã Publish mới chạy |

**Trạng thái**: `draft` → `published` → `active`. Rule nháp không bảo vệ production.

---

## E-009 — Release

| Field | Type | Mô tả |
|-------|------|-------|
| `id` | string | ID deployment Vercel |
| `environment` | `preview` \| `production` | |
| `commit_sha` | string | Commit được deploy |
| `created_at` | ISO-8601 | |
| `status` | `building` \| `ready` \| `error` \| `rolled_back` | |
| `previous_release_id` | string \| null | Dùng để quay lui |
| `acceptance_passed` | boolean | T1–T8 đã đạt chưa |

**Quy tắc**: chỉ `preview` có `acceptance_passed=true` mới được promote production; rollback
chọn `previous_release_id` còn `ready`.

---

## E-010 — AcceptanceCase

| Field | Type | Mô tả |
|-------|------|-------|
| `id` | `T1`…`T8` | Mã kiểm tra |
| `description` | string | Mục tiêu |
| `input` | string / action | Câu hỏi hoặc thao tác |
| `expected` | string | Kết quả mong đợi |
| `last_result` | `pass` \| `fail` \| `not_run` | |

T1–T8 được định nghĩa trong `quickstart.md`; mỗi lần deploy production phải chạy lại.

---

## E-011 — EvaluationCase (dùng cho tuning)

| Field | Type | Mô tả |
|-------|------|-------|
| `question` | string | Câu hỏi thử |
| `category` | `exact` \| `typo` \| `no_diacritics` \| `abbreviation` \| `ambiguous` \| `off_topic` | |
| `expected_answer` | string \| null | Giá trị mong đợi (nếu có) |

Nguồn hiện có: `backend/evaluation/questions.json`. `tune_weights.py` có thể mở rộng lên
30–50 câu theo yêu cầu của spec.

---

## Ma trận liên kết

```text
CanonicalSource 1 ──► N SourceRecord
CanonicalSource 1 ──► 0..1 VectorIndex 1 ──► N VectorEntry
RuntimeConfig  1 ──► 1 EmbeddingProvider
RuntimeConfig  1 ──► 1 VectorIndex (đường dẫn)
VectorIndex    ──► HealthReport (trạng thái)
Release        ──► AcceptanceCase[] (kết quả)
EvaluationCase ──► RuntimeConfig (đề xuất ngưỡng)
```
