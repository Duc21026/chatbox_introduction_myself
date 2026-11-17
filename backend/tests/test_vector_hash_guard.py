from types import SimpleNamespace

import pytest

from backend import kb_engine, vector_store


class FakeIndex:
    def __init__(self, hash_value):
        self.source_kb_hash = hash_value
        self.entries = [
            vector_store.VectorEntry(
                id="gpa#0",
                item_id="gpa",
                source_type="qa",
                question="GPA?",
                norm="gpa",
                vector=[0.1, 0.2],
            )
        ]

    def matches_source(self, source):
        return self.source_kb_hash == source.kb_hash


def test_stale_hash_disables_vectors_and_keeps_questions(monkeypatch):
    monkeypatch.setenv("CHATBOT_RUNTIME", "deployment")
    source = SimpleNamespace(
        kb_items=[
            {
                "id": "gpa",
                "topic": "Học tập",
                "questions": ["GPA của bạn?"],
                "answer": "8.51",
                "answer_bullets": None,
            }
        ],
        kb_hash="new",
        signature=None,
    )
    monkeypatch.setattr(
        kb_engine.vector_store,
        "load",
        lambda **kwargs: FakeIndex("old"),
    )
    monkeypatch.setattr(
        kb_engine.vector_store,
        "matches_entries",
        lambda index, source: True,
    )

    kb_engine._embeddings = None
    kb_engine._questions = []
    kb_engine._kb_hash_value = None
    kb_engine.warm_up_kb(source)

    assert kb_engine._embeddings is None
    assert kb_engine._questions == ["GPA của bạn?"]
    assert kb_engine._kb_hash_value == "new"


def test_index_vectors_rejects_unknown_item(monkeypatch):
    source = SimpleNamespace(
        kb_items=[{"id": "other", "questions": ["x"], "answer": "y"}],
        kb_hash="match",
    )
    monkeypatch.setattr(
        kb_engine.vector_store,
        "load",
        lambda **kwargs: FakeIndex("match"),
    )
    monkeypatch.setattr(
        kb_engine.vector_store,
        "matches_entries",
        lambda index, source: False,
    )
    assert kb_engine._index_vectors(source, source.kb_items) is None
