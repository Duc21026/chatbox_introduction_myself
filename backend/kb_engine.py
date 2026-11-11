"""KB Engine — knowledge-base lookup with hybrid cosine + fuzzy scoring.

Architecture (from specs/004-self-intro-chatbot-api/plan.md):
  - Loads kb.json at startup, embeds all question variants via bge-m3 (Ollama).
  - Caches the embedding matrix to embeddings_cache.npz (invalidated by MD5 hash).
  - Scores each incoming query with 0.8*cosine + 0.2*fuzzy (rapidfuzz.WRatio).
  - Returns AnswerResponse | SuggestResponse | UnknownResponse dict, or None if
    embeddings are not yet loaded (caller falls back to RAG pipeline).
  - LLM (Qwen) is called only in the MID zone (0.55–0.78) for spell correction,
    re-using _rewrite_query() from chatbox.py.

Contract: specs/004-self-intro-chatbot-api/contracts/chat-api.md
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from typing import Optional

import numpy as np
from cachetools import LRUCache
from langchain_ollama import OllamaEmbeddings
from rapidfuzz import fuzz

try:
    from .text_normalization import normalize_query
except ImportError:
    from text_normalization import normalize_query

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration (from env vars, with defaults)
# ---------------------------------------------------------------------------

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))

def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if not raw or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise RuntimeError(f"Giá trị env {name} không hợp lệ: {raw!r}") from exc


def _env_int(name: str, default: int) -> int:
    return int(_env_float(name, default))


def _kb_path() -> str:
    return os.environ.get("CHATBOT_KB_PATH", os.path.join(BACKEND_DIR, "kb.json"))

def _cache_path() -> str:
    return os.path.join(BACKEND_DIR, "embeddings_cache.npz")

def _ollama_base_url() -> str:
    return os.environ.get("CHATBOT_OLLAMA_BASE_URL", "http://127.0.0.1:11434")

def _embedding_model() -> str:
    return os.environ.get("CHATBOT_EMBEDDING_MODEL", "bge-m3")

def _high_threshold() -> float:
    return _env_float("CHATBOT_KB_HIGH_THRESHOLD", 0.78)

def _mid_threshold() -> float:
    return _env_float("CHATBOT_KB_MID_THRESHOLD", 0.55)

def _max_suggestions() -> int:
    return _env_int("CHATBOT_KB_MAX_SUGGESTIONS", 3)

def _cache_size() -> int:
    return _env_int("CHATBOT_QUERY_CACHE_SIZE", 512)

# ---------------------------------------------------------------------------
# Profanity filter (minimal list — extend as needed)
# ---------------------------------------------------------------------------

_PROFANITY_LIST = frozenset([
    "đụ", "địt", "lồn", "cặc", "buồi", "đĩ", "chó", "mẹ", "bố",
])

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------

_kb_items: list[dict] = []          # validated KnowledgeItem list
_questions: list[str] = []          # original question strings (for display)
_questions_norm: list[str] = []     # normalized versions (for fuzzy)
_item_indices: list[int] = []       # kb_items index for each question
_embeddings: Optional[np.ndarray] = None  # shape (N, D), float32
_query_cache: Optional[LRUCache] = None   # initialized lazily

# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _get_query_cache() -> LRUCache:
    global _query_cache
    if _query_cache is None:
        _query_cache = LRUCache(maxsize=_cache_size())
    return _query_cache


def _kb_hash(kb_path: str) -> str:
    """Return MD5 hex digest of kb.json content."""
    with open(kb_path, "rb") as fh:
        return hashlib.md5(fh.read()).hexdigest()


def _save_cache(path: str, kb_hash: str, questions: list[str],
                item_indices: list[int], embeddings: np.ndarray) -> None:
    try:
        np.savez_compressed(
            path,
            kb_hash=np.array([kb_hash]),
            questions=np.array(questions, dtype=object),
            item_indices=np.array(item_indices, dtype=np.int32),
            embeddings=embeddings.astype(np.float32),
        )
    except Exception as exc:
        logger.warning("KB Engine: không thể lưu embedding cache (%s): %s", path, exc)


def _load_cache(path: str) -> Optional[dict]:
    if not os.path.isfile(path):
        return None
    try:
        data = np.load(path, allow_pickle=True)
        return {
            "kb_hash": str(data["kb_hash"][0]),
            "questions": data["questions"].tolist(),
            "item_indices": data["item_indices"].tolist(),
            "embeddings": data["embeddings"].astype(np.float32),
        }
    except Exception as exc:
        logger.warning("KB Engine: cache bị corrupt, sẽ build lại (%s): %s", path, exc)
        return None

# ---------------------------------------------------------------------------
# KB loading & validation
# ---------------------------------------------------------------------------

def _load_kb(kb_path: str) -> list[dict]:
    """Load and validate kb.json. Returns list of valid KnowledgeItem dicts."""
    if not os.path.isfile(kb_path):
        raise RuntimeError(
            f"KB Engine: không tìm thấy file kb.json tại '{kb_path}'. "
            "Hãy kiểm tra CHATBOT_KB_PATH."
        )
    try:
        with open(kb_path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"KB Engine: kb.json không hợp lệ (JSON parse error): {exc}") from exc

    if not isinstance(raw, list):
        raise RuntimeError("KB Engine: kb.json phải là một JSON array.")
    if len(raw) == 0:
        raise RuntimeError("KB Engine: kb.json trống, không có KnowledgeItem nào.")

    items: list[dict] = []
    seen_ids: set[str] = set()

    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            logger.warning("KB Engine: bỏ qua mục %d (không phải object)", i)
            continue

        item_id = item.get("id")
        if not item_id or not isinstance(item_id, str):
            logger.warning("KB Engine: bỏ qua mục %d — thiếu hoặc sai trường 'id'", i)
            continue

        if item_id in seen_ids:
            logger.warning("KB Engine: bỏ qua mục '%s' (id trùng lặp)", item_id)
            continue

        if not item.get("topic") or not isinstance(item.get("topic"), str):
            logger.warning("KB Engine: bỏ qua mục '%s' — thiếu hoặc sai 'topic'", item_id)
            continue

        questions = item.get("questions")
        if not isinstance(questions, list) or len(questions) == 0:
            logger.warning("KB Engine: bỏ qua mục '%s' — 'questions' phải là array không rỗng", item_id)
            continue

        answer = item.get("answer")
        bullets = item.get("answer_bullets")
        if (not answer or not str(answer).strip()) and (not bullets or len(bullets) == 0):
            logger.warning(
                "KB Engine: bỏ qua mục '%s' — cả 'answer' lẫn 'answer_bullets' đều null/rỗng", item_id
            )
            continue

        seen_ids.add(item_id)
        items.append(item)

    if not items:
        raise RuntimeError("KB Engine: không có KnowledgeItem hợp lệ nào sau khi validate.")

    return items

# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------

def _build_embeddings(questions: list[str], ollama_base_url: str,
                      embedding_model: str) -> np.ndarray:
    """Embed all normalized questions. Returns float32 array (N, D)."""
    embedder = OllamaEmbeddings(model=embedding_model, base_url=ollama_base_url)
    normalized = [normalize_query(q) or q for q in questions]
    vectors = embedder.embed_documents(normalized)
    return np.array(vectors, dtype=np.float32)

# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two 1-D vectors."""
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0.0:
        return 0.0
    return float(np.dot(a, b) / denom)


