# Implementation Plan: Triển khai chatbot trên Vercel + Cloudflare Workers AI

**Branch**: `008-vercel-cloudflare-deploy` | **Date**: 2026-11-17 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/008-vercel-cloudflare-deploy/spec.md`

> **Cập nhật 2026-11-17**: Repo được cấu hình lại theo **Vercel Services mode**: service
> `backend` (Flask, root `.`) public tại `/api/*`, service `frontend` (Vite, root `frontend`)
> public tại `/`. Các entrypoint `api/chat.py`/`api/health.py` vẫn giữ cho kiểm thử local,
> nhưng production dùng services trong `vercel.json`; không có service binding vì frontend
> gọi backend từ trình duyệt qua `/api/*`.

## Summary

Đưa chatbot hiện có lên một URL công khai miễn phí bằng Vercel (frontend tĩnh + Python Function)
và Cloudflare Workers AI (`@cf/baai/bge-m3`) cho bước tạo vector câu hỏi. Vector của toàn bộ
câu hỏi trong `data/chatbot.txt` được tính sẵn thành `data/vectors.json`; khi có yêu cầu, backend
chỉ tạo vector cho câu hỏi người dùng rồi so khớp cosine + fuzzy trong bộ nhớ. Nếu Cloudflare lỗi,
hết hạn mức hoặc timeout, backend tự chuyển sang khớp từ khoá + fuzzy và vẫn trả
`answer` / `suggest` / `clarify`. Đường deploy không còn Ollama, FAISS hay LangChain; nhánh
Docker/Ollama cũ được giữ để quay lui.

## Technical Context

**Language/Version**: Python 3.12 (pin bằng `.python-version`; Vercel mặc định 3.12) cho function
deploy; Python 3.11 trong Docker cũ vẫn giữ cho nhánh rollback. Frontend React 18 + TypeScript +
Vite 8, build bằng Node 22.

**Primary Dependencies**: Flask, flask-cors, flask-limiter, cachetools, numpy, RapidFuzz, thư viện
chuẩn `urllib.request` cho Cloudflare REST. `requirements.txt` ở root chỉ chứa phụ thuộc runtime
deploy; `backend/requirements.txt` cũ (LangChain, FAISS, Ollama, pandas, pypdf…) chỉ dùng cho
Docker/legacy và không được Vercel cài.

**Storage**: Tệp trong repo. Nguồn chuẩn `data/chatbot.txt`; dữ liệu môn/bí danh
`data/sources/`; chỉ mục sinh sẵn `data/vectors.json`. Không dùng cơ sở dữ liệu. Vercel chỉ cho
ghi `/tmp`, nên runtime không ghi dữ liệu; script build ghi tệp tạm rồi thay thế nguyên tử.

**Testing**: `pytest` cho backend (unit + contract + fallback), `vitest` cho frontend, kiểm tra
`curl`/HTTP cho function đã deploy, và bộ nghiệm thu T1–T8 trong `quickstart.md`.

**Target Platform**: Vercel Static + Vercel Functions (Python 3.12, Fluid compute), Cloudflare
Workers AI REST API. Trình duyệt hiện đại; giao diện ưu tiên desktop/tablet.

**Project Type**: Web application (frontend tách thư mục + backend Python trong cùng repo).

**Performance Goals**: 95% câu hỏi nhận phản hồi < 1,5 giây khi function đã ấm; lần đầu sau thời
gian nghỉ < 5 giây; tạo vector câu hỏi tối đa 3 giây trước khi fallback.

**Constraints**: Chỉ gói miễn phí, không thẻ; Cloudflare 10.000 neurons/ngày; function Vercel
≤ 500 MB uncompressed, ≤ 2 GB RAM, ≤ 300 giây; Hobby có 3 rule firewall và đúng 1 rule rate limit;
đầu vào ≤ 200 ký tự; 30 yêu cầu/phút/IP; không lộ `CF_ACCOUNT_ID`/`CF_API_TOKEN`.

**Scale/Scope**: 1–2 lượt truy cập/ngày; khoảng 40–60 bản ghi `qa`, vài trăm câu hỏi; chỉ mục
vector dự kiến dưới 5 MB; chỉ hỗ trợ `qa` trong phạm vi này (RAG/doc ngoài phạm vi).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status | Evidence |
|-----------|------|--------|----------|
| I. Một nguồn dữ liệu, kiểm tra trước khi dùng | `data/chatbot.txt` là nguồn duy nhất; `check_chatbot.py` 0 lỗi; vector sinh lại và có hash | PASS | Kế hoạch chuyển nguồn chuẩn về `data/`, thêm `scripts/check_chatbot.py` và `scripts/build_vectors.py`; health cảnh báo hash lệch |
| II. Miễn phí, không thẻ, trong hạn mức | Chỉ Vercel Hobby + Cloudflare free; không phụ thuộc trả phí | PASS | `requirements.txt` deploy tối giản; không thêm dịch vụ trả phí; rate limit bảo vệ hạn mức |
| III. Suy giảm êm | Cloudflare lỗi → lexical/fuzzy; không 500/"không biết" cho câu hợp lệ | PASS | `embedding_provider` trả `None` khi lỗi; `kb_engine`/`assistant` đã có nhánh fallback; contract có test |
| IV. Bảo mật và riêng tư | Bí mật chỉ trong env; rate limit; 200 ký tự; thông báo Cloudflare | PASS | Env Vercel; WAF 30/phút/IP; validate sẵn có; thêm thông báo ở frontend |
| V. Kiểm chứng trước khi triển khai | Test local, hiệu chỉnh ngưỡng, T1–T8, rollback | PASS | pytest/vitest; `tune_weights.py`; quickstart T1–T8; giữ nhánh Ollama và lịch sử deploy Vercel |

Không có vi phạm cần justify. Complexity Tracking để trống.

## Project Structure

### Documentation (this feature)

```text
specs/008-vercel-cloudflare-deploy/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── chat-api.md
│   ├── health-api.md
│   ├── embedding-provider.md
│   └── vectors-json.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Created later by /speckit.tasks
```

### Source Code (repository root)

```text
api/
├── chat.py              # Vercel Function cho POST /api/chat (WSGI app = backend.app)
└── health.py            # Vercel Function cho GET /api/health

backend/
├── app.py               # Flask app; tách phần legacy/RAG để deploy không kéo LangChain/FAISS
├── assistant.py         # Giữ nguyên luồng answer/suggest/clarify
├── kb_engine.py         # Dùng embedding provider + vector store; bỏ import LangChain ở top-level
├── embedding_provider.py# Cloudflare REST + adapter Ollama (lazy) + hàm embed_query/embed_texts
├── vector_store.py      # Đọc/ghi data/vectors.json, kiểm tra model/dim/hash/version
├── source_store.py      # Tách get_source/khóa học/alias khỏi chatbox, không phụ thuộc LangChain
├── health.py            # Báo cáo sức khỏe chỉ mục, không gọi Cloudflare
├── source_format.py     # Giữ nguyên parser/validator (nguồn chuẩn)
├── text_normalization.py
├── suggestions.py
├── session.py
├── courses.py
├── aliases.py
├── doc_index.py         # Chỉ dùng local/Docker; không bắt buộc trong deploy qa-only
├── doc_loaders.py
└── chatbox.py           # Legacy Ollama/FAISS; re-export source_store để tương thích

data/
├── chatbot.txt          # Nguồn chuẩn duy nhất (chuyển từ backend/data)
├── sources/
│   ├── courses.csv
│   └── aliases.txt
├── inbox/               # Tệp chờ nạp (local; rỗng trong deploy)
└── vectors.json         # Sinh bởi scripts/build_vectors.py, commit cùng repo

backend/data/            # Giữ PDF/CV/archive cho RAG/legacy; KHÔNG còn là nguồn chuẩn

scripts/
├── check_chatbot.py     # Bọc source_format.validate_source, exit != 0 khi có lỗi
├── build_vectors.py     # data/chatbot.txt → data/vectors.json (Cloudflare, theo lô)
└── tune_weights.py      # Grid search HIGH/MID/FUZZY_W trên bộ câu hỏi thật

frontend/
├── src/lib/config.ts    # Hỗ trợ base URL tương đối "/api"; mặc định local giữ 127.0.0.1:5000
├── src/lib/health.ts    # Gọi /api/health, trạng thái đang khởi động
└── src/App.tsx          # Thêm thông báo câu hỏi được gửi tới Cloudflare

requirements.txt         # Phụ thuộc runtime deploy (tối giản)
.python-version          # 3.12
vercel.json              # Build frontend, output frontend/dist, includeFiles backend/** + data/**
```

**Structure Decision**: Giữ backend Python hiện có làm lõi nghiệp vụ, chỉ tách các phụ thuộc
Ollama/FAISS/LangChain ra khỏi đường deploy. Vercel dùng file-based Python Functions
(`api/chat.py` → `/api/chat`, `api/health.py` → `/api/health`) thay vì framework preset để frontend
tĩnh và function cùng project, cùng domain. Nguồn dữ liệu chuẩn chuyển về `data/` theo hiến pháp;
`backend/data/` chỉ còn tài liệu RAG/legacy.

## Implementation Strategy

### Phase A — Chuẩn hoá nguồn dữ liệu và baseline

- Chuyển `backend/data/chatbot.txt`, `sources/courses.csv`, `sources/aliases.txt`, `inbox/` sang
  `data/`; cập nhật `DEFAULT_SOURCE_PATH`, `CHATBOT_SOURCE_PATH`, Docker, README, `.gitignore`,
  `.dockerignore`.
- Thêm `scripts/check_chatbot.py`; chạy trên nguồn hiện tại phải 0 lỗi.
- Giữ `backend/data/` cho PDF/CV/archive; ghi rõ không phải nguồn chuẩn.
- Gate: `pytest` hiện có vẫn xanh sau khi đổi đường dẫn; `check_chatbot.py` trả 0.

### Phase B — Embedding provider và vector store

- Thêm `backend/embedding_provider.py`:
  - `cloudflare`: gọi REST `POST /accounts/{id}/ai/run/@cf/baai/bge-m3` với `{"text": [...]}`,
    timeout câu hỏi 3 giây, timeout build 30 giây, tối đa 1 lần thử lại; trả `None` khi lỗi.
  - `ollama`: adapter lazy import `langchain_ollama` chỉ dùng local/Docker.
- Thêm `backend/vector_store.py`: schema `vectors.json` (xem contract), kiểm tra model/dim/
  normalizer/source hash; ghi nguyên tử.
- Sửa `kb_engine.py`: bỏ import LangChain top-level; warm-up ưu tiên `CHATBOT_VECTORS_PATH`;
  hash lệch → không dùng vector cũ, log cảnh báo và chạy lexical fallback.
- Gate: unit test provider (mock HTTP), vector store (hash/model/dim), fallback khi provider lỗi.

### Phase C — Tách legacy và tạo entrypoint Vercel

- Tách `get_source` + xử lý khóa học/alias sang `backend/source_store.py`; `chatbox` re-export.
- `backend/app.py`: không import `chatbox`/FAISS ở top-level; tạo app factory với chế độ
  `deployment` (qa-only) và `legacy` (Docker). Giữ nguyên route `/chat`, `/chat/stream`.
- Thêm `backend/health.py`; gắn route `/health` vào Flask app để chạy local; thêm
  `api/chat.py`, `api/health.py` cho Vercel (`/api/chat`, `/api/health`).
- Thêm `requirements.txt` root tối giản, `.python-version` = 3.12, `vercel.json`.
- `vercel.json` dùng `buildCommand` build `frontend/`, `outputDirectory: frontend/dist`,
  `functions.includeFiles` cho `backend/**` + `data/**`, và `excludeFiles` cho
  `backend/tests`, `backend/data` (PDF/CV/archive), `backend/evaluation`, `library`, `specs`,
  `**/*.pdf`, `**/*.docx`, `**/__pycache__/**` để giữ bundle dưới 500 MB.
- Gate: chạy function local bằng `vercel dev` hoặc Flask test client; import `api.chat` không kéo
  `langchain`/`faiss`/`ollama` (kiểm tra bằng test import).

### Phase D — Frontend same-origin và trạng thái khởi động

- `config.ts`: chấp nhận `VITE_API_BASE_URL=/api` (tương đối); local giữ `http://127.0.0.1:5000`.
- `health.ts` + `App.tsx`: gọi `/api/health` khi tải, hiện "đang khởi động" nếu chậm; thêm dòng
  thông báo câu hỏi được gửi tới Cloudflare.
- Cập nhật test chat client/config; build production với `VITE_API_BASE_URL=/api`.
- Gate: `npm test`, `npm run lint`, `npm run build` xanh; gọi `/api/chat` cùng domain trong preview.

### Phase E — Script kiểm tra, build vector, hiệu chỉnh ngưỡng

- `build_vectors.py`: đọc nguồn qua `source_store`, chỉ lấy `qa` active, chuẩn hoá bằng đúng
  `normalize_query`, gọi Cloudflare theo lô, ghi `data/vectors.json` kèm hash/model/dim/version.
- `tune_weights.py`: đọc bộ 30–50 câu trong `backend/evaluation/questions.json` (hoặc tệp chỉ
  định), tạo vector câu hỏi một lần, grid search `FUZZY_W`, `HIGH`, `MID`; in bộ ngưỡng đề xuất.
- Gate: số vector khớp số câu hỏi active; hash khớp; script từ chối ghi nếu dữ liệu lỗi.

### Phase F — Deploy và nghiệm thu

- Import repo vào Vercel, đặt `CF_ACCOUNT_ID`, `CF_API_TOKEN`, `HIGH`, `MID`, `FUZZY_W`;
  build với `VITE_API_BASE_URL=/api`.
- Tạo 1 rule WAF rate limit: `POST /api/chat`, 30 request/60 giây/IP, hành động 429; Publish.
- Chạy T1–T8 trong `quickstart.md`; chỉ promote production khi tất cả đạt.
- Gate: URL công khai trả lời đúng; 0 secret trong bundle/frontend/log; 429 hoạt động.

### Phase G — Vận hành và rollback

- Ghi quy trình cập nhật dữ liệu 5 bước vào README/quickstart.
- Giữ nhánh `ollama-version` và lịch sử deploy Vercel; ghi cách rollback và cách tắt embedding
  (`CHATBOT_EMBEDDING_PROVIDER=none`) khi Cloudflare không ổn định.
- Gate: thử rollback một bản preview; xác nhận URL phục vụ lại bản trước.

## Post-Design Constitution Re-check

| Principle | Re-check | Status |
|-----------|----------|--------|
| I | `data/` là nguồn duy nhất; vector có hash và bước kiểm tra | PASS |
| II | Không thêm phụ thuộc trả phí; bundle deploy tối giản | PASS |
| III | Fallback lexical/fuzzy nằm trên đường chính; health không gọi dịch vụ ngoài | PASS |
| IV | Bí mật qua env; rate limit; giới hạn đầu vào; thông báo Cloudflare | PASS |
| V | Có test, tuning, T1–T8, rollback | PASS |

## Complexity Tracking

Không có vi phạm hiến pháp cần justify. Các thay đổi lớn (tách `source_store`, provider abstraction)
là cần thiết để loại Ollama/FAISS/LangChain khỏi đường deploy mà vẫn giữ nhánh rollback.
