"""KB Engine — knowledge-base lookup with hybrid cosine + fuzzy scoring.

Architecture (from specs/004-self-intro-chatbot-api/plan.md):
  - Loads kb.json at startup, embeds all question variants via bge-m3 (Ollama).
  - Caches the embedding matrix to embeddings_cache.npz (invalidated by MD5 hash).
  - Scores each incoming query with 0.8*cosine + 0.2*fuzzy (rapidfuzz.WRatio).
  - Returns :class:`QueryEvaluation` with all scored candidates.  The caller
    (``assistant``) decides between answer / suggest / clarify; this module no
    longer builds an ``unknown`` response and never calls an LLM on the main
    path.

Contracts: specs/004-self-intro-chatbot-api/contracts/chat-api.md and
specs/006-tiered-suggest-ingest/contracts/chat-api.md
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from cachetools import LRUCache
from rapidfuzz import fuzz

try:
    from . import embedding_provider, source_store, vector_store
    from .text_normalization import NORMALIZER_VERSION, normalize_query
except ImportError:
    import embedding_provider
    import source_store
    import vector_store
    from text_normalization import NORMALIZER_VERSION, normalize_query

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

def _embedding_model() -> str:
    return embedding_provider.model_name()

def _high_threshold() -> float:
    return _env_float("CHATBOT_KB_HIGH_THRESHOLD", 0.78)

def _suggest_threshold() -> float:
    return _env_float("CHATBOT_SUGGEST_THRESHOLD", 0.45)

def _ambiguity_gap() -> float:
    return _env_float("CHATBOT_AMBIGUITY_GAP", 0.05)

def _max_suggestions() -> int:
    raw = os.environ.get("CHATBOT_MAX_SUGGESTIONS")
    if raw is None or not raw.strip():
        raw = os.environ.get("CHATBOT_KB_MAX_SUGGESTIONS", "4")
    try:
        return max(1, int(raw))
    except ValueError as exc:
        raise RuntimeError(
            f"Giá trị biến môi trường CHATBOT_MAX_SUGGESTIONS không hợp lệ: {raw!r}"
        ) from exc


def _warn_deprecated_env() -> None:
    if os.environ.get("CHATBOT_KB_MID_THRESHOLD"):
        logger.warning(
            "CHATBOT_KB_MID_THRESHOLD đã deprecated và bị bỏ qua; "
            "dùng CHATBOT_SUGGEST_THRESHOLD thay thế."
        )

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
_evaluation_cache: Optional[LRUCache] = None
_kb_hash_value: Optional[str] = None
_source_signature = None

# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _get_query_cache() -> LRUCache:
    global _query_cache
    if _query_cache is None:
        _query_cache = LRUCache(maxsize=_cache_size())
    return _query_cache


def _get_evaluation_cache() -> LRUCache:
    global _evaluation_cache
    if _evaluation_cache is None:
        _evaluation_cache = LRUCache(maxsize=_cache_size())
    return _evaluation_cache


@dataclass
class QueryEvaluation:
    norm: str
    word_count: int
    query_vec: Optional[np.ndarray]
    top1: float = 0.0
    top2: float = 0.0
    candidates: list[dict] = field(default_factory=list)
    ambiguous: bool = False
    answer_item: Optional[dict] = None
    embeddings_ready: bool = False
    profane: bool = False


def get_items() -> list[dict]:
    """Return a copy of the validated KB items (for topic menus)."""

    _refresh_if_changed()
    return list(_kb_items)


def _kb_hash(source) -> str:
    """Return the KB hash provided by a ``DerivedSource``."""
    return source.kb_hash


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

def _load_kb(raw_items) -> list[dict]:
    """Validate KB items supplied by a ``DerivedSource``."""

    items: list[dict] = []
    seen_ids: set[str] = set()

    for i, raw_item in enumerate(raw_items or []):
        if hasattr(raw_item, "as_dict"):
            item = raw_item.as_dict()
        elif isinstance(raw_item, dict):
            item = raw_item
        else:
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

    return items

# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------

def _build_embeddings(questions: list[str]) -> np.ndarray:
    """Embed all normalized questions. Returns float32 array (N, D)."""
    normalized = [normalize_query(q) or q for q in questions]
    vectors = embedding_provider.embed_texts(normalized)
    if not vectors:
        raise RuntimeError("embedding provider không trả về vector")
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


def _fuzzy_weight() -> float:
    value = _env_float("CHATBOT_FUZZY_WEIGHT", 0.2)
    return min(1.0, max(0.0, value))


def _hybrid_score(query_emb: np.ndarray, candidate_emb: np.ndarray,
                  query_norm: str, candidate_norm: str) -> float:
    """(1 - FUZZY_W) * cosine_sim + FUZZY_W * WRatio/100."""
    cos = _cosine_sim(query_emb, candidate_emb)
    fuzzy = fuzz.WRatio(query_norm, candidate_norm) / 100.0
    weight = _fuzzy_weight()
    return round((1.0 - weight) * cos + weight * fuzzy, 4)


def _embed_query(query_norm: str) -> Optional[np.ndarray]:
    """Embed a single normalized query string."""
    try:
        vec = embedding_provider.embed_query(query_norm)
        if not vec:
            return None
        return np.array(vec, dtype=np.float32)
    except Exception as exc:
        logger.warning("KB Engine: không thể embed câu hỏi: %s", type(exc).__name__)
        return None

# ---------------------------------------------------------------------------
# Warm-up
# ---------------------------------------------------------------------------

def _is_deployment_runtime() -> bool:
    runtime = os.environ.get("CHATBOT_RUNTIME", "").strip().lower()
    return runtime == "deployment" or bool(os.environ.get("VERCEL"))


def _is_legacy_runtime() -> bool:
    return os.environ.get("CHATBOT_LEGACY_SOURCES", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _default_source():
    if _is_legacy_runtime():
        try:
            from . import chatbox
        except ImportError:
            import chatbox
        return chatbox.get_source()
    return source_store.get_source(source_store.default_config())


def _index_vectors(source, items):
    """Load a precomputed index only when it matches the current source."""

    index = vector_store.load(
        expected_model=_embedding_model(),
        expected_normalizer=NORMALIZER_VERSION,
    )
    if index is None:
        return None
    if not index.matches_source(source):
        logger.warning(
            "KB Engine: chỉ mục vector đã cũ (hash không khớp); dùng fallback lexical."
        )
        return None
    if not vector_store.matches_entries(index, source):
        logger.warning(
            "KB Engine: chỉ mục vector có item không còn trong nguồn; dùng fallback lexical."
        )
        return None

    index_by_id = {item["id"]: idx for idx, item in enumerate(items)}
    questions = []
    norms = []
    item_indices = []
    vectors = []
    for entry in index.entries:
        idx = index_by_id.get(entry.item_id)
        if idx is None:
            return None
        questions.append(entry.question)
        norms.append(entry.norm)
        item_indices.append(idx)
        vectors.append(entry.vector)
    return questions, norms, item_indices, np.array(vectors, dtype=np.float32)


def warm_up_kb(source=None) -> None:
    """Load KB items from the unified source and restore precomputed vectors.

    The deployment runtime never builds embeddings at startup: if the bundled
    index is missing/stale it logs a warning and uses lexical/fuzzy fallback.
    Local/Docker keeps the previous Ollama cache behavior.
    """
    global _kb_items, _questions, _questions_norm, _item_indices, _embeddings
    global _kb_hash_value, _source_signature

    if source is None:
        try:
            source = _default_source()
        except Exception as exc:
            logger.error(
                "KB Engine: không đọc được nguồn hợp nhất: %s — KB Engine disabled.",
                exc,
            )
            return

    items = _load_kb(source.kb_items)
    _source_signature = source.signature
    current_hash = _kb_hash(source)
    _kb_hash_value = current_hash

    if not items:
        _kb_items = []
        _questions = []
        _questions_norm = []
        _item_indices = []
        _embeddings = None
        logger.info("KB Engine: nguồn không có bản ghi qa — KB Engine disabled.")
        return

    questions: list[str] = []
    item_indices: list[int] = []
    for idx, item in enumerate(items):
        for q in item.get("questions", []):
            if isinstance(q, str) and q.strip():
                questions.append(q.strip())
                item_indices.append(idx)

    _kb_items = items
    _questions = questions
    _questions_norm = [normalize_query(q) or q for q in questions]
    _item_indices = item_indices

    loaded = _index_vectors(source, items)
    if loaded is not None:
        _questions, _questions_norm, _item_indices, _embeddings = loaded
        logger.info(
            "KB Engine: %d items, %d questions — precomputed vectors loaded.",
            len(items), len(_questions),
        )
        return

    _embeddings = None
    if _is_deployment_runtime():
        logger.warning(
            "KB Engine: không có chỉ mục vector hợp lệ trong môi trường deploy; "
            "dùng fallback lexical/fuzzy."
        )
        return

    cache_path = _cache_path()
    t0 = time.monotonic()
    cached = _load_cache(cache_path)
    if cached and cached["kb_hash"] == current_hash:
        _questions = cached["questions"]
        _questions_norm = [normalize_query(q) or q for q in _questions]
        _item_indices = cached["item_indices"]
        _embeddings = cached["embeddings"]
        logger.info(
            "KB Engine: %d items, %d questions — embeddings loaded from cache in %.1fs",
            len(items), len(_questions), time.monotonic() - t0,
        )
        return

    logger.info(
        "KB Engine: building embeddings for %d questions (source changed or no cache)…",
        len(questions),
    )
    try:
        embeddings = _build_embeddings(questions)
    except Exception as exc:
        logger.error(
            "KB Engine: failed to build embeddings: %s — dùng fallback lexical.",
            type(exc).__name__,
        )
        return

    _embeddings = embeddings
    _save_cache(cache_path, current_hash, questions, item_indices, embeddings)
    logger.info(
        "KB Engine: %d items, %d questions — embeddings rebuilt (source changed) in %.1fs",
        len(items), len(questions), time.monotonic() - t0,
    )


def _refresh_if_changed() -> None:
    """Rebuild KB state when the unified source's KB hash changes."""

    if _kb_hash_value is None:
        return
    try:
        source = _default_source()
    except Exception:
        return
    if source.kb_hash == _kb_hash_value:
        return
    logger.info("KB Engine: phát hiện nguồn thay đổi, đang làm mới chỉ mục KB…")
    warm_up_kb(source)

