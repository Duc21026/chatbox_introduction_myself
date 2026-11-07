# Contract: Frontend API Client

**Feature**: `003-react-chat-ui`  
**Module**: `frontend/src/lib/chatClient.ts`

The client is the only place that knows the backend URL and transport details. UI components consume a small, testable interface.

## Configuration

| Setting | Source | Default | Rules |
|---------|--------|---------|-------|
| `apiBaseUrl` | `import.meta.env.VITE_API_BASE_URL` | `http://127.0.0.1:5000` | Absolute URL; trailing slash removed; no credentials or secrets |

`frontend/.env.example`:

```dotenv
VITE_API_BASE_URL=http://127.0.0.1:5000
```

## Interface

```ts
type StreamEvent =
  | { type: "chunk"; content: string }
  | { type: "done" }
  | { type: "error"; message: string };

interface SendOptions {
  signal?: AbortSignal;
  onChunk?: (text: string) => void;
}

interface SendResult {
  mode: "stream" | "complete";
  content: string;
}

function sendMessage(message: string, options?: SendOptions): Promise<SendResult>;
```

Implementations MAY split this into smaller functions, but the observable behavior and error taxonomy below are required.

## Behavior

1. **Validate** the message client-side: trim; reject empty/whitespace-only input before any network call.
2. **Attempt streaming**: `POST {apiBaseUrl}/chat/stream` with `Accept: text/event-stream` and JSON body `{ "message": message }`.
3. **Classify the response**:
   - `404`, `405`, `501` → fall back to `POST /chat`.
   - `2xx` with `Content-Type: text/event-stream` → consume the stream.
   - `2xx` with `Content-Type: application/json` → parse `{ response }` and return `{ mode: "complete", content }`.
   - Other statuses → throw a typed `ChatApiError` with a retryability flag and a user-safe message.
4. **Consume SSE** incrementally:
   - Buffer partial lines across chunks.
   - Parse lines beginning with `data:`; ignore comments/other fields.
   - Append `chunk.content` and call `onChunk` as text arrives.
   - Stop on `done`; throw/return a typed interruption on `error`.
   - If the body ends without a terminal event, return partial content flagged as interrupted.
5. **Abort**: when `options.signal` aborts, stop reading, keep partial content, and return/throw an `AbortError` the store maps to `stopped`. Never show an abort as a generic error.
6. **Fallback call**: `POST {apiBaseUrl}/chat`; on success return `{ mode: "complete", content: response }`; map failures the same way.

## Error taxonomy

| Code | Trigger | Retryable | UI treatment |
|------|---------|-----------|--------------|
| `invalid-input` | Empty message | No | Keep focus in composer; no message bubble |
| `network` | Fetch rejects (non-abort) | Yes | Inline error + Retry |
| `server` | 5xx | Yes | Inline error + Retry |
| `client` | 4xx other than fallback codes | No | Inline error with safe message |
| `interrupted` | Stream closed without terminal event | Yes | Keep partial content; Retry |
| `aborted` | User cancel | — | Keep partial content; status `stopped` |

Error messages shown to users MUST be short, non-technical, and MUST NOT include stack traces, prompts, backend URLs, or model details.

## Constraints

- Do not send conversation history; the retained backend accepts one `message`.
- Do not log message content or responses in production builds.
- Do not retry automatically; retries are explicit user actions.
- Use `fetch` and `ReadableStream`; no SSE library is required.
- The client MUST be usable in jsdom tests with a mocked `fetch`/stream.

## Test expectations

- Streams chunks in order and concatenates exactly.
- Handles chunks split mid-line and multiple events per network chunk.
- Falls back on 404 and on JSON responses.
- Maps abort to `aborted` without calling error UI.
- Treats missing terminal event as `interrupted`.
- Rejects blank input without a network call.
- Never includes the backend base URL or secrets in user-visible errors.
