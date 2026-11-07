# Contract: Document Management CLI

**Feature**: `002-rag-doc-ingestion` | **Date**: 2026-11-04

Operator interface for the source lifecycle. The CLI is the only management surface; no HTTP admin endpoint or web admin UI is added.

## Commands

```text
python scripts/manage_docs.py add <input-path> --name <source-name> [--data-dir <dir>]
python scripts/manage_docs.py replace <input-path> --name <source-name> [--data-dir <dir>]
python scripts/manage_docs.py delete <source-name> [--data-dir <dir>]
python scripts/manage_docs.py list [--data-dir <dir>]
python scripts/manage_docs.py ask "<question>" [--debug] [--data-dir <dir>]
```

`--data-dir` overrides `CHATBOT_DATA_DIR`; when omitted, the configured/default `data` directory is used.

## Source identity and naming

| Rule | Requirement |
|------|-------------|
| Identity | `source-name` is the file name relative to the data directory and is the stable key for replace/delete/list |
| Allowed names | Plain basename with one supported extension: `.txt`, `.pdf`, `.docx`, `.xlsx`, `.csv` |
| Forbidden | Absolute paths, `.`/`..`, path separators, empty names, unsupported extensions, names resolving outside the data directory |
| Extension match | The source-name extension must match the input format (`.txt` for text, `.pdf` for PDF, and so on) |
| Case | Preserved; matching is exact |
| Uniqueness | `add` is an upsert: it creates when absent and safely replaces when present. `replace` requires the source to exist |

If `--name` is omitted for `add`, the input file's base name is used. For `replace`, `--name` is required so the target is explicit.

## Behavior

| Command | Valid input | Result |
|---------|-------------|--------|
| `add` | Readable file, supported format, non-empty extracted text, source name unused | Copies the file into the data directory atomically and reports success |
| `add` | Readable file, supported format, non-empty extracted text, source name already present | Atomically replaces the existing source (upsert); no duplicate is created |
| `add` | Unreadable/empty file, scanned PDF, invalid source name | Fails; knowledge base unchanged |
| `replace` | Existing source, readable new file, supported format, non-empty extracted text | Writes the new file to a temporary path, validates, then atomically replaces the old file |
| `replace` | Missing source, invalid input | Fails; old source remains intact |
| `delete` | Existing source | Removes the source file; its content is no longer retrievable after index refresh |
| `delete` | Missing source | Reports that the source does not exist; no other source is affected |
| `list` | Any | Prints current source names and formats, one per line or as a simple table |
| `ask` | Non-empty question | Answers through the normal retrieval path; with `--debug`, prints the diagnostic record |

### PDF handling

- Text-based PDFs are retained as PDF files; the existing loader extracts their text for indexing.
- A PDF whose extraction yields no usable text is rejected with a message explaining that OCR is not part of this feature.
- PDF text extraction is validated before an add/replace is committed.

### Atomicity and failure

- Validation happens before any destination file is modified.
- The new content is written to a temporary file in the same directory (using a non-source extension so indexing cannot pick it up) and moved into place with an atomic replace; temporary files are cleaned up on success and failure.
- If validation or writing fails, the previous source content must remain unchanged and a failure message must be returned.
- Deletion never partially updates a source; either the file is removed or it remains.

## Output and exit codes

| Outcome | Exit code | Output |
|---------|-----------|--------|
| Success | `0` | Short confirmation including the source name and action |
| Validation/operation failure | `1` | Clear reason on stderr; no fabricated success |
| Usage error (missing arguments/unknown option) | `2` | Usage hint on stderr |

`list` prints source names and formats. `ask --debug` prints the answer followed by the diagnostic fields: original question, normalized question, rewritten form (or `-`), selected sources, per-piece scores, and outcome (`answered`, `refused`, `rephrase`).

Re-adding a source name is an update, not a duplicate. Use `replace` when the source must already exist and a missing source should be treated as an error.

## Invariants

- The CLI never calls the HTTP API; it operates on the same data directory used by the running chatbot.
- The CLI does not create a second metadata store; the filesystem is the source of truth.
- Existing non-text sources remain listable, deletable, and replaceable (using the same format/extension).
- No operation may write outside the configured data directory.