# ---------------------------------------------------------------------------
# Public query interface
# ---------------------------------------------------------------------------

def evaluate(message: str, query_vec: Optional[np.ndarray] = None) -> QueryEvaluation:
    """Score a question against the KB without calling any LLM.

    The caller receives every scored question (sorted descending) so it can
    build suggestions, while ``top1``/``top2`` drive the three-tier decision.
    """

    _warn_deprecated_env()
    _refresh_if_changed()
    norm = normalize_query(message) if isinstance(message, str) else ""
    tokens = set(norm.split())
    profane = bool(tokens & _PROFANITY_LIST)
    if not norm or profane:
        return QueryEvaluation(
            norm=norm,
            word_count=0 if not norm else len(norm.split()),
            query_vec=None,
            profane=profane,
        )

    if _embeddings is None or len(_embeddings) == 0:
        return QueryEvaluation(
            norm=norm,
            word_count=len(norm.split()),
            query_vec=None,
        )

    cache = _get_evaluation_cache()
    cached = cache.get(norm)
    if cached is not None and query_vec is None:
        return cached

    if query_vec is None:
        query_vec = _embed_query(norm)
    if query_vec is None:
        return QueryEvaluation(
            norm=norm,
            word_count=len(norm.split()),
            query_vec=None,
        )

    query_vec = np.asarray(query_vec, dtype=np.float32)
    n = len(_embeddings)
    scores = np.empty(n, dtype=np.float32)
    for i in range(n):
        scores[i] = _hybrid_score(query_vec, _embeddings[i], norm, _questions_norm[i])

    order = np.argsort(scores)[::-1]
    candidates = []
    for i in order:
        item = _kb_items[_item_indices[int(i)]]
        question = _questions[int(i)]
        candidates.append(
            {
                "source": "kb",
                "item_id": item.get("id"),
                "topic": item.get("topic"),
                "question": question,
                "norm": _questions_norm[int(i)],
                "score": round(float(scores[int(i)]), 4),
                "question_count": len(item.get("questions") or []),
                "answer": item.get("answer"),
                "answer_bullets": item.get("answer_bullets"),
            }
        )

    top1 = float(scores[order[0]]) if n else 0.0
    top2 = float(scores[order[1]]) if n > 1 else 0.0
    gap = _ambiguity_gap()
    suggest_floor = _suggest_threshold()
    high = _high_threshold()
    same_item_second = (
        len(candidates) > 1
        and candidates[0].get("item_id") == candidates[1].get("item_id")
    )
    ambiguous = (
        (len(norm.split()) <= 3 and top1 < 0.95 and not same_item_second)
        or ((top1 - top2) < gap and not same_item_second)
        or (suggest_floor <= top1 < high)
    )
    answer_item = None
    if candidates and top1 >= high and not ambiguous:
        answer_item = _kb_items[_item_indices[int(order[0])]]

    evaluation = QueryEvaluation(
        norm=norm,
        word_count=len(norm.split()),
        query_vec=query_vec,
        top1=round(top1, 4),
        top2=round(top2, 4),
        candidates=candidates,
        ambiguous=bool(ambiguous),
        answer_item=answer_item,
        embeddings_ready=True,
    )
    cache[norm] = evaluation
    return evaluation


def query(message: str) -> Optional[dict]:
    """Legacy wrapper. New code should use :func:`evaluate` via ``assistant``.

    Returns an answer only for a crisp high-confidence KB match; all other
    cases return ``None`` so callers can fall through to suggestions/documents.
    """

    evaluation = evaluate(message)
    if not evaluation.embeddings_ready or evaluation.answer_item is None:
        return None
    item = evaluation.answer_item
    bullets = item.get("answer_bullets")
    response_text = (
        ", ".join(str(b) for b in bullets)
        if bullets
        else str(item.get("answer") or "")
    )
    return {
        "type": "answer",
        "score": round(evaluation.top1, 2),
        "response": response_text,
        "answer_bullets": bullets if bullets else None,
    }


def _try_rewrite(original_message: str) -> Optional[str]:
    """Deprecated compatibility helper; never called by ``evaluate``."""

    try:
        try:
            from .chatbox import _rewrite_query
        except ImportError:
            from chatbox import _rewrite_query
        return _rewrite_query(original_message)
    except Exception as exc:
        logger.debug("KB Engine: spell rewrite failed: %s", exc)
        return None
