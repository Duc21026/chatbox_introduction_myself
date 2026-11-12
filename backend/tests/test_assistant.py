import backend.assistant as assistant_module
from backend.assistant import Assistant
from backend.kb_engine import QueryEvaluation
from backend.session import SessionStore


def candidate(item_id, question, score=0.6, topic="Mục tiêu", count=1):
    return {
        "source": "kb",
        "item_id": item_id,
        "topic": topic,
        "question": question,
        "norm": question.lower(),
        "score": score,
        "question_count": count,
        "answer": "Câu trả lời",
    }


def evaluation(top1=0.2, answer_item=None, candidates=None, embeddings=True):
    return QueryEvaluation(
        norm="muc tieu",
        word_count=2,
        query_vec=None,
        top1=top1,
        top2=0.1,
        candidates=candidates or [],
        answer_item=answer_item,
        embeddings_ready=embeddings,
    )


class FakeDocIndex:
    def __init__(self, hits=None, topics=None):
        self.hits = hits or []
        self._topics = topics or []

    def search(self, question, query_vec=None, top_k=6):
        return self.hits

    def topics(self):
        return self._topics

    def candidates_for_topic(self, topic, limit=12):
        return []


KB_ITEMS = [
    {
        "id": "goal_career",
        "topic": "Mục tiêu",
        "questions": ["Mục tiêu nghề nghiệp?", "Bạn muốn làm gì?"],
        "answer": "Backend developer",
    },
    {
        "id": "skills",
        "topic": "Kỹ năng",
        "questions": ["Bạn giỏi gì?", "Kỹ năng chính?"],
        "answer": "Python",
    },
    {
        "id": "study",
        "topic": "Học tập",
        "questions": ["Bạn học trường nào?", "GPA bao nhiêu?"],
        "answer": "8.30",
    },
]


def test_high_score_returns_answer(monkeypatch):
    monkeypatch.setattr(
        assistant_module.kb_engine,
        "get_items",
        lambda: KB_ITEMS,
    )
    item = {"id": "gpa", "answer": "GPA 8.30", "answer_bullets": None}
    assistant = Assistant(
        evaluator=lambda question: evaluation(0.91, answer_item=item)
    )

    response = assistant.handle("GPA của bạn?")

    assert response["type"] == "answer"
    assert "8.30" in response["response"]
    assert response["source"] == "kb:gpa"
    assert response["session_id"].startswith("s-")


def test_mid_score_returns_suggestions(monkeypatch):
    monkeypatch.setattr(assistant_module.kb_engine, "get_items", lambda: KB_ITEMS)
    candidates = [
        candidate("goal_career", "Mục tiêu nghề nghiệp?", 0.7, count=2),
        candidate("skills", "Bạn giỏi gì?", 0.6),
        candidate("study", "GPA bao nhiêu?", 0.5),
    ]
    assistant = Assistant(
        evaluator=lambda question: evaluation(0.7, candidates=candidates),
        doc_searcher=FakeDocIndex(),
    )

    response = assistant.handle("mục tiêu")

    assert response["type"] == "suggest"
    assert 2 <= len(response["suggestions"]) <= 4
    assert response["actions"]
    assert response["actions"][0]["id"] == "other"


def test_low_score_uses_documents_with_sources(monkeypatch):
    monkeypatch.setattr(assistant_module.kb_engine, "get_items", lambda: KB_ITEMS)
    hit = {
        "source": "doc",
        "item_id": "chunk-1",
        "file": "CV.pdf",
        "page": 2,
        "sheet": None,
        "row_start": None,
        "row_end": None,
        "heading": "Kinh nghiệm",
        "question": "Tài liệu CV.pdf nói gì về Kinh nghiệm?",
        "score": 0.88,
        "text": "Tôi có ba năm kinh nghiệm backend. Tôi từng làm việc tại công ty A. Tôi dùng Python hằng ngày.",
    }
    assistant = Assistant(
        evaluator=lambda question: evaluation(0.1),
        doc_searcher=FakeDocIndex([hit]),
    )

    response = assistant.handle("kinh nghiệm backend?")

    assert response["type"] == "answer"
    assert response["sources"][0]["file"] == "CV.pdf"
    assert response["sources"][0]["page"] == 2
    assert len(response["answer_bullets"]) >= 3


