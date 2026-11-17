# Phase 0 Research — Vercel + Cloudflare Workers AI

**Feature**: `008-vercel-cloudflare-deploy`
**Date**: 2026-11-17
**Input**: [spec.md](./spec.md) và [plan.md](./plan.md)

Tất cả điểm chưa rõ trong Technical Context đã được giải quyết dưới đây. Không còn
`NEEDS CLARIFICATION`.

---

## R-001 — Cách gọi embedding của Cloudflare Workers AI

**Decision**: Dùng REST Run endpoint gốc:

```text
POST https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/ai/run/@cf/baai/bge-m3
Authorization: Bearer {CF_API_TOKEN}
Content-Type: application/json

{"text": ["câu 1", "câu 2", "..."]}
```

Gửi theo lô nhỏ (20–50 câu hoặc ≤ 10 MB), timeout câu hỏi 3 giây, timeout build 30 giây,
tối đa 1 lần thử lại. Bộ phân tích phản hồi chấp nhận vector ở `result.data` hoặc
`result.embeddings` và kiểm tra độ dài vector trước khi dùng. Nếu phản hồi không có
vector hợp lệ → coi như lỗi provider.

**Rationale**: Đây là API được Cloudflare tài liệu hoá cho `@cf/baai/bge-m3`, không cần
cài SDK, phù hợp với yêu cầu chỉ dùng thư viện chuẩn. Gửi lô giảm số lần gọi và thời
gian build vector.

**Alternatives considered**:
- *OpenAI-compatible `/v1/embeddings`*: cùng nhà cung cấp nhưng ít ví dụ cho `bge-m3`
  và thêm lớp tương thích; loại vì không cần thiết.
- *Workers binding*: cần deploy một Worker riêng; loại vì tăng số dịch vụ phải quản lý.
- *Batch async API (`queueRequest`)*: phù hợp lô lớn nhưng phải poll; loại vì kho dữ liệu
  nhỏ, gọi đồng bộ đơn giản hơn.

**Điểm cần xác minh ở Phase 1 của kế hoạch triển khai**: tên trường vector thực tế trong
phản hồi và số chiều (dự kiến 1024). Script `build_vectors.py` sẽ fail rõ ràng nếu phản
hồi không khớp thay vì ghi dữ liệu rác.

**Sources**:
- https://developers.cloudflare.com/workers-ai/models/bge-m3/
- https://developers.cloudflare.com/workers-ai/models/bge-m3/sync-input.json

---

## R-002 — Cách chạy Flask cùng frontend Vite trên một Vercel project

**Decision**: Dùng file-based Python Functions trong `api/`:

- `api/chat.py` → `/api/chat`, export `app` (WSGI Flask app lấy từ `backend.app`)
- `api/health.py` → `/api/health`, Flask app nhỏ gọi `backend.health`

Vercel build frontend bằng `vercel.json` (`buildCommand` chạy `npm --prefix frontend ci`
và `npm --prefix frontend run build`, `outputDirectory: frontend/dist`), đồng thời bundle
Python function với `includeFiles` cho `backend/**` và `data/**`. SPA fallback bằng
rewrite mọi đường dẫn không phải `/api/*` về `/index.html`.

**Rationale**: Vercel tài liệu hoá file-based Python Functions ánh xạ `.py` → route và hỗ
trợ WSGI `app`. Cách này giữ frontend tĩnh và API cùng domain, không CORS, không cần
project thứ hai. Framework preset cho Flask sẽ chiếm toàn bộ route và xung đột với SPA.

**Alternatives considered**:
- *Vercel framework preset Flask*: đơn giản cho API nhưng không phục vụ Vite SPA cùng
  project theo cách kiểm soát được; loại.
- *Hai project Vercel (frontend + backend)*: tách domain, phải cấu hình CORS và hai lần
  deploy; loại vì trái yêu cầu cùng domain.
