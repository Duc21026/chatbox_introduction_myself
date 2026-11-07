# Tasks: React Chat UI and Frontend/Backend Split

**Input**: Design documents from `/specs/003-react-chat-ui/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included because the plan's quality gates require frontend unit/component tests and backend contract tests. Tests are grouped by story and written before implementation.

**Organization**: Tasks are grouped by user story so each story can be implemented, tested, and validated independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: User story label (`US1`–`US5`), only in user story phases
- Every task includes an exact file path or a validation artifact path

## Path Conventions

Web application split: `frontend/` and `backend/` at the repository root, plus a root `app.py` compatibility shim. Historical specs retain their original paths.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the split layout, move the retained backend, and scaffold the frontend.

- [X] T001 Create `frontend/` and `backend/` directories and move the retained Python service per `specs/003-react-chat-ui/contracts/repository-layout.md`: `backend/app.py`, `backend/chatbox.py`, `backend/documents.py`, `backend/text_normalization.py`, `backend/requirements.txt`, `backend/qa.txt`, `backend/data/`, `backend/scripts/manage_docs.py`, `backend/evaluation/`, and `backend/tests/`
- [X] T002 Update backend imports, data/QA paths, env loading, and test bootstrap for the new location in `backend/app.py`, `backend/chatbox.py`, `backend/documents.py`, `backend/text_normalization.py`, `backend/scripts/manage_docs.py`, and `backend/tests/conftest.py`; verify `pytest backend/tests` still collects the suite
- [X] T003 Add the root compatibility shim in `app.py` that re-exports `backend.app.app` and runs the backend when executed as a script
- [X] T004 [P] Scaffold frontend configuration in `frontend/package.json`, `frontend/tsconfig.json`, `frontend/tsconfig.node.json`, `frontend/vite.config.ts`, `frontend/eslint.config.js`, and `frontend/index.html`
- [X] T005 [P] Create `frontend/src/main.tsx`, `frontend/src/vite-env.d.ts`, and `frontend/.env.example` with `VITE_API_BASE_URL=http://127.0.0.1:5000`
- [X] T006 Configure Vitest, React Testing Library, and jsdom in `frontend/vite.config.ts` and create `frontend/src/test/setup.ts` (depends on T004)
- [X] T007 Install frontend dependencies and generate `frontend/package-lock.json` with `dev`, `build`, `preview`, `test`, `lint`, and `typecheck` scripts (depends on T004)

**Checkpoint**: The backend runs from `backend/` and via root `app.py`; the frontend dev server starts with an empty shell.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared design system, state, configuration, and app shell required by every story.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T008 [P] Define theme tokens for surfaces, borders, text, controls, accent, radii, spacing, shadows, typography, and motion in `frontend/src/styles/tokens.css`; include light and dark values and a distinct teal/green brand accent
- [X] T009 [P] Create base layout, typography, focus-ring, and theme-attribute styles in `frontend/src/styles/app.css`
- [X] T010 [P] Implement runtime configuration loading and URL normalization in `frontend/src/lib/config.ts` using `VITE_API_BASE_URL` with the `http://127.0.0.1:5000` fallback
- [X] T011 [P] Implement system-preference resolution and versioned persistence for `system`/`light`/`dark` in `frontend/src/lib/theme.ts` using the `ThemePreference` rules in `data-model.md`
- [X] T012 Create the shared domain types and Zustand store skeleton (conversations, messages, statuses, active id, streaming flag, sidebar state, theme mode) in `frontend/src/store/chatStore.ts`
- [X] T013 Create deterministic test doubles for backend JSON and stream responses in `frontend/src/test/mockChat.ts` (depends on T012)
- [X] T014 Create the app shell in `frontend/src/App.tsx` with `header`/`nav`/`main` landmarks, theme application, and placeholder regions for header, sidebar, message list, and composer (depends on T008–T012)

**Checkpoint**: Tokens, theme, config, store types, and the shell render without story-specific behavior.

---

