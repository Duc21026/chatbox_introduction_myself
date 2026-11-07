# Data Model: RAG Document Ingestion and Editing

**Feature**: `002-rag-doc-ingestion` | **Date**: 2026-11-04

No database is introduced. Source documents live as files under `data/`; retrieval pieces and the index are derived at runtime. The entities below describe what is persisted, derived, and reported.

## SourceDocument

Represents one operator-managed knowledge-base source. In the file-backed design, `source_name` is the file name relative to `CHATBOT_DATA_DIR` (for example `quydinh.txt`).

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| `source_name` | string | Stable identity used by replace/delete/list | Plain basename, non-empty, allowed extension, no path separators, no traversal |
| `path` | string | Absolute or data-dir-relative file path | Must resolve inside the configured data directory |
| `format` | enum(`txt`, `pdf`, `docx`, `xlsx`, `csv`) | Loader/format family | Supported by the existing loader; PDFs are retained as PDFs |
| `content` | text | Text extracted by the loader for indexing | Non-empty and not whitespace-only |
| `size_bytes` | integer | File size used in the index fingerprint | Non-negative |
| `modified_ns` | integer | File modification time used in the fingerprint | Non-negative |

**Relationships**: one `SourceDocument` produces zero or more `Chunk`s after loading and splitting.

**Rules**:
- `source_name` must be unique in the final state; `add` creates when absent and replaces when present (upsert), while `replace` requires an existing name.
- A PDF source is retained as a PDF; its extracted text must be non-empty. Scanned PDFs with no extractable text are rejected.
- A source must never resolve outside the configured data directory.
- Deleting a source removes all of its derived chunks on the next index refresh.

## Chunk

A retrieval-sized, overlap-aware slice of a `SourceDocument`.

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| `content` | text | Original chunk text (not the normalized form) | Non-empty after source validation |
| `source_name` | reference | Owning `SourceDocument` | Must match a current source |
| `chunk_index` | integer | Position within the source after splitting | Non-negative, deterministic |
| `page` | integer or null | Page number for PDFs where available | Non-negative or null |
| `normalized_content` | text | Search-only normalized form | Produced by the shared normalization function; never displayed as the source of truth |

**Rules**:
- Chunking is deterministic for unchanged source content and unchanged size/overlap settings.
- Chunks keep the source text verbatim for prompts and display.
- Embeddings are computed from `normalized_content`, never directly from `content`.

## RetrievalIndex

The in-memory FAISS structure derived from current sources.

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| `signature` | string/collection | Fingerprint of source paths, sizes, mtimes, embedding model, chunk size, and overlap | Must match the current filesystem/config before reuse |
| `embedding_model` | string | Active embedding model | Must equal the configured value |
| `chunks` | collection | Chunks corresponding to vectors | Same length as vectors |
| `vectors` | collection | One vector per chunk, built from normalized text | Rebuilt from source whenever `signature` changes |

**Rules**:
- Rebuild from current sources when the fingerprint changes; never reuse vectors from a different embedding model or chunking configuration.
- The index is process-local; source files are the durable state.
- A failed rebuild must leave the previous index untouched or fail the request clearly; it must not serve a partially built index.

## NormalizedQuestion

The search-only form of a visitor question.

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| `original` | string | Visitor's unmodified question | Non-empty after trim |
| `normalized` | string | NFC, repeated-character/punctuation, lowercase, whitespace-normalized form | Empty when no letter or digit remains (for example punctuation-only input) |
| `rewritten` | string or null | LLM-corrected spelling/diacritics, when enabled and triggered | Must be non-empty and reasonably sized to be used; otherwise null/fallback |
| `rewrite_applied` | boolean | Whether the search form came from rewriting | Consistent with `rewritten` |

**Rules**:
- `original` is always used for the answer prompt and display.
- `normalized` is used for fuzzy Q&A matching and as the rewrite input.
- `rewritten` (when present) is normalized again before embedding.
- If `normalized` is empty, the system asks the visitor to rephrase and does not search.

## RetrievalDiagnostic

Operator-facing record of one answered (or refused) question.

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| `original_question` | string | Visitor input | Non-empty |
| `normalized_question` | string | Deterministic search form | Matches normalization rules |
| `rewritten_question` | string or null | Rewrite result used for embedding | Null when not applied |
| `source_names` | list of strings | Sources whose pieces were retrieved | Each must be a current source |
| `pieces` | list of objects | `source_name`, `chunk_index`, `score`, `excerpt` | Scores are finite numbers; excerpts are truncated original text |
| `passed_threshold` | boolean | Whether at least one piece was relevant | True only when a non-empty context is used |
| `outcome` | enum(`answered`, `refused`, `rephrase`) | Final behavior | Must match the returned answer |

**Rules**:
- Diagnostics are available through the operator CLI/library only; the public `POST /chat` response remains `{"response": ...}`.
- Diagnostics must not expose secrets or files outside the knowledge base.

## IngestionResult

Outcome of an add, replace, or delete operation.

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| `action` | enum(`add`, `replace`, `delete`) | Operation performed | Required |
| `source_name` | string | Target source | Required |
| `status` | enum(`success`, `failed`) | Operation result | Required |
| `message` | string | Human-readable result | Required; must explain failures |
| `chunks_expected` | integer or null | Estimated pieces after successful add/replace | Non-negative or null |

**State transitions**:

| Current state | Action | Resulting state |
|---------------|--------|-----------------|
| absent | add (valid) | active |
| absent | add (invalid) | absent |
| active | add (valid) | active with new content, old content removed (upsert) |
| active | add (invalid/failed) | active with old content intact |
| active | replace (valid) | active with new content, old content removed |
| active | replace (invalid/failed) | active with old content intact |
| active | delete | absent |
| absent | delete | absent with a clear failure/notice |
| absent | replace | absent with a clear failure |

## RuntimeConfiguration (additions to the existing config)

| Field | Type | Default | Validation | Purpose |
|-------|------|---------|------------|---------|
| `CHATBOT_TOP_K` | integer | `3` | ≥ 1; documented guidance to raise to 5 when answers are scattered | Number of pieces requested from retrieval |
| `CHATBOT_QUERY_REWRITE` | enum(`auto`, `always`, `off`) | `auto` | One of the three values | Controls LLM spelling/diacritic correction for search |
| `CHATBOT_DATA_DIR` | string | `data` | Existing directory | Source location |
| `CHATBOT_EMBEDDING_MODEL` | string | `bge-m3` | Installed Ollama model | Vector representation |
| `CHATBOT_CHUNK_SIZE` | integer | `500` | > 0 | Chunk size |
| `CHATBOT_CHUNK_OVERLAP` | integer | `50` | ≥ 0 and < chunk size | Chunk overlap |
| `CHATBOT_RELEVANCE_THRESHOLD` | number | `1.0` | Numeric; calibrated per embedding model | Maximum score still treated as relevant |

## QAEntry (unchanged shape, new normalization input)

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| `question` | string | Stored question from `qa.txt` | Non-empty; stored lowercased as today |
| `answer` | string | Canonical answer | Non-empty |

**Rules**:
- Stored questions are normalized with the shared function when loaded, so QA keys and incoming questions use the same form; answers remain unchanged.
- Fuzzy matching uses the shared normalized question form instead of only `.lower()`.
- A fuzzy Q&A match short-circuits retrieval and rewriting as it does today.