- *Vercel Services*: phù hợp backend + framework khác nhưng thêm cấu hình; loại cho phạm vi
  nhỏ này.
- *`api/index.py` + rewrite `/api/chat`*: khả thi nhưng ánh xạ file trực tiếp rõ ràng hơn;
  chọn `api/chat.py`.

**Sources**:
- https://vercel.com/docs/functions/runtimes/python/api-directory
- https://vercel.com/docs/frameworks/backend/flask
- https://vercel.com/docs/functions/runtimes/python

---

## R-003 — Phiên bản Python và dependency cho deploy

**Decision**: Pin `.python-version` = `3.12` (Vercel mặc định 3.12; hỗ trợ 3.12/3.13/3.14).
Tạo `requirements.txt` ở root chỉ gồm runtime deploy: Flask, flask-cors, flask-limiter,
cachetools, numpy, RapidFuzz. Giữ `backend/requirements.txt` (LangChain, FAISS, Ollama,
pandas, pypdf…) cho Docker/legacy. Không dùng `pyproject.toml` để tránh trùng nguồn
dependency.

**Rationale**: 3.12 là mặc định ổn định của Vercel và tương thích các thư viện hiện dùng.
Tách requirements giúp bundle function nhỏ, tránh kéo FAISS/LangChain vào deploy và tránh
vượt giới hạn 500 MB.

**Alternatives considered**:
- *Giữ Python 3.11 như Docker*: Vercel không còn hỗ trợ 3.11; loại.
- *Dùng chung `backend/requirements.txt`*: kéo toàn bộ Ollama/FAISS/LangChain vào function,
  trái hiến pháp và tăng bundle; loại.
- *Dùng `pyproject.toml`*: hợp lệ nhưng thêm nguồn cấu hình trong khi repo đang dùng
  requirements; loại để đơn giản.

**Sources**:
- https://vercel.com/docs/functions/runtimes/python/python-version
- https://vercel.com/docs/functions/limitations

---

## R-004 — Giới hạn tần suất và bảo vệ hạn mức miễn phí

**Decision**: Tạo một rule Vercel WAF Rate Limiting trên production:

- Điều kiện: `POST` tới `/api/chat`
- Giới hạn: 30 request / 60 giây / IP
- Hành động: 429 Too Many Requests
- Phải bấm **Publish** (rule đã lưu nhưng chưa publish chỉ là bản nháp)

Giữ `Flask-Limiter` 60/phút trong app như lớp bảo vệ local/Docker; không dựa vào nó cho
production vì request có thể chạm function trước khi app xử lý.

**Rationale**: Hobby chỉ có 1 rule rate limit và 3 custom rule; 30/phút/IP đủ cho người
xem thật, chặn spam đốt 10.000 neurons/ngày. Vercel tài liệu xác nhận rate limit có trên
mọi gói và Hobby có 1 rule.

**Alternatives considered**:
- *Chỉ dùng Flask-Limiter*: không bảo vệ hạn mức trước khi function khởi động; loại.
- *Rate limit theo header/JA4*: Hobby chỉ hỗ trợ IP và JA4; IP đủ cho phạm vi này.
- *Nhiều rule cho nhiều endpoint*: Hobby chỉ 1 rule rate limit; loại.

**Sources**:
- https://vercel.com/docs/vercel-firewall/vercel-waf/rate-limiting
- https://vercel.com/pricing

---

## R-005 — Nguồn dữ liệu chuẩn và vị trí tệp vector

**Decision**: Chuyển nguồn chuẩn về `data/chatbot.txt`, `data/sources/courses.csv`,
`data/sources/aliases.txt`, `data/inbox/`. Sinh `data/vectors.json` và commit tệp này.
`backend/data/` chỉ còn PDF/CV/archive phục vụ RAG/legacy, không phải nguồn chuẩn.
Cập nhật `.gitignore`, `.dockerignore`, Dockerfile, docker-compose, README và các default
trong code.