## Phase 3: User Story 1 — Use a Separated Frontend Against the Existing Backend (Priority: P1) 🎯 MVP

**Goal**: Send a question from the standalone frontend, receive the existing `/chat` answer, and show retryable errors without changing backend answer logic.

**Independent Test**: Start `backend/` and `frontend/` separately, send one question, and confirm the answer appears without a page reload; stop the backend and confirm a clear error with retry.

### Tests for User Story 1

> Write these tests first and confirm they fail before implementation.

- [X] T015 [P] [US1] Add a backend contract test asserting `POST /chat` accepts `{"message": "..."}` and returns `{"response": "..."}`, with 400 for blank input, in `backend/tests/test_chat_api_contract.py`
- [X] T016 [P] [US1] Add frontend tests for the JSON `/chat` path, blank-input rejection, and typed 4xx/5xx/network errors in `frontend/src/lib/chatClient.test.ts`
- [X] T017 [P] [US1] Add an app-level test for send, answer display, error, and retry (no duplicate user message) in `frontend/src/App.test.tsx`

### Implementation for User Story 1

- [X] T018 [US1] Implement the non-streaming `sendMessage` JSON path and `ChatApiError` taxonomy in `frontend/src/lib/chatClient.ts` using the rules in `contracts/frontend-api-client.md` (depends on T010, T016)
- [X] T019 [US1] Implement conversation creation and send/retry actions in `frontend/src/store/chatStore.ts`, including `"complete"` and `"error"` message transitions (depends on T018)
- [X] T020 [P] [US1] Implement the header shell with accessible controls in `frontend/src/components/Header/Header.tsx`
- [X] T021 [P] [US1] Implement the scrollable message container with `role="log"` and polite live updates in `frontend/src/components/MessageList/MessageList.tsx`
- [X] T022 [P] [US1] Implement user/assistant message rendering with distinct alignment, waiting state, and error+retry in `frontend/src/components/Message/Message.tsx`
- [X] T023 [P] [US1] Implement the basic composer with a labeled textarea, blank-input disabling, and send control in `frontend/src/components/Composer/Composer.tsx`
- [X] T024 [P] [US1] Implement the empty workspace greeting and optional example prompts in `frontend/src/components/EmptyState/EmptyState.tsx`
- [X] T025 [US1] Wire header, message list, composer, and empty state into `frontend/src/App.tsx`; ensure a send appends without reload and keeps focus in the composer (depends on T019–T024)
- [X] T026 [US1] Verify the retained backend CORS configuration allows the frontend origin and that `POST /chat` remains unchanged in `backend/app.py`; document the local base URL in `frontend/.env.example` (depends on T015, T025)

**Checkpoint**: US1 works end-to-end with full (non-streaming) answers and retryable errors.

---

## Phase 4: User Story 2 — Read Answers While They Are Being Produced (Priority: P1)

**Goal**: Render answers incrementally when available, fall back to complete responses, stop generation, and display readable Markdown/code with copy and IME-safe input.

**Independent Test**: Run a streaming and a non-streaming stub; confirm incremental text, Markdown/GFM, code copy, stop with partial content, fallback from `/chat/stream` to `/chat`, and that IME-composing Enter does not send.

### Tests for User Story 2

- [X] T027 [P] [US2] Add backend contract tests for `POST /chat/stream` event order, terminal `done`/`error`, blank-input 400, and unchanged `/chat` behavior in `backend/tests/test_chat_stream_api.py`
- [X] T028 [P] [US2] Add frontend tests for SSE line buffering, multiple events per chunk, split events, terminal handling, JSON fallback, 404 fallback, and abort in `frontend/src/lib/streamParser.test.ts`
- [X] T029 [P] [US2] Add component tests for Markdown/GFM rendering, code copy success/failure, IME-safe Enter, Shift+Enter, auto-resize, and stop in `frontend/src/components/Message/Message.test.tsx` and `frontend/src/components/Composer/Composer.test.tsx`

### Implementation for User Story 2

