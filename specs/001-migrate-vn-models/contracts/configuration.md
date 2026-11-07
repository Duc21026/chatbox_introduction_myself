# Contract: Runtime Configuration

**Feature**: `001-migrate-vn-models` | **Date**: 2026-11-02

Runtime settings are supplied as environment variables so the operator can change model size and tuning without editing source. Documented defaults must be safe on an 8 GB machine.

## Variables

| Variable | Type | Default | Allowed values | Purpose |
|----------|------|---------|----------------|---------|
| `CHATBOT_ANSWER_MODEL` | string | `qwen2.5:7b` | `qwen2.5:1.5b`, `qwen2.5:3b`, `qwen2.5:7b`, `qwen2.5:14b` | Answer (LLM) model |
| `CHATBOT_EMBEDDING_MODEL` | string | `bge-m3` | `bge-m3` | Retrieval embedding model |
| `CHATBOT_RELEVANCE_THRESHOLD` | number | Set after calibration | Any numeric value valid for the embedding score range | Max score still treated as relevant |
| `CHATBOT_FUZZY_CUTOFF` | number | `80` | 0–100 | Minimum fuzzy-match similarity for `qa.txt` answers |
| `CHATBOT_DATA_DIR` | string | `data` | Existing directory | Profile knowledge base location |
| `CHATBOT_QA_PATH` | string | `qa.txt` | Existing file | Curated Q&A location |

## Model size guidance (operator contract)

| Available memory | Answer model |
|------------------|--------------|
| Below 4 GB | `qwen2.5:1.5b` (usable but upgrade or use an external answer service) |
| About 4 GB | `qwen2.5:3b` |
| 8 GB or more | `qwen2.5:7b` (default) |
| 16 GB or more | `qwen2.5:14b` |

A discrete GPU improves speed but does not change the memory-based size rule (VRAM counts as available memory for the runtime).

## Behavior

- Startup MUST validate that configured models are reachable through the local runtime and fail with a clear message if not.
- Startup MUST validate file/directory paths and fail with a clear message if missing.
- Changing the embedding model MUST force a full index rebuild.
- The configuration MUST reject or ignore any Qwen3 model value; Qwen3 is not part of this feature.
- Configuration values used for a run MUST be recorded with evaluation results so comparisons are attributable.
