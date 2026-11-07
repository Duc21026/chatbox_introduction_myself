# Phase 0 Research: React Chat UI and Frontend/Backend Split

**Feature**: `003-react-chat-ui`  
**Date**: 2026-11-07

## R1 — Repository separation strategy

- **Decision**: Move the retained Python service and its assets into `backend/` (`app.py`, `chatbox.py`, `documents.py`, `text_normalization.py`, `requirements.txt`, `qa.txt`, `data/`, `scripts/`, `evaluation/`, `tests/`). Add `frontend/` as a self-contained Vite/React app. Keep a thin root `app.py` compatibility shim that re-exports `backend.app` so `python app.py` still works during the transition.
- **Rationale**: Satisfies the spec's explicit separation requirement while minimizing disruption to the working 002 backend. The shim gives one release of backward compatibility without duplicating logic. Backend behavior is not rewritten.
- **Alternatives considered**: (a) keep backend at root and only add `frontend/` — rejected because it does not clearly separate ownership; (b) rewrite the backend as part of this feature — rejected by spec scope and the temporary-retention assumption; (c) require a package install/build step for the backend — rejected because it adds friction for a local tool.

## R2 — Incremental answer delivery

- **Decision**: Add an additive `POST /chat/stream` endpoint that returns `text/event-stream` events `{"type":"chunk","content":"..."}`, then `{"type":"done"}` or `{"type":"error","message":"..."}`. Reuse the existing retrieval/normalization and QA-match path. For a QA match, emit the stored answer as one chunk. For the LLM path, use LangChain's `stream()` on the configured chat model. Keep `POST /chat` unchanged. The frontend prefers `/chat/stream` and falls back to `/chat` when the endpoint is missing, non-2xx, or returns JSON.
- **Rationale**: Delivers visible progressive output without breaking the existing contract. Real token streaming is achievable with the installed LangChain/Ollama stack and no new dependency. Fallback guarantees the UI works against an older or temporarily unavailable backend.
- **Alternatives considered**: (a) force streaming only — rejected because the spec requires graceful fallback; (b) use WebSockets — overkill for one-way text; (c) simulate streaming client-side from a full response — rejected as misleading.

## R3 — Frontend state and persistence

- **Decision**: Use Zustand for a single chat store with conversations, active conversation, message statuses, streaming flags, sidebar state, and theme. Conversations live only in memory for the session; theme (`system`/`light`/`dark`) persists in `localStorage`. Reloading the page starts a fresh empty workspace.
- **Rationale**: Matches the spec's session-only conversation requirement, keeps the state small and testable, and avoids a database or server history. Theme persistence is an explicit UI preference, not chat content.
- **Alternatives considered**: React Context only — workable but more prop/context churn for streaming updates; Redux Toolkit — heavier than needed; `localStorage` chat history — rejected by spec.

## R4 — Markdown, code, and untrusted content

- **Decision**: Render assistant content with `react-markdown` + `remark-gfm`, leave raw HTML disabled (`rehype-raw` not used), and highlight fenced code with `rehype-highlight`. Wrap fenced blocks in a `CodeBlock` component with a language label and copy button using `navigator.clipboard` with a `document.execCommand` fallback. Inline code gets a subtle style independent of the theme toggle. Links open in a new tab with `rel="noopener noreferrer"`.
- **Rationale**: Markdown/GFM cover lists, tables, quotes, and code; default escaping prevents injected HTML from executing; copy is essential for technical answers. No remote rendering service.
- **Alternatives considered**: `marked` + `DOMPurify` — more wiring and a larger XSS surface to manage; enabling raw HTML — rejected for untrusted model output; server-side rendering — unnecessary for a local SPA.

## R5 — Visual system and theming