- [X] T030 [US2] Implement an additive streaming answer generator in `backend/chatbox.py` that emits QA matches as one chunk, streams LLM tokens otherwise, and never exposes prompts/diagnostics (depends on T027)
- [X] T031 [US2] Implement `POST /chat/stream` in `backend/app.py` with `text/event-stream`, `chunk`/`done`/`error` events, and unchanged `POST /chat` (depends on T030)
- [X] T032 [US2] Extend `frontend/src/lib/chatClient.ts` with `/chat/stream` consumption, type detection, `/chat` fallback, abort handling, and `interrupted` mapping (depends on T018, T028)
- [X] T033 [US2] Implement `"streaming"`, `"stopped"`, and `"interrupted"` transitions and stop/retry actions in `frontend/src/store/chatStore.ts` (depends on T032)
- [X] T034 [P] [US2] Implement the copyable fenced `CodeBlock` with language label, Clipboard API, and `execCommand` fallback in `frontend/src/components/Message/CodeBlock.tsx`
- [X] T035 [US2] Render assistant Markdown with `react-markdown`, `remark-gfm`, and `rehype-highlight` (raw HTML disabled) and integrate `CodeBlock` in `frontend/src/components/Message/Message.tsx` (depends on T034)
- [X] T036 [US2] Implement auto-resize, Enter-to-send, Shift+Enter newline, and `isComposing`/keyCode 229 guards in `frontend/src/components/Composer/Composer.tsx` and `frontend/src/hooks/useAutoResize.ts`
- [X] T037 [US2] Render streaming cursor, stopped label, interrupted retry, and a stop control in `frontend/src/components/Message/Message.tsx` and `frontend/src/components/Composer/Composer.tsx` (depends on T033, T035, T036)
- [X] T038 [US2] Wire streaming into `frontend/src/App.tsx` and add bottom-following auto-scroll that yields to manual scroll-up in `frontend/src/components/MessageList/MessageList.tsx` and `frontend/src/hooks/useAutoScroll.ts` (depends on T031, T033, T035, T036, T037)

**Checkpoint**: US2 works with streaming and non-streaming backends, rich content, copy, stop, and Vietnamese IME.

---

## Phase 5: User Story 3 — Use the Interface Comfortably on Any Screen and Theme (Priority: P2)

**Goal**: Keep the conversation usable on phone and desktop, make navigation collapsible/dismissible, and support system/light/dark themes.

**Independent Test**: Check 360px and 1440px widths in both themes; open/close the drawer with keyboard and backdrop; collapse desktop navigation; toggle theme during a stream; verify reduced motion.

### Tests for User Story 3

- [X] T039 [P] [US3] Add tests for system preference, manual override persistence, invalid stored values, and theme during streaming in `frontend/src/lib/theme.test.ts`
- [X] T040 [P] [US3] Add tests for drawer open/close, `Esc`, focus restoration, desktop collapse, and `aria-current` navigation in `frontend/src/components/Sidebar/Sidebar.test.tsx`

### Implementation for User Story 3

- [X] T041 [P] [US3] Implement the system/light/dark theme toggle with accessible labels and document-root updates in `frontend/src/components/ThemeToggle/ThemeToggle.tsx`
- [X] T042 [US3] Implement the responsive sidebar shell with desktop collapse, mobile overlay drawer, backdrop close, `Esc` close, and focus trap/restore in `frontend/src/components/Sidebar/Sidebar.tsx` (depends on T040)
- [X] T043 [US3] Add breakpoint rules (≥1024px, 768–1023px, <768px), bounded reading width, no horizontal overflow at 320px, and safe-area composer padding in `frontend/src/styles/app.css` (depends on T042)
- [X] T044 [P] [US3] Add reduced-motion suppression and token-based animation rules in `frontend/src/styles/tokens.css` and `frontend/src/styles/app.css`
- [X] T045 [US3] Wire `ThemeToggle` into `frontend/src/components/Header/Header.tsx` and sidebar state/trigger into `frontend/src/App.tsx` (depends on T041–T044)
- [X] T046 [US3] Verify theme switching during an active stream preserves content and updates colors in `frontend/src/App.test.tsx` (depends on T045)

