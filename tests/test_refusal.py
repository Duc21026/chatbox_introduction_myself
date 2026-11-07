import pytest
from langchain_core.documents import Document

import chatbox
from tests.helpers import ollama_ready

READY = ollama_ready(
    chatbox.config.answer_model,
    chatbox.config.embedding_model,
    chatbox.config.ollama_base_url,
)


class FakeDB:
    def __init__(self, results):
        self.results = results

    def similarity_search_with_score(self, query, k=2):
        return self.results


def test_no_retrieved_document_returns_refusal(monkeypatch):
    monkeypatch.setattr(chatbox, "get_qa_data", lambda: {})
    monkeypatch.setattr(chatbox, "get_db", lambda: FakeDB([]))

    assert chatbox.ask_ai("Bạn có biết giá vàng hôm nay không?") == chatbox.REFUSAL


def test_high_score_returns_refusal_without_calling_llm(monkeypatch):
    def fail_llm():
        raise AssertionError("Không được gọi LLM khi tài liệu không liên quan")

    monkeypatch.setattr(chatbox, "get_qa_data", lambda: {})
    monkeypatch.setattr(
        chatbox,
        "get_db",
        lambda: FakeDB([(Document(page_content="không liên quan"), 99.0)]),
    )
    monkeypatch.setattr(chatbox, "get_llm", fail_llm)

    assert chatbox.ask_ai("Thời tiết Hà Nội ngày mai?") == chatbox.REFUSAL


@pytest.mark.skipif(not READY, reason="Ollama hoặc model chưa sẵn sàng")
def test_out_of_scope_questions_are_refused(questions_by_category):
    for item in questions_by_category["out_of_scope"]:
        answer = chatbox.ask_ai(item["question"])
        assert answer == chatbox.REFUSAL, (
            f"Không từ chối câu ngoài chủ đề {item['question']}: {answer}"
        )