**Rationale**: Hiến pháp dự án (v1.0.0) quy định `data/chatbot.txt` là nguồn duy nhất.
Tách khỏi `backend/` cũng làm đường dẫn deploy ổn định vì Vercel đọc tệp tương đối từ
project root. Vector là dữ liệu dẫn xuất không bí mật, cần commit để function không phải
gọi Cloudflare lúc khởi động.

**Alternatives considered**:
- *Giữ `backend/data/chatbot.txt`*: trái hiến pháp; loại.
- *Sinh vector lúc cold start*: tốn hạn mức, chậm, dễ timeout; loại.
- *Dùng `embeddings_cache.npz`*: định dạng nhị phân gắn với Ollama, khó review và không
  mang metadata model/hash; loại.

---

## R-006 — Tách embedding provider và fallback

**Decision**: Thêm `backend/embedding_provider.py` với hai provider:

- `cloudflare` (mặc định cho deploy)
- `ollama` (chỉ local/Docker, import lazy)
- `none` (tắt embedding, chỉ lexical/fuzzy — dùng khi sự cố)

Interface nội bộ: `embed_texts(texts) -> list[list[float]] | None` và
`embed_query(text) -> list[float] | None`. `kb_engine` chỉ phụ thuộc interface này, không
import `langchain_ollama` ở top-level. Khi provider trả `None`, `kb_engine.evaluate` trả
`embeddings_ready=False`; `assistant` đã có nhánh lexical/fuzzy.

**Rationale**: Giữ được nhánh rollback Ollama mà không kéo LangChain vào deploy; fallback
hiện có đã được kiểm thử và không cần viết lại luồng quyết định.

**Alternatives considered**:
- *Sửa trực tiếp `kb_engine` sang Cloudflare*: làm mất khả năng chạy local/Docker và
  rollback; loại.
- *Viết lại retrieval mới trong `api/retrieval.py`*: trùng lặp logic cosine/fuzzy đã có và
  tăng rủi ro sai lệch; loại, tái sử dụng `kb_engine`.
- *Bắt buộc mọi môi trường dùng Cloudflare*: trái yêu cầu giữ nhánh Ollama; loại.

---

## R-007 — Định dạng và kiểm tra `vectors.json`

**Decision**: `vectors.json` là JSON có metadata và mảng entry:

- `schema_version`, `model` (`@cf/baai/bge-m3`), `dim` (1024), `normalizer_version`
- `source_sha256` (hash nội dung `chatbot.txt`), `source_kb_hash` (hash KB dẫn xuất sau
  facts/courses/aliases), `built_at`
- `entries[]`: `{id, item_id, source_type: "qa", question, norm, vector[]}`

Chỉ dùng chỉ mục khi `model`, `dim`, `normalizer_version` và `source_kb_hash` khớp cấu
hình/nguồn hiện tại. Lệch hash → không dùng vector cũ, log cảnh báo, trả health
`source_hash_matches: false`, và chạy lexical fallback. Build ghi tệp tạm rồi
`os.replace` để không để lại tệp dở.

**Rationale**: Hash là cơ chế duy nhất phát hiện “quên build vector” — rủi ro lớn nhất
trong vận hành. Lưu cả hash nội dung và hash KB dẫn xuất vì điểm/courses/aliases cũng
ảnh hưởng câu trả lời.

**Alternatives considered**:
- *Chỉ lưu vector, không metadata*: không phát hiện lệch model/hash; loại.
- *Lưu NPZ*: nhỏ hơn nhưng khó review/diff và không tự mô tả; loại.
- *Tự động dùng vector cũ khi lệch hash*: có thể ghép câu hỏi mới với vector cũ, trả lời
  sai âm thầm; loại.

---

## R-008 — Hiệu chỉnh ngưỡng cho vector mới

