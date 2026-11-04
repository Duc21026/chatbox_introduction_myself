# Contract: Chat HTTP API

**Feature**: `002-rag-doc-ingestion` | **Date**: 2026-11-04

The existing public chat interface must remain backward compatible. The static frontend calls it without change.

## Endpoint

`POST /chat`

**Request headers**

| Header | Required | Value |
|--------|----------|-------|
| `Content-Type` | Yes | `application/json` |

**Request body**

```json
{
  "message": "cho   tôi hỏi GPA hiện tại?"
}
```

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `message` | string | Yes | Non-empty after trimming; may contain noisy Vietnamese text |

**Success response** — `200 OK`

```json
{
  "response": "GPA hiện tại là 8.30"
}
```

| Field | Type | Guarantees |
|-------|------|------------|
| `response` | string | Natural Vietnamese; contains only facts supported by current sources or curated Q&A; explicit refusal for unsupported questions |

**Error behavior**

| Condition | Expected behavior |
|-----------|-------------------|
| Missing/invalid JSON | `400` with an `error` field; no fabricated answer |
| Missing `message` field | `400` with an `error` field |
| Empty/whitespace-only `message` | `400` with an `error` field |
| Message normalizes to nothing searchable (for example punctuation only) | `200` with a rephrase request in `response` |
| Index cannot be built / model unavailable | `500` with a clear `error` field; no fabricated answer |

## Response invariants

- Exactly one `response` string per successful call; the diagnostic record is not exposed here.
- The visitor's original wording is used for the answer prompt and display.
- Out-of-scope questions return the refusal (`Tôi không biết`) and add no invented facts.
- The response must not come from a deleted or replaced source after the index refresh.
- The endpoint must not depend on any Qwen3 model.

## CORS

- Cross-origin access remains enabled for the local frontend (`flask-cors`), preserving current behavior.

## Compatibility

- The request field name (`message`) and response field name (`response`) do not change.
- Existing error codes for malformed/empty requests remain `400`.
- Existing fuzzy Q&A behavior remains available and is evaluated before document retrieval.
