# Feature Specification: RAG Document Ingestion and Editing

**Feature Branch**: `002-rag-doc-ingestion`

**Created**: 2026-11-04

**Status**: Draft

**Input**: User description: "cho tôi quy trình thêm và sửa cấu trúc thêm và sửa text cho chatbot" — define how an operator adds new text documents, updates or removes existing documents, and how user questions are normalized into the same representation so retrieval stays accurate for a Vietnamese RAG chatbot running local models.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Add a New Document to the Knowledge Base (Priority: P1)

An operator has a new text document (for example a policy or regulation file) and wants the chatbot to answer questions from it. They provide the document with a source name, and the chatbot makes its content searchable. Questions that match the new content are answered from it, while the rest of the knowledge base continues to work unchanged.

**Why this priority**: Without ingestion there is no knowledge base at all. Adding content is the foundational workflow that every other capability depends on.

**Independent Test**: Add one document whose facts are not present anywhere else, then ask a question answerable only from that document and confirm the answer uses it correctly.

**Acceptance Scenarios**:

1. **Given** an empty or existing knowledge base, **When** the operator adds a text document under a unique source name, **Then** the document becomes searchable and a question about its content is answered from it.
2. **Given** a document longer than a single retrieval unit, **When** it is added, **Then** its content is divided into coherent, overlapping pieces so no answer-bearing sentence is lost at a boundary.
3. **Given** a document with section headings or numbered clauses, **When** it is added, **Then** divisions follow those structural boundaries where possible rather than cutting through the middle of a clause.
4. **Given** a document that was already added under the same source name, **When** the operator adds it again, **Then** the knowledge base does not contain duplicate copies of its content.

---

### User Story 2 - Update or Remove an Existing Document (Priority: P1)

An operator needs to correct, replace, or retire a document that is already in the knowledge base. After the change, the chatbot answers only from the current version: no answer may come from the replaced content.

**Why this priority**: Outdated policy answers are as harmful as missing answers. Safe replacement is required for the knowledge base to remain trustworthy over time.

**Independent Test**: Add a document with a distinctive fact, replace it with a version where that fact changed, then ask about the old and new facts and confirm only the new fact is answered.

**Acceptance Scenarios**:

1. **Given** a document already in the knowledge base, **When** the operator replaces it with a new version, **Then** all content from the previous version becomes unretrievable and the new version is searchable.
2. **Given** a replacement is in progress, **When** the operation completes, **Then** the knowledge base contains exactly one current version of the document, not a mixture of old and new pieces.
3. **Given** a document that is no longer relevant, **When** the operator removes it, **Then** none of its content is returned by later searches.
4. **Given** a failed update (for example an unreadable source), **When** the operation ends, **Then** the previous version remains intact and the operator is told the update did not apply.
5. **Given** the chatbot is restarted after an add, update, or removal, **When** it answers questions, **Then** it reflects the latest knowledge base state.

---

### User Story 3 - Ask Questions in Messy Vietnamese (Priority: P1)

A visitor types a question with repeated letters, repeated punctuation, extra spaces, missing diacritics, or spelling mistakes. The chatbot understands the intended question and retrieves the same content it would have retrieved for a clean question.

**Why this priority**: Real chat input is noisy. If retrieval compares clean document text against unclean question text, relevant content is missed even when the answer exists.

**Independent Test**: Take a fixed set of clean questions, create noisy variants of each (repeated characters, no diacritics, extra whitespace, punctuation noise), and confirm the same relevant content is retrieved for every variant.

**Acceptance Scenarios**:

1. **Given** a question with repeated letters such as `choooo` or `đượcccc`, **When** it is submitted, **Then** the repeated characters are reduced without damaging legitimate double letters in Vietnamese words.
2. **Given** a question with repeated punctuation or irregular casing, **When** it is submitted, **Then** the retrieval form is normalized consistently with how documents are indexed.
3. **Given** a question with extra whitespace or decomposed Vietnamese diacritics, **When** it is submitted, **Then** it is normalized to a single consistent form before retrieval.
4. **Given** a question written without diacritics or with a spelling mistake, **When** it is submitted, **Then** the system produces a corrected search form and still finds the relevant content.
5. **Given** any question, **When** an answer is generated and displayed, **Then** the original wording, capitalization, and proper names are preserved for the answer and for display.

