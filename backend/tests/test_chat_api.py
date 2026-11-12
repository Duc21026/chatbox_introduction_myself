from backend import app as app_module


def _response(response_type="answer", session_id="s-test"):
    return {
        "type": response_type,
        "session_id": session_id,
        "score": 0.9 if response_type == "answer" else None,
        "response": "Nội dung",
        "message": None,
        "answer_bullets": None,
        "source": "kb:test" if response_type == "answer" else None,
        "sources": [],
        "suggestions": [] if response_type == "answer" else [
            {"id": "a", "question": "Câu A?", "score": 0.8},
            {"id": "b", "question": "Câu B?", "score": 0.7},
        ],
        "topics": [],
        "examples": [],
        "actions": [],
    }


def test_chat_returns_structured_response(monkeypatch):
    captured = {}

    def fake_handle(**payload):
        captured.update(payload)
        return _response()

    monkeypatch.setattr(app_module._assistant, "handle", fake_handle)
    client = app_module.app.test_client()

    response = client.post("/chat", json={"message": "GPA hiện tại?"})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["type"] == "answer"
    assert payload["session_id"] == "s-test"
    assert "response" in payload
    assert captured["question"] == "GPA hiện tại?"


def test_missing_message_returns_client_error():
    client = app_module.app.test_client()

    response = client.post("/chat", json={})

    assert response.status_code == 400
    assert "error" in response.get_json()


def test_empty_message_returns_client_error():
    client = app_module.app.test_client()

    response = client.post("/chat", json={"message": "   "})

    assert response.status_code == 422
    assert "error" in response.get_json()


def test_invalid_json_returns_client_error():
    client = app_module.app.test_client()

    response = client.post(
        "/chat", data="not-json", content_type="application/json"
    )

    assert response.status_code == 400
    assert "error" in response.get_json()


def test_diagnostics_are_not_exposed(monkeypatch):
    monkeypatch.setattr(
        app_module._assistant, "handle", lambda **payload: _response()
    )
    client = app_module.app.test_client()

    response = client.post("/chat", json={"message": "câu hỏi"})

    payload = response.get_json()
    assert "pieces" not in payload
    assert "normalized_question" not in payload


def test_punctuation_only_message_never_returns_unknown(monkeypatch):
    monkeypatch.setattr(
        app_module._assistant,
        "handle",
        lambda **payload: _response("clarify"),
    )
    client = app_module.app.test_client()

    response = client.post("/chat", json={"message": "!!!"})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["type"] == "clarify"
    assert payload["type"] != "unknown"
    assert "không biết" not in payload["response"].lower()


def test_session_id_is_forwarded_and_action_validated(monkeypatch):
    captured = {}

    def fake_handle(**payload):
        captured.update(payload)
        return _response("clarify")

    monkeypatch.setattr(app_module._assistant, "handle", fake_handle)
    client = app_module.app.test_client()

    response = client.post(
        "/chat",
        json={"session_id": "s-abc", "action": "topic", "topic": "Kỹ năng"},
    )

    assert response.status_code == 200
    assert captured["session_id"] == "s-abc"
    assert captured["action"] == "topic"
    assert captured["topic"] == "Kỹ năng"


def test_topic_action_requires_topic():
    client = app_module.app.test_client()

    response = client.post("/chat", json={"action": "topic"})

    assert response.status_code == 400
