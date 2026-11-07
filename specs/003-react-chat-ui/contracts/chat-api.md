# Contract: Chat HTTP API

**Feature**: `003-react-chat-ui`  
**Backend**: retained Python Flask service (`backend/app.py`)

## Compatibility rules

- `POST /chat` MUST keep its existing request and response shapes. Existing clients and backend tests must continue to pass.
- `POST /chat/stream` is additive. If it is unavailable, the frontend MUST fall back to `POST /chat`.
- No authentication, cookies, or user identifiers are introduced.
- CORS MUST allow the configured local frontend origin and the documented JSON/SSE content types.

## `POST /chat`

### Request

```http
POST /chat HTTP/1.1
Content-Type: application/json

{ "message": "Học phí ngành CNTT là bao nhiêu?" }
```

- `message` (string, required): the current user question. Leading/trailing whitespace is ignored by the backend's existing normalization.
- The backend does not accept conversation history. The frontend sends only the current question.

### Success response

```http
HTTP/1.1 200 OK
Content-Type: application/json

{ "response": "..." }
```

### Error responses

| Status | Body | Meaning |
|--------|------|---------|
| 400 | `{ "error": "..." }` | Missing/blank `message` or invalid JSON |
| 5xx | `{ "error": "..." }` | Backend/model/retrieval failure |

The frontend maps 400 to a non-retryable input error and 5xx/network failures to a retryable error.

## `POST /chat/stream` (additive)

### Request

Same body as `POST /chat`.

```http
POST /chat/stream HTTP/1.1
Accept: text/event-stream
Content-Type: application/json

{ "message": "..." }
```

### Success response

```http
HTTP/1.1 200 OK
Content-Type: text/event-stream; charset=utf-8
Cache-Control: no-cache
X-Accel-Buffering: no
Connection: keep-alive
```

Body is a sequence of Server-Sent Events. Each event is a single `data:` line containing compact JSON, followed by a blank line.

```text
data: {"type":"chunk","content":"Học phí "}

data: {"type":"chunk","content":"ngành CNTT là ..."}

data: {"type":"done"}

```

Event variants:

| `type` | Fields | Meaning |
|--------|--------|---------|
| `chunk` | `content: string` | Incremental text to append |
| `done` | — | Response completed successfully |
| `error` | `message: string` | Backend failure after the stream started; close after emitting |

Rules:
- Emit `chunk` zero or more times, then exactly one terminal `done` or `error`.
- A QA/cached match MAY be emitted as a single `chunk` followed by `done`.
- The stream MUST close after the terminal event.
- The backend MUST NOT include retrieval diagnostics, prompts, model names, or secrets in stream events exposed to the browser.
- If the request is invalid, respond with the normal JSON `400` before starting the stream.

### Failure and fallback

| Condition | Frontend behavior |
|-----------|-------------------|
| 404 / 405 / 501 | Fall back to `POST /chat` |
| Non-2xx JSON | Surface the error; offer retry |
| `Content-Type` is JSON | Treat the body as a normal `/chat` response |
| Stream ends without `done`/`error` | Mark the assistant message `interrupted`, keep partial content, offer retry |
| User cancels | Abort the fetch, keep partial content, mark `stopped` |

## CORS

- Allowed origin: the frontend dev origin (e.g., `http://localhost:5173`) and any explicitly configured deployed origin.
- Allowed methods: `POST`, `OPTIONS`.
- Allowed headers: `Content-Type`, `Accept`.

## Non-goals

- No WebSocket transport.
- No server-side conversation storage.
- No auth or rate limiting beyond what the retained backend already has.
- No changes to the answer content or RAG behavior.
