# Contract: Evaluation Harness

**Feature**: `001-migrate-vn-models` | **Date**: 2026-11-02

A repeatable, manually scored evaluation used to compare three milestones and produce a report-ready table.

## Input: question set

File: `evaluation/questions.json`

```json
{
  "questions": [
    {
      "id": "Q01",
      "question": "GPA hiện tại của bạn là bao nhiêu?",
      "category": "direct",
      "expected_answer": "8.30",
      "expected_refusal": false
    },
    {
      "id": "Q12",
      "question": "Giá vàng hôm nay bao nhiêu?",
      "category": "out_of_scope",
      "expected_answer": null,
      "expected_refusal": true
    }
  ]
}
```

### Coverage requirements

| Category | Minimum count | Purpose |
|----------|---------------|---------|
| `direct` | 4 | Clear facts: GPA, a subject score, university, goal |
| `paraphrase` | 3 | Different wording from `qa.txt` |
| `no_diacritics` | 2 | Typo, abbreviation, or diacritic-free Vietnamese |
| `pronoun_variant` | 2 | Uses bạn / em / anh |
| `out_of_scope` | 3 | Correct answer is refusal |

Total: about 15 questions, fixed across all milestones.

## Runner

Command: `python evaluation/run_eval.py --milestone <label>`

| Argument | Required | Description |
|----------|----------|-------------|
| `--milestone` | Yes | One of `original`, `embedding-changed`, `answer-model-changed` |
| `--output` | No | Output directory, default `evaluation/results/` |

The runner calls the same answering path used by `POST /chat` for each question, measures latency, and writes raw responses. It does not auto-score correctness; the operator scores results to avoid an unvalidated automatic Vietnamese grader.

## Output

File: `evaluation/results/<milestone>.json` plus a Markdown table.

Per-question fields: `question_id`, `answer`, `latency_seconds`, `factual_correct`, `refusal_correct`, `natural_vietnamese`, `notes`.

### Comparison table

| Milestone | Factual accuracy | Refusal rate | Naturalness | Avg latency | Selected |
|-----------|------------------|--------------|-------------|-------------|----------|
| original | | | | | |
| embedding-changed | | | | | |
| answer-model-changed | | | | | |

## Scoring rules

| Criterion | Pass condition |
|-----------|----------------|
| Factual correctness | Every figure and proper name matches the profile data / expected answer |
| Refusal correctness | Out-of-scope question is declined without invented facts |
| Natural Vietnamese | Response reads smoothly, correct grammar and context |
| Speed | Operator judges the wait acceptable on the target machine |

## Invariants

- The question set must not change between milestones.
- Each result record must include the active configuration (answer model, embedding model, threshold) for attribution.
- The comparison must let the operator identify the best configuration and retain it.