**Decision**: `scripts/tune_weights.py` đọc bộ câu hỏi thật (30–50 câu: đúng, sai chính
tả, không dấu, viết tắt, mơ hồ, ngoài chủ đề), tạo vector cho câu hỏi bằng provider hiện
tại một lần, rồi grid search `FUZZY_W` (0.0–0.4), `HIGH` (0.70–0.90), `MID` (0.40–0.65).
In bộ ngưỡng tốt nhất kèm tỷ lệ câu đúng/ngoài chủ đề. Không dùng lại 0.78/0.55 của
Ollama.

**Rationale**: Cosine của `bge-m3` qua Cloudflare có phân bố khác vector Ollama; dùng
nguyên ngưỡng cũ sẽ khiến câu đúng rơi vào gợi ý hoặc ngược lại.

**Alternatives considered**:
- *Giữ ngưỡng cũ*: trái hiến pháp và rủi ro sai hàng loạt; loại.
- *Chỉnh tay vài câu*: không đại diện, không đo được; loại.
- *Gọi Cloudflare cho từng tổ hợp tham số*: tốn hạn mức vô ích; loại — chỉ tạo vector một
  lần rồi tính điểm cục bộ.

---

## R-009 — Trạng thái khởi động và health

**Decision**: `GET /api/health` trả JSON:

```json
{
  "status": "ok",
  "vectors_loaded": true,
  "vector_count": 180,
  "model": "@cf/baai/bge-m3",
  "dim": 1024,
  "source_hash_matches": true,
  "normalizer_version": "2",
  "embedding_provider": "cloudflare"
}
```

Không gọi Cloudflare. Frontend gọi health khi tải; nếu chưa có phản hồi sau 2 giây, hiện
“đang khởi động” nhưng không chặn ô nhập.

**Rationale**: Vercel cold start vài giây; health rẻ, không đốt hạn mức, giúp phát hiện
quên build vector và cải thiện cảm nhận chờ.

**Alternatives considered**:
- *Health gọi Cloudflare*: tốn hạn mức mỗi lần tải trang; loại.
- *Không có health*: người dùng thấy màn hình trống khi cold start và không phát hiện
  vector cũ; loại.

---

## R-010 — Quay lui và vận hành

**Decision**: Giữ nhánh Git `ollama-version` và không xoá `backend/requirements.txt`,
`chatbox.py`, Docker Compose. Rollback production bằng cách chọn deployment trước trong
Vercel; rollback toàn bộ về Ollama bằng nhánh cũ. Thêm biến
`CHATBOT_EMBEDDING_PROVIDER=none` để tạm tắt embedding khi Cloudflare sự cố.

**Rationale**: Hiến pháp yêu cầu đường quay lui; Vercel giữ lịch sử deployment. Tắt
embedding là biện pháp tức thời không cần deploy code mới.

**Alternatives considered**:
- *Xoá code Ollama sau khi deploy*: mất đường lui; loại.
- *Chỉ dựa vào redeploy code cũ*: chậm hơn chọn deployment trước; loại làm phương án chính.

---

## Tổng hợp rủi ro kỹ thuật

| Rủi ro | Xử lý |
|--------|-------|
| Phản hồi Cloudflare khác tài liệu (tên trường vector) | Spike Phase 1; parser chấp nhận `result.data`/`result.embeddings`; fail rõ khi không đọc được |
| Quên build vector sau khi sửa dữ liệu | Hash trong `vectors.json`; health cảnh báo; quy trình 5 bước |
| Bundle vượt 500 MB | Requirements deploy tối giản; `excludeFiles` cho tests/docs; đo bằng build log |
| Cold start chậm | Health + thông báo “đang khởi động”; giữ function ấm bằng lưu lượng thật |
| Rate limit chỉ 1 rule ở Hobby | Một rule duy nhất cho `POST /api/chat`; Flask-Limiter chỉ là lớp phụ |
| Cloudflare hết hạn mức | Fallback lexical/fuzzy; 429 bảo vệ; `provider=none` khi cần |
| Lộ token | Chỉ env Vercel; `.gitignore`; thu hồi/xoay vòng; test quét bundle |
