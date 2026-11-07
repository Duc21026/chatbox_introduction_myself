# Quickstart: React Chat UI and Frontend/Backend Split

**Feature**: `003-react-chat-ui`  
**Purpose**: End-to-end validation of the split layout, new React UI, streaming/fallback behavior, and repository hygiene. See `contracts/` and `data-model.md` for details; this guide does not contain implementation code.

## Prerequisites

- Node.js 20+ and npm.
- Python 3.11+ with the backend dependencies installed from `backend/requirements.txt`.
- Ollama running locally with the configured answer model and `bge-m3` embeddings, or the backend's existing test doubles for automated checks.
- A knowledge base containing at least one source document (see `specs/002-rag-doc-ingestion/quickstart.md` for source management).

## Setup

### Backend

```bash
# From the repository root
python -m venv backend/.venv
source backend/.venv/bin/activate
pip install -r backend/requirements.txt
cp backend/.env.example backend/.env      # adjust model/data settings if needed
python app.py                             # or: python backend/app.py
```

Expected: the Flask service listens on the configured port (default `5000`), and `POST /chat` answers a known question.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env                      # VITE_API_BASE_URL=http://127.0.0.1:5000
npm run dev
```

Expected: the dev server prints a local URL (typically `http://localhost:5173`); opening it shows the empty React workspace, not the legacy `index.html`.

## Automated checks

```bash
# From the repository root
pytest backend/tests

# From frontend/
npm run test
npm run lint
npm run typecheck
npm run build
```

Expected:
- Backend tests pass, including `/chat` and additive `/chat/stream` contract tests; the two pre-existing live-model brittleness failures from 002 may be skipped when Ollama is unavailable.
- Frontend unit/component tests pass.
- Lint and typecheck report no errors.
- Production build completes and emits `frontend/dist/` (ignored by git).

## Validation scenarios

### 1. Send and answer

1. Open the frontend with a known question (e.g., tuition or a categories question).
2. Send it with the button and with `Enter`.

Expected: the user message appears immediately, a waiting/streaming state is visible, and the assistant answer renders without a page reload. If `/chat/stream` is available, text appends progressively; otherwise the full answer appears using `/chat`.

### 2. Markdown and code

1. Ask a question whose answer contains a list, table, or fenced code block (or stub the backend to return sample Markdown).
2. Click the code block's copy button.

Expected: GFM elements render correctly; fenced code is highlighted; copy places the exact code on the clipboard and shows a transient confirmation; inline code is visually distinct. Raw HTML in an answer is shown as text, not executed.

### 3. Streaming fallback

1. Stop the backend or run a stub without `/chat/stream`.
2. Send a question.

Expected: on 404/405/501 the client retries via `/chat`; a complete answer appears. A JSON response is rendered normally. No console error is shown to the user.

### 4. Cancel and interruption

1. Start a long response and press the Stop control.
2. Simulate a stream that closes without `done`.

Expected: cancelling keeps partial text and marks it "stopped"; closing without `done` keeps partial text and offers retry; neither duplicates the user message.

### 5. Error and retry

1. Point the frontend at a stopped backend (or return HTTP 500 from a stub).
2. Send a question.

Expected: a short, non-technical error with a Retry action. Retry re-sends once on demand; no stack trace, prompt, model name, or backend URL is exposed.

### 6. Theme and responsiveness

1. Toggle system/light/dark; reload the page.
2. Resize to phone width and open the sidebar drawer; close with backdrop and `Esc`.

Expected: theme applies consistently and the choice survives reload; the drawer traps focus, closes correctly, and returns focus to the menu trigger; 320px width has no horizontal scrolling; the composer remains reachable with safe-area padding.

### 7. Conversation management

1. Send a first question, start a new chat, send another question.
2. Switch between the two conversations; reload the page.

Expected: each conversation keeps its messages in session; titles derive from the first question; switching shows the correct history; reload starts a fresh empty workspace (no chat history persistence), while the theme preference remains.

### 8. Vietnamese input safety

1. Type with Telex/VNI and press `Enter` to confirm a candidate.
2. Press `Shift+Enter` for a newline, then send.

Expected: confirming a composition does not send a partial message; `Shift+Enter` inserts a newline; the explicit send action sends the complete text.

### 9. Split layout and ignore rules

```bash
# From the repository root
git status --porcelain
git check-ignore -v frontend/node_modules frontend/dist backend/__pycache__ backend/.pytest_cache backend/data backend/.env
git status --porcelain --ignored | grep -E '\.env\.example' || echo "env examples trackable"
```

Expected:
- `frontend/` and `backend/` exist with the documented ownership.
- `python app.py` still serves the same Flask app.
- Generated/build/cache/local-data files are ignored.
- Both `.env.example` files remain trackable (they do not appear as ignored).
- No frontend source imports from `backend/`.

### 10. Accessibility spot check

- Tab through header, sidebar, messages, composer, and code copy; focus is always visible.
- Screen reader announces new/streaming assistant text politely.
- Icons have accessible names; status is not conveyed by color alone.
- With reduced motion enabled, non-essential animation is suppressed.

## Troubleshooting

| Symptom | Check |
|---------|-------|
| Frontend requests fail with CORS | Backend CORS origin and `VITE_API_BASE_URL` match; restart dev server after env changes |
| Answers are empty | Ollama is running and the model names in `backend/.env` match pulled models |
| `/chat/stream` returns 404 | Expected on an older backend; the UI should fall back to `/chat` |
| `pytest` cannot import modules | Run `pytest backend/tests` from the root, or from `backend/`; ensure the venv is active |
| Build artifacts appear in git | Confirm the root `.gitignore` rules from `contracts/repository-layout.md` are present |
