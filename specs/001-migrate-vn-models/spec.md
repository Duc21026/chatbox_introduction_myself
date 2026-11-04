# Feature Specification: Migrate Chatbot to Vietnamese-Capable Models

**Feature Branch**: `001-migrate-vn-models`

**Created**: 2026-11-02

**Status**: Draft

**Input**: User description: "Đổi model cho chatbot giới thiệu bản thân" — replace the current English-centric answer model (tinyllama) and embedding model (nomic-embed-text) with Vietnamese-capable alternatives (Qwen2.5 family and bge-m3), re-index the knowledge base, recalibrate the relevance threshold, and evaluate before/after quality with a fixed question set.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Accurate Vietnamese Answers (Priority: P1)

A visitor asks the self-introduction chatbot about the student's GPA, subject scores, university, strengths, or goals. The chatbot answers in natural Vietnamese using only the supplied profile data, with numbers and proper names reproduced exactly.

**Why this priority**: The core purpose of the chatbot is to present the student's profile correctly. Wrong grades or unnatural Vietnamese defeat the feature; every other improvement depends on this.

**Independent Test**: Ask a fixed set of in-domain questions whose answers are present in the profile data and confirm that every number and name matches, and that the response reads as natural Vietnamese.

**Acceptance Scenarios**:

1. **Given** a question whose answer exists in the profile data, **When** the visitor asks it, **Then** the answer contains the correct figures and names and no invented details.
2. **Given** a question paraphrased differently from the stored questions, **When** the visitor asks it, **Then** the chatbot retrieves the relevant profile information and answers correctly.
3. **Given** a question written without diacritics, with typos, or with abbreviations, **When** the visitor asks it, **Then** the chatbot still understands and answers correctly.
4. **Given** the visitor uses different forms of address (bạn, em, anh), **When** they ask the same question, **Then** the answer remains correct and appropriately phrased.

---

### User Story 2 - Reliable Retrieval of Vietnamese Content (Priority: P1)

When a question is not an exact match to a stored question, the chatbot finds the most relevant Vietnamese passage from the profile documents instead of an unrelated passage or nothing.

**Why this priority**: Retrieval decides whether the answer model sees the right facts. A strong answer model cannot correct retrieval that selects the wrong passage, so retrieval quality is jointly critical with answer quality.

**Independent Test**: Ask paraphrased and diacritic-free Vietnamese questions and verify that the passage selected for the answer is the one that actually contains the answer.

**Acceptance Scenarios**:

1. **Given** a paraphrased Vietnamese question, **When** retrieval runs, **Then** the top selected passage contains the information needed to answer.
2. **Given** the knowledge base is re-indexed with the new retrieval representation, **When** the chatbot starts, **Then** all indexed content is rebuilt from the current profile data and no stale index is reused.
3. **Given** the relevance threshold is applied to the new retrieval representation, **When** an out-of-scope question is asked, **Then** the chatbot declines instead of retrieving an unrelated passage.

---

### User Story 3 - Honest Refusal Outside Scope (Priority: P2)

A visitor asks something the profile data does not cover. The chatbot says it does not know rather than inventing an answer.

**Why this priority**: Fabricated grades or achievements are the most damaging failure for a personal introduction chatbot, but this depends on retrieval and answer behavior being in place first.

**Independent Test**: Ask a set of questions unrelated to the profile and confirm every response is a refusal or an explicit statement of not knowing.

**Acceptance Scenarios**:

1. **Given** a question with no supporting content in the profile data, **When** the visitor asks it, **Then** the chatbot responds that it does not know and adds no invented facts.
2. **Given** an ambiguous question that is only loosely related to the profile, **When** the visitor asks it, **Then** the chatbot either answers strictly from available content or declines, without speculation.

---

### User Story 4 - Suitable Model Size for the Machine (Priority: P2)

The operator runs the chatbot on a machine with limited memory and needs the selected answer model to fit the available memory while remaining responsive.

**Why this priority**: A model that is too large will fail to load or be unusably slow; a model that is too small will not deliver the quality gains. The choice must follow the machine's capacity.

**Independent Test**: Determine available memory on the target machine, select the corresponding model size, and confirm the chatbot loads and answers within an acceptable wait.

**Acceptance Scenarios**:

1. **Given** available memory below 4 GB, **When** the operator configures the chatbot, **Then** the smallest supported model size is selected and the system remains usable (with a documented recommendation to upgrade or use an external service).
2. **Given** about 4 GB of available memory, **When** the operator configures the chatbot, **Then** the compact mid-size model is selected.
3. **Given** 8 GB or more of available memory, **When** the operator configures the chatbot, **Then** the default large model is selected.
4. **Given** 16 GB or more of available memory, **When** the operator configures the chatbot, **Then** the largest supported model size is selected.

---

### User Story 5 - Before/After Comparison for the Project Report (Priority: P3)

The operator needs evidence that the migration improved quality and needs to record it in the project report. They run the same fixed question set against three configurations and compare results.

**Why this priority**: The comparison supports the report and justifies keeping the new configuration, but the chatbot already delivers value before the report is written.

**Independent Test**: Run the fixed question set against the original configuration, after the retrieval change, and after the answer-model change, and produce a comparison table.

**Acceptance Scenarios**:

1. **Given** a fixed set of about 15 real questions covering in-domain answers, paraphrases, typo/diacritic-free variants, varied forms of address, and out-of-scope questions, **When** the operator evaluates a configuration, **Then** each answer is scored on factual correctness, appropriate refusal, natural Vietnamese, and response speed.
2. **Given** results from all three configurations, **When** the operator compares them, **Then** the best-performing configuration is identified and retained.
3. **Given** changes are applied incrementally (retrieval first, then answer model), **When** the operator compares milestones, **Then** the contribution of each change is distinguishable.

