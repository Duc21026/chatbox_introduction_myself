# Feature Specification: React Chat UI and Frontend/Backend Split

**Feature Branch**: `003-react-chat-ui`

**Created**: 2026-11-07

**Status**: Draft

**Input**: User description: "chỉnh lên và phân chia frontend và backend viết lại git ignore, backend giữ lại tạm thời, sử dụng chuyển qua chuyển UI python sang react" plus a reference design for a Claude-inspired chat interface.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Use a Separated Frontend Against the Existing Backend (Priority: P1)

A visitor opens the new chat interface and exchanges messages with the existing chatbot. The interface is a standalone browser application that communicates with the retained backend service over its documented HTTP contract. The backend continues to provide answers as it does today; only the presentation layer is replaced.

**Why this priority**: Separating the interface from the answering service is the foundation for every other capability. Without a working frontend-to-backend connection there is no usable product, and the backend must remain available until the replacement path is proven.

**Independent Test**: Start the backend, start the new frontend, send one question from the browser, and confirm the answer appears without reloading the page and without modifying backend answer logic.

**Acceptance Scenarios**:

1. **Given** the backend is running and the frontend is launched separately, **When** the visitor submits a question, **Then** the answer returned by the backend is displayed in the conversation.
2. **Given** the frontend is served from a different origin than the backend, **When** the visitor sends a message, **Then** the request succeeds without manual browser configuration.
3. **Given** the backend is unavailable or returns an error, **When** the visitor sends a message, **Then** the interface shows a clear error with a retry action and does not fabricate an answer.
4. **Given** the existing backend API contract has not changed, **When** the frontend is integrated, **Then** existing backend consumers and automated contract checks still work.

---

### User Story 2 - Read Answers While They Are Being Produced (Priority: P1)

A visitor sends a question and sees the answer appear progressively rather than waiting for the entire response. Answers that contain headings, lists, tables, links, inline code, or fenced code stay readable, and code blocks can be copied with one action.

**Why this priority**: Perceived responsiveness and readable rich content are the core value of the new interface. A migration that only reproduces a single text blob does not deliver the requested experience.

**Independent Test**: Send a question whose answer contains paragraphs and a code block; confirm text appears incrementally, Markdown is rendered, and the copy action copies exactly the code.

**Acceptance Scenarios**:

1. **Given** an answer is being generated, **When** the first content arrives, **Then** it appears in the conversation and subsequent content appends without replacing earlier text.
2. **Given** the backend supports incremental delivery, **When** the answer streams, **Then** the visitor can stop generation and keep the partial answer visible.
3. **Given** the backend returns the whole answer at once, **When** the response arrives, **Then** the interface displays it correctly as a complete answer.
4. **Given** an answer contains Markdown, **When** it is displayed, **Then** paragraphs, headings, lists, tables, links, and inline code render as formatted content.
5. **Given** an answer contains a fenced code block, **When** the visitor activates copy, **Then** only the code is copied and a visible confirmation appears.
6. **Given** the visitor presses Enter while composing, **When** the input method is still composing Vietnamese text, **Then** the message is not sent prematurely.

---

### User Story 3 - Use the Interface Comfortably on Any Screen and Theme (Priority: P2)

A visitor uses the chat on a desktop or phone, in light or dark conditions. The layout stays focused on the conversation, the navigation can be collapsed, and the interface follows the system theme unless the visitor chooses otherwise.

**Why this priority**: The new interface replaces a page that already works on the target devices. Responsive behavior and comfortable reading are required for the migration to be acceptable, but they depend on the chat experience existing first.

**Independent Test**: Open the interface at phone and desktop widths in light and dark themes, send a message, open and close navigation, and confirm the conversation remains readable and all controls reachable.

**Acceptance Scenarios**:

1. **Given** a narrow mobile viewport, **When** the visitor opens navigation, **Then** it appears as an overlay drawer that can be dismissed without losing the conversation.
2. **Given** a wide desktop viewport, **When** the visitor collapses navigation, **Then** the conversation area expands and the reading width stays comfortable.
3. **Given** the operating system changes between light and dark, **When** no explicit visitor choice exists, **Then** the interface follows the system preference.
4. **Given** the visitor chooses a theme, **When** the page is reloaded in the same session, **Then** the chosen theme remains active.
5. **Given** reduced-motion is enabled at the system level, **When** the interface animates, **Then** non-essential motion is suppressed.

