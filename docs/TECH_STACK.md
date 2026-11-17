# Công nghệ & thư viện — Chatbot giới thiệu bản thân

**Cập nhật**: 2026-11-17
**Production**: https://chatbot-gamma-gilt-33.vercel.app
**Kiến trúc**: Vercel Services (Flask + Vite) + Cloudflare Workers AI

---

## 1. Công nghệ sử dụng

| Lớp | Công nghệ | Vai trò |
|-----|-----------|---------|
| Giao diện | React 18 + TypeScript + Vite 8 | Chat UI, gợi ý, menu chủ đề, dark/light mode |
| Styling | CSS thuần (CSS variables) | Theme sáng/tối, responsive |
| State | Zustand 5 | Quản lý hội thoại, theme, sidebar |
| Backend API | Python 3.12 + Flask | `/api/chat`, `/api/health`, KB engine |
| Embedding | Cloudflare Workers AI `@cf/baai/bge-m3` | Tạo vector cho câu hỏi người dùng |
| Vector index | `data/vectors.json` + NumPy | Cosine similarity + fuzzy, tính sẵn khi build |
| Dữ liệu | `data/chatbot.txt` (`CHATBOT-SOURCE v1`) | Nguồn tri thức viết tay duy nhất |
| Dữ liệu môn học | `data/sources/courses.csv` | Điểm, tín chỉ, xét chuyên ngành |
| Bí danh | `data/sources/aliases.txt` | oop, ctdl, xstk, vtp2… |
| Deploy | Vercel Services | Một project, hai service `backend` + `frontend` |
| CDN / domain | Vercel | HTTPS, `*.vercel.app` |
| Rate limit | Vercel WAF + Flask-Limiter | Chặn spam, bảo vệ hạn mức Cloudflare |
| Legacy/rollback | Docker Compose + Ollama + FAISS + LangChain | Nhánh `ollama-version` |
| Testing | pytest, Vitest, Testing Library | Backend + frontend |
| Lint/typecheck | ESLint, TypeScript (`tsc --noEmit`) | Chất lượng mã frontend |

---

## 2. Cấu trúc đồ án

```text
chatbot/
├── app.py                      # Entrypoint Flask ở root cho Vercel (service backend)
├── api/                        # Entrypoint local/dự phòng cho /api/chat, /api/health
│   ├── chat.py
│   └── health.py
├── backend/
│   ├── app.py                  # Flask app, routes /api/chat, /api/health, /chat, /health
│   ├── assistant.py            # Luồng answer / suggest / clarify
│   ├── kb_engine.py            # Chấm điểm cosine + fuzzy, nạp vector tính sẵn
│   ├── embedding_provider.py   # Cloudflare / Ollama / none
│   ├── vector_store.py         # Đọc/ghi/kiểm tra data/vectors.json
│   ├── source_store.py         # Đọc nguồn + courses + aliases (không LangChain)
│   ├── source_format.py        # Parser/validator CHATBOT-SOURCE v1
│   ├── health.py               # Báo cáo /api/health
│   ├── suggestions.py          # Xếp hạng gợi ý, menu chủ đề
│   ├── session.py              # Session state trong RAM
│   ├── courses.py              # Đọc/kiểm tra courses.csv
│   ├── aliases.py              # Bí danh câu hỏi
│   ├── text_normalization.py   # Chuẩn hoá tiếng Việt
│   ├── chatbox.py              # Legacy Ollama/FAISS (rollback)
│   ├── documents.py            # Legacy RAG
│   ├── doc_index.py            # Chỉ mục tài liệu local
│   ├── doc_loaders.py          # PDF/DOCX/XLSX/CSV/TXT/MD
│   ├── tests/                  # pytest
│   └── evaluation/             # Bộ câu hỏi đánh giá + tune
├── data/
│   ├── chatbot.txt             # Nguồn tri thức chuẩn
│   ├── sources/
│   │   ├── courses.csv
│   │   └── aliases.txt
│   ├── inbox/                  # Tệp chờ nạp (local)
│   └── vectors.json            # Vector Cloudflare tính sẵn (commit)
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/         # Sidebar, Header, Composer, MessageList…
│   │   ├── store/chatStore.ts  # Zustand
│   │   └── lib/
│   │       ├── config.ts       # Base URL /api
│   │       ├── chatClient.ts   # Gọi /api/chat
│   │       ├── health.ts       # Gọi /api/health
│   │       ├── streamParser.ts
│   │       └── theme.ts
│   ├── package.json
│   └── vite.config.ts
├── scripts/
│   ├── check_chatbot.py        # Kiểm tra dữ liệu nguồn
│   ├── build_vectors.py        # Sinh data/vectors.json bằng Cloudflare
│   ├── tune_weights.py         # Grid search HIGH/MID/FUZZY_W
│   ├── smoke_deploy.py         # Smoke test URL production
│   ├── check_secrets.py        # Quét token vô tình lộ
│   └── setup_vercel_env.sh     # Đẩy env từ .env lên Vercel
├── docs/
│   ├── PROJECT_OVERVIEW.md     # Sơ đồ kiến trúc/luồng xử lý
│   └── TECH_STACK.md           # File này
├── specs/008-vercel-cloudflare-deploy/  # Spec/plan/tasks/contracts
├── vercel.json                 # Services: backend + frontend
├── requirements.txt            # Dependency tối giản cho deploy
├── .python-version             # 3.12
├── docker-compose.yml          # Bản Docker/Ollama
└── README.md
```

