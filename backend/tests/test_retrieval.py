import pytest
from langchain_core.documents import Document

from backend import chatbox
from backend.tests.helpers import contains_answer, ollama_ready


class FakeDB:
    def __init__(self, results):
        self.results = results

    def similarity_search_with_score(self, query, k=2):
        return self.results


def test_relevant_score_passes_threshold():
    assert chatbox.is_relevant(chatbox.config.relevance_threshold) is True
    assert chatbox.is_relevant(chatbox.config.relevance_threshold - 0.1) is True


def test_irrelevant_score_fails_threshold():
    assert chatbox.is_relevant(chatbox.config.relevance_threshold + 0.1) is False


def test_irrelevant_document_is_rejected(monkeypatch):
    monkeypatch.setattr(chatbox, "get_qa_data", lambda: {})
    monkeypatch.setattr(
        chatbox,
        "get_db",
        lambda: FakeDB([(Document(page_content="không liên quan"), 99.0)]),
    )

    assert chatbox.ask_ai("Giá vàng hôm nay bao nhiêu?") == chatbox.REFUSAL


def test_empty_retrieval_is_rejected(monkeypatch):
    monkeypatch.setattr(chatbox, "get_qa_data", lambda: {})
    monkeypatch.setattr(chatbox, "get_db", lambda: FakeDB([]))

    assert chatbox.ask_ai("Giá vàng hôm nay bao nhiêu?") == chatbox.REFUSAL


READY = ollama_ready(
    chatbox.config.answer_model,
    chatbox.config.embedding_model,
    chatbox.config.ollama_base_url,
)


@pytest.mark.skipif(not READY, reason="Ollama hoặc model chưa sẵn sàng")
def test_paraphrase_and_no_diacritics_retrieve_expected_fact(
    questions_by_category,
):
    db = chatbox.get_db()
    cases = questions_by_category["paraphrase"][:1] + questions_by_category[
        "no_diacritics"
    ][:1]

    for item in cases:
        docs = db.similarity_search_with_score(item["question"].lower(), k=2)
        assert docs
        contents = [doc.page_content for doc, _ in docs]
        assert any(
            contains_answer(content, item["expected_answer"])
            for content in contents
        ), f"Không tìm thấy {item['expected_answer']} cho câu {item['question']}"
