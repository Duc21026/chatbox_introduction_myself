from types import SimpleNamespace

from backend.app import create_app


class FakeAssistant:
    def __init__(self, payload=None):
        self.payload = payload or {
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

    def handle(self, **kwargs):
        return self.payload


def _app(monkeypatch, assistant=None):
    import backend.app as app_module

    monkeypatch.setattr(
        app_module.health,
        "health_report",
        lambda: {"status": "ok", "vectors_loaded": True, "source_hash_matches": True},
    )
    return create_app("deployment", assistant=assistant or FakeAssistant())


def test_chat_contract_shape(monkeypatch):
    app = _app(monkeypatch)
    response = app.test_client().post("/chat", json={"message": "câu hỏi"})

    assert response.status_code == 200
    assert response.get_json()["type"] == "answer"


def test_chat_rejects_blank_message(monkeypatch):
    app = _app(monkeypatch)
    response = app.test_client().post("/chat", json={"message": "   "})
    assert response.status_code == 422


def test_chat_rejects_long_message(monkeypatch):
    app = _app(monkeypatch)
    response = app.test_client().post("/chat", json={"message": "x" * 201})
    assert response.status_code == 422


def test_chat_rejects_invalid_json(monkeypatch):
    app = _app(monkeypatch)
    response = app.test_client().post(
        "/chat", data="not-json", content_type="application/json"
    )
    assert response.status_code == 400


def test_health_endpoint(monkeypatch):
    app = _app(monkeypatch)
    for path in ("/health", "/api/health"):
        response = app.test_client().get(path)
        assert response.status_code == 200
        assert response.get_json()["status"] == "ok"


def test_services_paths(monkeypatch):
    app = _app(monkeypatch)
    for path in ("/chat", "/api/chat"):
        response = app.test_client().post(path, json={"message": "câu hỏi"})
        assert response.status_code == 200
        assert response.get_json()["type"] == "answer"
