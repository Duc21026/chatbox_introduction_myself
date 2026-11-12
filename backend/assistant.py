"""Tiered response engine: answer / suggest / clarify (never ``unknown``).

The main path is deterministic and calls no LLM.  An optional LLM summary is a
separate concern controlled by ``ENABLE_LLM_SUMMARY``.
"""

from __future__ import annotations

import logging
import os
from collections import OrderedDict
from typing import Optional

try:
    from . import kb_engine
    from .doc_index import DocIndex, doc_threshold, extractive_answer
    from .session import SessionStore
    from .suggestions import (
        build_examples,
        build_fuzzy_suggestions,
        build_suggestions,
        build_topics,
        candidates_from_items,
        clarify_payload,
        topic_candidates_from_items,
    )
    from .text_normalization import normalize_query
except ImportError:  # direct execution
    import kb_engine
    from doc_index import DocIndex, doc_threshold, extractive_answer
    from session import SessionStore
    from suggestions import (
        build_examples,
        build_fuzzy_suggestions,
        build_suggestions,
        build_topics,
        candidates_from_items,
        clarify_payload,
        topic_candidates_from_items,
    )
    from text_normalization import normalize_query

logger = logging.getLogger(__name__)

SUGGEST_ACTIONS = [{"id": "other", "label": "Câu hỏi khác"}]
CLARIFY_ACTIONS = [
    {"id": "rephrase", "label": "Hỏi lại cách khác"},
    {"id": "other", "label": "Câu hỏi khác"},
]


def _max_suggestions() -> int:
    return kb_engine._max_suggestions()


def _suggest_floor() -> float:
    return kb_engine._suggest_threshold()


def _cache_size() -> int:
    raw = os.environ.get("CHATBOT_QUERY_CACHE_SIZE", "512")
    try:
        value = int(raw)
    except ValueError:
        raise ValueError(
            f"CHATBOT_QUERY_CACHE_SIZE phải là số nguyên, nhận được: {raw!r}"
        )
    if value < 0:
        raise ValueError(
            f"CHATBOT_QUERY_CACHE_SIZE phải >= 0, nhận được: {raw!r}"
        )
    return value


