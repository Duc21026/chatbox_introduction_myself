# Implementation Plan: React Chat UI and Frontend/Backend Split

**Branch**: `003-react-chat-ui` | **Date**: 2026-11-07 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-react-chat-ui/spec.md`

## Summary

Replace the static Python-served chat page with a standalone React frontend while retaining the existing Python answering backend temporarily. The repository is split into `frontend/` (Vite + React 18 + TypeScript) and `backend/` (the retained Flask/LangChain/FAISS/Ollama service), with a root compatibility entry point so existing backend commands keep working during the transition. The new interface provides a focused, Claude-inspired reading experience: streaming-ready message rendering with a complete-response fallback, Markdown and code-block support with copy, light/dark theming, responsive navigation, session-scoped conversations, accessible controls, and Vietnamese input-method-safe composition. An additive `POST /chat/stream` endpoint enables incremental delivery without changing the existing `POST /chat` contract. Root ignore rules are rewritten to cover both ecosystems.

## Technical Context

**Language/Version**: Frontend: TypeScript 5.x on Node.js 20+ with React 18; Backend: Python 3.11+ (existing project virtualenv; the bundled Windows-only `venv/` is not used)

**Primary Dependencies**: Frontend: Vite, React 18, TypeScript, Zustand, react-markdown, remark-gfm, rehype-highlight, lucide-react, Vitest, React Testing Library, jsdom. Backend: existing stack only — Flask, flask-cors, langchain, langchain-community, langchain-ollama, langchain-text-splitters, faiss-cpu, rapidfuzz, pandas, pypdf, python-docx, docx2txt; Ollama runs the configured Qwen2.5 answer model and `bge-m3` embeddings. No new backend runtime dependency is required for streaming (Flask generator responses + LangChain `stream`).

**Storage**: Conversation state is in-memory in the browser (Zustand) for the current session; theme preference is stored in `localStorage`. The backend keeps source documents under `backend/data/` and derives FAISS in memory; no database is introduced.

**Testing**: Frontend: Vitest + React Testing Library + jsdom for store, streaming client, composer/IME, Markdown/code copy, theme and error states; optional Playwright end-to-end coverage deferred. Backend: existing pytest suite relocated under `backend/tests/`, plus contract tests for `POST /chat` and additive `POST /chat/stream`.

**Target Platform**: Modern desktop and mobile browsers against a local single-user backend; offline-capable once dependencies are installed; no external CDN or hosted font service required.

**Project Type**: Web application with separated frontend and backend (`frontend/` + `backend/`), retaining a root compatibility shim for the backend entry point during migration.

**Performance Goals**: First meaningful paint under 2 seconds on a local machine; first streamed content visible within 1 second of the backend starting a response; composer input and message scrolling remain responsive with long answers; no full-page reload during chat.

**Constraints**: Vietnamese-first input handling (Telex/VNI `isComposing` safety); no secrets in the frontend; all message content treated as untrusted; existing `POST /chat` payload/response contract preserved; CORS continues to allow the local frontend; accessible keyboard navigation and 4.5:1 contrast; reduced-motion respected; backend retained temporarily and not rewritten.

**Scale/Scope**: One local operator/visitor, a handful of in-session conversations, a small knowledge base, roughly 15 evaluation questions; no authentication, multi-user permissions, or cross-session history.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md` still contains unratified template placeholders, so no project-specific principles are enforceable yet. The plan is checked against the template's intended principles and the repository's established conventions:

| Gate | Status | Notes |
|------|--------|-------|
| Simplicity / YAGNI | PASS | Adds one frontend application and an additive streaming endpoint; reuses the existing backend, models, and knowledge base. No database, auth, or server-side history. |
| Library/CLI-first, independently testable | PASS | Frontend behavior is isolated in a store, a chat client, and small components; backend answering remains in `chatbox.py`/`documents.py`; streaming is additive and does not alter `/chat`. |
| Test-first | PASS (adapted) | Frontend unit/component tests and backend contract tests are defined before behavior changes; live Ollama checks remain gated by environment readiness. |
| Integration testing | PASS | Covers browser → HTTP → backend answer, non-streaming fallback, streaming chunks, error/retry, Markdown/code copy, theme, mobile drawer, and conversation switching. |
| Observability | PASS (adapted) | Frontend surfaces waiting, streaming, stopped, interrupted, and error states; backend keeps existing retrieval diagnostics for the operator CLI. |
| No secrets / local-first | PASS | Backend credentials stay server-side; the frontend uses only a base URL; no cloud calls, secret storage, external fonts, or remote persistence. |
| Repository hygiene | PASS | `frontend/` and `backend/` have distinct ownership; one root ignore file covers Node, Python, environment, cache, and editor/OS artifacts while keeping example env files trackable. |

