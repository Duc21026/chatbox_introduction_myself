import json

from backend import app as app_module


def _events(response):
    payload = response.get_data(as_text=True)
    return [
        json.loads(line[len("data:") :])
        for line in payload.splitlines()
        if line.startswith("data:")
    ]


def test_stream_contract_emits_chunks_then_done(monkeypatch):
    def fake_stream(question):
        assert question == "câu hỏi"
        yield "Xin "
        yield "chào"

    monkeypatch.setattr(app_module, "ask_ai_stream", fake_stream)
    client = app_module.app.test_client()

    response = client.post("/chat/stream", json={"message": "câu hỏi"})

    assert response.status_code == 200
    assert response.mimetype == "text/event-stream"
    assert _events(response) == [
        {"type": "chunk", "content": "Xin "},
        {"type": "chunk", "content": "chào"},
        {"type": "done"},
    ]


def test_stream_contract_emits_error_event(monkeypatch):
    def failing_stream(question):
        yield "phần đầu"
        raise RuntimeError("boom")

    monkeypatch.setattr(app_module, "ask_ai_stream", failing_stream)
    client = app_module.app.test_client()

    response = client.post("/chat/stream", json={"message": "câu hỏi"})
    events = _events(response)

    assert events[0] == {"type": "chunk", "content": "phần đầu"}
    assert events[-1]["type"] == "error"
    assert "message" in events[-1]


def test_stream_contract_rejects_blank_message():
    client = app_module.app.test_client()

    response = client.post("/chat/stream", json={"message": "   "})

    assert response.status_code == 400
    assert "error" in response.get_json()


def test_chat_endpoint_remains_unchanged(monkeypatch):
    monkeypatch.setattr(app_module, "ask_ai", lambda question: "đầy đủ")
    client = app_module.app.test_client()

    response = client.post("/chat", json={"message": "câu hỏi"})

    assert response.status_code == 200
    assert response.get_json() == {"response": "đầy đủ"}
