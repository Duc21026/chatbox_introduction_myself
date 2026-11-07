# Contract: Retrieval and Text Normalization

**Feature**: `002-rag-doc-ingestion` | **Date**: 2026-11-04

Defines the shared text form used for indexing and searching, how query rewriting is triggered, and how retrieval results are filtered and reported.

## Normalization pipeline

The same function is applied to document chunks before embedding and to visitor questions before search.

| Order | Step | Rule |
|-------|------|------|
| 1 | Unicode normalization | `NFC` so composed and decomposed Vietnamese diacritics compare equally |
| 2 | Repeated-character collapse | Runs of **3 or more** identical characters become one character; legitimate doubles (for example `xoong`) are preserved |
| 3 | Lowercase | Applied only to the search form |
| 4 | Repeated punctuation collapse | Runs of `!`, `?`, `.`, `,` become one character |
| 5 | Whitespace collapse | All whitespace runs become a single space; trim leading/trailing spaces |
| 6 | Empty check | If no letter or digit remains (for example punctuation-only input), normalize to an empty search form and return a rephrase request instead of searching |

### Invariants

- The original document text and original question are never overwritten by the normalized form.
- The normalized form is search-only: it is used for QA fuzzy matching, query rewriting input, and embeddings.
- The original question is used for the answer prompt and display, preserving capitalization, names, abbreviations, and numbers.
- A document chunk's stored text remains the original chunk text; only its embedding input is normalized.

## Embedding wrapper

- All document embeddings and query embeddings pass through the shared normalization function before reaching the embedding model.
- If the embedding model or chunking configuration changes, the index is rebuilt from source; old vectors are never reused.
- Documents and queries therefore share one representation, preventing clean-document/noisy-query mismatch.

## Query rewriting

| Mode (`CHATBOT_QUERY_REWRITE`) | Behavior |
|--------------------------------|----------|
| `auto` (default) | Rewrite only when the normalized question has no Vietnamese diacritics, or when the raw input contained repeated-character/punctuation noise |
| `always` | Rewrite every question before retrieval |
| `off` | Never rewrite; use only deterministic normalization |

### Rewrite rules

- The correction prompt fixes spelling and adds missing Vietnamese diacritics and must preserve proper names, abbreviations, and numbers.
- The model returns only the corrected sentence, with no explanation.
- The rewritten text is normalized again before it is embedded.
- Fall back to the deterministically normalized question when rewriting fails, returns empty, or is unreasonably longer than the input.
- Rewriting never replaces the original question in the answer prompt or UI.

## Retrieval

| Setting | Default | Rule |
|---------|---------|------|
| `CHATBOT_TOP_K` | `3` | Number of pieces requested; documented guidance to use `5` when answers are scattered |
| `CHATBOT_RELEVANCE_THRESHOLD` | `1.0` | Maximum score still treated as relevant for the active embedding model |

### Behavior

1. Fuzzy-match the normalized question against `qa.txt`; a match returns the curated answer and skips retrieval.
2. Otherwise retrieve up to `CHATBOT_TOP_K` pieces using the search form.
3. Discard every piece whose score exceeds the relevance threshold.
4. If no pieces remain, return the refusal (`Tôi không biết`).
5. Otherwise build the answer context from the remaining pieces' original text and call the answer model.
6. The answer prompt must contain only the retrieved content and must refuse when that content does not support an answer.

## Index refresh

- Compute a fingerprint over supported source files (relative path, modification time, size) plus the embedding model, chunk size, and chunk overlap.
- Reuse the current in-memory index when the fingerprint matches.
- Rebuild from current sources when the fingerprint changes, including after CLI add/replace/delete.
- A source's metadata must carry a normalized `source` value so diagnostics can name the origin.

## Diagnostics

The operator path (`ask --debug` or the library function) returns:

| Field | Meaning |
|-------|---------|
| `original_question` | Visitor input as typed |
| `normalized_question` | Deterministic search form |
| `rewritten_question` | Rewrite used for embedding, or null |
| `pieces` | Selected source name, chunk index, score, and a short excerpt |
| `passed_threshold` | Whether at least one piece survived filtering |
| `outcome` | `answered`, `refused`, or `rephrase` |

Diagnostics are never added to the public `POST /chat` response.