---

## 3. Thư viện Frontend

Khai báo trong `frontend/package.json`:

### Runtime

| Thư viện | Phiên bản | Dùng để |
|---------|-----------|---------|
| `react` | ^18.3.1 | UI |
| `react-dom` | ^18.3.1 | Render DOM |
| `zustand` | ^5.0.1 | State management |
| `react-markdown` | ^9.0.1 | Render Markdown trong câu trả lời |
| `remark-gfm` | ^4.0.0 | Bảng, link, strikethrough |
| `rehype-highlight` | ^7.0.1 | Highlight code block |
| `lucide-react` | ^0.468.0 | Icon |

### Dev / test / build

| Thư viện | Phiên bản | Dùng để |
|---------|-----------|---------|
| `vite` | ^8.3.7 | Dev server + build |
| `typescript` | ^5.7.2 | Type checking |
| `vitest` | ^5.1.0 | Unit test |
| `jsdom` | ^25.0.1 | Môi trường DOM cho test |
| `@testing-library/react` | ^16.1.0 | Test component |
| `@testing-library/user-event` | ^14.5.2 | Mô phỏng người dùng |
| `@testing-library/jest-dom` | ^6.6.3 | Matcher DOM |
| `eslint` + `typescript-eslint` | ^9 / ^8 | Lint |
| `eslint-plugin-react-hooks` | ^5.0.0 | Rule React Hooks |
| `eslint-plugin-react-refresh` | ^0.4.16 | Rule HMR |
| `@vitejs/plugin-react` | ^5.2.0 | React plugin cho Vite |

---

## 4. Thư viện Backend — bản deploy Vercel

Khai báo trong `requirements.txt` ở root:

| Thư viện | Phiên bản | Dùng để |
|---------|-----------|---------|
| `flask` | >=3.0,<4 | Web framework / API |
| `flask-cors` | >=4.0,<7 | CORS khi chạy local/khác domain |
| `flask-limiter` | >=3.5,<5 | Rate limit lớp ứng dụng |
| `cachetools` | >=5.3,<7 | Cache đánh giá truy vấn |
| `numpy` | >=1.26,<3 | Cosine similarity, vector |
| `RapidFuzz` | >=3.9,<4 | Fuzzy matching tiếng Việt |

Bản deploy **không** cài LangChain, FAISS hay Ollama.

