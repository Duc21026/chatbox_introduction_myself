# Data Model: Migrate Chatbot to Vietnamese-Capable Models

**Feature**: `001-migrate-vn-models` | **Date**: 2026-11-02

This feature does not introduce a persistent database. It changes runtime configuration, the retrieval representation, and adds evaluation artifacts. Entities below describe the data the system loads, derives, and reports.

## ProfileDocument

Represents one source file in the profile knowledge base.

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| `path` | string | Location under `data/` | Must exist and be readable |
| `format` | enum(`txt`, `pdf`, `docx`, `xlsx`, `csv`) | Loader selection | Unsupported formats are skipped |
| `content` | text | Extracted text | Empty documents are skipped |
| `source` | string | Provenance for retrieved chunks | Non-empty |

**Relationships**: one `ProfileDocument` produces many `Chunk`s.

**Rules**:
- A file that cannot be parsed must not abort loading of the remaining files.
- `data.xlsx`/`data.csv` rows are flattened into one text record per row using `column: value` pairs.

## Chunk

A retrieval-sized slice of a `ProfileDocument`.

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| `content` | text | Chunk text | Non-empty |
| `source_document` | reference | Owning `ProfileDocument` | Must resolve |
| `chunk_size` | integer | Maximum characters per chunk | Fixed strategy value (current 500) |
| `chunk_overlap` | integer | Overlap between chunks | Fixed strategy value (current 50) |

**Rules**:
- Chunking strategy must be deterministic so evaluation is repeatable.

## QAEntry

A curated question-answer pair from `qa.txt`.

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| `question` | string | Stored question | Non-empty, lowercased for matching |
| `answer` | string | Canonical answer | Non-empty |
| `match_score` | number | Similarity when matched at runtime | Must exceed the fuzzy-match cutoff to be returned |

**Rules**:
- Lines without a `|` separator are ignored.
- Exact/fuzzy matching behavior is preserved from the current implementation.

## RetrievalIndex

The in-memory search structure over all `Chunk`s.

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| `embedding_model` | string | Active embedding model | Must match the configured value |
| `vectors` | collection | One vector per `Chunk` | Rebuilt in full at startup |
| `chunks` | collection | Chunks corresponding to `vectors` | Same length as `vectors` |

**Rules**:
- When `embedding_model` changes, the index must be rebuilt from source; old vectors must never be reused.
- Index is process-local and not persisted.

## ModelConfiguration

Runtime settings that select models and tuning values.

| Field | Type | Default | Validation |
|-------|------|---------|------------|
| `answer_model` | string | `qwen2.5:7b` | Must be a Qwen2.5 size supported by the machine |
| `embedding_model` | string | `bge-m3` | Must be a supported embedding model |
| `relevance_threshold` | number | Set after calibration | Must separate in-domain from out-of-scope questions on the evaluation set |
| `fuzzy_match_cutoff` | number | Current value (80) | Range 0–100 |
| `qa_path` | string | `qa.txt` | Must exist |
| `data_dir` | string | `data` | Must exist |

**Rules**:
- Invalid or missing values fail fast with a clear message rather than silently using an incompatible model.
- The accidental Qwen3 model must never appear as a default or fallback.

## EvaluationQuestion

One entry in the fixed evaluation set.

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| `id` | string | Stable identifier | Unique |
| `question` | string | Vietnamese question text | Non-empty |
| `category` | enum(`direct`, `paraphrase`, `no_diacritics`, `pronoun_variant`, `out_of_scope`) | Coverage bucket | All buckets represented |
| `expected_answer` | string or null | Expected fact(s), or null for out-of-scope | Present for non-out-of-scope |
| `expected_refusal` | boolean | Whether the correct behavior is refusal | `true` for out-of-scope |

**Rules**:
- About 15 questions total; at least one per category, with several direct-fact questions (GPA, a subject score, university, goal).
- The set is fixed across all three evaluation milestones.

## EvaluationResult

Per-question outcome for one configuration.

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| `question_id` | reference | Links to `EvaluationQuestion` | Must resolve |
| `configuration` | string | Milestone label (original / embedding-changed / answer-model-changed) | Non-empty |
| `answer` | text | Chatbot response | Recorded verbatim |
| `factual_correct` | boolean | Figures/names match expected | Required for non-out-of-scope |
| `refusal_correct` | boolean | Out-of-scope properly declined | Required for out-of-scope |
| `natural_vietnamese` | boolean | Reads smoothly and correctly | Required |
| `latency_seconds` | number | Response time | Non-negative |
| `notes` | string | Operator observations | Optional |

## ComparisonReport

Aggregated before/after view for the project report.

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| `milestones` | list | Ordered configurations compared | At least the three planned milestones |
| `factual_accuracy` | number | Share of correct in-domain answers per milestone | 0–1 |
| `refusal_rate` | number | Share of correct refusals per milestone | 0–1 |
| `naturalness_rate` | number | Share judged natural per milestone | 0–1 |
| `average_latency` | number | Mean response time per milestone | Non-negative |
| `selected_configuration` | string | Configuration retained after comparison | Must be one of the milestones |

**State transitions**: original → embedding changed → answer model changed → selected configuration retained.
