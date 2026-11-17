---
description: "Task list for Vercel + Cloudflare Workers AI deployment"
---

# Tasks: Triển khai chatbot trên Vercel + Cloudflare Workers AI

**Input**: Design documents from `/specs/008-vercel-cloudflare-deploy/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Bộ kiểm thử được đưa vào như **cổng kiểm chứng** theo Hiến pháp V (kiểm chứng trước
khi deploy), không phải yêu cầu TDD bắt buộc. Trong mỗi user story, viết test trước phần triển
khai tương ứng khi có thể.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- Web app: `backend/`, `frontend/`, `api/`, `scripts/`, `data/` at repository root.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Tạo khung thư mục và cấu hình dependency tối thiểu cho đường deploy.

- [x] T001 Create deployment skeleton directories `api/`, `scripts/`, `data/sources/`, `data/inbox/` with `.gitkeep` for empty dirs at `data/inbox/.gitkeep`
- [x] T002 [P] Add `.python-version` with `3.12` and root `requirements.txt` containing only Flask, flask-cors, flask-limiter, cachetools, numpy, RapidFuzz
- [x] T003 [P] Update `.gitignore` and `.dockerignore` to keep `data/chatbot.txt`, `data/sources/**`, `data/vectors.json` while ignoring `data/inbox/*`, `.env`, and generated artifacts

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Chuẩn hoá nguồn dữ liệu, tách provider/vector store, tạo entrypoint Vercel và cấu hình frontend dùng chung. **Không user story nào bắt đầu trước khi phase này xong.**

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T004 Move canonical data with `git mv backend/data/chatbot.txt data/chatbot.txt`, `git mv backend/data/sources/courses.csv data/sources/courses.csv`, and `git mv backend/data/sources/aliases.txt data/sources/aliases.txt`; move inbox files only if present, otherwise keep `data/inbox/.gitkeep`; leave PDF/CV/archive under `backend/data/`
- [x] T005 Update source paths in `backend/chatbox.py`, `backend/.env.example`, `backend/Dockerfile`, `docker-compose.yml`, and `README.md` from `backend/data/...` to `data/...`
- [x] T006 [P] Extract `get_source`, computed fact overrides, and course/alias merge logic from `backend/chatbox.py` into `backend/source_store.py`; re-export `get_source` from `backend/chatbox.py`
- [x] T007 [P] Create `backend/embedding_provider.py` with `cloudflare` REST provider (`POST /accounts/{id}/ai/run/@cf/baai/bge-m3`, `{"text": [...]}`, 3s query timeout, 30s build timeout, 1 retry), `none` provider, and lazy `ollama` adapter
- [x] T008 [P] Create `backend/vector_store.py` to load/save/validate `data/vectors.json` per `contracts/vectors-json.md`, including model/dim/normalizer/source-hash checks and atomic `os.replace` writes
- [x] T009 Refactor `backend/kb_engine.py` to use `backend/embedding_provider.py` and `backend/vector_store.py`; remove top-level `langchain_ollama` import; on hash mismatch log warning, disable vectors, and use lexical fallback
- [x] T010 Refactor `backend/app.py` into an app factory with `deployment` (qa-only, no `chatbox`/FAISS import) and `legacy` (Docker) modes; add `/health` route; keep `/chat` and `/chat/stream` contracts unchanged
- [x] T011 Create `backend/health.py` returning the `HealthReport` fields from `contracts/health-api.md` without calling Cloudflare or any external service
- [x] T012 Create `api/chat.py` exposing the WSGI `app` for `POST /api/chat` and `api/health.py` exposing `GET /api/health`
- [x] T013 [P] Create `scripts/check_chatbot.py` wrapping `backend/source_format.validate_source` plus course/alias/fact consistency checks; exit non-zero with file/line messages on any error
- [x] T014 Create `scripts/build_vectors.py` per `contracts/vectors-json.md`: validate source, filter `kind=qa` and `status=active`, normalize with `normalize_query`, batch-call `embed_texts`, and write `data/vectors.json` atomically
- [x] T015 [P] Update `frontend/src/lib/config.ts` to accept a relative base URL such as `/api` while keeping `http://127.0.0.1:5000` for local development
- [x] T016 Create `vercel.json` with `buildCommand` for `frontend/`, `outputDirectory: frontend/dist`, `functions.includeFiles` for `backend/**` + `data/**`, `excludeFiles` for tests/docs/PDF/DOCX/archive, and SPA rewrite excluding `/api/*`
- [x] T017 [P] Add `backend/tests/test_embedding_provider.py` covering Cloudflare success shape (`result.data`/`result.embeddings`) and `embed_texts`/`embed_query` return values
- [x] T018 [P] Add `backend/tests/test_vector_store.py` covering valid load, model/dim/normalizer/hash mismatch, NaN/short vector rejection, and atomic write behavior
- [x] T019 [P] Add `backend/tests/test_deploy_imports.py` asserting `api.chat` imports without loading `langchain`, `langchain_ollama`, `faiss`, or `chatbox` legacy modules
- [x] T020 [P] Add `backend/tests/test_health.py` covering `ok`, missing vectors, and hash-mismatch `degraded` states without network calls

**Checkpoint**: Foundation ready — user story implementation can now begin.

---

## Phase 3: User Story 1 - Người xem dùng chatbot qua URL công khai (Priority: P1) 🎯 MVP

**Goal**: Public chat endpoint trả đúng answer/suggest/clarify, kể cả khi provider vector lỗi; frontend cùng domain hiển thị trạng thái khởi động và thông báo Cloudflare.

**Independent Test**: Chạy local/preview, hỏi GPA, OOP, "mục tiêu", "asdf"; sau đó làm provider lỗi và xác nhận vẫn nhận gợi ý/clarify, không 500.

### Tests for User Story 1

- [x] T021 [P] [US1] Add contract tests for `POST /api/chat`, `GET /api/health`, 400/422/429 mapping in `backend/tests/test_deployment_api.py`
- [x] T022 [P] [US1] Add provider-failure integration test asserting `suggest`/`clarify` and no HTTP 500 in `backend/tests/test_deployment_fallback.py`
- [x] T023 [P] [US1] Add offline T1–T3 sample-answer test for GPA 8.51/10, OOP 6.9, "mục tiêu", and "asdf" in `backend/tests/test_deployment_answers.py`
- [x] T024 [P] [US1] Update `frontend/src/lib/chatClient.test.ts` to expect `/api/chat` when `VITE_API_BASE_URL=/api` and keep `/chat` for the local base URL
- [x] T025 [US1] Add `frontend/src/lib/health.ts` and `frontend/src/lib/health.test.ts` for parsing `/api/health` and detecting degraded status

### Implementation for User Story 1

- [x] T026 [US1] Integrate health/cold-start state and the public Cloudflare notice into `frontend/src/App.tsx` and `frontend/src/styles/app.css`
- [x] T027 [US1] Add `scripts/smoke_deploy.py` to call `/api/health`, `/api/chat` with T1–T3 questions, and assert expected content/status
- [x] T028 [US1] Add `frontend/src/App.test.tsx` coverage for the "đang khởi động" state and the visible Cloudflare notice
- [x] T029 [US1] Run US1 independent validation locally per `specs/008-vercel-cloudflare-deploy/quickstart.md` §4 and record results in that file

**Checkpoint**: User Story 1 should be fully functional and testable independently.

---

## Phase 4: User Story 2 - Chủ dự án triển khai miễn phí, không cần thẻ (Priority: P1)

**Goal**: Deploy cùng domain trên Vercel Hobby bằng push, không thẻ; bí mật chỉ trong env; WAF 30/phút/IP; bundle không chứa dependency nặng.

**Independent Test**: Từ tài khoản sạch, làm theo hướng dẫn deploy; URL trả lời đúng; không có token trong repo/frontend; gửi 35 request/phút bị 429.

### Tests for User Story 2

- [x] T030 [P] [US2] Add `backend/tests/test_vercel_config.py` validating `vercel.json` build/output/include/exclude/rewrite settings, `.python-version` = `3.12`, and root `requirements.txt` excluding LangChain/FAISS/Ollama
- [x] T031 [P] [US2] Add `frontend/src/lib/config.test.ts` covering relative `/api`, local `127.0.0.1:5000`, and invalid configured URL fallback
- [x] T032 [P] [US2] Add `backend/tests/test_no_secrets_in_frontend.py` scanning `frontend/src/**` and build-time config for `CF_API_TOKEN` patterns

### Implementation for User Story 2

- [x] T033 [US2] Add root `.env.example` with `CF_ACCOUNT_ID`, `CF_API_TOKEN`, `CHATBOT_EMBEDDING_PROVIDER`, `HIGH`, `MID`, `FUZZY_W`, `CHATBOT_VECTORS_PATH`, and update `frontend/.env.example` with `VITE_API_BASE_URL=/api`
- [x] T034 [US2] Add `scripts/check_secrets.py` scanning repo/frontend for token-like values and wire it into `README.md` verification steps
- [x] T035 [US2] Document Vercel project import, env vars, `vercel --prod`, WAF rule `POST /api/chat` 30/60s/IP/429, and **Publish** step in `README.md`
- [ ] T036 [US2] Run `vercel build`, inspect function bundle for LangChain/FAISS/Ollama/PDF, adjust `vercel.json` `excludeFiles` if needed, and record bundle size in `README.md`
- [x] T037 [US2] Add free-tier/no-card checklist and expected Cloudflare 10.000 neurons/day protection to `README.md`

**Checkpoint**: User Stories 1 and 2 should both work independently; production URL is deployable.

---

## Phase 5: User Story 3 - Chủ dự án cập nhật tri thức và deploy lại an toàn (Priority: P2)

**Goal**: Sửa `data/chatbot.txt` → check → build vector → push → nội dung mới được phục vụ; quên build vector thì health cảnh báo và fallback.

**Independent Test**: Sửa một mục hỏi-đáp, chạy quy trình 5 bước, hỏi lại thấy nội dung mới; sau đó sửa nguồn nhưng không build vector và xác nhận health `source_hash_matches=false`.

### Tests for User Story 3

- [x] T038 [P] [US3] Add `backend/tests/test_check_chatbot_cli.py` covering valid source exit 0 and invalid source non-zero with file/line output
- [x] T039 [P] [US3] Add `backend/tests/test_build_vectors.py` covering fake provider batching, correct `question_count`, source hashes, 5-decimal rounding, and no file write on mid-batch failure
- [x] T040 [P] [US3] Add `backend/tests/test_vector_hash_guard.py` asserting stale hash disables embeddings, sets health degraded, and still returns suggestions
- [x] T041 [P] [US3] Add `backend/tests/test_source_path_migration.py` asserting canonical `data/chatbot.txt` exists and no canonical copy remains at `backend/data/chatbot.txt`

### Implementation for User Story 3

- [x] T042 [US3] Complete course/alias/fact consistency checks in `scripts/check_chatbot.py` so invalid aggregate or missing placeholder exits non-zero
- [x] T043 [US3] Harden `scripts/build_vectors.py` to refuse invalid source, keep the previous `data/vectors.json` on failure, and print entry/hash summary
- [ ] T044 [US3] Run `scripts/build_vectors.py` against the current source, verify `question_count` equals active QA questions, and commit `data/vectors.json`
- [x] T045 [US3] Document the 5-step data update workflow (edit → check → build vectors → push → smoke test) in `README.md`
- [x] T046 [US3] Verify the hash-mismatch path end-to-end with a temporary source edit; record observed health/fallback behavior in `specs/008-vercel-cloudflare-deploy/quickstart.md`

**Checkpoint**: Data updates and stale-vector detection work end-to-end.

---

## Phase 6: User Story 4 - Chủ dự án xử lý sự cố và quay lui (Priority: P2)

**Goal**: Provider lỗi/hết hạn mức → fallback; deploy lỗi → rollback; token lộ → thu hồi/xoay vòng; cold start có thông báo.

**Independent Test**: Dùng token sai và mô phỏng 429/5xx/timeout, xác nhận không 500; rollback một deployment preview; chạy `provider=none`.

### Tests for User Story 4

- [x] T047 [US4] Extend `backend/tests/test_embedding_provider.py` with 401/403/429/5xx/timeout/invalid-schema cases asserting `None` and no exception
- [x] T048 [P] [US4] Add `backend/tests/test_provider_none.py` asserting `CHATBOT_EMBEDDING_PROVIDER=none` makes no network call and uses lexical/fuzzy
- [x] T049 [P] [US4] Add `backend/tests/test_no_secret_leaks.py` asserting health/log payloads never contain `CF_API_TOKEN`, `CF_ACCOUNT_ID`, or exception stack traces

### Implementation for User Story 4

- [x] T050 [US4] Update `backend/health.py` and `backend/tests/test_health.py` for missing provider config, missing vectors, and stale hash degraded states
- [x] T051 [US4] Document Vercel previous-deployment rollback, `CHATBOT_EMBEDDING_PROVIDER=none`, and `ollama-version` branch rollback in `README.md` and `specs/008-vercel-cloudflare-deploy/quickstart.md`
- [x] T052 [US4] Document token-compromise procedure (revoke `CF_API_TOKEN`, create replacement, update Vercel env, redeploy) in `README.md`
- [x] T053 [US4] Verify or create the `ollama-version` branch and record exact Docker rollback commands in `README.md`
- [ ] T054 [US4] Exercise a preview rollback and `provider=none` mode; record results in `specs/008-vercel-cloudflare-deploy/quickstart.md`

**Checkpoint**: Failure modes are safe and rollback is proven.

---

## Phase 7: User Story 5 - Chủ dự án hiệu chỉnh chất lượng trả lời (Priority: P3)

**Goal**: Chọn lại `HIGH`, `MID`, `FUZZY_W` trên vector Cloudflare bằng 30–50 câu thật, không dùng ngưỡng Ollama cũ.

**Independent Test**: Chạy `scripts/tune_weights.py` trên bộ câu hỏi, áp dụng ngưỡng, kiểm tra câu đúng ≥ HIGH và câu ngoài chủ đề < MID.

### Tests for User Story 5

- [x] T055 [P] [US5] Add `backend/tests/test_tune_weights.py` with fake vectors/cases verifying grid search boundaries and deterministic best-threshold output
- [x] T056 [P] [US5] Review and expand `backend/evaluation/deploy_questions.json` to 30–50 cases covering exact, typo, no-diacritics, abbreviation, ambiguous, and off-topic categories

### Implementation for User Story 5

- [x] T057 [US5] Create `scripts/tune_weights.py` to embed evaluation questions once, grid-search `FUZZY_W` (0.0–0.4), `HIGH` (0.70–0.90), `MID` (0.40–0.65), and print the recommended set
- [x] T058 [US5] Document tuning usage and how to apply `HIGH`/`MID`/`FUZZY_W` to Vercel env in `README.md` and `.env.example`
- [ ] T059 [US5] Run tuning against real Cloudflare vectors and record recommended thresholds in `specs/008-vercel-cloudflare-deploy/quickstart.md`

**Checkpoint**: Thresholds are retuned for the new embedding provider.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Đồng bộ tài liệu, dọn đường deploy, và chạy toàn bộ cổng kiểm chứng.

- [x] T060 [P] Update `README.md` architecture, environment variables, deploy commands, free-tier limits, and troubleshooting for the Vercel path
- [x] T061 [P] Update `backend/README.md` with the new provider/vector/source paths and the legacy Ollama/FAISS boundary
- [x] T062 Remove dead legacy imports/references from `backend/app.py`, `backend/chatbox.py`, and `backend/kb_engine.py` while keeping `ollama-version` rollback behavior
- [x] T063 Run `pytest -q`, `npm --prefix frontend test -- --run`, `npm --prefix frontend run lint`, and `npm --prefix frontend run build`; fix all failures
- [x] T064 Run `scripts/check_secrets.py` across the repository and built frontend; confirm no `CF_ACCOUNT_ID`/`CF_API_TOKEN` leakage
- [ ] T065 Run `vercel build`, confirm the Python function stays under 500 MB and excludes tests/docs/PDF/DOCX, and fix `vercel.json` if needed
- [ ] T066 Run the full T1–T8 acceptance suite from `specs/008-vercel-cloudflare-deploy/quickstart.md` against a preview deployment and record pass/fail
- [ ] T067 Verify rollback and `CHATBOT_EMBEDDING_PROVIDER=none` on the preview; record outcomes in `specs/008-vercel-cloudflare-deploy/quickstart.md`
- [ ] T068 Record measured warm/cold response times and final bundle size in `specs/008-vercel-cloudflare-deploy/quickstart.md`
- [x] T069 Final consistency check across `specs/008-vercel-cloudflare-deploy/spec.md`, `plan.md`, `data-model.md`, `contracts/`, and `quickstart.md`; fix path or contract drift

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup — **blocks all user stories**.
- **User Stories (Phase 3–7)**: All depend on Foundational completion.
  - US1 (P1) and US2 (P1) can start in parallel after Foundational if staffed, but US2 production verification needs US1's endpoint.
  - US3, US4, US5 follow after US1/US2 foundations.
- **Polish (Phase 8)**: Depends on all desired stories complete.

### User Story Dependencies

- **US1 (P1)**: Starts after Foundational. No dependency on US2–US5.
- **US2 (P1)**: Starts after Foundational; verifies production deployment of US1 output.
- **US3 (P2)**: Depends on Foundational scripts (`check_chatbot.py`, `build_vectors.py`) and US1 health/chat.
- **US4 (P2)**: Depends on US1 fallback path and US2 deployment/rollback.
- **US5 (P3)**: Depends on Foundational provider/vector store and US3 vector build.

### Within Each User Story

- Tests before corresponding implementation where feasible.
- Provider/vector store before `kb_engine`; `kb_engine` before app/API; app/API before frontend/smoke tests.
- Scripts before running them; build vector before T1–T8 acceptance.
- Story complete before moving to next priority unless parallel staffing is available.

### Parallel Opportunities

- Setup: T002 and T003.
- Foundational: T006, T007, T008, T013, T015 can run in parallel; T017–T020 can run in parallel after their targets exist.
- US1: T021–T024 tests in parallel; T027 can run while T025/T026 are in progress.
- US2: T030–T032 tests in parallel; T033/T034 can run in parallel; T036 after T016/T033.
- US3: T038–T041 tests in parallel; T042/T043 can run in parallel on different scripts.
- US4: T047–T049 tests in parallel (T047 extends an existing file, keep it after T017); T048/T049 same phase but different files.
- US5: T055/T056 in parallel; T057/T058 after tests.
- Polish: T060/T061 in parallel; verification tasks T063–T069 run sequentially.

---

## Parallel Example: User Story 1

```bash
# Tests for US1 (different files, parallel):
Task: "Contract tests for /api/chat and /api/health in backend/tests/test_deployment_api.py"
Task: "Provider-failure integration test in backend/tests/test_deployment_fallback.py"
Task: "Offline T1–T3 answers in backend/tests/test_deployment_answers.py"
Task: "Frontend /api/chat URL test in frontend/src/lib/chatClient.test.ts"

# Then implementation:
Task: "Health client in frontend/src/lib/health.ts"
Task: "App health/cold-start + Cloudflare notice in frontend/src/App.tsx"
Task: "Smoke script in scripts/smoke_deploy.py"
```

## Parallel Example: User Story 2

```bash
# Tests for US2 (different files, parallel):
Task: "Vercel config validation in backend/tests/test_vercel_config.py"
Task: "Frontend relative-base test in frontend/src/lib/config.test.ts"
Task: "Frontend secret scan in backend/tests/test_no_secrets_in_frontend.py"

# Then implementation:
Task: "Root .env.example + frontend/.env.example"
Task: "Secret scan script in scripts/check_secrets.py"
Task: "Deploy/WAF docs in README.md"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational — **critical**, blocks all stories.
3. Complete Phase 3: US1.
4. **STOP and VALIDATE**: run US1 independent test locally/preview.
5. Demo the public chat flow with fallback.

### Incremental Delivery

1. Setup + Foundational → nền tảng sẵn sàng.
2. US1 → public chat + fallback (MVP).
3. US2 → production Vercel deployment, no card, WAF, secret safety.
4. US3 → safe data update workflow + stale-vector warning.
5. US4 → incident handling, rollback, token rotation.
6. US5 → retuned thresholds.
7. Polish → full T1–T8 acceptance and documentation sync.

### Parallel Team Strategy

1. Team completes Setup + Foundational together.
2. After Foundational:
   - Developer A: US1 (chat API + frontend).
   - Developer B: US2 (Vercel config + security docs).
   - Developer C: US3 scripts/tests after T013–T014 land.
3. US4 and US5 can start once US1/US2 and US3 foundations are stable.
4. Polish runs after all desired stories.

---

## Notes

- `[P]` tasks touch different files and have no dependency on incomplete tasks.
- `[Story]` labels map tasks to `spec.md` user stories for traceability.
- Tests are verification gates required by Constitution V, not optional extras.
- Commit after each logical group; do not commit `.env`, tokens, or `data/inbox` contents.
- Stop at each checkpoint to validate the story independently.
- Avoid: duplicating vector scoring logic, adding paid dependencies, serving stale vectors silently, or exposing secrets in logs/frontend.