**Checkpoint**: US3 works at phone/desktop widths, both themes, keyboard-only navigation, and reduced motion.

---

## Phase 6: User Story 4 — Manage Conversations in the Current Session (Priority: P2)

**Goal**: Create, title, and switch between session-only conversations without message leakage, and reset to an empty workspace on reload.

**Independent Test**: Send two different first questions, switch between conversations, confirm titles and isolated message lists, then reload and confirm a fresh empty workspace.

### Tests for User Story 4

- [X] T047 [P] [US4] Add store tests for first-question title derivation (~40 characters), new/select actions, single streaming invariant, and session reset in `frontend/src/store/chatStore.test.ts`
- [X] T048 [P] [US4] Add a component test for two isolated conversations, switching, and reload-to-empty behavior in `frontend/src/App.test.tsx`

### Implementation for User Story 4

- [X] T049 [US4] Implement `newConversation`, `selectConversation`, title derivation, and session reset in `frontend/src/store/chatStore.ts` (depends on T047)
- [X] T050 [US4] Render the in-session conversation list with active state and `aria-current` in `frontend/src/components/Sidebar/Sidebar.tsx` (depends on T042, T049)
- [X] T051 [US4] Show the active conversation title or empty placeholder in `frontend/src/components/Header/Header.tsx` (depends on T045, T049)
- [X] T052 [US4] Wire New chat and conversation selection in `frontend/src/App.tsx`; ensure selecting a conversation never mixes messages and reload starts empty (depends on T048–T051)

**Checkpoint**: US4 works with at least two conversations and no message leakage.

---

## Phase 7: User Story 5 — Keep the Repository Cleanly Split and Ignorable (Priority: P3)

**Goal**: Make frontend/backend ownership obvious, document the temporary backend, replace the legacy UI, and enforce ignore rules.

**Independent Test**: Inspect the layout, run documented commands, and confirm generated/build/cache/env/editor artifacts are ignored while `.env.example` files remain trackable.

### Implementation for User Story 5

- [X] T053 [P] [US5] Rewrite `.gitignore` with the Node, Python, environment, local-data, archive/partial, editor/OS, and tooling sections from `contracts/repository-layout.md`, including `!.env.example` and `!**/.env.example`
- [X] T054 [P] [US5] Update `README.md` with the split layout, temporary-backend statement, backend/frontend install and run commands, and test/build commands; add `backend/README.md` explaining backend ownership and the future replacement direction
- [X] T055 [P] [US5] Remove the legacy static page `backend/index.html` and its serving route from `backend/app.py` while preserving the answering endpoints and backend tests
- [X] T056 [P] [US5] Ensure `frontend/.env.example` and `backend/.env.example` are present, contain no secrets, and remain trackable
- [X] T057 [US5] Validate the repository split with `git status --porcelain`, `git check-ignore -v` on `frontend/node_modules`, `frontend/dist`, `backend/__pycache__`, `backend/.pytest_cache`, `backend/data`, and `backend/.env`, and confirm `git check-ignore` reports nothing for both `.env.example` files; update `specs/003-react-chat-ui/quickstart.md` if commands differ (depends on T053–T056)

**Checkpoint**: US5 works: the layout is clear, the legacy UI is gone, and ignore rules behave as documented.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Accessibility, resilience, performance, and final validation across all stories.

