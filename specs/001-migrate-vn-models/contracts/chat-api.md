# Contract: Chat HTTP API

**Feature**: `001-migrate-vn-models` | **Date**: 2026-11-02

The existing public interface must remain backward compatible: the static frontend calls it without change.

## Endpoint

`POST /chat`

**Request headers**

| Header | Required | Value |
|--------|----------|-------|
| `Content-Type` | Yes | `application/json` |

**Request body**

```json
{
  "message": "GPA hiện tại của bạn là bao nhiêu?"
}
```

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `message` | string | Yes | Non-empty question text |

**Success response** — `200 OK`

```json
{
  "response": "GPA hiện tại là 8.30"
}
```

| Field | Type | Guarantees |
|-------|------|------------|
| `response` | string | Natural Vietnamese; contains only facts supported by the profile data or the curated Q&A; for out-of-scope questions it is an explicit "I don't know" style refusal |

**Error behavior**

| Condition | Expected behavior |
|-----------|-------------------|
| Missing/invalid JSON | Do not return a fabricated answer; return a client error |
| Missing `message` field | Return a client error |
| Empty `message` | Return a client error |
| Model unavailable / cannot load | Return a clear server error; do not return a fabricated answer |

**Invariants**

- Exactly one `response` string per successful call.
- Response must not include data absent from the profile knowledge base or curated Q&A.
- Response must stay concise (short self-introduction answers).
- The endpoint must not depend on any Qwen3 model.

## CORS

- Cross-origin access remains enabled for the local frontend (`flask-cors`), preserving current behavior.
