# Quickstart: Migrate Chatbot to Vietnamese-Capable Models

**Feature**: `001-migrate-vn-models` | **Date**: 2026-11-02

Validation guide for proving the migration works end to end. Contracts and entity details live in [contracts/](./contracts/) and [data-model.md](./data-model.md); this file only covers how to run and check the feature.

## Prerequisites

- Ollama installed and running locally.
- Python 3.11+ with the project dependencies installed.
- The profile knowledge base present in `data/` and curated pairs in `qa.txt`.
- Enough memory for the selected answer-model size (see [configuration contract](./contracts/configuration.md)).

## 1. Determine available memory

```bash
# Linux
free -h
# Windows (PowerShell)
systeminfo | findstr /C:"Available Physical Memory"
```

Choose the answer model from the memory table in the configuration contract. If below 4 GB, use the 1.5B model and note the recommendation to upgrade or use an external answer service.

## 2. Install dependencies and models

```bash
pip install -r requirements.txt
ollama pull bge-m3
ollama pull qwen2.5:7b     # replace with your selected size
```

Verify the models are available:

```bash
ollama list
```

Expected: both `bge-m3` and the chosen Qwen2.5 size appear, and no Qwen3 model is required.

## 3. Configure

```bash
export CHATBOT_ANSWER_MODEL=qwen2.5:7b
export CHATBOT_EMBEDDING_MODEL=bge-m3
export CHATBOT_RELEVANCE_THRESHOLD=<calibrated value>
export CHATBOT_FUZZY_CUTOFF=80
```

On Windows PowerShell use `$env:CHATBOT_ANSWER_MODEL = "qwen2.5:7b"` etc. All values are documented in the configuration contract.

## 4. Start the application

```bash
python app.py
```

Open `index.html` and send an in-domain question such as "GPA hiện tại là bao nhiêu?".

Expected: a concise, natural Vietnamese answer with the correct figure (`8.30`), no invented facts, and no startup error about a missing model or index.

## 5. Validate retrieval and refusal behavior

```bash
pytest tests/
```

Expected:
- `test_retrieval.py` — a paraphrased Vietnamese question selects the passage containing the expected fact.
- `test_refusal.py` — out-of-scope questions return an explicit refusal.
- `test_chat_api.py` — `POST /chat` accepts `{"message": "..."}` and returns `{"response": "..."}`; invalid requests do not produce fabricated answers.

## 6. Calibrate the relevance threshold

1. Start with the current threshold and run the evaluation set (step 7) in the embedding-changed milestone.
2. Note scores for in-domain vs out-of-scope questions.
3. Adjust `CHATBOT_RELEVANCE_THRESHOLD` so in-domain questions are not falsely refused and out-of-scope questions are still declined.
4. Re-run until both behaviors hold; record the chosen value.

Expected: a single threshold value that separates the two groups on this dataset.

## 7. Run the evaluation milestones

Run in this order, changing one thing at a time:

```bash
# Milestone A: original configuration (tinyllama + nomic-embed-text)
python evaluation/run_eval.py --milestone original

# Milestone B: after embedding change (bge-m3, recalibrated threshold)
python evaluation/run_eval.py --milestone embedding-changed

# Milestone C: after answer-model change (selected Qwen2.5 size)
python evaluation/run_eval.py --milestone answer-model-changed
```

Expected: one result file per milestone under `evaluation/results/`, each including the active configuration, per-question answers, latency, and the operator's scores.

## 8. Build the comparison table

For each milestone compute factual accuracy, refusal rate, naturalness rate, and average latency; record them in the table from the [evaluation contract](./contracts/evaluation.md).

Expected outcome (from the spec):
- At least 90% of in-domain answers have exact figures/names.
- 100% of out-of-scope questions are refused without fabrication.
- At least 80% of paraphrased/diacritic-free variants are answered correctly.
- The post-migration configuration is at least as good on correctness and refusal, and better on natural Vietnamese.
- The best-performing configuration is identified and retained.

## 9. Fall back if the model does not fit

If the chosen model fails to load or is unusably slow, switch to the next smaller Qwen2.5 size, restart, and re-run the affected milestone. Do not change the embedding model or question set during this fallback, so the comparison stays attributable.

Expected: the chatbot loads and answers with acceptable latency, and the configuration used is recorded with the result.

## Artifact checklist

- [ ] `evaluation/questions.json` contains the fixed ~15-question set with all categories covered.
- [ ] `evaluation/results/` has one result per milestone.
- [ ] The comparison table is filled and identifies the retained configuration.
- [ ] `requirements.txt` no longer contains the stray `ollama run qwen3:1.7b` line.
