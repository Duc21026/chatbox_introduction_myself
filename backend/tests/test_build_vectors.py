import json

from scripts import build_vectors

SOURCE = """CHATBOT-SOURCE v1

=== RECORD ===
kind: qa
id: gpa
topic: Học tập
questions:
- GPA của bạn?
answer:
GPA là 8.51.
=== END ===
"""


def test_build_vectors_writes_valid_index(tmp_path, monkeypatch):
    source = tmp_path / "chatbot.txt"
    source.write_text(SOURCE, encoding="utf-8")
    output = tmp_path / "vectors.json"

    def fake_embed(texts, timeout=None):
        return [[float(len(text)), 1.0, 0.0] for text in texts]

    monkeypatch.setattr(build_vectors.embedding_provider, "embed_texts", fake_embed)
    assert build_vectors.build(str(source), str(output), 8, 1.0) == 0

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["question_count"] == len(payload["entries"]) >= 1
    assert payload["source_sha256"]
    assert payload["source_kb_hash"]
    assert all(len(entry["vector"]) == payload["dim"] for entry in payload["entries"])


def test_build_vectors_does_not_write_on_provider_failure(tmp_path, monkeypatch):
    source = tmp_path / "chatbot.txt"
    source.write_text(SOURCE, encoding="utf-8")
    output = tmp_path / "vectors.json"
    monkeypatch.setattr(
        build_vectors.embedding_provider, "embed_texts", lambda texts, timeout=None: None
    )

    assert build_vectors.build(str(source), str(output), 8, 1.0) == 1
    assert not output.exists()
