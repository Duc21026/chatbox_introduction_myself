# Research: RAG Document Ingestion and Editing

**Feature**: `002-rag-doc-ingestion` | **Date**: 2026-11-04

All unknowns from the Technical Context have been resolved. No `NEEDS CLARIFICATION` markers remain.

## R1. Persistence model: source files plus rebuildable index

- **Decision**: Persist each source document as a file under `data/` and continue building the FAISS index from those files. Supported source formats remain `.txt`, `.pdf`, `.docx`, `.xlsx`, and `.csv`; a source's file name is its identity. Add/replace write the file atomically and validate that the loader can extract non-empty text before committing. No vector database is added.
- **Rationale**: The repository already treats `data/` as the knowledge base and deliberately rebuilds FAISS from source on startup (see README and the prior migration plan). Keeping source text on disk means add/update/delete survive a restart without migrating to ChromaDB or persisting vectors. The knowledge base is small, so rebuild cost is negligible, and stale vectors cannot survive because every rebuild starts from current sources.
- **Alternatives considered**:
  - ChromaDB persistent client — directly matches the user's reference workflow but adds a new dependency, a second storage model, and a migration from FAISS without improving correctness for a few-KB corpus. Rejected for this scope.
  - Persist the FAISS index with `save_local`/`load_local` — still needs source files for editing/deletion, and saved vectors become stale or incompatible when the embedding model or chunking changes. Rejected.
  - Keep everything in memory and require re-adding documents each run — fails persistence. Rejected.

## R2. Vietnamese normalization pipeline

- **Decision**: Implement one pure normalization function used for both indexing and search: Unicode NFC → collapse runs of 3+ identical characters to one (preserving legitimate doubles such as `xoong`) → lowercase → collapse repeated sentence punctuation (`! ? . ,`) → collapse whitespace, and trim; treat a form with no remaining letter or digit (for example punctuation-only input) as unsearchable. Keep the original text untouched for storage, prompts, and display.
- **Rationale**: The mismatch between clean document text and noisy chat input is the main avoidable retrieval failure. NFC makes composed/decomposed diacritics comparable; collapsing 3+ repeats fixes `choooo` without damaging Vietnamese doubles; lowercasing and whitespace collapse align both sides. Applying the function in one place makes it impossible for ingestion and query paths to drift.
- **Alternatives considered**:
  - Lowercase only (current behavior) — does not handle repeated characters, decomposed diacritics, or punctuation noise. Rejected.
  - Aggressive removal of all diacritics — destroys Vietnamese meaning and proper names. Rejected.
  - Collapse every repeated character to one — breaks legitimate `xoong`, `boong`, and similar words. Rejected.
  - Normalize and store only the normalized form — loses capitalization and names needed for answers and display. Rejected.

## R3. Query rewriting trigger and safety

- **Decision**: Add a configurable `CHATBOT_QUERY_REWRITE` mode (`auto` default, `always`, `off`). In `auto`, invoke the configured chat model to fix spelling/add diacritics only when the normalized question has no Vietnamese diacritics, or when the raw input contained repeated-character/punctuation noise. The rewrite prompt must preserve proper names, abbreviations, and numbers and return only the corrected sentence. If rewriting fails, returns empty, or grows unreasonably long, fall back to the deterministically normalized question. The original question remains the prompt/display text.
- **Rationale**: Query rewriting helps diacritic-free and typo-heavy input, but running an extra LLM call on every message adds latency and can change names. Auto-triggering keeps the common clean-question path fast while still covering the noisy cases the spec emphasizes. A fallback prevents a rewrite failure from blocking the answer.
- **Alternatives considered**:
  - Rewrite every query — highest coverage but doubles model calls and risks silently changing names. Rejected as the default.
  - Never rewrite — fails the missing-diacritics/typo requirement. Rejected.
  - Use a separate dedicated rewrite model — another model to install and manage for a small corpus; not justified. Rejected.

## R4. Source lifecycle and atomic writes

- **Decision**: Treat the source name as the stable identity used for replacement and deletion; in the file-backed design it is the file name relative to `data/`. `add` is an upsert: it creates a new source when the name is absent and safely replaces the existing source when the name is present. `replace` is update-only and fails when the source is absent. Both write a temporary file in `data/` before atomically replacing the destination; `delete` removes the file; `list` reports current sources. Validate that names are plain basenames with an allowed extension and reject path traversal.
- **Rationale**: Whole-source replacement avoids the trap described in the feature input: after content changes, chunk boundaries and IDs no longer correspond, so patching individual chunks is unsafe. An atomic replace means a failed write leaves the previous version intact. Using the file name as identity keeps the existing loader and provenance model unchanged.
- **Alternatives considered**:
  - Chunk-level edit/update — requires stable chunk IDs across content changes and cannot guarantee no stale pieces. Rejected.
  - Reject duplicate `add` and require a separate replace only — contradicts the requirement that re-adding an existing source is an update, and adds an avoidable operator error. Rejected.
  - Separate metadata manifest — adds a second source of truth that can drift from `data/`. Rejected.
  - Write directly to the destination file — a partial write or crash can destroy the previous version. Rejected.
  - Allow arbitrary nested source names — increases traversal and collision risk with no user value. Rejected.

