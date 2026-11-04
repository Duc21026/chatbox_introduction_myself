# Research: Migrate Chatbot to Vietnamese-Capable Models

**Feature**: `001-migrate-vn-models` | **Date**: 2026-11-02

All unknowns from the Technical Context have been resolved. No `NEEDS CLARIFICATION` markers remain.

## R1. Answer model family and size selection

- **Decision**: Use the Qwen2.5 instruction-tuned family through Ollama, defaulting to `qwen2.5:7b`, with size chosen by available memory: `qwen2.5:1.5b` (< 4 GB), `qwen2.5:3b` (~4 GB), `qwen2.5:7b` (8 GB+), `qwen2.5:14b` (16 GB+).
- **Rationale**: Qwen2.5 is trained on multilingual data including Vietnamese, produces more natural Vietnamese than same-size English-first models, follows instructions well (important for RAG "answer only from context"), and offers a size ladder that preserves the same integration path. Ollama is already the runtime used by the project.
- **Alternatives considered**:
  - Qwen3 4B/8B — stronger reasoning but unnecessary for short Q&A; thinking mode adds latency. Rejected.
  - Llama 3.1 8B — solid multilingual support but less natural Vietnamese in public comparisons. Rejected.
  - Gemma 3 4B — fast but Vietnamese reportedly stiff. Rejected.
  - Phi 3.5 — strong English, not a Vietnamese strength. Rejected.

## R2. Embedding model

- **Decision**: Replace `nomic-embed-text` with `bge-m3` for retrieval embeddings.
- **Rationale**: bge-m3 covers 100+ languages including Vietnamese, handles longer passages with less meaning loss when chunking, and is available directly through Ollama. Retrieval quality is the main determinant of RAG correctness; an English-biased embedding would keep sending the answer model the wrong Vietnamese passage.
- **Alternatives considered**:
  - Vietnamese-specialized PhoBERT-family embeddings — potentially stronger on pure Vietnamese benchmarks, but require word segmentation, extra setup, and do not run directly through Ollama; unjustified for a few-KB knowledge base. Rejected.
  - Keep `nomic-embed-text` — fails the retrieval-robustness goal for Vietnamese. Rejected.

## R3. Index rebuild strategy after changing embeddings

- **Decision**: Rebuild the FAISS index from source documents at every application startup, discarding any prior vectors; do not persist or migrate old vectors.
- **Rationale**: `chatbox.py` already builds the index in memory at import time, so startup rebuild is natural. Vectors from different embedding models are incompatible, so reuse is unsafe. The knowledge base is small, making rebuild cost negligible.
- **Alternatives considered**:
  - Persist and reload the old index — incompatible vector space, would silently corrupt retrieval. Rejected.
  - Versioned index files — unnecessary overhead for a few-KB dataset. Rejected.

## R4. Relevance threshold recalibration

- **Decision**: Expose the relevance cutoff as a configurable value, and determine the new value empirically by scoring a labeled set of in-domain and out-of-scope questions under bge-m3 before finalizing it.
- **Rationale**: Each embedding model produces a different score distribution, so the existing hardcoded cutoff (`> 1` on a distance score) will misclassify under bge-m3. Choosing a new value by measurement avoids both false refusals and fabricated answers.
- **Alternatives considered**:
  - Keep the old threshold — unsupported across embedding changes. Rejected.
  - Remove the cutoff and always answer — violates the refusal requirement. Rejected.
  - Fixed universal threshold from documentation — no guarantee it matches this dataset. Rejected.

## R5. Configuration mechanism

- **Decision**: Read answer-model name, embedding-model name, and relevance threshold from environment variables with documented defaults (`qwen2.5:7b`, `bge-m3`, and a threshold value set after calibration).
- **Rationale**: The operator must switch model sizes per machine without editing source, and must be able to tune the threshold after the embedding change. Environment variables keep the existing single-process design and avoid new dependencies.
- **Alternatives considered**:
  - Edit constants in `chatbox.py` per machine — error-prone and hard to record in evaluation runs. Rejected.
  - Full config file/service — overkill for a single local chatbot. Rejected.

## R6. Prompt behavior after switching to a larger model

- **Decision**: Keep the "answer only from supplied data; otherwise say you don't know; do not fabricate" constraints and add an explicit conciseness instruction.
- **Rationale**: Larger models follow instructions better but tend to produce longer answers. The product is a short self-introduction chatbot, so brevity must be stated explicitly. The anti-fabrication clause remains the core safety behavior.
- **Alternatives considered**:
  - Reuse the current prompt unchanged — risks verbose, less focused answers. Rejected.
  - Few-shot examples — unnecessary for a small, clear task. Rejected.

## R7. Evaluation methodology and tooling

- **Decision**: Maintain a fixed set of about 15 real Vietnamese questions spanning (a) direct facts with clear answers, (b) paraphrases of `qa.txt`, (c) missing-diacritic/typo/abbreviation variants, (d) varied forms of address, and (e) out-of-scope questions. Run it against three configurations: original, after embedding change, after answer-model change. Score each answer on factual correctness, appropriate refusal, natural Vietnamese, and speed; record results in a comparison table.
- **Rationale**: The comparison isolates the contribution of each change, matches the spec's success criteria, and produces report-ready evidence. Manual scoring is appropriate for a small set and avoids building an unreliable automatic grader.
- **Alternatives considered**:
  - Automatic LLM-as-judge scoring — adds cost/complexity and is itself unvalidated for Vietnamese. Rejected for this scope.
  - Ad-hoc spot checks — not repeatable, not comparable. Rejected.

## R8. Handling the accidental Qwen3 line and dependency hygiene

- **Decision**: Remove the stray `ollama run qwen3:1.7b` line from `requirements.txt`, and ensure runtime code references only the configured Qwen2.5 and bge-m3 model names.
- **Rationale**: The line is a pasted terminal command, not a Python dependency; leaving it can confuse setup and implies a model the code does not use.
- **Alternatives considered**:
  - Leave it as harmless text — still misleading and contradicts the documented runtime. Rejected.

## R9. Verification approach

- **Decision**: Add pytest checks for retrieval passage selection, out-of-scope refusal, and the `POST /chat` JSON contract, plus the evaluation harness for qualitative scoring.
- **Rationale**: These cover the behaviors most likely to regress during a model swap and keep the change verifiable without a full UI test stack.
- **Alternatives considered**:
  - Only manual evaluation — misses API-level regressions. Rejected.
  - Full browser end-to-end tests — disproportionate for a static form and single endpoint. Rejected.
