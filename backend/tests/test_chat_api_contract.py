from backend import app as app_module


def test_chat_contract_shape(monkeypatch):
    payload = {
        "type": "answer",
        "session_id": "s-1",
        "score": 0.9,
        "response": "câu trả lời",
        "message": None,
        "answer_bullets": None,
        "source": "kb:test",
        "sources": [],
        "suggestions": [],
        "topics": [],
        "examples": [],
        "actions": [],
    }
    monkeypatch.setattr(
        app_module._assistant, "handle", lambda **kwargs: payload
    )
    client = app_module.app.test_client()

    response = client.post("/chat", json={"message": "câu hỏi"})

    assert response.status_code == 200
    assert response.get_json() == payload


def test_chat_contract_rejects_blank_message():
    client = app_module.app.test_client()

    response = client.post("/chat", json={"message": "   "})

    assert response.status_code == 422
    assert "error" in response.get_json()


def test_chat_contract_rejects_invalid_json():
    client = app_module.app.test_client()

    response = client.post(
        "/chat", data="not-json", content_type="application/json"
    )

    assert response.status_code == 400
    assert "error" in response.get_json()
