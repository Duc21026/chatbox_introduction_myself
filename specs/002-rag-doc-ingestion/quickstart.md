# Quickstart Validation: RAG Document Ingestion and Editing

**Feature**: `002-rag-doc-ingestion` | **Date**: 2026-11-04

Runnable scenarios that prove the document lifecycle, shared normalization, and retrieval behavior end to end. Run them against a temporary knowledge-base directory so the real `data/` is never modified.

## Prerequisites

- Python 3.11+ and the project virtualenv.
- Ollama running locally with the configured answer model and embedding model installed.
- Run all commands from the repository root.

```bash
python -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install -r requirements.txt
ollama pull qwen2.5:7b
ollama pull bge-m3
```

Prepare a scratch knowledge base:

```bash
export CHATBOT_DATA_DIR=/tmp/chatbot-kb
mkdir -p "$CHATBOT_DATA_DIR"
```

## Scenario 1 — Add a source and answer from it

Create a text source with a fact that exists nowhere else in the knowledge base:

```bash
printf 'Chính sách nghỉ phép: nhân viên được nghỉ 12 ngày phép mỗi năm.\n' > /tmp/nghi-phep.txt
python scripts/manage_docs.py add /tmp/nghi-phep.txt --name nghi-phep.txt
python scripts/manage_docs.py list
python scripts/manage_docs.py ask "nhân viên được nghỉ bao nhiêu ngày phép?" --debug
```

**Expected**:

- `add` exits `0` and confirms `nghi-phep.txt`.
- `list` shows `nghi-phep.txt`.
- The answer contains `12` and the debug record names `nghi-phep.txt` as the source.
- `outcome` is `answered` and `passed_threshold` is `true`.

## Scenario 2 — Replace a source and remove the old fact

Replace the same source with a changed number:

```bash
printf 'Chính sách nghỉ phép: nhân viên được nghỉ 15 ngày phép mỗi năm.\n' > /tmp/nghi-phep-moi.txt
python scripts/manage_docs.py replace /tmp/nghi-phep-moi.txt --name nghi-phep.txt
python scripts/manage_docs.py ask "nhân viên được nghỉ bao nhiêu ngày phép?" --debug
```

**Expected**:

- `replace` exits `0`.
- The answer contains `15`.
- The answer does not contain `12`.
- The debug record still points to `nghi-phep.txt` with the new content.
- Running `add` again with the same name updates the source rather than creating a duplicate (upsert); `list` shows it once.

## Scenario 3 — Delete a source and refuse its questions

```bash
python scripts/manage_docs.py delete nghi-phep.txt
python scripts/manage_docs.py list
python scripts/manage_docs.py ask "nhân viên được nghỉ bao nhiêu ngày phép?" --debug
```

**Expected**:

- `delete` exits `0`.
- `list` no longer shows `nghi-phep.txt`.
- The answer is the refusal (`Tôi không biết`), and the diagnostic outcome is `refused`.
- No deleted content appears in the answer.

## Scenario 4 — Noisy Vietnamese input still retrieves

Re-add the source, then ask with repeated characters, extra spaces, and no diacritics:

```bash
python scripts/manage_docs.py add /tmp/nghi-phep.txt --name nghi-phep.txt

python scripts/manage_docs.py ask "nhânnn viênnn   được nghỉii bao nhiêu ngàyyy phéppp?" --debug
python scripts/manage_docs.py ask "nhan vien duoc nghi bao nhieu ngay phep" --debug
```

**Expected**:

- Both questions still retrieve `nghi-phep.txt`.
- The debug record shows a normalized question with repeated runs collapsed and whitespace trimmed.
- In the no-diacritics case, the debug record shows a rewritten form when `CHATBOT_QUERY_REWRITE=auto`.
- The original question remains unchanged in the prompt/display path.

## Scenario 5 — Import a text-based PDF

Use an existing text-based PDF in the repository:

```bash
python scripts/manage_docs.py add research_paper_ai_education.pdf --name research-paper.pdf
python scripts/manage_docs.py list
python scripts/manage_docs.py ask "bài báo nói về chủ đề gì?" --debug
```

**Expected**:

- The PDF is accepted and listed as `research-paper.pdf`.
- Its extracted text is indexed; the diagnostic shows retrieved pieces from that source when the question matches the content.
- A scanned/image-only PDF is rejected with a clear message and is not added.

## Scenario 6 — Changes are visible without losing persistence

With the Flask app already running (`python app.py`), add a second source from another terminal:

```bash
printf 'Quy định: thời gian thử việc là 2 tháng.\n' > /tmp/thu-viec.txt
python scripts/manage_docs.py add /tmp/thu-viec.txt --name thu-viec.txt
```

Ask through the API:

```bash
curl -s http://127.0.0.1:5000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"thời gian thử việc là bao lâu?"}'
```

**Expected**:

- The answer reflects the new source without restarting the server (index refresh).
- Stop and restart the app, ask the same question again; the answer still comes from `thu-viec.txt` (source persistence).
- Delete the source and ask again; the answer no longer uses it.

## Scenario 7 — Public API compatibility

```bash
curl -s http://127.0.0.1:5000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"GPA hiện tại là bao nhiêu?"}'

curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:5000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"   "}'

curl -s http://127.0.0.1:5000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"!!!"}'
```

**Expected**:

- The first response has exactly one `response` string and no diagnostic fields.
- The empty message returns `400`.
- The punctuation-only message returns `200` with a rephrase request, not a retrieval result.

## Automated checks

```bash
pytest tests/test_normalization.py tests/test_document_management.py
pytest tests/test_retrieval_normalization.py
pytest tests/
```

**Expected**:

- Normalization and lifecycle tests pass without Ollama (they use fakes/temp directories).
- Ollama-dependent tests skip automatically when models are unavailable and pass when they are available.
- Existing `test_chat_api.py`, `test_retrieval.py`, `test_refusal.py`, and `test_answers.py` behavior remains valid.

## Artifact cross-references

- Source lifecycle details: [contracts/document-cli.md](./contracts/document-cli.md)
- Normalization, rewriting, retrieval, diagnostics: [contracts/retrieval-normalization.md](./contracts/retrieval-normalization.md)
- HTTP compatibility: [contracts/chat-api.md](./contracts/chat-api.md)
- Entities and validation rules: [data-model.md](./data-model.md)