def _hybrid_score(query_emb: np.ndarray, candidate_emb: np.ndarray,
                  query_norm: str, candidate_norm: str) -> float:
    """0.8 * cosine_sim + 0.2 * WRatio/100."""
    cos = _cosine_sim(query_emb, candidate_emb)
    fuzzy = fuzz.WRatio(query_norm, candidate_norm) / 100.0
    return round(0.8 * cos + 0.2 * fuzzy, 4)


def _embed_query(query_norm: str) -> Optional[np.ndarray]:
    """Embed a single normalized query string."""
    try:
        embedder = OllamaEmbeddings(
            model=_embedding_model(), base_url=_ollama_base_url()
        )
        vec = embedder.embed_query(query_norm)
        return np.array(vec, dtype=np.float32)
    except Exception as exc:
        logger.warning("KB Engine: không thể embed câu hỏi: %s", exc)
        return None

# ---------------------------------------------------------------------------
# Response builders
# ---------------------------------------------------------------------------

def _build_answer_response(item: dict, score: float) -> dict:
    bullets = item.get("answer_bullets")
    if bullets and len(bullets) > 0:
        response_text = ", ".join(str(b) for b in bullets)
    else:
        response_text = str(item.get("answer") or "")
    return {
        "type": "answer",
        "score": round(score, 2),
        "response": response_text,
        "answer_bullets": bullets if (bullets and len(bullets) > 0) else None,
    }


def _build_suggest_response(candidates: list[tuple[str, float]]) -> dict:
    """candidates: list of (original_question, score)."""
    return {
        "type": "suggest",
        "response": "Ý bạn có phải là một trong những câu hỏi này không?",
        "suggestions": [
            {"question": q, "score": round(s, 2)} for q, s in candidates
        ],
    }


def _build_unknown_response() -> dict:
    topics = []
    seen: set[str] = set()
    for item in _kb_items:
        t = item.get("topic", "")
        if t and t not in seen:
            topics.append(t)
            seen.add(t)
    return {
        "type": "unknown",
        "response": "Mình chưa có thông tin về điều này.",
        "message": "Mình chưa có thông tin về điều này. Bạn có thể hỏi về các chủ đề sau:",
        "topics": topics,
    }

# ---------------------------------------------------------------------------
# Warm-up
# ---------------------------------------------------------------------------

