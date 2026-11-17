"""Health report for the deployment runtime.

Cheap by design: it reads the bundled index metadata and the current source
hash, but never calls Cloudflare, Ollama or any other network service.
"""

from __future__ import annotations

import logging

try:
    from . import embedding_provider, source_store, vector_store
except ImportError:  # direct execution
    import embedding_provider
    import source_store
    import vector_store

logger = logging.getLogger(__name__)


def health_report() -> dict:
    source = None
    try:
        source = source_store.get_source(source_store.default_config())
    except Exception as exc:
        logger.warning("Health: không đọc được nguồn hiện tại (%s).", type(exc).__name__)

    info = vector_store.inspect()
    provider = embedding_provider.provider_status()
    source_hash_matches = bool(
        source is not None
        and info.get("vectors_loaded")
        and info.get("source_kb_hash") == getattr(source, "kb_hash", None)
    )
    provider_ready = bool(provider.get("ready"))
    provider_name = provider.get("name") or "none"
    healthy = (
        bool(info.get("vectors_loaded"))
        and source_hash_matches
        and provider_name != "none"
        and provider_ready
    )

    if healthy:
        message = "Sẵn sàng"
    elif not info.get("vectors_loaded"):
        message = "Chưa có chỉ mục vector; dùng fallback từ khoá."
    elif not source_hash_matches:
        message = "Chỉ mục vector đã cũ; dùng fallback từ khoá."
    elif provider_name == "none":
        message = "Embedding đang tắt; dùng fallback từ khoá."
    elif not provider_ready:
        message = "Thiếu cấu hình embedding; dùng fallback từ khoá."
    else:
        message = "Đang suy giảm; dùng fallback từ khoá."

    return {
        "status": "ok" if healthy else "degraded",
        "vectors_loaded": bool(info.get("vectors_loaded")),
        "vector_count": int(info.get("vector_count") or 0),
        "model": info.get("model"),
        "dim": int(info.get("dim") or 0),
        "normalizer_version": info.get("normalizer_version"),
        "source_hash_matches": source_hash_matches,
        "embedding_provider": provider_name,
        "provider_ready": provider_ready,
        "message": message,
    }
