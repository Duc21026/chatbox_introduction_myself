import dataclasses
from pathlib import Path

from langchain_core.documents import Document

from backend import app as app_module
from backend import chatbox


SOURCE = """CHATBOT-SOURCE v1

=== RECORD ===
kind: qa
id: gpa
topic: Học tập
questions:
- GPA của bạn là bao nhiêu?
answer:
GPA hiện tại là 8.30 / 10.
=== END ===

=== RECORD ===
kind: doc
id: scholarship
topic: Học bổng
content:
Mục tiêu là săn học bổng toàn phần Thạc sĩ tại Đức.
=== END ===
"""


class FakeDB:
    def __init__(self, documents):
        self.documents = documents

    def similarity_search_with_score(self, query, k=2):
        return [(document, 0.1) for document in self.documents[:k]]


class FakeLLM:
    def invoke(self, prompt):
        return type("Response", (), {"content": "Học bổng toàn phần tại Đức."})()


def _prepare(tmp_path, monkeypatch):
    source = Path(tmp_path) / "chatbot.txt"
    source.write_text(SOURCE, encoding="utf-8")
    config = dataclasses.replace(
        chatbox.config,
        source_path=str(source),
        legacy_sources=False,
        qa_path=str(Path(tmp_path) / "missing-qa.txt"),
        kb_path=str(Path(tmp_path) / "missing-kb.json"),
        data_dir=str(tmp_path / "missing-data"),
        query_rewrite="off",
    )
    monkeypatch.setattr(chatbox, "config", config)
    monkeypatch.setattr(chatbox, "_source_cache", None)
    monkeypatch.setattr(chatbox, "_source_cache_key", None)
    monkeypatch.setattr(chatbox, "_qa_data", None)
    monkeypatch.setattr(chatbox, "_qa_data_signature", None)
    monkeypatch.setattr(chatbox, "_db", None)
    monkeypatch.setattr(chatbox, "_index_signature", None)
    monkeypatch.setattr(app_module.kb_engine, "query", lambda question: None)
    return source


def test_chat_answers_from_unified_source(tmp_path, monkeypatch):
    _prepare(tmp_path, monkeypatch)

    client = app_module.app.test_client()
    response = client.post(
        "/chat", json={"message": "GPA của bạn là bao nhiêu?"}
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["type"] == "answer"
    assert "8.30" in payload["response"]


def test_chat_answers_doc_question_from_unified_source(tmp_path, monkeypatch):
    _prepare(tmp_path, monkeypatch)

    source = chatbox.get_source()
    doc = [
        document
        for document in source.rag_documents
        if document.metadata["kind"] == "doc"
    ][0]
    monkeypatch.setattr(
        chatbox,
        "get_db",
        lambda: FakeDB(
            [
                Document(
                    page_content=doc.page_content, metadata=dict(doc.metadata)
                )
            ]
        ),
    )
    monkeypatch.setattr(chatbox, "get_llm", lambda: FakeLLM())

    client = app_module.app.test_client()
    response = client.post(
        "/chat", json={"message": "Mục tiêu học bổng là gì?"}
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["type"] == "answer"
    assert "Học bổng" in payload["response"]