def warm_up_kb() -> None:
    """Load kb.json, build or restore embedding cache.

    Called from app.py during server startup (alongside chatbox.warm_up()).
    Non-fatal: logs errors but does not raise so the server can still start
    and fall back to the RAG pipeline.
    """
    global _kb_items, _questions, _questions_norm, _item_indices, _embeddings

    kb_path = _kb_path()
    cache_path = _cache_path()

    try:
        items = _load_kb(kb_path)
    except RuntimeError as exc:
        logger.error("KB Engine: %s — KB Engine disabled, falling back to RAG.", exc)
        return

    # Flatten questions list
    questions: list[str] = []
    item_indices: list[int] = []
    for idx, item in enumerate(items):
        for q in item.get("questions", []):
            if isinstance(q, str) and q.strip():
                questions.append(q.strip())
                item_indices.append(idx)

    current_hash = _kb_hash(kb_path)
    t0 = time.monotonic()

    # Try to load from cache
    cached = _load_cache(cache_path)
    if cached and cached["kb_hash"] == current_hash:
        _kb_items = items
        _questions = cached["questions"]
        _questions_norm = [normalize_query(q) or q for q in _questions]
        _item_indices = cached["item_indices"]
        _embeddings = cached["embeddings"]
        elapsed = time.monotonic() - t0
        logger.info(
            "KB Engine: %d items, %d questions — embeddings loaded from cache in %.1fs",
            len(items), len(_questions), elapsed,
        )
        return

    # Build embeddings
    logger.info(
        "KB Engine: building embeddings for %d questions (kb.json changed or no cache)…",
        len(questions),
    )
    try:
        embeddings = _build_embeddings(questions, _ollama_base_url(), _embedding_model())
    except Exception as exc:
        logger.error("KB Engine: failed to build embeddings: %s — KB Engine disabled.", exc)
        return

    _kb_items = items
    _questions = questions
    _questions_norm = [normalize_query(q) or q for q in questions]
    _item_indices = item_indices
    _embeddings = embeddings

    _save_cache(cache_path, current_hash, questions, item_indices, embeddings)

    elapsed = time.monotonic() - t0
    logger.info(
        "KB Engine: %d items, %d questions — embeddings rebuilt (kb.json changed) in %.1fs",
        len(items), len(questions), elapsed,
    )

# ---------------------------------------------------------------------------
# Public query interface
# ---------------------------------------------------------------------------

def query(message: str) -> Optional[dict]:
    """Return ChatResponse dict or None if KB Engine is not ready / no match.

    None signals the caller (app.py) to fall back to the RAG pipeline.
    """
    if _embeddings is None or len(_embeddings) == 0:
        return None

    cache = _get_query_cache()

    # Normalize
    norm = normalize_query(message)
    if not norm:
        return _build_unknown_response()

    # Profanity check
    tokens = set(norm.split())
    if tokens & _PROFANITY_LIST:
        return _build_unknown_response()

    # LRU cache lookup
    if norm in cache:
        return cache[norm]

    # Embed query
    query_emb = _embed_query(norm)
    if query_emb is None:
        return None  # Ollama unavailable → fall back to RAG

    # Score all candidates
    n = len(_embeddings)
    scores = np.empty(n, dtype=np.float32)
    for i in range(n):
        scores[i] = _hybrid_score(query_emb, _embeddings[i], norm, _questions_norm[i])

    best_idx = int(np.argmax(scores))
    best_score = float(scores[best_idx])

    HIGH = _high_threshold()
    MID = _mid_threshold()

    # HIGH zone → answer directly
    if best_score >= HIGH:
        item = _kb_items[_item_indices[best_idx]]
        result = _build_answer_response(item, best_score)
        cache[norm] = result
        return result

    # MID zone → try spell correction via Qwen, then re-score
    if best_score >= MID:
        rewritten_norm = _try_rewrite(message)
        if rewritten_norm and rewritten_norm != norm:
            rw_emb = _embed_query(rewritten_norm)
            if rw_emb is not None:
                rw_scores = np.empty(n, dtype=np.float32)
                for i in range(n):
                    rw_scores[i] = _hybrid_score(
                        rw_emb, _embeddings[i], rewritten_norm, _questions_norm[i]
                    )
                rw_best_idx = int(np.argmax(rw_scores))
                rw_best_score = float(rw_scores[rw_best_idx])
                if rw_best_score >= HIGH:
                    item = _kb_items[_item_indices[rw_best_idx]]
                    result = _build_answer_response(item, rw_best_score)
                    cache[norm] = result
                    return result
                # Use rewritten scores for suggest if better
                if rw_best_score > best_score:
                    scores = rw_scores

        # Build suggest list from candidates ≥ MID
        candidates: list[tuple[str, float]] = []
        for i in np.argsort(scores)[::-1]:
            s = float(scores[i])
            if s < MID:
                break
            q_display = _questions[i]
            if not any(q_display == c[0] for c in candidates):
                candidates.append((q_display, s))
            if len(candidates) >= _max_suggestions():
                break

        if candidates:
            result = _build_suggest_response(candidates)
            cache[norm] = result
            return result

    # Below MID → unknown
    result = _build_unknown_response()
    cache[norm] = result
    return result


def _try_rewrite(original_message: str) -> Optional[str]:
    """Call Qwen spell-corrector from chatbox._rewrite_query() if available."""
    try:
        try:
            from .chatbox import _rewrite_query
        except ImportError:
            from chatbox import _rewrite_query
        return _rewrite_query(original_message)
    except Exception as exc:
        logger.debug("KB Engine: spell rewrite failed: %s", exc)
        return None