- [X] T058 [P] Audit and fix accessibility in `frontend/src/App.tsx`, `frontend/src/components/Header/Header.tsx`, `frontend/src/components/Sidebar/Sidebar.tsx`, `frontend/src/components/MessageList/MessageList.tsx`, and `frontend/src/components/Composer/Composer.tsx`: landmarks, live-region politeness, labels, focus order, keyboard operation, and status text
- [X] T059 [P] Add scroll-to-latest affordance, long unbroken text wrapping, and bounded reading column behavior in `frontend/src/components/MessageList/MessageList.tsx`, `frontend/src/components/Message/Message.tsx`, and `frontend/src/hooks/useAutoScroll.ts`
- [X] T060 Add timeout, rate-limit/quota, and misconfigured-URL error copy and retry behavior in `frontend/src/lib/chatClient.ts` and `frontend/src/components/Message/Message.tsx`
- [X] T061 Run `npm run test`, `npm run lint`, `npm run typecheck`, and `npm run build` in `frontend/`; fix all failures
- [X] T062 Run `pytest backend/tests` from the repository root; confirm `/chat` contract tests pass and document any live-model-dependent failures in `specs/003-react-chat-ui/tasks.md`
- [X] T063 Execute quickstart scenarios 1–10 from `specs/003-react-chat-ui/quickstart.md` and record outcomes in the Implementation Notes section of `specs/003-react-chat-ui/tasks.md`
- [X] T064 Remove dead legacy references, verify no frontend source imports from `backend/`, check theme contrast ≥4.5:1, and confirm all task checkboxes accurately reflect completed work in `specs/003-react-chat-ui/tasks.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies; T001 → T002 → T003, while T004 → T005/T006/T007 proceed in parallel after T004.
- **Foundational (Phase 2)**: Depends on Setup; blocks all user stories. T014 depends on T008–T012.
- **User Stories (Phase 3+)**: Depend on Foundational.
  - US1 and US2 are both P1; implement US1 first because US2 extends the shared client, store, message, and composer.
  - US3 depends on the US1 layout and Header/App shell; it can start after US2 for least conflict.
  - US4 depends on the US3 sidebar shell.
  - US5 depends only on Setup and can run in parallel with any story.
- **Polish (Phase 8)**: Depends on all desired stories; run after US5 and at least US1–US4.

### User Story Dependencies

- **US1 (P1)**: Starts after Foundational; no other story dependency. MVP.
- **US2 (P1)**: Starts after Foundational and integrates with US1's `chatClient`, store, `Message`, and `Composer`; backend endpoint and parser can be developed in parallel.
- **US3 (P2)**: Starts after Foundational and US1's shell; shares Header/App with US1.
- **US4 (P2)**: Starts after US3's Sidebar shell; shares store with US1/US2.
- **US5 (P3)**: Starts after Setup; independent of UI stories except for final docs.

### Within Each User Story

- Tests first, then implementation, then integration, then checkpoint validation.
- Backend helper before endpoint; client parser before store transitions; store before wiring.
- Components on different files can be built in parallel once their inputs are defined.

### Parallel Opportunities

- Setup: T005, T006, and T007 can start after T004; T003 needs T001/T002.
- Foundational: T008, T009, T010, and T011 are independent files.
- US1: T015–T017 (tests), T020–T024 (components) are parallelizable.
- US2: T027–T029 (tests), T034 (CodeBlock) are parallelizable; T036 touches Composer after T023.
- US3: T039–T041 and T044 are parallelizable; T042 waits for T040.
- US4: T047–T048 (tests) are parallelizable.
- US5: T053–T056 are independent files.

---

## Parallel Example: User Story 1

```bash
# Tests
Task: "Backend `/chat` contract test in backend/tests/test_chat_api_contract.py"
Task: "Frontend `/chat` client test in frontend/src/lib/chatClient.test.ts"
Task: "App send/error/retry test in frontend/src/App.test.tsx"

