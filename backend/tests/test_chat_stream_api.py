import json

from backend import app as app_module


def _events(response):
    payload = response.get_data(as_text=True)
    return [
        json.loads(line[len("data:") :])
        for line in payload.splitlines()
        if line.startswith("data:")
    ]


def _answer():
    return {
        "type": "answer",
        "session_id": "s-1",
        "score": 0.9,
        "response": "Xin chào",
        "message": None,
        "answer_bullets": None,
        "source": "kb:test",
        "sources": [],
        "suggestions": [],
        "topics": [],
        "examples": [],
        "actions": [],
    }


def _suggest():
    return {
        "type": "suggest",
        "session_id": "s-1",
        "score": None,
        "response": "Bạn muốn hỏi câu nào?",
        "message": "Bạn muốn hỏi câu nào?",
        "answer_bullets": None,
        "source": None,
        "sources": [],
        "suggestions": [
            {"id": "a", "question": "Câu A?", "score": 0.8},
            {"id": "b", "question": "Câu B?", "score": 0.7},
        ],
        "topics": [],
        "examples": [],
        "actions": [{"id": "other", "label": "Câu hỏi khác"}],
    }


def test_stream_contract_emits_chunk_then_done(monkeypatch):
    monkeypatch.setattr(
        app_module._assistant, "handle", lambda **payload: _answer()
    )
    client = app_module.app.test_client()

    response = client.post("/chat/stream", json={"message": "câu hỏi"})

    assert response.status_code == 200
    assert response.mimetype == "text/event-stream"
    assert _events(response) == [
        {"type": "chunk", "content": "Xin chào"},
        {"type": "done"},
    ]


def test_stream_emits_result_event_for_suggest(monkeypatch):
    monkeypatch.setattr(
        app_module._assistant, "handle", lambda **payload: _suggest()
    )
    client = app_module.app.test_client()

    response = client.post("/chat/stream", json={"message": "mục tiêu"})
    events = _events(response)

    assert events[0]["type"] == "chunk"
    assert events[1]["type"] == "result"
    assert events[1]["data"]["type"] == "suggest"
    assert events[-1] == {"type": "done"}


def test_stream_contract_rejects_blank_message():
    client = app_module.app.test_client()

    response = client.post("/chat/stream", json={"message": "   "})

    assert response.status_code == 422
    assert "error" in response.get_json()
