# Contract: UI and Interaction

**Feature**: `003-react-chat-ui`  
**Scope**: Layout, visual states, accessibility, responsive behavior, and theme

## Layout

```text
┌──────────────┬──────────────────────────────────────────────┐
│ Sidebar      │ Header: conversation title, theme toggle,    │
│ (collapsible │         new-chat / menu controls             │
│  on desktop, ├──────────────────────────────────────────────┤
│  drawer on   │ Message list (scrolls; centered max width)   │
│  mobile)     │                                              │
│              │                                              │
│ - New chat   │                                              │
│ - History    ├──────────────────────────────────────────────┤
│ - Footer     │ Composer (auto-resizing textarea, send/stop) │
└──────────────┴──────────────────────────────────────────────┘
```

- Empty workspace: centered greeting + short subtitle + composer; no fake messages.
- Conversation: messages top-aligned in a reading column with generous spacing; the list auto-scrolls while the user is near the bottom and does not fight manual scroll-up.
- Composer stays pinned to the bottom of the conversation column.

## Visual tokens

Define in `frontend/src/styles/tokens.css`; consumed by `app.css` and components.

- **Surfaces**: app background, sidebar background, elevated surface, subtle surface.
- **Borders**: default, strong.
- **Text**: primary, secondary, tertiary.
- **Controls**: hover, active, disabled, focus ring.
- **Accent**: brand deep teal/green (distinct from the reference), accent-hover, accent-soft.
- **Radii**: sm/md/lg/pill.
- **Spacing**: 4/8/12/16/24/32/48 scale.
- **Shadows**: subtle, elevated.
- **Typography**: serif reading stack for assistant prose; sans stack for UI; mono stack for code. Sizes for body, small, heading, code.
- **Motion**: short fades/slide for menus and drawer; disabled or reduced under `prefers-reduced-motion`.

Rules:
- Every color used in components comes from a token; no hard-coded hex outside `tokens.css`.
- Both themes define the same token names; contrast ≥ 4.5:1 for text.
- The accent is configurable in one place.

## Component contracts

### Sidebar

- Desktop: icon-first rail with labels available via accessible names/tooltips; can collapse to icons and remembers the state for the session.
- Mobile (<768px): hidden by default; opened by a header menu button as an overlay drawer; backdrop click, `Esc`, and selecting a conversation close it; focus returns to the trigger.
- Shows "New chat" and the in-session conversation list; active item is visually distinct and marked with `aria-current`.
- Footer may show a static service status/config hint; no account UI.

### Header

- Shows the active conversation title (or a neutral placeholder for the empty workspace).
- Contains the mobile menu trigger (small screens), theme toggle, and new-chat control where appropriate.
- Controls have visible focus and accessible names.

### MessageList

- Container has `role="log"`, `aria-live="polite"`, and `aria-relevant="additions text"`.
- Renders messages in order with stable keys.
- Auto-scrolls only when the user is at/near the bottom; a "scroll to latest" affordance appears when scrolled up during streaming.

### Message

- User message: plain text, visually distinct bubble/alignment, no Markdown execution.
- Assistant message: Markdown rendering with GFM; raw HTML disabled.
- States:
  - `streaming`: content appends progressively; show a subtle cursor/indicator; send is replaced by stop.
  - `complete`: full content; no indicator.
  - `stopped`: partial content plus a muted "stopped" label.
  - `interrupted`: partial content plus retry.
  - `error`: short message plus retry; no stack traces.
- Long words/URLs wrap; no horizontal overflow of prose.

### CodeBlock

- Fenced code renders in a distinct block with a language label when known.
- Copy button copies the exact code, shows a transient "Copied" state, and falls back when the Clipboard API is unavailable.
- Copy failure shows a short error, not a thrown exception.
- Inline code uses a token background/border and does not inherit block layout.

### Composer

- Multi-line textarea with an accessible label and placeholder.
- Auto-resizes up to a capped height, then scrolls.
- `Enter` sends; `Shift+Enter` inserts a newline; `Enter` during IME composition does not send.
- Send is disabled for blank input or while streaming; while streaming the primary action is Stop.
- After send: clear the textarea, keep focus, and show the new message immediately.
- Error/retry does not duplicate the user message.

### EmptyState

- Short greeting, one-line subtitle, and example prompts (optional).
- Selecting an example fills/sends only after explicit user action.

### ThemeToggle

- Options: system, light, dark. Defaults to system.
- Persists the choice; updates `data-theme` on the document root; updates `color-scheme`.
- Announcement or accessible label reflects the current mode.

## Responsive breakpoints

| Range | Behavior |
|-------|----------|
| ≥ 1024px | Sidebar visible (collapsible); conversation max-width ~760px; header controls inline |
| 768–1023px | Sidebar collapsible rail or overlay; reduced outer padding |
| < 768px | Sidebar overlay drawer; full-width conversation; header shows menu trigger; composer full-width with safe-area bottom padding |

No horizontal scrolling at 320px width.

## Accessibility requirements

- All interactive controls are reachable by keyboard in a logical order and have visible focus.
- Icon-only buttons have `aria-label`/`title`.
- The drawer traps focus while open and restores focus on close.
- Streaming updates and errors are announced politely; do not use `aria-live="assertive"`.
- Status is conveyed with text/icon as well as color.
- The page has a meaningful title and landmarks (`header`, `nav`, `main`).
- `prefers-reduced-motion` disables non-essential animation.
- Touch targets are at least 40×40px where practical.

## Content and safety

- Assistant Markdown is sanitized by construction (no raw HTML).
- Links open safely (`target="_blank"`, `rel="noopener noreferrer"`).
- User content is rendered as text.
- No external images/fonts/CDNs are required for the core experience.
