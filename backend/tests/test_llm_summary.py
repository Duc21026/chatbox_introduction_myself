import json
from types import SimpleNamespace

import backend.chatbox as chatbox
from backend.assistant import Assistant
from backend.kb_engine import QueryEvaluation
from backend.session import SessionStore

DOC_HIT = {
    "source": "doc",
    "item_id": "chunk-1",
    "file": "CV.pdf",
    "page": 1,
    "heading": None,
    "score": 0.9,
    "text": "Câu trích một. Câu trích hai. Câu trích ba.",
}


class FakeDoc:
    def search(self, question, query_vec=None, top_k=6):
        return [dict(DOC_HIT)]

    def topics(self):
        return []

    def candidates_for_topic(self, topic, limit=12):
        return []


def _evaluation(question):
    return QueryEvaluation(
        norm=question.lower(),
        word_count=2,
        query_vec=None,
        top1=0.1,
        top2=0.0,
        candidates=[],
        answer_item=None,
        embeddings_ready=True,
    )


def _assistant(**kwargs):
    return Assistant(
        evaluator=_evaluation,
        doc_searcher=FakeDoc(),
        session_store=SessionStore(ttl=60, max_sessions=10),
        **kwargs,
    )


def test_summary_disabled_does_not_call_llm(monkeypatch):
    monkeypatch.setenv("ENABLE_LLM_SUMMARY", "false")
    monkeypatch.setattr(
        chatbox,
        "ChatOllama",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not call LLM")),
    )

    response = _assistant().handle("câu hỏi")

    assert response["type"] == "answer"
    assert "Câu trích một" in response["response"]
    assert chatbox.summarize_document_answer(["một", "hai"], "hỏi") is None


def test_summary_enabled_limits_predict_and_uses_extracted_context(monkeypatch):
    calls = []

    class FakeLLM:
        def __init__(self, **kwargs):
            calls.append(("init", kwargs))

        def invoke(self, prompt):
            calls.append(("invoke", prompt))
            return SimpleNamespace(content="Tóm tắt từ trích xuất.")

    monkeypatch.setenv("ENABLE_LLM_SUMMARY", "true")
    monkeypatch.setattr(chatbox, "ChatOllama", FakeLLM)

    response = _assistant().handle("kinh nghiệm?")

    assert response["response"] == "Tóm tắt từ trích xuất."
    init = next(payload for kind, payload in calls if kind == "init")
    assert init["num_predict"] <= 120
    prompt = next(payload for kind, payload in calls if kind == "invoke")
    assert "Câu trích một" in prompt
    assert "Câu trích hai" in prompt
    assert "CV.pdf" not in prompt


def test_summary_failure_falls_back_to_extractive(monkeypatch):
    class BrokenLLM:
        def __init__(self, **kwargs):
            pass

        def invoke(self, prompt):
            raise RuntimeError("ollama down")

    monkeypatch.setenv("ENABLE_LLM_SUMMARY", "true")
    monkeypatch.setattr(chatbox, "ChatOllama", BrokenLLM)

    response = _assistant().handle("câu hỏi")

    assert response["type"] == "answer"
    assert "Câu trích một" in response["response"]
    assert len(response["answer_bullets"]) >= 3


def test_chat_and_stream_call_summary_once(monkeypatch):
    from backend import app as app_module

    calls = []

    class FakeLLM:
        def __init__(self, **kwargs):
            pass

        def invoke(self, prompt):
            calls.append(prompt)
            return SimpleNamespace(content="Bản tóm tắt.")

        def stream(self, prompt):
            calls.append(prompt)
            yield SimpleNamespace(content="Bản ")
            yield SimpleNamespace(content="tóm tắt.")

    monkeypatch.setenv("ENABLE_LLM_SUMMARY", "true")
    monkeypatch.setattr(chatbox, "ChatOllama", FakeLLM)
    monkeypatch.setattr(app_module, "_assistant", _assistant())

    client = app_module.app.test_client()
    response = client.post("/chat", json={"message": "câu hỏi"})
    assert response.status_code == 200
    assert response.get_json()["response"] == "Bản tóm tắt."
    assert len(calls) == 1

    calls.clear()
    stream = client.post("/chat/stream", json={"message": "câu hỏi"})
    assert stream.status_code == 200
    body = stream.get_data(as_text=True)
    events = [
        json.loads(line[len("data: "):])
        for line in body.splitlines()
        if line.startswith("data: ")
    ]
    chunks = [event for event in events if event["type"] == "chunk"]
    assert len(chunks) == 2
    assert "".join(event["content"] for event in chunks) == "Bản tóm tắt."
    assert events[-1]["type"] == "done"
    assert len(calls) == 1