- **Decision**: Define CSS custom properties in `tokens.css` for surfaces, borders, text, controls, accent, radii, spacing, and shadows. Use a distinct brand accent (deep teal/green rather than the reference's terracotta), a compact icon-first sidebar, serif reading text, sans UI text, and mono code. Resolve `system` preference with `prefers-color-scheme`, allow manual light/dark override, persist the choice, and honor `prefers-reduced-motion`. Use system font stacks (no external font CDN) to keep the app offline-capable and avoid licensing issues.
- **Rationale**: Makes the UI feel intentional rather than a generic template, supports light/dark consistently, and avoids remote assets or copied branding. Tokens keep components consistent and make future rebranding a one-file change.
- **Alternatives considered**: Tailwind — fast but adds build config and class noise for a small app; a component library — heavy visual opinions and bundle cost; remote Google Fonts — privacy/offline downside.

## R6 — Responsive layout and accessibility

- **Decision**: Desktop: fixed collapsible icon sidebar plus a centered conversation column with a max reading width. Below 768px: the sidebar becomes an overlay drawer opened from the header, closes on backdrop click or `Esc`, and returns focus to the trigger. Messages are exposed as a polite live log; the composer has a labeled textarea; icon buttons have accessible names; status text is not conveyed by color alone; focus rings are visible; contrast targets 4.5:1.
- **Rationale**: The spec requires phone/desktop usability and keyboard access. A drawer avoids a permanently cramped sidebar on phones. Live-region announcements make streaming and errors perceivable to assistive technology.
- **Alternatives considered**: bottom tab bar — poor fit for conversation history; always-visible sidebar — unusable on narrow screens.

## R7 — Vietnamese input-method safety

- **Decision**: Enter sends only when `!event.nativeEvent.isComposing` and the key code is not 229; Shift+Enter inserts a newline. The send button remains available for pointer and keyboard users. The textarea auto-resizes up to a capped height and scrolls beyond it.
- **Rationale**: Telex/VNI composition can emit Enter while selecting candidates; naive handlers send partial text. The explicit guard is a small, testable rule.
- **Alternatives considered**: debounce-only — does not prevent the spurious Enter; send on button only — slower for common use.

## R8 — Configuration and local integration

- **Decision**: The frontend reads `VITE_API_BASE_URL` (default `http://127.0.0.1:5000`) from `frontend/.env`; only `frontend/.env.example` is committed. The backend keeps its `.env`-based model and data settings in `backend/.env.example`. CORS remains enabled for the local dev origin. No credentials or model endpoints are exposed in the frontend bundle.
- **Rationale**: A single base URL is enough for local development and future deployment. Example files document the contract without committing secrets. Defaults keep `npm run dev` plus `python app.py` working out of the box.
- **Alternatives considered**: hard-coded backend URL — prevents deployment; a backend proxy in Vite — adds coupling and hides CORS issues.

## R9 — Testing and quality gates

- **Decision**: Use Vitest + React Testing Library + jsdom for store logic, SSE parsing, `/chat` fallback, composer/IME behavior, Markdown rendering, code copy, theme switching, conversation switching, and error/retry states. Keep backend pytest under `backend/tests/` and add contract tests for `/chat` and `/chat/stream` with a deterministic fake model. Run `npm run lint`, `npm run typecheck`, `npm run build`, and `pytest` as completion gates. Defer browser-level end-to-end automation to a follow-up unless needed.
- **Rationale**: The highest-risk logic is the streaming/fallback client, composer behavior, and state transitions; those are fast to test in jsdom. Backend contract tests protect the existing API. Lint/typecheck/build catch integration errors.
- **Alternatives considered**: Cypress/Playwright first — slower to set up and unnecessary for initial confidence; snapshot-only tests — brittle and low value.

## R10 — Ignore rules

- **Decision**: One root `.gitignore` with sections for Node (`node_modules/`, `dist/`, `.vite/`, `coverage/`, `*.local`), Python (`__pycache__/`, `*.py[cod]`, `.venv/`, `venv/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `*.egg-info/`), environment files (`.env`, `.env.*` with `!.env.example` and `!**/.env.example`), local knowledge-base data (`data/`, `backend/data/`), generated archives/partials (`*.tmp`, `*.part`), editor/OS files, and Spec Kit tooling (`.specify/`, `.opencode/`). Do not ignore `frontend/.env.example` or `backend/.env.example`.
- **Rationale**: Prevents build output, caches, local data, and secrets from being committed without hiding required examples. Keeps both ecosystems' artifacts out of review.
- **Alternatives considered**: per-directory ignore files — more places to keep consistent; ignoring `frontend/` wholesale — would hide source.

## R11 — Temporary backend boundary

- **Decision**: Document in the root README and `contracts/repository-layout.md` that `backend/` is retained temporarily, owns the answering logic, and will be replaced in a later feature. The frontend depends only on the documented HTTP contracts, never on backend source paths. No backend rewrite, model change, or knowledge-base migration occurs in this feature.
- **Rationale**: Preserves the working RAG behavior while allowing the UI to evolve independently. The HTTP contract is the seam for the eventual replacement.
- **Alternatives considered**: deleting the backend now — would leave no answering service; embedding the backend in the frontend repo — contradicts separation.

## R12 — Conversation titles and navigation

- **Decision**: Create a new conversation when the workspace is empty or the user explicitly starts one. Derive the title from the first user question, trimmed to ~40 characters with an ellipsis. Selecting a conversation replaces the active message list; stopping or failing a response leaves the conversation intact and offers retry. No rename/delete in this phase.
- **Rationale**: Gives useful orientation with minimal UI and matches the spec's session-only scope. Derived titles avoid extra prompts.
- **Alternatives considered**: numbered conversations — less recognizable; model-generated titles — extra latency and failure modes; rename/delete — deferred.

## R13 — Root compatibility shim

- **Decision**: The root `app.py` becomes `from backend.app import app` plus a `__main__` guard that calls the backend runner. Existing tests move to `backend/tests/` and run with backend on `sys.path`; scripts are invoked from the repository root as `python backend/scripts/manage_docs.py` or from `backend/`.
- **Rationale**: Keeps the familiar entry point during the split and gives users one migration cycle to adopt the new paths.
- **Alternatives considered**: no shim — breaks muscle memory and existing docs immediately; symlinks — platform-fragile.

## Resolved unknowns

All Technical Context entries are resolved; no `NEEDS CLARIFICATION` items remain. The stack, storage, testing, performance targets, constraints, and scope are defined above and reflected in `plan.md`.
