"""Suggestion ranking and clarify-level construction.

All functions are pure Python (no Ollama calls) so they can be unit tested
with candidate dictionaries from ``kb_engine.evaluate`` or ``doc_index``.
"""

from __future__ import annotations

import hashlib

from rapidfuzz import fuzz

try:
    from .text_normalization import normalize_query, normalize_text, tokenize
except ImportError:  # direct execution
    from text_normalization import normalize_query, normalize_text, tokenize

MAX_TOPICS = 8
MAX_EXAMPLES = 3


def _digest(text: str, length: int) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:length]


def suggestion_id(candidate: dict) -> str:
    """Stable per-question identifier used by ``shown_ids``."""

    source = candidate.get("source") or "kb"
    if source in {"doc", "rag"}:
        file_name = candidate.get("file") or candidate.get("item_id") or "document"
        heading = candidate.get("heading") or ""
        return f"doc:{file_name}#{heading}"
    question = candidate.get("question") or ""
    norm = candidate.get("norm") or normalize_query(question) or question
    item_id = candidate.get("item_id")
    if item_id:
        if int(candidate.get("question_count") or 1) <= 1:
            return str(item_id)
        return f"{item_id}#{_digest(norm, 8)}"
    return f"kb:{_digest(norm, 12)}"


def keyword_score(query_norm: str, candidate: dict) -> float:
    """Topic/keyword overlap plus fuzzy string similarity (0..1)."""

    query_tokens = set(tokenize(query_norm))
    if not query_tokens:
        return 0.0
    candidate_text = " ".join(
        str(part or "")
        for part in (
            candidate.get("topic"),
            candidate.get("question"),
            " ".join(candidate.get("keywords") or []),
        )
    )
    candidate_tokens = set(tokenize(candidate_text))
    overlap = (
        len(query_tokens & candidate_tokens) / len(query_tokens)
        if query_tokens
        else 0.0
    )
    question_norm = candidate.get("norm") or normalize_query(
        candidate.get("question") or ""
    )
    fuzzy = fuzz.WRatio(query_norm, question_norm or "") / 100.0
    return round(0.6 * overlap + 0.4 * fuzzy, 4)


def _combined_score(query_norm: str, candidate: dict) -> float:
    embedding_part = float(candidate.get("score") or 0.0)
    keyword_part = keyword_score(query_norm, candidate)
    return round(0.6 * embedding_part + 0.4 * keyword_part, 4)


def build_suggestions(
    query_norm: str,
    candidates: list[dict],
    shown_ids=None,
    max_suggestions: int = 4,
) -> list[dict]:
    """Rank candidates, de-duplicate, drop shown ids, return 0..N items."""

    shown = set(shown_ids or [])
    ranked = []
    seen = set()
    for candidate in candidates:
        item_id = suggestion_id(candidate)
        if item_id in shown or item_id in seen:
            continue
        question = (candidate.get("question") or "").strip()
        if not question:
            continue
        seen.add(item_id)
        ranked.append(
            {
                "id": item_id,
                "question": question,
                "score": round(_combined_score(query_norm, candidate), 2),
            }
        )
    ranked.sort(key=lambda item: item["score"], reverse=True)
    return ranked[: max(1, int(max_suggestions))]


def candidates_from_items(items: list[dict]) -> list[dict]:
    """Flatten KB items into one candidate per question."""

    candidates = []
    for item in items or []:
        questions = item.get("questions") or []
        for question in questions:
            if not isinstance(question, str) or not question.strip():
                continue
            candidates.append(
                {
                    "source": "kb",
                    "item_id": item.get("id"),
                    "topic": item.get("topic"),
                    "question": question.strip(),
                    "norm": normalize_query(question),
                    "score": 0.0,
                    "question_count": len(questions),
                    "keywords": item.get("keywords") or [],
                }
            )
    return candidates


def build_fuzzy_suggestions(
    query_norm: str,
    items: list[dict],
    shown_ids=None,
    max_suggestions: int = 4,
) -> list[dict]:
    """Fallback when embeddings are unavailable (no LLM, no network)."""

    candidates = candidates_from_items(items)
    for candidate in candidates:
        candidate["score"] = keyword_score(query_norm, candidate)
    q = query_norm or ""
    candidates.sort(key=lambda item: keyword_score(q, item), reverse=True)
    return build_suggestions(q, candidates, shown_ids, max_suggestions)


def build_topics(
    kb_items: list[dict],
    doc_topics=None,
    max_topics: int = MAX_TOPICS,
) -> list[str]:
    """Merge KB topics and document labels, most populated first."""

    counts: dict[str, int] = {}
    order: list[str] = []

    def add(label, weight=1):
        label = str(label or "").strip()
        if not label:
            return
        if label not in counts:
            order.append(label)
        counts[label] = counts.get(label, 0) + max(1, int(weight or 1))

    for item in kb_items or []:
        add(item.get("topic"), len(item.get("questions") or []) or 1)

    for entry in doc_topics or []:
        if isinstance(entry, str):
            add(entry)
        elif isinstance(entry, dict):
            add(entry.get("label") or entry.get("topic"), entry.get("count") or 1)

    ranked = sorted(order, key=lambda label: (-counts[label], order.index(label)))
    return ranked[: max(1, int(max_topics))]


def build_examples(candidates: list[dict], limit: int = MAX_EXAMPLES) -> list[str]:
    examples = []
    seen = set()
    for candidate in candidates or []:
        question = (candidate.get("question") or "").strip()
        if not question or question in seen:
            continue
        seen.add(question)
        examples.append(question)
        if len(examples) >= limit:
            break
    return examples


def select_topic_candidates(candidates: list[dict], topic: str) -> list[dict]:
    wanted = normalize_text(topic)
    selected = []
    for candidate in candidates or []:
        if normalize_text(candidate.get("topic") or "") == wanted:
            selected.append(candidate)
    return selected


def topic_candidates_from_items(items: list[dict], topic: str) -> list[dict]:
    return select_topic_candidates(candidates_from_items(items), topic)


def clarify_message(level: int) -> str:
    if level >= 3:
        return "Bạn thử mô tả cụ thể hơn nhé, ví dụ:"
    if level == 2:
        return "Bạn muốn hỏi câu nào về chủ đề này?"
    return (
        "Mình chưa chắc bạn muốn hỏi phần nào. "
        "Bạn chọn một mục bên dưới, hoặc mô tả thêm giúp mình nhé:"
    )


def clarify_payload(level: int, topics=None, examples=None) -> dict:
    if level >= 3:
        topics = []
    return {
        "message": clarify_message(level),
        "topics": list(topics or []),
        "examples": list(examples or [])[:MAX_EXAMPLES],
    }
