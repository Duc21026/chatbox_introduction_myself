import json
import urllib.error

import pytest

from backend import embedding_provider


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


@pytest.fixture
def cloudflare_env(monkeypatch):
    monkeypatch.setenv("CHATBOT_EMBEDDING_PROVIDER", "cloudflare")
    monkeypatch.setenv("CF_ACCOUNT_ID", "account")
    monkeypatch.setenv("CF_API_TOKEN", "token")
    monkeypatch.setenv("CHATBOT_EMBEDDING_RETRIES", "0")


def test_cloudflare_success_parses_result_data(monkeypatch, cloudflare_env):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append((request, timeout))
        return FakeResponse(
            {"success": True, "result": {"data": [[0.1, 0.2], [0.3, 0.4]]}}
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    vectors = embedding_provider.embed_texts(["a", "b"])

    assert vectors == [[0.1, 0.2], [0.3, 0.4]]
    assert len(calls) == 1
    assert calls[0][1] == 3.0


def test_cloudflare_accepts_result_embeddings(monkeypatch, cloudflare_env):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout: FakeResponse(
            {"success": True, "result": {"embeddings": [[1.0, 2.0]]}}
        ),
    )
    assert embedding_provider.embed_query("a") == [1.0, 2.0]


@pytest.mark.parametrize(
    "error",
    [
        urllib.error.HTTPError("http://x", 401, "unauthorized", {}, None),
        urllib.error.HTTPError("http://x", 403, "forbidden", {}, None),
        urllib.error.HTTPError("http://x", 429, "quota", {}, None),
        urllib.error.HTTPError("http://x", 500, "server", {}, None),
        urllib.error.URLError("offline"),
        TimeoutError("slow"),
    ],
)
def test_cloudflare_failures_return_none(monkeypatch, cloudflare_env, error):
    def fake_urlopen(request, timeout):
        raise error

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    assert embedding_provider.embed_texts(["a"]) is None


def test_cloudflare_invalid_schema_returns_none(monkeypatch, cloudflare_env):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout: FakeResponse(
            {"success": True, "result": {"data": [[0.1, 0.2]]}}
        ),
    )
    assert embedding_provider.embed_texts(["a", "b"]) is None


def test_none_provider_never_calls_network(monkeypatch):
    monkeypatch.setenv("CHATBOT_EMBEDDING_PROVIDER", "none")

    def fail(*args, **kwargs):
        raise AssertionError("không được gọi mạng")

    monkeypatch.setattr("urllib.request.urlopen", fail)
    assert embedding_provider.embed_texts(["a"]) is None
    assert embedding_provider.embed_query("a") is None


def test_provider_status_reports_missing_cloudflare_config(monkeypatch):
    monkeypatch.setenv("CHATBOT_EMBEDDING_PROVIDER", "cloudflare")
    monkeypatch.delenv("CF_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("CF_API_TOKEN", raising=False)

    status = embedding_provider.provider_status()
    assert status["name"] == "cloudflare"
    assert status["ready"] is False
    assert "CF_ACCOUNT_ID" in status["reason"]


def test_default_model_follows_provider(monkeypatch):
    monkeypatch.delenv("CHATBOT_EMBEDDING_MODEL", raising=False)
    monkeypatch.setenv("CHATBOT_EMBEDDING_PROVIDER", "cloudflare")
    assert embedding_provider.model_name() == "@cf/baai/bge-m3"
    monkeypatch.setenv("CHATBOT_EMBEDDING_PROVIDER", "ollama")
    assert embedding_provider.model_name() == "bge-m3"
