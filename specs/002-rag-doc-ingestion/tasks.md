---
description: "Task list for RAG document ingestion and editing"
---

# Tasks: RAG Document Ingestion and Editing

**Input**: Design documents from `/specs/002-rag-doc-ingestion/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included because `plan.md` explicitly commits to pytest unit tests for normalization and file lifecycle plus Ollama-gated integration tests. Write tests first and confirm they fail before implementing.

**Organization**: Tasks are grouped by user story so each story can be implemented and tested independently. User Story 1 (add) is the MVP and the base of the other lifecycles; User Story 2 (replace/delete) builds on the same `documents.py` module but is independently testable once the add path exists.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- Single-project web app at repository root: `app.py`, `chatbox.py`, `index.html`, `data/`, `qa.txt`
- New modules at repository root: `text_normalization.py`, `documents.py`
- Operator CLI in `scripts/manage_docs.py`; tests in `tests/`
- Paths below follow `plan.md` "Project Structure"

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and test scaffolding

- [X] T001 [P] Update `.env.example` to document `CHATBOT_TOP_K=3` and `CHATBOT_QUERY_REWRITE=auto`, keeping the existing `CHATBOT_CHUNK_SIZE=500`, `CHATBOT_CHUNK_OVERLAP=50`, `CHATBOT_RELEVANCE_THRESHOLD=1.0`, and other values exactly as defined in `specs/002-rag-doc-ingestion/data-model.md`
- [X] T002 [P] Add reusable test helpers in `tests/helpers.py`: a temporary knowledge-base directory helper that never touches the real `data/`, a text-source writer, and a fake-embeddings/fake-LLM factory so normalization and lifecycle tests run without Ollama
- [X] T003 [P] Confirm `requirements.txt` needs no new package (the feature reuses Flask, LangChain, FAISS, Ollama, rapidfuzz, pandas, pypdf, python-docx, docx2txt) and record in `README.md` that no additional dependency is required

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared normalization, configuration, and index infrastructure required by every user story

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 [P] Create `tests/test_normalization.py` with failing tests for the pipeline in `specs/002-rag-doc-ingestion/contracts/retrieval-normalization.md`: NFC normalization of decomposed diacritics; runs of **3 or more** identical characters collapsed to one while legitimate doubles (for example `xoong`) are preserved; lowercase; runs of `!`, `?`, `.`, `,` collapsed to one; whitespace runs collapsed to a single space and trimmed; punctuation-only input normalizes to an empty string; the original input is never mutated
- [X] T005 Implement the pure normalization function in `text_normalization.py` to satisfy T004, exposing one function used for both indexing and search and returning the search form only
- [X] T006 [P] Extend the `Config` dataclass and `load_config()` in `chatbox.py` with `top_k` (default `3`; must be `>= 1`) and `query_rewrite` (enum `auto` | `always` | `off`, default `auto`), raising a clear runtime error for invalid values
- [X] T007 Add normalized embedding input in `chatbox.py`: wrap the configured `OllamaEmbeddings` so every document and query vector is produced from the shared normalization function, while chunk `page_content` remains the original text
- [X] T008 Add index freshness in `chatbox.py`: compute a `signature` over supported files under `CHATBOT_DATA_DIR` (relative path, modification time, size) plus embedding model, chunk size, and chunk overlap; reuse the in-memory FAISS index when the signature matches and rebuild from current sources when it changes, and never replace a live index with a partially built one
- [X] T009 Attach a normalized `source` metadata value to every loaded document and chunk in `chatbox.py` so diagnostics and source filtering can name the origin

**Checkpoint**: Normalization, configuration, normalized embeddings, index fingerprinting, and source metadata are ready.

---

## Phase 3: User Story 1 - Add a New Document to the Knowledge Base (Priority: P1) 🎯 MVP

**Goal**: An operator adds a text document under a unique source name and the chatbot answers questions from it without disturbing the rest of the knowledge base.

**Independent Test**: Add a document whose facts exist nowhere else, then ask a question answerable only from that document and confirm the answer uses it and `list` shows exactly one source.

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST and ensure they FAIL before implementation.**

- [X] T010 [P] [US1] Add failing add-path tests in `tests/test_document_management.py`: adding a valid `.txt` source creates it and reports success; re-adding the same name is an upsert with exactly one current version (no duplicate); empty, whitespace-only, or unreadable input is rejected with a clear reason and leaves the knowledge base unchanged; source names that are absolute paths, contain `.`/`..`, path separators, an empty name, or an unsupported extension are rejected; a failed validation never leaves a partial or temporary file in `data/`
- [X] T011 [P] [US1] Add an Ollama-gated integration test in `tests/test_retrieval_normalization.py` using a temporary `CHATBOT_DATA_DIR`: add a source with a unique fact, ask a question answerable only from it, and assert the answer contains the fact and the diagnostic names the source

### Implementation for User Story 1

- [X] T012 [US1] Implement `documents.py`: `SourceDocument` and `IngestionResult` dataclasses per `data-model.md` (`action` enum `add` | `replace` | `delete`; `status` enum `success` | `failed`), `validate_source_name` enforcing "Plain basename, non-empty, allowed extension, no path separators, no traversal" with allowed formats `txt`, `pdf`, `docx`, `xlsx`, `csv`, and an `add_source` upsert that writes a temporary file in the same directory with a non-source extension before atomically replacing the destination
- [X] T013 [US1] Implement text extraction for `.txt`, `.docx`, `.xlsx`, and `.csv` in `documents.py`, rejecting content that is not "Non-empty and not whitespace-only" before any destination file is committed
- [X] T014 [US1] Update `_load_documents()` and the splitter in `chatbox.py` to configure `RecursiveCharacterTextSplitter` separators in priority order (blank line/paragraph, newline, Vietnamese sentence-ending punctuation, other sentence punctuation, space, character) and preserve `source` metadata on every chunk, keeping `CHATBOT_CHUNK_SIZE=500` and `CHATBOT_CHUNK_OVERLAP=50` defaults
- [X] T015 [US1] Create `scripts/manage_docs.py` with the `add <input-path> --name <source-name>` subcommand, `--data-dir` override, exit code `0` on success, `1` on validation/operation failure with the reason on stderr, and `2` on usage errors; use the input base name when `--name` is omitted and require the source-name extension to match the input format
- [X] T016 [US1] Wire the add path end to end in `chatbox.py` so a newly added source is visible on the next query through the T008 fingerprint check, without restarting the Flask process

**Checkpoint**: User Story 1 is fully functional and testable independently (MVP).

---

## Phase 4: User Story 2 - Update or Remove an Existing Document (Priority: P1)

**Goal**: An operator replaces or deletes a source and only the current knowledge-base state is ever used to answer.

**Independent Test**: Add a document with a distinctive fact, replace it with a changed fact, then ask about both; only the new fact is answered. Delete it and the question is refused.

**Dependency**: US2 reuses `documents.py` and the index refresh from US1/Phase 2; it can start as soon as US1 exists.

### Tests for User Story 2 ⚠️

> **NOTE: Write these tests FIRST and ensure they FAIL before implementation.**

- [X] T017 [P] [US2] Add failing replace/delete tests in `tests/test_document_management.py`: `replace` requires an existing source and fails clearly when absent; a valid replace removes all previous chunks and leaves exactly one current version; a failed replace (unreadable or empty input) leaves the previous version intact; `delete` removes the source; deleting a missing source reports a clear notice without affecting other sources
- [X] T018 [P] [US2] Add Ollama-gated integration tests in `tests/test_retrieval_normalization.py` using a temporary `CHATBOT_DATA_DIR`: after replace, questions about the old fact are no longer answered from old content and the new fact is answered; after delete, the source's questions are refused with `Tôi không biết`; after restart/re-import the same state is reflected

### Implementation for User Story 2

- [X] T019 [US2] Implement `replace_source` and `delete_source` in `documents.py`: validate and extract before touching the destination, write the new version to a temporary file in the data directory (non-source extension), atomically replace on success, clean up temporary files on success and failure, and remove the file on delete; never write outside the configured data directory
- [X] T020 [US2] Add the `replace <input-path> --name <source-name>` and `delete <source-name>` subcommands to `scripts/manage_docs.py` with the exit codes and output rules from `specs/002-rag-doc-ingestion/contracts/document-cli.md`, including `--data-dir`
- [X] T021 [US2] Harden `get_db()` in `chatbox.py` so a failed rebuild after a replace/delete leaves the previous index untouched and surfaces a clear error instead of serving a partially updated or mixed old/new index

**Checkpoint**: User Stories 1 and 2 work independently; replaced and deleted content is never retrievable.

---

## Phase 5: User Story 3 - Ask Questions in Messy Vietnamese (Priority: P1)

**Goal**: Noisy Vietnamese input (repeated letters, punctuation, extra whitespace, missing diacritics, typos) retrieves the same content as a clean question, while the original wording is preserved for the answer and display.

**Independent Test**: Compare clean questions with noisy variants (repeated characters, no diacritics, extra whitespace, punctuation noise) and confirm the same relevant content is retrieved for every variant.

### Tests for User Story 3 ⚠️

> **NOTE: Write these tests FIRST and ensure they FAIL before implementation.**

- [X] T022 [P] [US3] Add failing query-path tests in `tests/test_normalization.py` and `tests/test_retrieval_normalization.py`: stored `qa.txt` questions and incoming questions use the same shared normalized form for fuzzy matching; a question normalizing to an empty string returns a rephrase request and never searches; the original question (capitalization, proper names, abbreviations, numbers) is what reaches the answer prompt and display while the normalized form is used for search
- [X] T023 [P] [US3] Add failing query-rewrite tests in `tests/test_retrieval_normalization.py`: mode `off` never rewrites; mode `always` rewrites every question; mode `auto` rewrites only when the normalized question has no Vietnamese diacritics or the raw input contained repeated-character/punctuation noise; a failed, empty, or unreasonably long rewrite falls back to the deterministically normalized question; rewritten text is normalized again before embedding
- [X] T024 [P] [US3] Add Ollama-gated noisy-variant integration coverage in `tests/test_retrieval_normalization.py` for `choooo`/`đượcccc`, extra spaces, and no-diacritics questions, asserting the same relevant content is retrieved as the clean variant

### Implementation for User Story 3

- [X] T025 [US3] Update `_load_qa_data()` and the RapidFuzz matching in `chatbox.py` to normalize stored questions and incoming questions with the shared function instead of only `.lower()`, keeping answers unchanged
- [X] T026 [US3] Integrate the shared normalization into `ask_ai()` in `chatbox.py`: build a `NormalizedQuestion` (`original`, `normalized`, `rewritten`, `rewrite_applied`) per `data-model.md`, search with the normalized/rewritten form, and return the rephrase request when `normalized` is empty
- [X] T027 [US3] Implement query rewriting in `chatbox.py` per `CHATBOT_QUERY_REWRITE` (`auto` | `always` | `off`): the prompt fixes spelling and adds missing Vietnamese diacritics, preserves proper names/abbreviations/numbers, returns only the corrected sentence, and falls back to the deterministic form on failure, empty output, or excessive length
- [X] T028 [US3] Ensure the original question is passed to `_build_prompt()` and the response path in `chatbox.py`, while only the normalized/rewritten form reaches the embedding query

**Checkpoint**: Messy Vietnamese input retrieves like clean input and the original wording is preserved.

---

## Phase 6: User Story 4 - Understand Where an Answer Came From (Priority: P2)

**Goal**: An operator can inspect which sources and pieces produced an answer, the normalized question form, and which sources are currently indexed.

**Independent Test**: Ask a question that produces a poor answer and confirm the operator can identify the source names, per-piece scores, normalized/rewritten question, and outcome without reading application internals.

### Tests for User Story 4 ⚠️

> **NOTE: Write these tests FIRST and ensure they FAIL before implementation.**

- [X] T029 [P] [US4] Add failing diagnostics tests in `tests/test_retrieval_normalization.py`: the operator path returns `original_question`, `normalized_question`, `rewritten_question` (or null), `pieces` with `source_name`/`chunk_index`/`score`/excerpt, `passed_threshold`, and `outcome` enum `answered` | `refused` | `rephrase`; a source listing reflects current sources; the public `POST /chat` response still contains exactly one `response` string and no diagnostic fields

### Implementation for User Story 4

- [X] T030 [US4] Add `list_sources(data_dir)` in `documents.py` returning current source names and formats, and expose diagnostics or the operator CLI through it
- [X] T031 [US4] Implement an operator diagnostics path in `chatbox.py` (for example `ask_ai_detailed()`) returning the answer plus a `RetrievalDiagnostic` record, and keep `ask_ai()` returning only the answer string so `app.py` and `POST /chat` stay unchanged
- [X] T032 [US4] Add the `list` and `ask "<question>" [--debug]` subcommands to `scripts/manage_docs.py`; `list` prints source names and formats, and `ask --debug` prints the answer followed by original question, normalized question, rewritten form (or `-`), selected sources, per-piece scores, and outcome per `contracts/document-cli.md`
- [X] T033 [US4] Verify in `tests/test_chat_api.py` that diagnostics never leak into the HTTP response and that existing `400` behavior for missing/empty `message` is preserved

**Checkpoint**: Operators can trace an answer back to its sources and inspect the search form.

---

## Phase 7: User Story 5 - Import Content from PDF (Priority: P2)

**Goal**: A text-based PDF can be imported and queried like a text document; a scanned/image-only PDF is rejected with a clear message and never added as an empty source.

**Independent Test**: Add a text-based PDF with a unique fact and ask about it, then try a scanned PDF and confirm rejection.

**Dependency**: US5 builds on the validation and atomic-write path from US1/US2.

### Tests for User Story 5 ⚠️

> **NOTE: Write these tests FIRST and ensure they FAIL before implementation.**

- [X] T034 [P] [US5] Add failing PDF tests in `tests/test_document_management.py`: a text-based PDF is accepted, retained as a `.pdf` source, and yields non-empty extracted text; an image-only/scanned PDF whose extraction yields no usable text is rejected with a message explaining OCR is not part of this feature and is not added; a failed PDF import leaves any existing source intact
- [X] T035 [P] [US5] Add an Ollama-gated integration test in `tests/test_retrieval_normalization.py` using the existing `research_paper_ai_education.pdf`: import it as a source and confirm a matching question retrieves pieces from that source

### Implementation for User Story 5

- [X] T036 [US5] Implement PDF extraction in `documents.py` using the existing `PyPDFLoader`/`pypdf`, retain the PDF file itself, and validate that extracted text is non-empty before committing an add/replace
- [X] T037 [US5] Allow `.pdf` source names and input formats in `scripts/manage_docs.py` for both `add` and `replace`, enforcing that the source-name extension matches the input format
- [X] T038 [US5] Ensure PDF chunks carry page metadata where available (`page` non-negative or null) and the `source` name remains the PDF source name for diagnostics

**Checkpoint**: Text PDFs are importable and searchable; scanned PDFs fail cleanly.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, validation, and hardening across all stories

- [X] T039 [P] Update `README.md` with the operator document lifecycle (`add`, `replace`, `delete`, `list`, `ask --debug`), the new configuration values, the PDF/OCR limitation, and the index-refresh behavior
- [X] T040 [P] Update `.gitignore` to ignore temporary in-progress source files (for example `*.tmp` and `data/.*.tmp`) so atomic-write leftovers are never indexed
- [X] T041 Run the seven scenarios in `specs/002-rag-doc-ingestion/quickstart.md` against a temporary `CHATBOT_DATA_DIR` and confirm the expected add/replace/delete/noisy/PDF/restart/API outcomes
- [X] T042 Run `pytest tests/` and confirm normalization, document-management, and retrieval-normalization tests pass without Ollama (fakes/temp dirs) and Ollama-gated tests skip cleanly when models are unavailable; existing `test_chat_api.py`, `test_retrieval.py`, `test_refusal.py`, and `test_answers.py` remain valid
- [X] T043 Perform a security review of `documents.py` and `scripts/manage_docs.py`: reject path traversal, guarantee every write stays inside the configured data directory, clean up temporary files on both success and failure, and ensure diagnostics expose no secrets or files outside the knowledge base
- [X] T044 [P] Verify `app.py` and `index.html` are unchanged in their public contract and confirm `requirements.txt` still contains no new runtime dependency

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phases 3-7)**: All depend on Foundational completion
  - US1 and US3 can start in parallel once Phase 2 is done
  - US2 depends on US1 (`documents.py` add path and index refresh)
  - US5 depends on US1/US2 (validation and atomic-write path)
  - US4 depends on US1 (source lifecycle) and US3 (normalized question) for its diagnostic fields
- **Polish (Phase 8)**: Depends on all desired user stories being complete

### User Story Dependencies

- **US1 - Add (P1)**: Starts after Phase 2 - no other story dependency
- **US2 - Replace/Delete (P1)**: Starts after US1 - reuses `documents.py` and the index refresh
- **US3 - Noisy Vietnamese (P1)**: Starts after Phase 2 - independent of the document lifecycle; shares only the normalization function
- **US4 - Diagnostics (P2)**: Starts after US1 and US3 - composes lifecycle listing with the normalized question record
- **US5 - PDF (P2)**: Starts after US1/US2 - extends the same extraction and atomic-write path

### Within Each User Story

- Tests are written and must FAIL before implementation
- Models/dataclasses before services/helpers
- Helpers before CLI wiring
- Core implementation before integration with `chatbox.py`
- Story complete and independently validated before moving to the next priority

### Parallel Opportunities

- Setup tasks T001-T003 all touch different files and can run in parallel
- Foundational T004 (normalization tests) and T006 (configuration) can run in parallel; T005 follows T004, T007-T009 follow T006
- After Phase 2: US1 and US3 can proceed in parallel (different modules: `documents.py`/CLI vs `chatbox.py` query path)
- Within US1: T010 and T011 test files are separate and parallel; T012 and T013 both edit `documents.py` and must be sequential
- Within US3: T022-T024 tests are parallel; T025-T028 all edit `chatbox.py` and are sequential
- Within US5: T034 and T035 are parallel; T036-T038 are sequential

---

## Parallel Example: User Story 1

```bash
# Launch the add-path tests together (separate files):
Task: "Add failing add-path tests in tests/test_document_management.py"
Task: "Add Ollama-gated add→ask integration test in tests/test_retrieval_normalization.py"

