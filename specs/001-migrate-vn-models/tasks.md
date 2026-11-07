---
description: "Task list for migrating the chatbot to Vietnamese-capable models"
---

# Tasks: Migrate Chatbot to Vietnamese-Capable Models

**Input**: Design documents from `/specs/001-migrate-vn-models/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included because `plan.md` commits to a lightweight pytest suite and evaluation harness. Write tests before the corresponding behavior change.

**Organization**: Tasks are grouped by user story so each story can be implemented and tested independently. Both P1 stories are core, but the embedding change is sequenced first because the spec's rollout order requires changing one thing at a time (embedding → answer model).

## Implementation Status

Code, tests, configuration, evaluation tooling, and the model-recommendation script are implemented. `pytest tests/` passes (10 passed, 3 skipped). The skipped tests and tasks marked `[ ]` below require a machine with Ollama and the bge-m3/Qwen2.5 models; they could not be run in this environment (Ollama is not installed).

**Blocked on live models**: T009 (original baseline), T014 (threshold calibration), T018 (manual Vietnamese validation), T021 (live refusal validation), T024 (3B fallback run), T026/T027 (post-change milestones), T028 (final comparison), T031 (full quickstart), T032 (final answer review).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

## Path Conventions

- Single-project web app at repository root: `app.py`, `chatbox.py`, `index.html`, `data/`, `qa.txt`
- Tests in `tests/`; evaluation artifacts in `evaluation/`; helper scripts in `scripts/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and hygiene