---

### User Story 4 - Manage Conversations in the Current Session (Priority: P2)

A visitor starts a new conversation, returns to an earlier one, and sees each conversation identified by its first question. Conversations remain available while the page is open, without requiring an account or server-side storage.

**Why this priority**: Conversation switching makes the interface feel like a real assistant workspace rather than a single-shot query box. It is valuable but not required for the first usable release.

**Independent Test**: Create two conversations with different questions, switch between them, and confirm each keeps its own messages and title.

**Acceptance Scenarios**:

1. **Given** no conversation is active, **When** the visitor sends the first question, **Then** a conversation is created and titled from that question.
2. **Given** multiple conversations exist, **When** the visitor selects one, **Then** only that conversation's messages are shown.
3. **Given** the visitor starts a new conversation, **When** it is created, **Then** the previous conversation remains available in the list.
4. **Given** the page is reloaded, **When** the interface starts again, **Then** the visitor sees a fresh empty state without corrupted prior state.

---

### User Story 5 - Keep the Repository Cleanly Split and Ignorable (Priority: P3)

A maintainer can tell frontend and backend apart in the repository, understands that the backend is retained temporarily, and can trust that generated, local, and secret files are excluded from version control.

**Why this priority**: Repository hygiene reduces accidents during and after the migration. It is important for maintainability but does not change the visitor experience on its own.

**Independent Test**: Inspect the repository layout, run the documented frontend and backend startup commands, and verify that generated dependencies, build output, caches, local environment files, and editor/OS files are not tracked.

**Acceptance Scenarios**:

1. **Given** the repository after the change, **When** a maintainer looks at the top level, **Then** frontend and backend responsibilities are clearly separated.
2. **Given** frontend dependencies and build output have been generated, **When** version-control status is inspected, **Then** those artifacts are ignored.
3. **Given** local environment or secret files exist, **When** version-control status is inspected, **Then** those files are ignored while example configuration remains trackable.
4. **Given** the backend is intentionally retained, **When** a maintainer reads the project documentation, **Then** the temporary status and replacement direction are explicit.

---

### Edge Cases

- The backend returns a non-streaming response while the frontend expects streaming: the full answer is displayed once instead of hanging.
- A stream is interrupted mid-answer: the partial answer remains visible and the visitor is told the response was interrupted.
- The visitor sends an empty or whitespace-only message: the send action is unavailable or the message is rejected without contacting the backend.
- A very long answer or very long unbroken text: the conversation scrolls vertically and the reading column stays bounded.
- A message contains untrusted HTML or script content: it is rendered as text/Markdown and never executed.
- The clipboard is unavailable or permission is denied: the copy action reports failure without breaking the page.
- The backend is slow or times out: the interface shows a waiting state, then a clear error with retry.
- The backend responds with a rate-limit or quota error: the interface explains the condition and when to retry.
- The visitor switches theme while a message is streaming: rendered content and colors update without losing the stream.
- The visitor collapses navigation on a phone with the drawer open: the drawer closes and focus returns sensibly.
- Vietnamese input method composition is active: Enter confirms the composition rather than sending the message.
- The backend URL is misconfigured: the visitor sees a connection error rather than an empty conversation.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a standalone browser frontend that runs independently from the answering backend and communicates with it only through a documented HTTP contract.
- **FR-002**: The system MUST retain the existing backend answering behavior and public chat contract temporarily, without requiring changes to backend answer logic.
- **FR-003**: Visitors MUST be able to submit a question and receive the backend answer in the same conversation without a full page reload.
- **FR-004**: The frontend MUST support incremental display of answer content when the backend provides it incrementally, and MUST correctly display a complete answer when the backend responds all at once.
- **FR-005**: Visitors MUST be able to stop an in-progress answer generation and keep the partial content that has already appeared.
- **FR-006**: The frontend MUST render Markdown content, including paragraphs, headings, lists, tables, links, and inline code.
- **FR-007**: The frontend MUST render fenced code blocks with readable formatting and provide a one-action copy control with visible success or failure feedback.
- **FR-008**: The frontend MUST present visitor messages differently from assistant messages, keeping assistant content as plain readable text without a chat bubble.
- **FR-009**: The frontend MUST follow the system light/dark preference by default and MUST allow the visitor to override the theme, retaining the choice within the current browser session.
- **FR-010**: The frontend MUST be usable on phone and desktop widths, with navigation that collapses on wide screens and becomes a dismissible drawer on narrow screens.
- **FR-011**: The frontend MUST provide a composer that grows with its content up to a limit, sends on Enter, inserts a newline on Shift+Enter, and respects Vietnamese input-method composition.
- **FR-012**: The frontend MUST show distinct states for an empty conversation, waiting for the first content, streaming, error with retry, rate limiting, and an interrupted response.
- **FR-013**: The frontend MUST let a visitor start a new conversation, switch between conversations held in the current session, and identify each conversation by its first question.
- **FR-014**: The frontend MUST keep conversations in the browser for the current session only; cross-session history, login, and multi-user permissions are out of scope for this feature.
- **FR-015**: The frontend MUST NOT contain backend credentials, API keys, or secrets, and MUST treat all message content as untrusted.
- **FR-016**: The frontend MUST provide accessible navigation and announcements, including a live conversation region, labels for icon-only controls, visible keyboard focus, and keyboard-operable navigation.
- **FR-017**: The repository MUST clearly separate frontend and backend responsibilities and MUST document that the backend is retained temporarily while the interface is migrated.
- **FR-018**: The repository ignore rules MUST exclude generated frontend dependencies and build output, local environment and secret files, Python caches and virtual environments, test/build caches, and editor/OS artifacts, while keeping example configuration trackable.
- **FR-019**: The frontend MUST be configurable to point at the backend's base address without editing source code.
- **FR-020**: The existing static Python-rendered chat page MUST be replaced as the primary interface, and visitors MUST no longer depend on it for normal chat use.

