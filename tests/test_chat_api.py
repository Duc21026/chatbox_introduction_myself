import app as app_module


def test_chat_returns_single_response(monkeypatch):
    monkeypatch.setattr(
        app_module, "ask_ai", lambda question: "GPA hiện tại là 8.30"
    )
    client = app_module.app.test_client()

    response = client.post("/chat", json={"message": "GPA hiện tại?"})

    assert response.status_code == 200
    payload = response.get_json()
    assert set(payload.keys()) == {"response"}
    assert isinstance(payload["response"], str)


def test_missing_message_returns_client_error(monkeypatch):
    monkeypatch.setattr(app_module, "ask_ai", lambda question: "unused")
    client = app_module.app.test_client()

    response = client.post("/chat", json={})

    assert response.status_code == 400
    assert "error" in response.get_json()


def test_empty_message_returns_client_error(monkeypatch):
    monkeypatch.setattr(app_module, "ask_ai", lambda question: "unused")
    client = app_module.app.test_client()

    response = client.post("/chat", json={"message": "   "})

    assert response.status_code == 400
    assert "error" in response.get_json()


def test_invalid_json_returns_client_error(monkeypatch):
    monkeypatch.setattr(app_module, "ask_ai", lambda question: "unused")
    client = app_module.app.test_client()

    response = client.post(
        "/chat", data="not-json", content_type="application/json"
    )

    assert response.status_code == 400
    assert "error" in response.get_json()
