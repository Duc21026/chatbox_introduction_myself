# Implementation Plan: Migrate Chatbot to Vietnamese-Capable Models

**Branch**: `001-migrate-vn-models` | **Date**: 2026-11-02 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-migrate-vn-models/spec.md`

## Summary

Replace the English-centric answer model (`tinyllama`) with a Qwen2.5 model selected by available memory, replace the retrieval representation (`nomic-embed-text`) with `bge-m3`, rebuild the in-memory index, make the relevance threshold configurable and recalibrate it, tighten the response prompt for concise Vietnamese answers, and add a repeatable 15-question evaluation harness that produces a before/after comparison table for the project report. Changes are rolled out incrementally: retrieval first, then answer model.

## Technical Context

**Language/Version**: Python 3.11+ (project currently runs on Python 3.x with a Windows venv; verify on target interpreter)

**Primary Dependencies**: Flask, flask-cors, langchain, langchain-community, langchain-ollama, langchain-text-splitters, faiss-cpu, rapidfuzz, pandas, pypdf, python-docx, docx2txt; Ollama as the local model runtime

**Storage**: Profile source files in `data/` (`.txt`, `.xlsx`, plus supported PDF/DOCX/CSV); curated Q&A in `qa.txt`; FAISS index built in memory at application startup (not persisted)

**Testing**: No test suite exists today. Plan adds a lightweight evaluation harness plus pytest-based checks for retrieval, refusal, and the `/chat` contract.

**Target Platform**: Single local developer/user machine running Ollama; Linux or Windows. Optional GPU; memory capacity is the binding constraint.

**Project Type**: Web application — Flask backend (`app.py`, `chatbox.py`) serving a static Tailwind frontend (`index.html`)

**Performance Goals**: Each chat response must complete within a wait the operator judges acceptable for conversational self-introduction on the target machine; small Q&A dataset (a few KB to a few MB)

**Constraints**: Answer-model size must fit available memory (1.5B below 4 GB, 3B around 4 GB, 7B at 8 GB+, 14B at 16 GB+); embedding switch requires full index rebuild; relevance score ranges differ per embedding model; no cloud dependency required

**Scale/Scope**: Single chatbot, one profile knowledge base, roughly 15 evaluation questions, one local operator

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md` still contains unratified template placeholders, so no project-specific principles are enforceable yet. The plan is checked against the template's intended principles and the repository's existing conventions:

| Gate | Status | Notes |
|------|--------|-------|
| Simplicity / YAGNI | PASS | Reuses the existing Flask + LangChain + FAISS architecture; adds only a small evaluation harness and configuration values. |
| Library/CLI-first, independently testable | PASS (adapted) | Core answering stays in `ask_ai`; evaluation is a separate runnable script so it can be tested without the UI. |
| Test-first | PASS (adapted) | No suite exists; evaluation questions and contract tests are defined before behavior changes are validated. |
| Integration testing | PASS | Retrieval quality and refusal behavior are exercised end-to-end through the evaluation set. |
| Observability | PASS | Each evaluation run records configuration and scores in a comparison table. |
| No secrets / no runtime dependency on accidental Qwen3 line | PASS | Uses local Ollama models only; the stray `qwen3:1.7b` command is removed/ignored. |

**Result**: PASS — no violations requiring justification.

## Project Structure

### Documentation (this feature)

```text
specs/001-migrate-vn-models/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── chat-api.md
│   ├── configuration.md
│   └── evaluation.md
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created here)
```

### Source Code (repository root)

```text
app.py                   # Flask HTTP layer, POST /chat
chatbox.py               # Document loading, chunking, embedding, retrieval, LLM, ask_ai
index.html               # Static chat UI (unchanged, minus any response-length assumptions)
qa.txt                   # Curated question-answer pairs
requirements.txt         # Python dependencies; remove stray model command line
data/                    # Profile knowledge base (data.txt, data.xlsx, ...)

evaluation/
├── questions.json       # Fixed ~15-question evaluation set with expected answers/categories
├── run_eval.py          # Runs the question set against the active configuration, writes results
└── results/             # Generated comparison tables (one file per configuration)

tests/
├── test_retrieval.py    # Relevant passage selection and threshold behavior
├── test_refusal.py      # Out-of-scope questions are declined
└── test_chat_api.py     # POST /chat request/response contract
```

**Structure Decision**: Keep the existing single-project web layout. Extend it with `evaluation/` (repeatable quality comparison) and `tests/` (retrieval, refusal, API contract). New runtime configuration is introduced as environment variables read by `chatbox.py`, so model size and threshold can change without editing code.

## Complexity Tracking

> No constitution violations. Section intentionally empty.