---

### User Story 4 - Understand Where an Answer Came From (Priority: P2)

An operator investigating a wrong answer can see which source documents and content pieces were used, what the normalized question looked like, and whether the knowledge base contains the expected document.

**Why this priority**: Without visibility the operator cannot tell whether a bad answer comes from missing content, bad question cleaning, or bad retrieval, and cannot fix it.

**Independent Test**: Ask a question that produces a poor answer and confirm the operator can identify the source and retrieved pieces that led to it.

**Acceptance Scenarios**:

1. **Given** a question is answered, **When** the operator inspects retrieval details, **Then** they can see the source names and content pieces used to build the answer.
2. **Given** a question is cleaned before retrieval, **When** the operator inspects the search form, **Then** they can compare the original question with the normalized form.
3. **Given** an operator suspects a document is missing, **When** they list the knowledge base contents, **Then** they can see which source names are currently indexed.

---

### User Story 5 - Import Content from PDF (Priority: P2)

An operator has a text-based PDF and wants to add it without manually copying the text. When the PDF contains only scanned images, the operator is told that text extraction is not possible rather than receiving an empty document.

**Why this priority**: Many real documents arrive as PDFs, but text documents are the primary path, so PDF support is valuable without being foundational.

**Independent Test**: Add a text-based PDF containing a unique fact and ask about it; then try a scanned PDF and confirm a clear failure message.

**Acceptance Scenarios**:

1. **Given** a text-based PDF, **When** the operator imports it, **Then** its extracted text becomes searchable like a text document.
2. **Given** a scanned or image-only PDF, **When** the operator imports it, **Then** the system reports that no usable text was extracted and does not add an empty document.
3. **Given** a PDF with extraction artifacts such as broken diacritics, **When** the operator inspects retrieval, **Then** the affected source can be identified for correction or re-import.

---

### Edge Cases

- A document is empty, whitespace-only, or unreadable: it is rejected with a clear message and the existing knowledge base is unchanged.
- A document is very short (shorter than the normal retrieval unit): it is stored as a single piece rather than discarded.
- Two different documents share the same source name: the system treats them as the same document and requires an explicit replace, preventing silent duplication.
- A document contains conflicting statements internally: retrieval returns the relevant passages and the answer does not invent a resolution.
- A question normalizes to an empty string (for example only punctuation): the system asks the visitor to rephrase instead of searching.
- Question correction changes meaning (for example a name or an abbreviation): the original question remains the source of truth for the answer, and correction is used only for search.
- The knowledge base is empty: the chatbot declines to answer rather than answering from general knowledge.
- A failure occurs midway through a replacement: the previous version remains available and no partially updated state is left behind.
- The same document is added concurrently twice: the final state contains one current version, not duplicates.
- Retrieval returns no sufficiently relevant content: the chatbot says it does not know instead of answering from unrelated content.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST allow an operator to add a text document to the knowledge base under an explicit, unique source name.
- **FR-002**: The system MUST divide added documents into coherent, overlapping retrieval pieces sized so that a complete answer is normally contained in one piece.
- **FR-003**: The system MUST prefer document structure (paragraphs, lines, sentences, headings, numbered clauses) as division boundaries instead of cutting through the middle of a sentence or clause.
- **FR-004**: The system MUST store, for each retrieval piece, its original text and a reference to its source document.
- **FR-005**: The system MUST persist the knowledge base so that added, updated, and removed content survives a restart.
- **FR-006**: The system MUST apply the same text normalization to documents being indexed and to user questions being searched, so both sides use a consistent form.
- **FR-007**: The normalization MUST handle decomposed Vietnamese diacritics, repeated characters, repeated punctuation, casing, and extra whitespace.
- **FR-008**: The normalization MUST reduce runs of three or more identical characters while preserving legitimate double letters in Vietnamese words.
- **FR-009**: The system MUST keep the original text of documents and questions for answer generation and display, using the normalized form only for search.
- **FR-010**: The system MUST support query rewriting that corrects spelling and adds missing Vietnamese diacritics before search when correction is needed.
- **FR-011**: The system MUST replace an existing document by removing all of its previous retrieval pieces before adding the new version, so no content from the old version remains retrievable.
- **FR-012**: The system MUST remove all retrieval pieces of a source document when that document is deleted.
- **FR-013**: The system MUST treat re-adding a document under an existing source name as an update, not as an additional copy.
- **FR-014**: The system MUST leave the previous document version intact when an add, update, or removal fails.
- **FR-015**: The system MUST reject empty, whitespace-only, or unreadable documents with a clear failure message and without changing the knowledge base.
- **FR-016**: The system MUST accept text-based PDF documents and MUST report when a PDF contains no extractable text.
- **FR-017**: The system MUST retrieve the most relevant content pieces for a normalized question and combine them into the answer context.
- **FR-018**: The system MUST generate answers using only the retrieved content and MUST decline with an explicit "do not know" response when the retrieved content does not support an answer.
- **FR-019**: The system MUST preserve the visitor's original question, including capitalization and proper names, when generating and displaying the answer.
- **FR-020**: The system MUST provide retrieval diagnostics that show the sources and content pieces used for an answer and the normalized form of the question.
- **FR-021**: The system MUST allow an operator to list which source documents are currently indexed.
- **FR-022**: The system MUST allow the number of retrieved content pieces used per answer to be configured, increasing it when an answer is spread across multiple pieces.
- **FR-023**: The system MUST ask the visitor to rephrase when a question normalizes to nothing searchable.