# Components
Task: "Header in frontend/src/components/Header/Header.tsx"
Task: "MessageList in frontend/src/components/MessageList/MessageList.tsx"
Task: "Message in frontend/src/components/Message/Message.tsx"
Task: "Composer in frontend/src/components/Composer/Composer.tsx"
Task: "EmptyState in frontend/src/components/EmptyState/EmptyState.tsx"
```

## Parallel Example: User Story 2

```bash
# Tests and isolated components
Task: "Backend stream contract tests in backend/tests/test_chat_stream_api.py"
Task: "SSE parser tests in frontend/src/lib/streamParser.test.ts"
Task: "Markdown/IME component tests in frontend/src/components/Message/Message.test.tsx and Composer/Composer.test.tsx"
Task: "CodeBlock in frontend/src/components/Message/CodeBlock.tsx"
```

## Parallel Example: User Story 5

```bash
Task: "Rewrite .gitignore"
Task: "Update README.md and add backend/README.md"
Task: "Remove legacy backend/index.html and static route"
Task: "Verify both .env.example files are trackable"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational.
3. Complete Phase 3: US1.
4. **STOP and VALIDATE**: Start backend and frontend separately, send a question, confirm the answer and error/retry behavior.
5. Demo the separated frontend with complete answers.

### Incremental Delivery

1. Setup + Foundational → split layout and shell ready.
2. US1 → working separated frontend with full answers (MVP).
3. US2 → streaming, Markdown/code, stop, IME-safe composer.
4. US3 → responsive navigation and themes.
5. US4 → session conversation management.
6. US5 → repository hygiene and legacy UI removal.
7. Polish → accessibility, resilience, and final validation.

### Parallel Team Strategy

1. Team completes Setup + Foundational together.
2. After Foundational:
   - Developer A: US1 (client, store, send/error).
   - Developer B: US2 backend (`chatbox`/`app.py`) and SSE parser tests; joins UI after US1.
   - Developer C: US5 repository split, ignore rules, docs.
3. After US1: US2 UI and US3 can split by component ownership; US4 follows US3's sidebar shell.

---

## Notes

- `[P]` marks different files with no dependency on incomplete work.
- Tests are included per the plan's quality gates; write them first and confirm failure before implementation.
- Do not change backend answer behavior; `POST /chat` stays compatible, and `/chat/stream` is additive.
- Keep secrets out of `frontend/` and out of any user-visible error text.
- Preserve Vietnamese-first input behavior and accessible keyboard navigation.
- Commit after each task or logical group; stop at checkpoints to validate independently.
- Avoid vague tasks, same-file conflicts, and cross-story dependencies that break independence.

## Implementation Notes

> Fill during implementation: test results, live-model-dependent skips/failures, quickstart scenario outcomes, and deviations from this plan.

### Implementation Notes (recorded 2026-11-07)

- **Repository split**: backend modules/assets moved to `backend/`; root `app.py` is a compatibility shim; backend imports support both `backend.*` and direct execution.
- **Frontend tests**: `npm run test` — 8 files, 40 tests passed.
- **Frontend gates**: `npm run lint`, `npm run typecheck`, and `npm run build` passed. Manual vendor chunking keeps all production chunks below Vite's 500 kB advisory threshold.
- **Backend tests**: `pytest backend/tests` — 67 passed, 2 failed. Both failures pre-date this feature and reproduce on the original backend: `test_retrieval.py::test_paraphrase_and_no_diacritics_retrieve_expected_fact` and `test_answers.py::test_in_domain_answers_contain_expected_facts[categories0]` (live-model/ranking brittleness).
- **Endpoint smoke checks**: `POST /chat` returned 200 with the QA answer; `POST /chat/stream` returned `text/event-stream` with one `chunk` and `done`; blank messages returned 400 on both endpoints.
- **Quickstart scenarios**: scenarios 1–4 and 6–10 have automated equivalents in `frontend/src/**/*.test.ts(x)`; scenario 5 (error/retry) is covered by App/store tests; scenario 8 (IME) by Composer tests. Headless Chrome screenshots at 1440x900 and 360x800 confirmed the light theme layout, collapsed mobile sidebar, composer, and empty state. Dark-mode colors were verified by WCAG contrast calculation and theme tests rather than screenshot.
- **Accessibility**: landmark regions, labeled controls, `aria-live` message log, keyboard focus states, reduced-motion handling, and text contrast ≥4.5:1 were checked; `--text-tertiary` was darkened to meet the threshold.
- **Known deviations**: no Playwright/browser E2E suite; endpoint smoke checks used Flask's test client rather than a long-running external server.
