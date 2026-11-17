from types import SimpleNamespace

from backend import health


def _source(hash_value="abc"):
    return SimpleNamespace(kb_hash=hash_value)


def test_health_ok(monkeypatch):
    monkeypatch.setattr(health.source_store, "get_source", lambda config=None: _source())
    monkeypatch.setattr(
        health.vector_store,
        "inspect",
        lambda path=None: {
            "vectors_loaded": True,
            "vector_count": 10,
            "model": "@cf/baai/bge-m3",
            "dim": 1024,
            "normalizer_version": "2",
            "source_kb_hash": "abc",
        },
    )
    monkeypatch.setattr(
        health.embedding_provider,
        "provider_status",
        lambda: {"name": "cloudflare", "ready": True, "model": "@cf/baai/bge-m3", "reason": None},
    )

    report = health.health_report()
    assert report["status"] == "ok"
    assert report["source_hash_matches"] is True
    assert report["vector_count"] == 10


def test_health_degraded_on_stale_hash(monkeypatch):
    monkeypatch.setattr(health.source_store, "get_source", lambda config=None: _source("new"))
    monkeypatch.setattr(
        health.vector_store,
        "inspect",
        lambda path=None: {
            "vectors_loaded": True,
            "vector_count": 10,
            "model": "@cf/baai/bge-m3",
            "dim": 1024,
            "normalizer_version": "2",
            "source_kb_hash": "old",
        },
    )
    monkeypatch.setattr(
        health.embedding_provider,
        "provider_status",
        lambda: {"name": "cloudflare", "ready": True, "model": "@cf/baai/bge-m3", "reason": None},
    )

    report = health.health_report()
    assert report["status"] == "degraded"
    assert report["source_hash_matches"] is False


def test_health_degraded_without_provider(monkeypatch):
    monkeypatch.setattr(health.source_store, "get_source", lambda config=None: _source())
    monkeypatch.setattr(
        health.vector_store,
        "inspect",
        lambda path=None: {
            "vectors_loaded": True,
            "vector_count": 10,
            "model": "@cf/baai/bge-m3",
            "dim": 1024,
            "normalizer_version": "2",
            "source_kb_hash": "abc",
        },
    )
    monkeypatch.setattr(
        health.embedding_provider,
        "provider_status",
        lambda: {"name": "none", "ready": True, "model": "x", "reason": "disabled"},
    )

    report = health.health_report()
    assert report["status"] == "degraded"
    assert report["embedding_provider"] == "none"