# Then implement the module and CLI sequentially:
Task: "Implement documents.py SourceDocument/IngestionResult/validate_source_name/add_source"
Task: "Create scripts/manage_docs.py add subcommand"
```

## Parallel Example: User Story 3

```bash
# Launch the query-path test suites together:
Task: "Add query normalization tests in tests/test_normalization.py"
Task: "Add query rewrite mode tests in tests/test_retrieval_normalization.py"
Task: "Add Ollama-gated noisy-variant integration coverage"

# Then implement sequentially in chatbox.py:
Task: "Normalize qa.txt keys and fuzzy matching"
Task: "Integrate NormalizedQuestion into ask_ai()"
Task: "Implement CHATBOT_QUERY_REWRITE modes and fallback"
Task: "Preserve original question for prompt and display"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: add a source, ask a question, confirm the answer and `list`
5. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational → normalization, config, and index refresh ready
2. US1 → add-and-answer works → MVP
3. US2 → safe replace/delete
4. US3 → noisy Vietnamese input retrieves correctly
5. US4 → operator diagnostics and source listing
6. US5 → PDF import
7. Polish → README, quickstart, security review

### Parallel Team Strategy

With multiple developers after Phase 2:

- Developer A: US1 then US2 then US5 (document lifecycle chain)
- Developer B: US3 (normalization/rewrite in `chatbox.py`)
- Developer C: US4 after US1 + US3 (diagnostics and CLI)