## R5. Structure-aware chunking

- **Decision**: Keep `RecursiveCharacterTextSplitter` and the existing configurable size/overlap defaults (`CHATBOT_CHUNK_SIZE=500`, `CHATBOT_CHUNK_OVERLAP=50`, i.e. 10% overlap, within the spec's 500–1000 / 10–20% range). Configure separators in priority order: blank line/paragraph, newline, Vietnamese sentence-ending punctuation, other sentence punctuation, space, character. Preserve source metadata on every chunk.
- **Rationale**: Recursive splitting already avoids cutting mid-word when possible; adding paragraph/newline/sentence separators makes numbered clauses and headings more likely to stay intact. Keeping existing defaults avoids an unrelated retrieval regression and remains configurable for larger documents.
- **Alternatives considered**:
  - Fixed-length character windows — cuts through sentences and clauses. Rejected.
  - Separate heading-aware parser per document format — high complexity for a small mixed-format corpus; not justified now. Rejected.
  - Change defaults to 800/150 — within the spec but not required, and would alter current evaluation behavior. Deferred; operators can set it through existing variables.

## R6. Index freshness and source provenance

- **Decision**: Compute a lightweight fingerprint over the supported files in `data/` (relative path, modification time, size) plus the embedding model and chunking configuration. Rebuild the in-memory FAISS index when the fingerprint differs from the indexed one; otherwise reuse it. Attach a normalized `source` metadata value to every loaded document and chunk.
- **Rationale**: A running Flask process would otherwise serve the old index after an operator edits a file. Fingerprint checking makes add/replace/delete visible on the next question without requiring a restart or a new HTTP admin endpoint. Metadata makes diagnostics and source filtering possible.
- **Alternatives considered**:
  - Require a server restart after every change — simple but violates the expected "after the operation completes" behavior and adds operator friction. Rejected.
  - Add a reload HTTP endpoint — exposes an unnecessary management surface and needs authentication or local-only assumptions. Rejected.
  - Watch filesystem events — extra dependency and platform differences for a tiny corpus. Rejected.
  - Rebuild on every query — correct but wasteful; fingerprinting avoids needless work. Rejected.

## R7. PDF import behavior

- **Decision**: Accept text-based PDFs, persist the PDF file itself, and rely on the existing `PyPDFLoader` to extract its text during indexing. Validate extraction before committing an add/replace; reject PDFs that yield no usable text with a clear message. Do not OCR scanned PDFs.
- **Rationale**: Persisting the original PDF keeps source identity and replacement simple and avoids a second representation on disk. The loader already handles PDF text extraction, and empty extraction is the reliable signal for scanned/image-only PDFs. `pypdf` is already a dependency.
- **Alternatives considered**:
  - Convert the PDF to a `.txt` source at import — changes the source name/format and makes replacing the original PDF ambiguous. Rejected.
  - Add OCR — new system dependencies and scope beyond this feature. Rejected.
  - Silently add an empty document — produces misleading sources and no answers. Rejected.

## R8. Retrieval depth, threshold filtering, and diagnostics

- **Decision**: Add `CHATBOT_TOP_K` (default 3, with a documented increase to 5 when information is scattered). Retrieve up to top-k pieces, discard every piece whose score exceeds the existing relevance threshold, and decline if none remain. Add a diagnostics path that reports the original question, deterministically normalized question, rewritten form (if any), selected sources, per-piece scores, and whether the threshold was passed.
- **Rationale**: Returning all retrieved pieces even when only the best one is relevant can mislead the answer model. Filtering per piece keeps context clean. Top-k configurability matches the spec's guidance for scattered answers. Diagnostics are required to distinguish missing content from bad normalization or retrieval.
- **Alternatives considered**:
  - Keep hardcoded `k=2` — fails the scattered-information guidance and is untestable as a setting. Rejected.
  - Check only the best score but pass all pieces — can include unrelated context. Rejected.
  - Always return diagnostics in the HTTP response — breaks the existing `{"response": ...}` contract. Rejected; diagnostics stay in the operator CLI/library path.

## R9. Configuration and testing strategy

- **Decision**: Extend the existing environment-based `Config` with `CHATBOT_TOP_K` and `CHATBOT_QUERY_REWRITE`; keep existing variables and defaults. Add pytest unit tests for normalization and document lifecycle, plus Ollama-gated integration tests for noisy-query retrieval, replace/delete behavior, index refresh, and diagnostics. Update `.env.example` and README.
- **Rationale**: Environment variables already control the chatbot and avoid new configuration files. Unit tests can run without Ollama by faking embeddings/LLM; integration tests skip when models are unavailable, matching the existing suite's pattern.
- **Alternatives considered**:
  - Add a YAML/TOML configuration file — new format and loader for two values. Rejected.
  - Replace environment variables with a service/UI — out of scope per spec assumptions. Rejected.
  - Only manual testing — misses normalization and atomicity regressions. Rejected.
