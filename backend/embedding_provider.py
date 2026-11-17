"""Embedding provider abstraction for local and deployed runtimes.

Deployment uses Cloudflare Workers AI (``@cf/baai/bge-m3``); local/Docker can
keep using Ollama.  Every failure is converted to ``None`` so the caller can
fall back to lexical/fuzzy matching and never return HTTP 500 for a valid
question.
"""

from __future__ import annotations

import json
import logging
import math
import os
import time
import urllib.error
import urllib.request
from typing import Optional

logger = logging.getLogger(__name__)

CLOUDFLARE_MODEL = "@cf/baai/bge-m3"
CLOUDFLARE_ENDPOINT = (
    "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/@cf/baai/bge-m3"
)
DEFAULT_QUERY_TIMEOUT = 3.0
DEFAULT_BUILD_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 1


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def provider_name() -> str:
    return os.environ.get("CHATBOT_EMBEDDING_PROVIDER", "ollama").strip().lower()


def model_name() -> str:
    return os.environ.get("CHATBOT_EMBEDDING_MODEL", CLOUDFLARE_MODEL).strip()


def _cloudflare_credentials():
    account_id = os.environ.get("CF_ACCOUNT_ID", "").strip()
    token = os.environ.get("CF_API_TOKEN", "").strip()
    return account_id, token


def provider_status() -> dict:
    """Return provider readiness without making a network call."""

    name = provider_name()
    if name == "none":
        return {"name": "none", "ready": True, "model": model_name(), "reason": "disabled"}
    if name == "cloudflare":
        account_id, token = _cloudflare_credentials()
        ready = bool(account_id and token)
        return {
            "name": "cloudflare",
            "ready": ready,
            "model": model_name(),
            "reason": None if ready else "Thiếu CF_ACCOUNT_ID hoặc CF_API_TOKEN",
        }
    if name == "ollama":
        return {"name": "ollama", "ready": True, "model": model_name(), "reason": None}
    return {"name": name, "ready": False, "model": model_name(), "reason": "provider không hỗ trợ"}


def _parse_cloudflare_vectors(payload, expected: int) -> Optional[list[list[float]]]:
    if not isinstance(payload, dict) or payload.get("success") is False:
        return None
    result = payload.get("result")
    if isinstance(result, dict):
        vectors = result.get("data")
        if vectors is None:
            vectors = result.get("embeddings")
        if vectors is None and isinstance(result.get("response"), list):
            vectors = result.get("response")
    elif isinstance(result, list):
        vectors = result
    else:
        return None

    if not isinstance(vectors, list) or len(vectors) != expected:
        return None

    parsed = []
    dim = None
    for vector in vectors:
        if isinstance(vector, dict):
            vector = vector.get("embedding") or vector.get("vector")
        if not isinstance(vector, (list, tuple)) or not vector:
            return None
        if dim is None:
            dim = len(vector)
        if len(vector) != dim:
            return None
        values = []
        for value in vector:
            if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                return None
            values.append(float(value))
        parsed.append(values)
    return parsed


def _cloudflare_embed(texts: list[str], timeout: float) -> Optional[list[list[float]]]:
    account_id, token = _cloudflare_credentials()
    if not account_id or not token:
        logger.warning("Cloudflare embedding chưa được cấu hình; dùng fallback.")
        return None

    url = CLOUDFLARE_ENDPOINT.format(account_id=account_id)
    body = json.dumps({"text": list(texts)}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )

    retries = max(0, _env_int("CHATBOT_EMBEDDING_RETRIES", DEFAULT_MAX_RETRIES))
    attempt = 0
    while attempt <= retries:
        attempt += 1
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
            parsed = _parse_cloudflare_vectors(payload, len(texts))
            if parsed is None:
                logger.warning("Cloudflare trả về vector không hợp lệ; dùng fallback.")
            return parsed
        except urllib.error.HTTPError as exc:
            if exc.code in {400, 401, 403, 429}:
                logger.warning("Cloudflare từ chối yêu cầu (HTTP %s); dùng fallback.", exc.code)
                return None
            logger.warning("Cloudflare lỗi HTTP %s (lần %s); dùng fallback.", exc.code, attempt)
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            logger.warning("Cloudflare không phản hồi (%s, lần %s); dùng fallback.", type(exc).__name__, attempt)
        if attempt <= retries:
            time.sleep(0.2)
    return None


def _ollama_embed(texts: list[str]) -> Optional[list[list[float]]]:
    try:
        from langchain_ollama import OllamaEmbeddings
    except ImportError:
        logger.warning("Không có langchain_ollama; dùng fallback.")
        return None
    try:
        embedder = OllamaEmbeddings(
            model=model_name(),
            base_url=os.environ.get("CHATBOT_OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        )
        vectors = embedder.embed_documents(list(texts))
        return [[float(value) for value in vector] for vector in vectors]
    except Exception as exc:
        logger.warning("Ollama embedding lỗi (%s); dùng fallback.", type(exc).__name__)
        return None


def embed_texts(texts, timeout: Optional[float] = None) -> Optional[list[list[float]]]:
    texts = [str(text) for text in (texts or [])]
    if not texts:
        return []
    name = provider_name()
    if name == "none":
        return None
    if name == "cloudflare":
        return _cloudflare_embed(
            texts, timeout if timeout is not None else _env_float("CHATBOT_EMBEDDING_TIMEOUT", DEFAULT_QUERY_TIMEOUT)
        )
    if name == "ollama":
        return _ollama_embed(texts)
    logger.warning("Provider embedding không hỗ trợ: %s; dùng fallback.", name)
    return None


def embed_query(text: str, timeout: Optional[float] = None) -> Optional[list[float]]:
    vectors = embed_texts([text], timeout=timeout)
    if not vectors:
        return None
    return vectors[0]
