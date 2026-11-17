import backend.assistant as assistant_module
from backend.app import create_app
from backend.assistant import Assistant
from backend.kb_engine import QueryEvaluation


class EmptySpans:
    def similarity_search_with_score(self, query, k=2):
        return []


def _evaluation(norm):
    return QueryEvaluation(
        norm=norm,
        word_count=len(norm.split()),
        query_vec=None,
        candidates=[],
        embeddings_ready=False,
    )


def test_provider_failure_falls_back_to_suggest_or_clarify(monkeypatch):
    items = [
        {
            "id": "goal",
            "topic": "Mục tiêu",
            "questions": ["Mục tiêu nghề nghiệp?", "Mục tiêu học tập?"],
            "answer": "Backend developer",
        },
        {
            "id": "ielts",
            "topic": "Mục tiêu",
            "questions": ["Mục tiêu IELTS?"],
            "answer": "IELTS 6.5",
        },
    ]
    monkeypatch.setattr(assistant_module.kb_engine, "get_items", lambda: items)
    assistant = Assistant(
        evaluator=_evaluation,
        qa_searcher=lambda question: [],
        rag_searcher=lambda question, query_vec=None: [],
        doc_searcher=EmptySpans(),
    )
    app = create_app("deployment", assistant=assistant)
    response = app.test_client().post("/chat", json={"message": "mục tiêu"})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["type"] in {"suggest", "clarify"}
    assert payload["type"] != "answer"