- [X] T001 Remove the stray `ollama run qwen3:1.7b` line from `requirements.txt`, add `pytest` under a dev section, and confirm the remaining dependencies match `plan.md`
- [X] T002 [P] Create `tests/` and `evaluation/results/` directories with `.gitkeep` files so generated results can be committed
- [X] T003 [P] Create `.env.example` documenting `CHATBOT_ANSWER_MODEL`, `CHATBOT_EMBEDDING_MODEL`, `CHATBOT_RELEVANCE_THRESHOLD`, `CHATBOT_FUZZY_CUTOFF`, `CHATBOT_DATA_DIR`, `CHATBOT_QA_PATH` exactly as defined in `specs/001-migrate-vn-models/contracts/configuration.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before any user story work

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T004 Implement environment-variable configuration loading and validation in `chatbox.py`: default `answer_model=qwen2.5:7b`, `embedding_model=bge-m3`, `fuzzy_match_cutoff=80`, `data_dir=data`, `qa_path=qa.txt`; fail fast with a clear message when a configured path is missing. Values and allowed ranges come from `specs/001-migrate-vn-models/contracts/configuration.md`
- [X] T005 [P] Create `evaluation/questions.json` with about 15 fixed questions covering the minimum counts in `specs/001-migrate-vn-models/contracts/evaluation.md`: at least 4 `direct` (GPA, one subject score, university, goal), 3 `paraphrase`, 2 `no_diacritics`, 2 `pronoun_variant`, 3 `out_of_scope`. Verify every `expected_answer` against `data/data.txt` and `qa.txt`; `out_of_scope` entries use `expected_answer: null` and `expected_refusal: true`
- [X] T006 [P] Implement `evaluation/run_eval.py` CLI per `specs/001-migrate-vn-models/contracts/evaluation.md`: accept `--milestone` (`original`, `embedding-changed`, `answer-model-changed`) and optional `--output`, call the same answering path as `POST /chat`, measure latency, and write `evaluation/results/<milestone>.json` including active answer model, embedding model, and threshold
- [X] T007 [P] Create `tests/conftest.py` with fixtures that provide project-root paths and a temporary data directory for importing `ask_ai` without touching real user files
- [X] T008 [P] Create `tests/test_chat_api.py` contract test for `POST /chat` per `specs/001-migrate-vn-models/contracts/chat-api.md`: valid `{"message": "..."}` returns `200` with exactly one string `response`; missing/empty `message` returns a client error and no fabricated answer
- [ ] T009 Capture the baseline: run `python evaluation/run_eval.py --milestone original` against the current `tinyllama` + `nomic-embed-text` configuration before any model change, and confirm `evaluation/results/original.json` records all 15 answers, latencies, and the active configuration

**Checkpoint**: Foundation ready — baseline evidence exists and user stories can begin.

---

## Phase 3: User Story 2 - Reliable Retrieval of Vietnamese Content (Priority: P1)

**Goal**: Paraphrased and diacritic-free Vietnamese questions retrieve the passage that actually contains the answer, using bge-m3 with a rebuilt index and a recalibrated relevance threshold.

**Independent Test**: Ask paraphrased and diacritic-free questions from `evaluation/questions.json`; confirm the top selected passage contains the expected fact, and out-of-scope retrieval does not pass the threshold.

### Tests for User Story 2

> **NOTE: Write these tests FIRST and ensure they FAIL before implementation.**

- [X] T010 [P] [US2] Create `tests/test_retrieval.py` asserting that a `paraphrase` question and a `no_diacritics` question each select a passage containing the expected fact from `data/data.txt`, and that an `out_of_scope` question does not pass the relevance threshold

### Implementation for User Story 2

- [X] T011 [US2] Replace `OllamaEmbeddings(model="nomic-embed-text")` with `OllamaEmbeddings(model=config.embedding_model)` in `chatbox.py` so the configured `bge-m3` is used
- [X] T012 [US2] Enforce a full index rebuild on startup in `chatbox.py`: always build FAISS from current source documents and record the active embedding model with the index; never reuse vectors from a different model
- [X] T013 [US2] Replace the hardcoded `if best_score > 1` cutoff in `chatbox.py` with `config.relevance_threshold` from `specs/001-migrate-vn-models/contracts/configuration.md`
- [ ] T014 [US2] Calibrate `CHATBOT_RELEVANCE_THRESHOLD` against the in-domain and `out_of_scope` entries in `evaluation/questions.json` so in-domain questions are not falsely refused and out-of-scope questions are still declined; record the chosen value in `.env.example` and `evaluation/results/threshold-calibration.md`

**Checkpoint**: Retrieval works independently and the threshold is justified with evidence.

---

## Phase 4: User Story 1 - Accurate Vietnamese Answers (Priority: P1) 🎯 MVP core

**Goal**: The configured Qwen2.5 model answers in natural Vietnamese using only retrieved profile data, reproducing figures and names exactly and staying concise.

**Independent Test**: Ask the `direct`, `paraphrase`, `no_diacritics`, and `pronoun_variant` questions; confirm every figure/name matches and the answer reads as natural Vietnamese.

### Tests for User Story 1

- [X] T015 [P] [US1] Create `tests/test_answers.py` verifying that direct-fact questions return the exact figures/names from `data/data.txt` (for example GPA `8.30`, the configured subject score, university name, long-term goal) and that answers contain no invented facts

### Implementation for User Story 1

- [X] T016 [US1] Replace `ChatOllama(model="tinyllama")` with `ChatOllama(model=config.answer_model)` in `chatbox.py` so the configured Qwen2.5 size is used
- [X] T017 [US1] Rewrite the response prompt in `chatbox.py` to require concise Vietnamese, restrict answers to the supplied context, and return an explicit "Tôi không biết" when the context does not contain the answer
- [ ] T018 [US1] Manually verify the direct-fact acceptance scenarios from `spec.md` (GPA, one subject score, university, goal) and different forms of address (bạn, em, anh); record observations in `evaluation/results/us1-notes.md`

**Checkpoint**: User Story 1 works with the new answer model and the calibrated retrieval path.

---

## Phase 5: User Story 3 - Honest Refusal Outside Scope (Priority: P2)

**Goal**: Out-of-scope questions are declined explicitly, with no invented grades, achievements, or facts.

**Independent Test**: Ask every `out_of_scope` question; every response must be an explicit refusal and contain no fabricated detail.

### Tests for User Story 3

- [X] T019 [P] [US3] Create `tests/test_refusal.py` asserting that each `out_of_scope` question in `evaluation/questions.json` returns an explicit "Tôi không biết" style refusal and that no response introduces facts absent from `data/data.txt` or `qa.txt`

### Implementation for User Story 3

- [X] T020 [US3] Ensure the refusal branch in `chatbox.py` returns `"Tôi không biết"` when no retrieved document passes `config.relevance_threshold`, and that the prompt forbids speculation when context is unrelated
- [ ] T021 [US3] Validate all `out_of_scope` questions end to end, adjust the threshold only if a genuine false answer appears, and record false positives/negatives in `evaluation/results/refusal-notes.md`

**Checkpoint**: The chatbot refuses safely without breaking in-domain answers.

---

## Phase 6: User Story 4 - Suitable Model Size for the Machine (Priority: P2)

**Goal**: The operator can choose the answer-model size from available memory and get a clear error plus fallback guidance when the selected size does not fit.

**Independent Test**: Run the recommendation helper on the target machine, apply the recommended model, and confirm the chatbot starts and answers; then force the smallest fallback and confirm clear behavior.

### Implementation for User Story 4

- [X] T022 [P] [US4] Create `scripts/recommend_model.py` that reports available memory and prints the recommended Qwen2.5 size using the exact mapping in `specs/001-migrate-vn-models/contracts/configuration.md` (below 4 GB → `qwen2.5:1.5b`, about 4 GB → `qwen2.5:3b`, 8 GB+ → `qwen2.5:7b`, 16 GB+ → `qwen2.5:14b`)
- [X] T023 [US4] Add startup model-availability validation in `chatbox.py`: if the configured answer model is missing or cannot load, raise a clear error that names the configured model and recommends either a smaller Qwen2.5 size or an external answer service
- [ ] T024 [US4] Verify the documented fallback end to end: set `CHATBOT_ANSWER_MODEL=qwen2.5:3b`, restart, ask one in-domain question, confirm acceptable startup/answer, and record the result in `evaluation/results/us4-notes.md`

**Checkpoint**: Model-size selection is guided and failures are actionable.

---

## Phase 7: User Story 5 - Before/After Comparison for the Project Report (Priority: P3)

**Goal**: Produce a report-ready comparison across the original, embedding-changed, and answer-model-changed configurations, and retain the best one.

**Independent Test**: Run the fixed 15-question set against all three milestones and confirm the generated table identifies the best configuration with scores on factual correctness, refusal, naturalness, and latency.

### Implementation for User Story 5

- [X] T025 [P] [US5] Create `evaluation/report.py` that aggregates `evaluation/results/original.json`, `embedding-changed.json`, and `answer-model-changed.json` into the comparison table defined in `specs/001-migrate-vn-models/contracts/evaluation.md` (factual accuracy, refusal rate, naturalness, average latency, selected configuration)
- [ ] T026 [US5] Run `python evaluation/run_eval.py --milestone embedding-changed` with `bge-m3` and the calibrated threshold, then record the milestone's active configuration in `evaluation/results/embedding-changed.json`
- [ ] T027 [US5] Run `python evaluation/run_eval.py --milestone answer-model-changed` with the selected Qwen2.5 size on top of the embedding change, then record the milestone's active configuration in `evaluation/results/answer-model-changed.json`
- [ ] T028 [US5] Generate `evaluation/results/comparison.md` via `evaluation/report.py`, score each answer on the four criteria, identify the best configuration, and record the retained configuration (per `SC-006`)

**Checkpoint**: All three milestones are comparable and the best configuration is justified.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Final consistency, verification, and report quality

- [X] T029 [P] Audit `requirements.txt`, `chatbox.py`, `.env.example`, and `app.py` for any remaining Qwen3 reference or stale `nomic-embed-text`/`tinyllama` default; remove or replace it
- [X] T030 [P] Run the full pytest suite (`pytest tests/`) and fix failures in `tests/test_retrieval.py`, `tests/test_answers.py`, `tests/test_refusal.py`, and `tests/test_chat_api.py`
- [ ] T031 Run the full `specs/001-migrate-vn-models/quickstart.md` validation and confirm every artifact-checklist item (fixed question set, three result files, comparison table, clean `requirements.txt`)
- [ ] T032 [P] Review answers across all evaluation results for conciseness and natural Vietnamese; adjust the prompt in `chatbox.py` only if the evaluation shows verbosity or awkward phrasing, then re-run the affected milestone

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories; T009 baseline MUST run before any model change
- **User Story 2 (Phase 3, P1)**: Depends on Foundational — the embedding change must precede the answer-model change per spec §8 rollout order
- **User Story 1 (Phase 4, P1)**: Depends on Foundational and Phase 3 (uses the calibrated retrieval path)
- **User Story 3 (Phase 5, P2)**: Depends on Phase 3 (threshold) and Phase 4 (answer model)
- **User Story 4 (Phase 6, P2)**: Depends on Phase 4 (answer model configuration); independent of US3
- **User Story 5 (Phase 7, P3)**: Depends on Phases 3 and 4 for the two post-change milestones; baseline comes from T009
- **Polish (Phase 8)**: Depends on all desired stories

### User Story Dependencies

- **US2 (P1)**: Independent after Foundational; it is the first model change by design
- **US1 (P1)**: Independent user value, but shares `chatbox.py` with US2, so implement after US2 to avoid conflicting edits
- **US3 (P2)**: Builds on US2's threshold and US1's prompt; independently testable via the out-of-scope set
- **US4 (P2)**: Builds on US1's configured model; independently testable via the recommendation helper and fallback run
- **US5 (P3)**: Integrates US2 and US1; independently testable via the comparison table

### Within Each User Story

- Tests MUST be written and fail before the corresponding implementation
- Configuration/model changes before prompt tuning
- Threshold calibration before refusal validation
- Milestone run after the change it measures
- Story complete and validated before moving to the next priority

### Parallel Opportunities

- Setup: T002 and T003 can run in parallel after T001
- Foundational: T005, T006, T007, T008 can run in parallel; T009 waits for T006 and the existing config
- US2: T010 is parallel with nothing that edits `chatbox.py`; T011–T014 are sequential because they share `chatbox.py`
- US1: T015 is parallel-safe; T016–T018 sequential
- US3: T019 parallel-safe; T020–T021 sequential
- US4: T022 is parallel-safe with T023; T024 waits for T023
- US5: T025 is parallel-safe; T026–T028 sequential
- Polish: T029, T030, T032 can run in parallel; T031 runs last

---

## Parallel Example: Foundational Phase

```bash
# After T004 config loading:
Task: "Create evaluation/questions.json per contracts/evaluation.md"
Task: "Implement evaluation/run_eval.py CLI"
Task: "Create tests/conftest.py fixtures"
Task: "Create tests/test_chat_api.py contract test"
```

## Parallel Example: User Story 2

```bash
# Write the retrieval test first:
Task: "Create tests/test_retrieval.py for paraphrase and diacritic-free selection"

