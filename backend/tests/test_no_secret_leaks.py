import json

from backend import health


def test_health_response_does_not_leak_secrets(monkeypatch):
    monkeypatch.setenv("CF_API_TOKEN", "supersecret-token-value")
    monkeypatch.setenv("CF_ACCOUNT_ID", "account-id-value")
    monkeypatch.setattr(
        health.source_store,
        "get_source",
        lambda config=None: type("S", (), {"kb_hash": "hash"})(),
    )
    monkeypatch.setattr(
        health.vector_store,
        "inspect",
        lambda path=None: {
            "vectors_loaded": True,
            "vector_count": 1,
            "model": "@cf/baai/bge-m3",
            "dim": 2,
            "normalizer_version": "2",
            "source_kb_hash": "hash",
        },
    )
    monkeypatch.setattr(
        health.embedding_provider,
        "provider_status",
        lambda: {"name": "cloudflare", "ready": True, "model": "m", "reason": None},
    )

    payload = json.dumps(health.health_report())
    assert "supersecret-token-value" not in payload
    assert "account-id-value" not in payload