### Key Entities *(include if feature involves data)*

- **Source Document**: A named text or PDF input owned by the knowledge base; identified by its source name and used as the unit for update and removal.
- **Retrieval Piece**: A coherent, overlapping portion of a source document; carries the original text and a reference to its source.
- **Knowledge Base**: The persisted collection of all currently indexed source documents and their retrieval pieces.
- **Normalized Question**: The search-only form of a visitor question after Unicode, repetition, punctuation, casing, whitespace, and spelling correction.
- **Original Question**: The visitor's unmodified wording, used for answer generation and display.
- **Retrieved Content**: The set of content pieces selected as context for one answer, with their source references.
- **Ingestion Result**: The outcome of an add, update, or removal, including success or a clear failure reason.
- **Retrieval Diagnostic**: The recorded normalized question, selected pieces, and source names for an answered question.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator can add a new text document and get a correct answer from its content in a single add-then-ask session without manual data editing.
- **SC-002**: After replacing a document, 100% of test questions about removed facts are no longer answered from the old content.
- **SC-003**: After deleting a document, 100% of test questions about its content receive a decline or an answer from other legitimate sources, never from the deleted content.
- **SC-004**: Re-adding the same document under the same source name leaves exactly one current version and produces no duplicate answers.
- **SC-005**: At least 95% of noisy question variants (repeated characters, missing diacritics, extra whitespace, punctuation noise) retrieve the same relevant content as their clean counterparts.
- **SC-006**: At least 90% of in-scope questions across the knowledge base are answered with figures and names matching the source documents.
- **SC-007**: 100% of out-of-scope questions are declined without fabricated facts.
- **SC-008**: All added, updated, and removed content is reflected correctly after a restart, with no stale content returned.
- **SC-009**: An operator can identify the source and retrieved pieces behind a poor answer without reading application internals.
- **SC-010**: A text-based PDF can be imported and queried with the same success as an equivalent text document, while a scanned PDF is rejected with a clear message.

## Assumptions

- The feature extends the existing self-introduction chatbot rather than creating a separate application.
- The primary language is Vietnamese; normalization and query correction are tuned for Vietnamese input.
- A single operator manages the knowledge base; no multi-user permissions or approval workflow is required.
- The knowledge base is small (a few KB to a few MB), so full replacement on update is simpler and safer than partial editing.
- The default retrieval piece size is 500-1000 characters with 10-20% overlap, and the default number of retrieved pieces per answer is three, increased to five when information is scattered.
- Local models already available to the chatbot are used for embeddings and answer generation; no cloud service is required.
- Update and removal are performed through the operator's existing interface (command line or script); a dedicated management web interface is out of scope for this feature.
- Scanned PDFs are not OCR-processed in this feature; the operator must OCR them beforehand.
- Hybrid keyword-plus-semantic search and a graphical interface are deferred to later work.
- Existing exact/fuzzy question-answer matching, if present, remains in place alongside document retrieval.
- Retrieval diagnostics may be exposed as console output or logs; no separate monitoring system is required.