# Then, sequentially in chatbox.py:
Task: "Switch embeddings to config.embedding_model"
Task: "Enforce full index rebuild at startup"
Task: "Replace hardcoded score cutoff with config.relevance_threshold"
Task: "Calibrate threshold and record in threshold-calibration.md"
```

---

## Implementation Strategy

### MVP First (Core: Setup + Foundational + US2 + US1)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational, including the **original baseline run (T009)**
3. Complete Phase 3: US2 (embedding change + threshold)
4. Complete Phase 4: US1 (answer-model change + prompt)
5. **STOP and VALIDATE**: run `pytest tests/`, ask the direct/paraphrase/diacritic-free questions, and confirm exact figures and natural Vietnamese
6. Deploy/demo the core improvement

Both P1 stories form the MVP because retrieval alone cannot produce a user-visible answer and the answer model alone cannot fix wrong retrieval.

### Incremental Delivery

1. Setup + Foundational → baseline evidence captured
2. Add US2 → validate retrieval and threshold → demo retrieval improvement
3. Add US1 → validate answers → demo (MVP)
4. Add US3 → validate refusal → demo safety
5. Add US4 → validate size selection and fallback → demo portability
6. Add US5 → generate comparison table → report-ready evidence
7. Polish → full suite and quickstart validation

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together (T009 baseline must happen before model edits)
2. After Foundational:
   - Developer A: US2 (embedding/threshold) — must go first
   - Developer B: US3 tests and US5 report aggregation in parallel (do not edit `chatbox.py` until US2 lands)
   - Developer C: US4 helper script and US1 test in parallel
3. Once US2 lands: Developer A/B continue US1; Developer C validates US4
4. Complete US5 once US2 and US1 are both merged

---

## Notes

- `[P]` tasks touch different files and have no incomplete dependencies
- `[Story]` labels map every story-phase task back to `spec.md` for traceability
- `chatbox.py` is shared by US2, US1, US3, and parts of US4; those edits must be sequential, not parallel
- The baseline (T009) is mandatory before any model change so the comparison in US5 is valid
- Change one thing at a time: embedding first, then answer model, per spec §8
- Commit after each task or logical group
- Stop at any checkpoint to validate the story independently