### Key Entities *(include if feature involves data)*

- **Conversation**: A session-scoped collection of messages identified by a generated identifier and a title derived from its first visitor question.
- **Message**: A single exchange item with a role (visitor or assistant), text content, a stable identifier, and ordering within its conversation.
- **Streaming Response**: The incremental content produced for one assistant message, which may be partial, complete, stopped, or interrupted.
- **Runtime Configuration**: Frontend-visible settings for the backend base address and theme preference, excluding any secret values.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A visitor can send a question from the separated frontend and see the backend answer without reloading the page in 100% of tested normal cases.
- **SC-002**: When incremental delivery is available, the first content becomes visible within 1 second of the backend beginning the response.
- **SC-003**: At least 95% of tested Markdown samples (paragraphs, headings, lists, tables, links, inline code, fenced code) render correctly, and code copy succeeds or reports a clear failure in 100% of attempts.
- **SC-004**: The interface remains fully usable at a 360-pixel-wide viewport and at a 1440-pixel-wide viewport, with no control requiring horizontal scrolling.
- **SC-005**: All tested text/background combinations in both themes meet a contrast ratio of at least 4.5:1.
- **SC-006**: 100% of keyboard-only navigation checks reach the composer, send/stop control, navigation, and theme control in a logical order.
- **SC-007**: Vietnamese input-method tests send zero messages when Enter is used to confirm composition.
- **SC-008**: Generated frontend dependencies, build output, Python virtual environments/caches, local secrets, and editor/OS files are absent from version-control status after a normal build and run.
- **SC-009**: No backend credential or secret appears in the frontend build output.
- **SC-010**: A visitor can create and switch between at least two conversations in one session with no message leakage between them.

## Assumptions

- The existing Python backend remains the answering service for this phase and is retained temporarily; a backend replacement is a separate future effort.
- The existing public chat contract (`POST /chat` returning a response string) stays available; incremental delivery may require an additional backend capability, and the frontend degrades gracefully when that capability is absent.
- The user has explicitly requested React for the replacement interface; specific build tooling, state management, Markdown, highlighting, and icon libraries are selected during planning and recorded in `plan.md`.
- Conversation history is in-memory for the current browser session; no account system, server-side history, or cross-device sync is introduced.
- The deployment target is a single local environment with a known backend address; authentication and multi-tenant access are out of scope.
- The interface draws inspiration from the provided reference layout and tokens but uses the project's own branding, accent color, and assets rather than copying another product's identity.
- Both light and dark themes are supported through system preference and a visitor override.
- A text-based browser without streaming support still receives the complete answer as a fallback.
- The backend remains reachable from the frontend through a configurable base address, including when frontend and backend run on different origins.
- Existing backend tests and contract checks remain authoritative for backend behavior during the migration.
