# Implementation Plan: RAG Document Ingestion and Editing

**Branch**: `002-rag-doc-ingestion` | **Date**: 2026-11-04 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-rag-doc-ingestion/spec.md`

## Summary

Add an operator-facing document lifecycle to the existing RAG chatbot: add a source, replace it, delete it, and list sources. Source files stay persisted on disk under `data/`; the FAISS index continues to be derived from those sources and is refreshed automatically when the source set changes. Documents and questions share one Vietnamese normalization pipeline, with optional LLM-based query rewriting used only for the search form. Retrieval becomes configurable in depth, exposes diagnostics (normalized question, sources, scores), and filters every retrieved piece through the relevance threshold before answering. The public `POST /chat` contract remains unchanged, and no new runtime dependency is required.

## Technical Context

**Language/Version**: Python 3.11+ (project virtualenv currently targets Python 3.11; do not rely on the Windows-only `venv/` bundled in the repository)

**Primary Dependencies**: Existing stack only — Flask, flask-cors, langchain, langchain-community, langchain-ollama, langchain-text-splitters, faiss-cpu, rapidfuzz, pandas, pypdf, python-docx, docx2txt; Ollama runs the configured Qwen2.5 answer model and `bge-m3` embeddings. No new package is planned.

**Storage**: Source documents persist as files under `data/` (`.txt`, `.pdf`, `.docx`, `.xlsx`, `.csv`). Add/replace operations are atomic file writes; PDF files are retained as PDFs and their text is extracted for indexing. FAISS remains an in-memory index rebuilt from `data/` at startup and whenever the source fingerprint changes. No database is introduced.

**Testing**: pytest. Existing API/retrieval/refusal tests remain; add unit tests for normalization and file lifecycle, plus Ollama-gated integration tests for noisy questions, source replacement, index refresh, and diagnostics.

**Target Platform**: Single local Linux or Windows machine running Flask and Ollama; optional GPU; offline-capable.

**Project Type**: Single-project web application (`app.py`, `chatbox.py`, `index.html`) plus an operator command-line script under `scripts/`.

**Performance Goals**: A chat response remains within a wait acceptable for conversational use on the target machine; normalization is negligible; query rewriting runs only in configured/auto cases; index rebuild happens only when source files or indexing configuration change.

**Constraints**: Vietnamese-first text handling; local models only; knowledge base is small (a few KB to a few MB); no OCR for scanned PDFs; no management web UI; existing fuzzy Q&A behavior and `POST /chat` response shape must remain compatible.

**Scale/Scope**: One knowledge base, a handful of source files, one operator, roughly 15 evaluation questions; retrieval defaults to 3 pieces, configurable up to 5 when answers are scattered.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md` still contains unratified template placeholders, so no project-specific principles are enforceable yet. The plan is checked against the template's intended principles and the repository's established conventions:

| Gate | Status | Notes |
|------|--------|-------|
| Simplicity / YAGNI | PASS | Reuses Flask, LangChain, FAISS, Ollama, and the existing `data/` loading path. Adds one small file-management module and one CLI, not a new service or database. |
| Library/CLI-first, independently testable | PASS | Source lifecycle lives in `documents.py` and is exercised through `scripts/manage_docs.py`; retrieval normalization is isolated in `text_normalization.py`. |
| Test-first | PASS (adapted) | Normalization and file lifecycle unit tests are defined before changing runtime behavior; Ollama-dependent checks remain gated by environment readiness. |
| Integration testing | PASS | Tests cover add → ask, replace → old content gone, delete → refusal, restart/refresh, and noisy Vietnamese queries. |
| Observability | PASS | Retrieval diagnostics expose the normalized question, rewritten form, selected sources, and scores to the operator. |
| No secrets / local-first | PASS | No cloud services, API keys, or remote persistence are introduced; source data stays on the local disk. |

**Result**: PASS — no violations requiring justification.

**Post-design re-check (after Phase 1)**: PASS — the design keeps the existing Flask/FAISS/Ollama architecture, adds no new dependency or service, isolates lifecycle and normalization logic in testable modules, and leaves the public chat contract unchanged.

## Project Structure

### Documentation (this feature)

```text
specs/002-rag-doc-ingestion/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── chat-api.md
│   ├── document-cli.md
│   └── retrieval-normalization.md
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created here)
```

### Source Code (repository root)

```text
app.py                         # Flask HTTP layer; POST /chat unchanged
chatbox.py                    # Config, loaders, index refresh, normalization wrapper, retrieval, LLM
documents.py                  # Source lifecycle: validate, extract, add, replace, delete, list
text_normalization.py         # Pure Vietnamese normalization helpers
index.html                    # Static chat UI; unchanged
qa.txt                        # Curated Q&A; matching now uses shared normalization
data/                         # Persisted knowledge-base sources
.env.example                  # Documented configuration defaults
README.md                     # Operator instructions for document lifecycle

scripts/
└── manage_docs.py            # CLI: add / replace / delete / list / ask --debug

tests/
├── conftest.py
├── helpers.py
├── test_answers.py            # Existing, Ollama-gated
├── test_chat_api.py           # Existing HTTP contract
├── test_refusal.py            # Existing refusal behavior
├── test_retrieval.py          # Existing retrieval behavior
├── test_normalization.py      # New: NFC, repeats, punctuation, whitespace, empty
├── test_document_management.py # New: add/replace/delete/list, atomicity, PDF extraction
└── test_retrieval_normalization.py # New: normalized indexing/queries, top-k, diagnostics, refresh
```

**Structure Decision**: Keep the existing single-project web layout. Add two focused modules (`text_normalization.py`, `documents.py`) and one operator CLI (`scripts/manage_docs.py`), then integrate them into `chatbox.py`. The web UI and `POST /chat` payload remain untouched; the operator manages documents before or while the server runs.

## Delivery Phases

1. **Normalization and configuration**: add pure normalization helpers; extend configuration with top-k and query-rewrite mode; wrap embeddings so document and query vectors are produced from normalized text.
2. **Document lifecycle**: add atomic source add/replace/delete/list with source-name tracking, PDF text extraction, and empty/unreadable rejection.
3. **Retrieval integration**: add index fingerprint refresh, source metadata, relevant-piece filtering, optional query rewriting, empty-query rephrase response, and diagnostics.
4. **Operator CLI and docs**: expose lifecycle commands and an `ask --debug` path; update README and `.env.example`.
5. **Verification**: add unit tests, keep Ollama-gated integration checks, and validate the quickstart scenarios.

## Complexity Tracking

> No constitution violations. Section intentionally empty.