---

## 5. Thư viện Backend — bản Docker/Ollama (legacy)

Khai báo trong `backend/requirements.txt`, chỉ dùng cho local/Docker và nhánh rollback:

| Thư viện | Dùng để |
|---------|---------|
| `langchain`, `langchain-community`, `langchain-ollama`, `langchain-text-splitters` | Pipeline RAG/LLM cũ |
| `faiss-cpu` | Vector store local |
| `pandas`, `openpyxl` | Đọc Excel/CSV |
| `pypdf`, `python-docx`, `docx2txt` | Đọc PDF/DOCX |
| `RapidFuzz` | Fuzzy matching |
| `flask-cors`, `flask-limiter`, `cachetools`, `numpy` | API/cache/vector |
| `pytest` | Test |

---

## 6. Script vận hành

| Lệnh | Chức năng |
|------|-----------|
| `python scripts/check_chatbot.py data/chatbot.txt` | Kiểm tra dữ liệu nguồn, courses, aliases |
| `python scripts/build_vectors.py` | Gọi Cloudflare, sinh `data/vectors.json` |
| `python scripts/tune_weights.py` | Chọn `FUZZY_W`, `HIGH`, `MID` bằng bộ câu hỏi thật |
| `python scripts/smoke_deploy.py --base-url <url>` | Kiểm tra health + T1–T3 trên production |
| `python scripts/check_secrets.py` | Quét token trong repo/frontend |
| `bash scripts/setup_vercel_env.sh` | Đẩy biến từ `.env` lên Vercel (Production + Preview) |

---

## 7. Biến môi trường

| Biến | Nơi đặt | Mô tả |
|------|---------|-------|
| `CF_ACCOUNT_ID` | Vercel + `.env` | Account ID Cloudflare |
| `CF_API_TOKEN` | Vercel + `.env` | Token Workers AI (bí mật) |
| `CHATBOT_EMBEDDING_PROVIDER` | Vercel + `.env` | `cloudflare` / `ollama` / `none` |
| `CHATBOT_EMBEDDING_MODEL` | mặc định theo provider | `@cf/baai/bge-m3` hoặc `bge-m3` |
| `CHATBOT_VECTORS_PATH` | Vercel | `data/vectors.json` |
| `CHATBOT_KB_HIGH_THRESHOLD` | Vercel | Ngưỡng trả lời trực tiếp (mặc định 0.78) |
| `CHATBOT_SUGGEST_THRESHOLD` | Vercel | Ngưỡng gợi ý (mặc định 0.55) |
| `CHATBOT_FUZZY_WEIGHT` | Vercel | Trọng số fuzzy (mặc định 0.2) |
| `VITE_API_BASE_URL` | build frontend | `/api` khi deploy |

Không commit `.env`, `.env.local` hoặc token thật.

---

## 8. Lệnh chạy & kiểm thử

### Local (dùng Ollama)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

CHATBOT_EMBEDDING_PROVIDER=ollama \
CHATBOT_EMBEDDING_MODEL=bge-m3 \
python -m flask --app api.chat run --port 5000

VITE_API_BASE_URL=http://127.0.0.1:5000 npm --prefix frontend run dev
```

### Kiểm thử

```bash
pytest backend/tests -q
npm --prefix frontend test -- --run
npm --prefix frontend run lint
npm --prefix frontend run build
```

### Deploy

```bash
npx vercel --prod
```

---

## 9. Ghi chú

- `backend/` là lõi nghiệp vụ; `api/` chỉ là entrypoint local/dự phòng.
- Vercel Services dùng `backend` root `.` và `frontend` root `frontend`.
- `data/vectors.json` phải được build lại mỗi khi sửa `data/chatbot.txt`.
- Bản Vercel hiện tại chỉ hỗ trợ `qa`; RAG/PDF/DOCX vẫn dùng bản Docker/Ollama.
- Nhánh `ollama-version` giữ bản cũ để rollback.