---

### Edge Cases

- What happens when the profile data contains conflicting values for the same fact? The chatbot must not silently choose; it should answer with the value(s) present and avoid inventing a resolution.
- What happens when the same question is matched both by the exact/fuzzy question store and by document retrieval? The chatbot must produce one consistent answer, not duplicate or contradictory content.
- What happens when the new retrieval representation scores an in-domain question above the relevance threshold (false refusal)? The threshold must be recalibrated so genuinely relevant questions are not rejected.
- What happens when the new retrieval representation scores an out-of-scope question below the threshold (false answer)? The threshold must be recalibrated so unrelated questions are still declined.
- What happens when a document is unreadable, empty, or in an unsupported format? It is skipped and the remaining content is still indexed.
- What happens when the selected model cannot be loaded due to insufficient memory? The operator must be able to fall back to a smaller supported size without changing the approach.
- What happens when a response is much longer than needed? The answer must stay concise and focused on the question.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The chatbot MUST replace the current English-centric answer model with a Vietnamese-capable model from the Qwen2.5 family.
- **FR-002**: The chatbot MUST default to the 7B answer model, with the 3B model as the documented fallback for machines with about 4 GB available memory.
- **FR-003**: The system MUST support selecting the answer model size according to available memory: 1.5B below 4 GB, 3B at about 4 GB, 7B at 8 GB or more, and 14B at 16 GB or more.
- **FR-004**: The chatbot MUST replace the current document retrieval representation with bge-m3.
- **FR-005**: The system MUST rebuild the entire retrieval index from the current profile data when the retrieval representation changes; no vector produced by the previous representation may remain in use.
- **FR-006**: The system MUST define the relevance threshold as a configurable value that can be recalibrated for the new retrieval representation.
- **FR-007**: The chatbot MUST decline with an explicit "I don't know" style response when no sufficiently relevant content is found.
- **FR-008**: The answer model MUST restrict its response to the retrieved content and MUST NOT invent facts, figures, or names.
- **FR-009**: The response prompt MUST instruct the model to answer concisely.
- **FR-010**: The system MUST preserve the existing exact/fuzzy question matching behavior for questions already stored in the question-answer data.
- **FR-011**: The system MUST expose the evaluation question set and the scoring criteria so the operator can repeat the comparison across configurations.
- **FR-012**: The system MUST allow the operator to run the evaluation before the retrieval change, after the retrieval change, and after the answer-model change, and record results in a comparison table.
- **FR-013**: The requirements list MUST NOT include the accidental `qwen3:1.7b` terminal command; the runtime configuration must not depend on any Qwen3 model.
- **FR-014**: When available memory is insufficient even for the smallest supported answer model, the system MUST report this clearly and recommend upgrading the machine or using an external answer service.

### Key Entities *(include if feature involves data)*

- **Profile Data**: The self-introduction knowledge base loaded from the `data` folder (text, spreadsheet, document, and PDF formats) that supplies facts about the student.
- **Question-Answer Pairs**: Curated stored questions and canonical answers used for exact and fuzzy matching.
- **Retrieval Index**: The searchable representation of profile data built from document chunks; must be fully rebuilt when the retrieval representation changes.
- **Configuration**: The selected answer model size, retrieval model, and relevance threshold used at runtime.
- **Evaluation Question Set**: Roughly 15 real questions spanning direct facts, paraphrases, typo/diacritic-free variants, varied forms of address, and out-of-scope questions.
- **Evaluation Result**: Per-question scores for factual correctness, appropriate refusal, natural Vietnamese, and response speed, grouped by configuration.
- **Comparison Table**: Before/after summary across the three evaluated configurations used in the project report.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: At least 90% of in-domain questions in the evaluation set return answers whose figures and proper names exactly match the profile data.
- **SC-002**: 100% of out-of-scope questions in the evaluation set are declined without any fabricated facts.
- **SC-003**: At least 80% of paraphrased and diacritic-free variants in the evaluation set are answered correctly, demonstrating retrieval robustness.
- **SC-004**: Every evaluated answer is judged readable and natural in Vietnamese by the operator, with no responses that read as translated English or broken grammar.
- **SC-005**: The chatbot responds quickly enough that the operator considers the wait acceptable for a conversational introduction on the target machine.
- **SC-006**: The comparison table shows the post-migration configuration scoring at least as well as the original configuration on factual correctness and refusal, and better on natural Vietnamese.
- **SC-007**: A new operator can determine the correct model size for a given machine from documented memory guidance without trial and error.

## Assumptions

- The chatbot runs on a single local machine and uses locally hosted models; no cloud service is required for the primary path.
- The target machine's available memory can be determined before configuration; the model-size guidance in the feature description applies.
- A dedicated GPU is optional; when present it improves speed, but memory capacity remains the binding constraint for model size.
- The profile knowledge base is small (a few KB to a few MB), so index rebuild time and storage are not significant concerns.
- The retrieval index is rebuilt at application startup, so replacing the retrieval representation and restarting is sufficient to eliminate stale vectors.
- The existing question-answer matching layer remains valuable and is kept alongside retrieval.
- External claims about Vietnamese quality for each model family are taken from public comparisons and have not been verified on the target machine; the evaluation step is the source of truth.
- The evaluation is performed manually by the operator with the fixed question set; no automated scoring service is assumed.
- `requirements.txt` may retain unrelated dependencies, but the accidental `qwen3:1.7b` line is treated as documentation debt and must not be relied on at runtime.