class Assistant:
    def __init__(
        self,
        *,
        evaluator=None,
        doc_searcher=None,
        session_store=None,
        rag_searcher=None,
        qa_searcher=None,
        summarizer=None,
        summary_streamer=None,
    ):
        self.evaluator = evaluator or kb_engine.evaluate
        self.doc_searcher = doc_searcher
        self.session_store = session_store or SessionStore()
        self.rag_searcher = rag_searcher
        self.qa_searcher = qa_searcher
        self.summarizer = summarizer
        self.summary_streamer = summary_streamer
        self._cache_size = _cache_size()
        self._evaluation_cache = OrderedDict()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def handle(
        self,
        question: Optional[str] = None,
        session_id: Optional[str] = None,
        action: Optional[str] = None,
        topic: Optional[str] = None,
        stream_summary: bool = False,
    ) -> dict:
        session_id, state = self.session_store.get_or_create(session_id)
        action = (action or "").strip().lower() or None
        if action in {"other", "rephrase"}:
            return self._clarify_action(session_id, state, action, question)
        if action == "topic":
            return self._topic_action(session_id, state, topic)
        if action == "retry":
            question = (question or state.last_query or "").strip()
            if not question:
                return self._clarify_action(session_id, state, "rephrase", question)
        return self._answer_question(
            session_id, state, question or "", stream_summary=stream_summary
        )

    def _answer_question(
        self, session_id: str, state, question: str, stream_summary: bool = False
    ) -> dict:
        question = (question or "").strip()
        evaluation = self._evaluate(question)
        state.last_query = question
        state.level = 1
        state.last_candidates = [
            candidate.get("question")
            for candidate in evaluation.candidates[:8]
            if candidate.get("question")
        ]

        # 1. Crisp KB answer (top1 >= high and not ambiguous).
        if evaluation.answer_item is not None:
            response = self._kb_answer(session_id, evaluation)
            if response is not None:
                return response

        # 2. Suggest zone (0.45..0.78, or an ambiguous high match).
        if evaluation.candidates:
            max_suggestions = _max_suggestions()
            suggestions = build_suggestions(
                evaluation.norm,
                evaluation.candidates,
                state.shown_ids,
                max_suggestions,
            )
            if (
                evaluation.top1 >= _suggest_floor()
                and len(suggestions) >= 2
            ):
                state.add_shown(item["id"] for item in suggestions)
                return self._suggest_response(
                    session_id,
                    suggestions,
                    "Bạn muốn hỏi câu nào?",
                )

        # 3. Embedding unavailable/weak: lexical fallback over KB questions.
        if not evaluation.embeddings_ready or evaluation.top1 < _suggest_floor():
            suggestions = build_fuzzy_suggestions(
                evaluation.norm,
                kb_engine.get_items(),
                state.shown_ids,
                _max_suggestions(),
            )
            strong = [
                item for item in suggestions if float(item.get("score") or 0.0) >= 0.25
            ]
            if len(strong) >= 2:
                state.add_shown(item["id"] for item in strong)
                return self._suggest_response(
                    session_id,
                    strong,
                    "Bạn muốn hỏi câu nào?",
                )

        # 3b. Source Q&A fallback (005 compatibility, no LLM/embeddings).
        qa_hits = self._source_qa(question)
        if qa_hits:
            best = qa_hits[0]
            if float(best.get("score") or 0.0) >= kb_engine._high_threshold():
                return self._qa_answer(session_id, best)
            qa_suggestions = build_suggestions(
                evaluation.norm,
                qa_hits,
                state.shown_ids,
                _max_suggestions(),
            )
            if (
                float(best.get("score") or 0.0) >= _suggest_floor()
                and len(qa_suggestions) >= 2
            ):
                state.add_shown(item["id"] for item in qa_suggestions)
                return self._suggest_response(
                    session_id,
                    qa_suggestions,
                    "Bạn muốn hỏi câu nào?",
                )

        # 4. Documents (only when the KB is genuinely weak).
        if evaluation.top1 < _suggest_floor() or not evaluation.candidates:
            doc_response = self._document_answer(
                session_id,
                state,
                question,
                evaluation.query_vec,
                stream_summary=stream_summary,
            )
            if doc_response is not None:
                return doc_response

        # 5. Clarify with topic menu.
        topics = self._topics()
        examples = build_examples(evaluation.candidates or self._all_candidates())
        state.last_topics = topics
        return self._clarify_response(
            session_id, state.level, topics, examples
        )

    def _clarify_action(self, session_id: str, state, action: str, question=None) -> dict:
        state.level = min(3, max(1, int(state.level or 1) + 1))
        topics = [] if state.level >= 3 else self._topics()
        examples = []
        if action == "rephrase":
            examples = build_examples(self._all_candidates())
            if state.last_query:
                examples = build_examples(self._all_candidates(), limit=2)
            return self._clarify_response(
                session_id, max(3, state.level), topics, examples
            )
        state.last_topics = topics
        return self._clarify_response(session_id, state.level, topics, examples)

    def _topic_action(self, session_id: str, state, topic: Optional[str]) -> dict:
        topic = (topic or "").strip()
        if not topic:
            return self._clarify_response(
                session_id, state.level, self._topics(), []
            )
        candidates = topic_candidates_from_items(kb_engine.get_items(), topic)
        candidates.extend(self._doc_topic_candidates(topic))
        for candidate in candidates:
            candidate.setdefault("question", "")
        suggestions = build_suggestions(
            normalize_query(topic),
            candidates,
            state.shown_ids,
            _max_suggestions(),
        )
        if len(suggestions) >= 2:
            state.add_shown(item["id"] for item in suggestions)
            state.last_query = topic
            return self._suggest_response(
                session_id,
                suggestions,
                f"Các câu hỏi về {topic}:",
            )
        examples = build_examples(candidates or self._all_candidates())
        state.level = min(3, max(2, int(state.level or 1)))
        state.last_topics = self._topics()
        return self._clarify_response(
            session_id, state.level, state.last_topics, examples
        )

    # ------------------------------------------------------------------
    # Response builders
    # ------------------------------------------------------------------
    def _kb_answer(self, session_id: str, evaluation) -> Optional[dict]:
        item = evaluation.answer_item
        if not item:
            return None
        bullets = item.get("answer_bullets")
        answer = item.get("answer")
        if isinstance(bullets, list) and bullets:
            response_text = ", ".join(str(bullet) for bullet in bullets)
            answer_bullets = [str(bullet) for bullet in bullets]
        elif answer:
            response_text = str(answer)
            answer_bullets = None
        else:
            return None
        return {
            "type": "answer",
            "session_id": session_id,
            "score": round(float(evaluation.top1), 2),
            "response": response_text,
            "message": None,
            "answer_bullets": answer_bullets,
            "source": f"kb:{item.get('id')}",
            "sources": [],
            "suggestions": [],
            "topics": [],
            "examples": [],
            "actions": [],
        }

    def _document_answer(
        self,
        session_id: str,
        state,
        question: str,
        query_vec,
        stream_summary: bool = False,
    ) -> Optional[dict]:
        hits = []
        if self.doc_searcher is not None:
            try:
                hits = self.doc_searcher.search(
                    question,
                    query_vec=query_vec,
                    top_k=6,
                )
            except Exception as exc:
                logger.warning("Doc search lỗi: %s", exc)
                hits = []
        threshold = doc_threshold()
        hits = [hit for hit in hits if float(hit.get("score") or 0.0) >= threshold]
        if not hits and self.rag_searcher is not None:
            try:
                rag_hits = self.rag_searcher(question, query_vec)
                hits = [
                    hit
                    for hit in (rag_hits or [])
                    if float(hit.get("score") or 0.0) >= threshold
                ]
            except Exception as exc:
                logger.warning("RAG doc search lỗi: %s", exc)
                hits = []
        if not hits:
            return None
        payload = extractive_answer(hits, question)
        if not payload:
            return None
        state.last_candidates = [
            hit.get("question") for hit in hits[:8] if hit.get("question")
        ]
        response_text = payload.get("response") or ""
        extra = {}
        if stream_summary:
            chunks = self._summarize_stream(payload.get("answer_bullets"), question)
            if chunks:
                response_text = "".join(chunks)
                extra["_summary_chunks"] = chunks
        else:
            summary = self._summarize(payload.get("answer_bullets"), question)
            if summary:
                response_text = summary
        response = {
            "type": "answer",
            "session_id": session_id,
            "score": payload.get("score"),
            "response": response_text,
            "message": None,
            "answer_bullets": payload.get("answer_bullets"),
            "source": payload.get("source"),
            "sources": payload.get("sources") or [],
            "suggestions": [],
            "topics": [],
            "examples": [],
            "actions": [],
        }
        response.update(extra)
        return response

    def _evaluate(self, question):
        norm = normalize_query(question)
        if self._cache_size <= 0:
            return self.evaluator(question)
        cached = self._evaluation_cache.get(norm)
        if cached is not None:
            self._evaluation_cache.move_to_end(norm)
            return cached
        evaluation = self.evaluator(question)
        self._evaluation_cache[norm] = evaluation
        self._evaluation_cache.move_to_end(norm)
        if evaluation.norm and evaluation.norm != norm:
            self._evaluation_cache[evaluation.norm] = evaluation
            self._evaluation_cache.move_to_end(evaluation.norm)
        while len(self._evaluation_cache) > self._cache_size:
            self._evaluation_cache.popitem(last=False)
        return evaluation

    def _summarize_stream(self, bullets, question):
        import os

        if os.environ.get("ENABLE_LLM_SUMMARY", "false").strip().lower() not in {
            "1",
            "true",
            "yes",
            "on",
        }:
            return None
        if not bullets:
            return None
        provider = self.summary_streamer
        if provider is None:
            try:
                try:
                    from .chatbox import stream_document_summary
                except ImportError:
                    from chatbox import stream_document_summary
                provider = stream_document_summary
            except Exception:
                return None
        try:
            chunks = [str(chunk) for chunk in provider(bullets, question) if chunk]
            return chunks or None
        except Exception as exc:
            logger.warning("LLM summary stream lỗi; fallback extractive: %s", exc)
            return None

    def _summarize(self, bullets, question):
        import os

        if os.environ.get("ENABLE_LLM_SUMMARY", "false").strip().lower() not in {
            "1",
            "true",
            "yes",
            "on",
        }:
            return None
        if not bullets:
            return None
        provider = self.summarizer
        if provider is None:
            try:
                try:
                    from .chatbox import summarize_document_answer
                except ImportError:
                    from chatbox import summarize_document_answer
                provider = summarize_document_answer
            except Exception:
                return None
        try:
            return provider(bullets, question)
        except Exception as exc:
            logger.warning("LLM summary lỗi; fallback extractive: %s", exc)
            return None

    def _qa_answer(self, session_id: str, candidate: dict) -> Optional[dict]:
        answer = candidate.get("answer")
        if not answer:
            return None
        return {
            "type": "answer",
            "session_id": session_id,
            "score": round(float(candidate.get("score") or 0.0), 2),
            "response": str(answer),
            "message": None,
            "answer_bullets": None,
            "source": f"kb:{candidate.get('item_id')}",
            "sources": [],
            "suggestions": [],
            "topics": [],
            "examples": [],
            "actions": [],
        }

    def _suggest_response(self, session_id: str, suggestions, message: str) -> dict:
        return {
            "type": "suggest",
            "session_id": session_id,
            "score": None,
            "response": message,
            "message": message,
            "answer_bullets": None,
            "source": None,
            "sources": [],
            "suggestions": suggestions,
            "topics": [],
            "examples": [],
            "actions": list(SUGGEST_ACTIONS),
        }

    def _clarify_response(self, session_id: str, level: int, topics, examples) -> dict:
        payload = clarify_payload(level, topics, examples)
        return {
            "type": "clarify",
            "session_id": session_id,
            "score": None,
            "response": payload["message"],
            "message": payload["message"],
            "answer_bullets": None,
            "source": None,
            "sources": [],
            "suggestions": [],
            "topics": payload["topics"],
            "examples": payload["examples"],
            "actions": list(CLARIFY_ACTIONS),
        }

    # ------------------------------------------------------------------
    # Topic helpers
    # ------------------------------------------------------------------
    def _source_qa(self, question):
        if self.qa_searcher is None:
            return []
        try:
            return self.qa_searcher(question) or []
        except Exception as exc:
            logger.warning("Source QA search lỗi: %s", exc)
            return []

    def _doc_topics(self):
        if self.doc_searcher is None:
            return []
        try:
            return self.doc_searcher.topics()
        except Exception:
            return []

    def _topics(self):
        topics = build_topics(kb_engine.get_items(), self._doc_topics())
        return topics

    def _doc_topic_candidates(self, topic: str):
        if self.doc_searcher is None:
            return []
        try:
            return self.doc_searcher.candidates_for_topic(topic)
        except Exception:
            return []

    def _all_candidates(self):
        try:
            return candidates_from_items(kb_engine.get_items())
        except Exception:
            return []


_default_assistant: Optional[Assistant] = None


def get_default_assistant() -> Assistant:
    global _default_assistant
    if _default_assistant is None:
        _default_assistant = Assistant(doc_searcher=DocIndex())
    return _default_assistant


def handle(
    question: Optional[str] = None,
    session_id: Optional[str] = None,
    action: Optional[str] = None,
    topic: Optional[str] = None,
) -> dict:
    return get_default_assistant().handle(
        question, session_id=session_id, action=action, topic=topic
    )