---

## Notes

- `[P]` tasks touch different files and can run in parallel
- `[Story]` labels map every story-phase task to its user story for traceability
- Each user story is independently completable and testable at its checkpoint
- Tests must fail before implementing the corresponding behavior
- The public `POST /chat` contract must remain `{"response": "..."}` at every checkpoint
- Do not add a database, OCR, an HTTP admin endpoint, or a new runtime dependency


---

## Implementation Notes

- All Setup, Foundational, US1-US5, and Polish tasks are implemented.
- New/updated automated tests pass: `tests/test_normalization.py`, `tests/test_document_management.py`, `tests/test_retrieval_normalization.py`, `tests/test_chat_api.py` (53 passed).
- Quickstart scenarios 1-7 were exercised against a temporary `CHATBOT_DATA_DIR`; add, replace, delete, noisy-input, PDF import, no-restart index refresh, and API compatibility behaved as expected.
- Full `pytest tests/` has two pre-existing live-model failures unrelated to this feature (they also fail with the pre-change `chatbox.py`):
  - `tests/test_retrieval.py::test_paraphrase_and_no_diacritics_retrieve_expected_fact` — the no-diacritics question ranks a different document above the `data.txt` chunk containing `8.30` at `k=2`.
  - `tests/test_answers.py::test_in_domain_answers_contain_expected_facts[categories0]` — the answer model paraphrases the school name, so the test helper's exact substring check misses it.
  All new feature tests pass, and `tests/test_refusal.py` now passes because QA matching uses normalized exact/fuzzy scoring instead of partial `WRatio` matching.
- No database, OCR, management HTTP endpoint, or new runtime dependency was added; `app.py` and `index.html` keep the public `POST /chat` contract unchanged.