def test_low_score_without_docs_returns_clarify(monkeypatch):
    monkeypatch.setattr(assistant_module.kb_engine, "get_items", lambda: KB_ITEMS)
    assistant = Assistant(
        evaluator=lambda question: evaluation(0.1),
        doc_searcher=FakeDocIndex(topics=[{"label": "Học bổng", "count": 2}]),
    )

    response = assistant.handle("asdf")

    assert response["type"] == "clarify"
    assert len(response["topics"]) >= 3
    assert response["examples"]
    assert response["actions"]
    assert "không biết" not in response["response"].lower()
    assert response["type"] != "unknown"


def test_action_other_and_topic(monkeypatch):
    monkeypatch.setattr(assistant_module.kb_engine, "get_items", lambda: KB_ITEMS)
    evaluator = lambda question: evaluation(0.2)
    assistant = Assistant(
        evaluator=evaluator,
        doc_searcher=FakeDocIndex(),
        session_store=SessionStore(ttl=60, max_sessions=10),
    )

    first = assistant.handle("asdf")
    assert first["type"] == "clarify"
    session_id = first["session_id"]

    second = assistant.handle(session_id=session_id, action="other")
    assert second["type"] == "clarify"
    assert second["response"] != first["response"] or second["topics"]

    third = assistant.handle(
        session_id=session_id, action="topic", topic="Mục tiêu"
    )
    assert third["type"] == "suggest"
    assert all(
        "Mục tiêu" in suggestion["question"] or suggestion["score"] >= 0
        for suggestion in third["suggestions"]
    )


def test_shown_ids_prevent_repeating_suggestions(monkeypatch):
    monkeypatch.setattr(assistant_module.kb_engine, "get_items", lambda: KB_ITEMS)
    candidates = [
        candidate("goal_career", "Mục tiêu nghề nghiệp?", 0.7, count=2),
        candidate("skills", "Bạn giỏi gì?", 0.65),
        candidate("study", "GPA bao nhiêu?", 0.6),
    ]
    assistant = Assistant(
        evaluator=lambda question: evaluation(0.7, candidates=candidates),
        doc_searcher=FakeDocIndex(),
    )

    first = assistant.handle("mục tiêu")
    second = assistant.handle("mục tiêu", session_id=first["session_id"])

    first_ids = {item["id"] for item in first["suggestions"]}
    second_ids = {
        item["id"] for item in (second.get("suggestions") or [])
    }
    assert not (first_ids & second_ids)


def test_optional_summary_is_used_only_when_provided(monkeypatch):
    monkeypatch.setattr(assistant_module.kb_engine, "get_items", lambda: KB_ITEMS)
    monkeypatch.setenv("ENABLE_LLM_SUMMARY", "true")
    hit = {
        "source": "doc",
        "item_id": "chunk-1",
        "file": "CV.pdf",
        "page": 1,
        "heading": None,
        "score": 0.9,
        "text": "Dòng một. Dòng hai. Dòng ba.",
    }
    assistant = Assistant(
        evaluator=lambda question: evaluation(0.1),
        doc_searcher=FakeDocIndex([hit]),
        summarizer=lambda bullets, question: "Tóm tắt ngắn.",
    )

    response = assistant.handle("câu hỏi")

    assert response["response"] == "Tóm tắt ngắn."
    assert response["sources"]


def test_evaluation_cache_reuses_same_normalized_question(monkeypatch):
    monkeypatch.setattr(assistant_module.kb_engine, "get_items", lambda: KB_ITEMS)
    calls = [0]

    def evaluator(question):
        calls[0] += 1
        return evaluation(
            0.6,
            candidates=[
                candidate("x", "Câu hỏi mẫu?"),
                candidate("y", "Câu hỏi khác?"),
            ],
        )

    assistant = Assistant(evaluator=evaluator, doc_searcher=FakeDocIndex())
    first = assistant.handle("Mục tiêu?")
    second = assistant.handle("Mục tiêu?", session_id=first["session_id"])

    assert calls[0] == 1
    assert first["type"] == "suggest"
    assert second["type"] in {"suggest", "clarify"}
