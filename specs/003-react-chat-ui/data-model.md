# Data Model: React Chat UI and Frontend/Backend Split

**Feature**: `003-react-chat-ui`  
**Date**: 2026-11-07

This feature has no database. The model describes browser-session state, configuration, and the HTTP payloads exchanged with the retained backend.

## Conversation

Represents one in-session chat thread.

| Field | Type | Notes |
|-------|------|-------|
| `id` | `string` | Client-generated identifier (e.g., crypto UUID); unique within the session |
| `title` | `string` | Derived from the first user message, trimmed to ~40 characters with an ellipsis; default placeholder before the first send |
| `messages` | `Message[]` | Ordered oldest → newest |
| `createdAt` | `number` | Epoch milliseconds, session only |
| `isActive` | `boolean` | Derived/selected view state; exactly one active conversation at a time |

**Relationships**: A conversation owns many messages. Conversations are independent; there is no cross-conversation context or server persistence.

**Validation rules**
- `id` must be non-empty and unique in the store.
- `title` is never empty; use a localized placeholder until the first user message exists.
- A conversation with no messages may exist only as the fresh/empty workspace.

**Lifecycle**
- Created when the workspace is empty and the user sends the first message, or when the user selects "New chat".
- Updated while a response streams.
- Removed on page reload (session-only), by design.
- Selecting another conversation deactivates the previous one without deleting it.

## Message

Represents one user or assistant turn.

| Field | Type | Notes |
|-------|------|-------|
| `id` | `string` | Client-generated identifier |
| `role` | `"user" \| "assistant"` | Message author |
| `content` | `string` | Plain text for user messages; Markdown for assistant messages |
| `status` | `"complete" \| "streaming" \| "stopped" \| "interrupted" \| "error"` | Drives the visual state |
| `error` | `string \| null` | Short user-facing error when `status === "error"` |
| `createdAt` | `number` | Epoch milliseconds, session only |

**Validation rules**
- User messages are non-empty after trimming; whitespace-only sends are rejected.
- Assistant content may be empty only while `status === "streaming"` (show a typing indicator).
- `error` is required when `status === "error"` and `null` otherwise.
- `stopped` retains the partial content that was received before the user cancelled.
- `interrupted` retains partial content and offers retry (stream ended without a completion signal).

**State transitions**

```text
assistant: (created) streaming ──done──> complete
                              ├─cancel──> stopped
                              ├─stream end without done──> interrupted
                              └─failure──> error ──retry──> streaming
```

**Rendering rules**
- User content is rendered as plain text (no Markdown execution).
- Assistant content is rendered as sanitized Markdown (raw HTML disabled), with GFM and highlighted fenced code.
- Empty assistant `streaming` state shows an animated indicator; `error` shows a retry action; `stopped` shows a subtle "stopped" label.

## ThemePreference

| Field | Type | Notes |
|-------|------|-------|
| `mode` | `"system" \| "light" \| "dark"` | Default `"system"` |
| `resolved` | `"light" \| "dark"` | Derived from `mode` and `prefers-color-scheme`; not stored |

**Validation rules**
- Persist only `mode` in `localStorage` under a versioned key (e.g., `chatbot.theme.v1`).
- Invalid/missing stored values fall back to `"system"`.
- The resolved theme is applied via a root attribute (e.g., `data-theme`).

## RuntimeConfig

| Field | Type | Notes |
|-------|------|-------|
| `apiBaseUrl` | `string` | From `VITE_API_BASE_URL`; default `http://127.0.0.1:5000`; trailing slash normalized |

**Validation rules**
- Must be a valid absolute URL.
- No secrets or credentials are included.
- Missing value uses the default and logs a development warning.

## SessionState (store shape)

| Field | Type | Notes |
|-------|------|-------|
| `conversations` | `Record<string, Conversation>` | Session-only |
| `activeConversationId` | `string \| null` | `null` for the empty workspace |
| `sidebarOpen` | `boolean` | Desktop collapse / mobile drawer state |
| `isStreaming` | `boolean` | True while any response is in flight |
| `themeMode` | `ThemePreference["mode"]` | Persisted |

**Invariants**
- At most one message per conversation is `streaming`.
- Sending is disabled while `isStreaming` is true.
- Selecting another conversation is disabled while streaming, or the active stream is completed/stopped first (choose the latter in implementation and document it in the UI).
- Reloading resets `conversations`, `activeConversationId`, and `isStreaming`; `themeMode` survives.

## HTTP Payloads

### Request (`POST /chat`, `POST /chat/stream`)

```json
{ "message": "Câu hỏi của người dùng" }
```

- `message` is required, a string, non-empty after trimming.
- The client sends only the current question; it does not send prior turns because the retained backend accepts a single `message`.

### Response (`POST /chat`, unchanged)

```json
{ "response": "Câu trả lời" }
```

- Success: HTTP 200 with a JSON object containing `response`.
- Validation error: HTTP 400 with a JSON error.
- Backend failure: HTTP 5xx; the client shows a retryable error.

### Stream events (`POST /chat/stream`, additive)

`Content-Type: text/event-stream`

```text
data: {"type":"chunk","content":"..."}

data: {"type":"chunk","content":"..."}

data: {"type":"done"}

```

- Error event: `data: {"type":"error","message":"..."}` followed by stream close.
- The client treats a stream that ends without `done` as `interrupted`.

## Source Document (backend, unchanged)

The retained backend's source lifecycle is unchanged by this feature. Existing `documents.py` records remain the backend's concern; the frontend never reads or writes them. See `specs/002-rag-doc-ingestion/data-model.md` for the authoritative source-document model.
