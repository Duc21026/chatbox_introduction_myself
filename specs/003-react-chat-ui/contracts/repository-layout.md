# Contract: Repository Layout, Migration, and Ignore Rules

**Feature**: `003-react-chat-ui`  
**Scope**: Directory ownership, backward-compatible entry points, and root `.gitignore`

## Target layout

```text
/
├── frontend/                 # React UI; owns Node/TypeScript/build artifacts
├── backend/                  # Retained Python service; temporary per spec
├── app.py                    # Compatibility shim -> backend.app
├── README.md                 # Split layout, run commands, temporary-backend note
├── .env.example              # (optional) repo-level pointer; no secrets
└── .gitignore                # Single source of truth for both ecosystems
```

## Ownership

| Path | Owner | Rules |
|------|-------|-------|
| `frontend/` | Frontend | No Python source; no backend imports; configuration via `VITE_*` only |
| `backend/` | Backend | No Node tooling; no frontend build output; existing behavior preserved |
| `app.py` (root) | Backend compatibility | Only imports/exposes `backend.app`; no business logic |
| `README.md` | Repo | Documents split, commands, and the temporary backend |
| `.gitignore` | Repo | One file covering both ecosystems |

## Migration mapping (this feature)

| Before | After |
|--------|-------|
| `app.py` | `backend/app.py` plus root `app.py` shim |
| `chatbox.py` | `backend/chatbox.py` |
| `documents.py` | `backend/documents.py` |
| `text_normalization.py` | `backend/text_normalization.py` |
| `requirements.txt` | `backend/requirements.txt` |
| `qa.txt` | `backend/qa.txt` |
| `data/` | `backend/data/` |
| `scripts/manage_docs.py` | `backend/scripts/manage_docs.py` |
| `evaluation/` | `backend/evaluation/` |
| `tests/` | `backend/tests/` |
| `.env.example` | `backend/.env.example` |
| `index.html` | Removed from backend; replaced by `frontend/index.html` |

Run commands after migration:

```bash
# backend (from repo root)
python app.py                                  # compatibility shim
python backend/app.py                          # direct
pytest backend/tests                           # backend tests
python backend/scripts/manage_docs.py list     # operations CLI

# frontend
cd frontend
npm install
npm run dev
npm run build
npm run test
```

Backward compatibility:
- `python app.py` keeps working for one transition period.
- `pytest backend/tests` replaces root `pytest tests`; the README is updated.
- Historical specs keep their original paths; this document is authoritative for the new layout.

## Temporary backend statement

The root README MUST state:

> The Python backend under `backend/` is retained temporarily while the React frontend is introduced. It keeps the existing RAG/answer behavior and `POST /chat` contract. Replacing it is a separate future feature. The frontend depends only on the HTTP contracts in `specs/003-react-chat-ui/contracts/`.

## Root `.gitignore` requirements

The file MUST include at least the following, organized by section with comments, and MUST NOT ignore required example files.

### Node / frontend

```gitignore
node_modules/
dist/
build/
.vite/
coverage/
*.local
npm-debug.log*
yarn-debug.log*
yarn-error.log*
pnpm-debug.log*
```

### Python / backend

```gitignore
__pycache__/
*.py[cod]
*$py.class
.venv/
venv/
env/
.pytest_cache/
.mypy_cache/
.ruff_cache/
*.egg-info/
.eggs/
```

### Environment and secrets

```gitignore
.env
.env.*
!.env.example
!**/.env.example
```

### Local data and generated archives

```gitignore
data/
backend/data/
*.tmp
*.part
```

### Editor / OS

```gitignore
.vscode/
.idea/
.DS_Store
Thumbs.db
*.swp
```

### Tooling

```gitignore
.specify/
.opencode/
```

### Required exceptions (must remain trackable)

- `frontend/.env.example`
- `backend/.env.example`
- `frontend/package.json`, `frontend/package-lock.json`
- `backend/requirements.txt`

## Acceptance checks

- `git status --porcelain` after a clean install/build shows no `node_modules/`, `dist/`, `__pycache__/`, `.pytest_cache/`, `.env`, `data/`, or cache files.
- `.env.example` files are visible to `git status`/`git check-ignore`.
- Frontend and backend commands in the README work from a clean checkout.
- The root shim imports the same Flask `app` object used by `backend/app.py`.
- No frontend source imports from `backend/`.