**Result**: PASS — no violations requiring justification.

**Post-design re-check (after Phase 1)**: PASS — the design keeps the existing answering stack, isolates the new UI, documents the temporary backend boundary, adds no database or secret, and preserves the public `/chat` contract.

## Project Structure

### Documentation (this feature)

```text
specs/003-react-chat-ui/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── chat-api.md
│   ├── frontend-api-client.md
│   ├── repository-layout.md
│   └── ui-contract.md
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created here)
```

### Source Code (repository root)

```text
frontend/
├── index.html
├── package.json
├── package-lock.json
├── tsconfig.json
├── tsconfig.node.json
├── vite.config.ts
├── eslint.config.js
├── .env.example                 # VITE_API_BASE_URL
└── src/
    ├── main.tsx
    ├── App.tsx
    ├── vite-env.d.ts
    ├── styles/
    │   ├── tokens.css
    │   └── app.css
    ├── store/
    │   └── chatStore.ts
    ├── hooks/
    │   ├── useAutoResize.ts
    │   └── useAutoScroll.ts
    ├── lib/
    │   └── chatClient.ts
    ├── test/
    │   └── setup.ts
    └── components/
        ├── Sidebar/Sidebar.tsx
        ├── Header/Header.tsx
        ├── MessageList/MessageList.tsx
        ├── Message/Message.tsx
        ├── Message/CodeBlock.tsx
        ├── Composer/Composer.tsx
        ├── EmptyState/EmptyState.tsx
        └── ThemeToggle/ThemeToggle.tsx

backend/
├── app.py                     # Flask API; POST /chat unchanged, POST /chat/stream additive
├── chatbox.py                 # Config, loaders, index refresh, retrieval, LLM, streaming helper
├── documents.py               # Source lifecycle
├── text_normalization.py      # Shared Vietnamese normalization
├── requirements.txt
├── qa.txt
├── data/                      # Persisted knowledge-base sources
├── .env.example               # Backend configuration
├── scripts/
│   └── manage_docs.py
├── evaluation/
│   └── ...
└── tests/
    ├── conftest.py
    ├── helpers.py
    ├── test_answers.py
    ├── test_chat_api.py
    ├── test_document_management.py
    ├── test_normalization.py
    ├── test_refusal.py
    ├── test_retrieval.py
    └── test_retrieval_normalization.py

app.py                         # Root compatibility shim: python app.py -> backend.app
README.md                      # Split layout, temporary backend note, run instructions
.gitignore                     # Root rules for frontend and backend
```

**Structure Decision**: Choose the web-application layout with `frontend/` and `backend/` directories. The Python backend code and its assets move under `backend/` unchanged in behavior; a thin root `app.py` shim preserves `python app.py` while the migration completes. The frontend is a self-contained Vite/React application and has no build-time coupling to backend source files. The backend remains explicitly temporary per the spec, and replacing it is a separate future feature.

## Delivery Phases

1. **Repository split and ignore rules**: create `frontend/` and `backend/`, move retained backend files and assets, add the root compatibility shim, rewrite `.gitignore`, and update the README with run instructions and the temporary backend note.
2. **Frontend foundation**: scaffold Vite + React + TypeScript, add design tokens, layout shell, theme handling, routing-free state store, and build/lint/typecheck scripts.
3. **Chat experience**: implement the API client (streaming detection + non-streaming fallback), message list, Markdown rendering, code blocks with copy, composer with auto-resize and IME-safe Enter, and empty/loading/error/stopped states.
4. **Navigation and conversation workspace**: sidebar with new-chat/select behavior, conversation titles from the first question, desktop collapse, mobile drawer, and session-only state.
5. **Additive backend streaming**: add `POST /chat/stream` reusing the existing retrieval/answer path, keep `/chat` untouched, and document the event format.
6. **Verification**: frontend unit/component tests, backend contract tests, accessibility checks, responsive checks, and quickstart validation.

## Complexity Tracking

> No constitution violations. Section intentionally empty.
