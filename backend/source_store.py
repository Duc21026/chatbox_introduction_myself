"""Source loading shared by the legacy backend and the Vercel deployment.

This module is intentionally free of Ollama, FAISS and LangChain imports so it
can run inside the Vercel Python function.  ``chatbox`` and ``kb_engine`` both
build on it.

Canonical source: ``data/chatbot.txt`` (plus ``data/sources/courses.csv`` and
``data/sources/aliases.txt``).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from typing import Optional

from rapidfuzz import fuzz

try:
    from . import aliases as aliases_mod
    from . import courses as courses_mod
    from . import source_format
    from .text_normalization import NORMALIZER_VERSION, normalize_text, register_aliases
except ImportError:  # direct execution from backend/
    import aliases as aliases_mod
    import courses as courses_mod
    import source_format
    from text_normalization import NORMALIZER_VERSION, normalize_text, register_aliases

logger = logging.getLogger(__name__)

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(BACKEND_DIR)
DEFAULT_DATA_DIR = os.path.join(REPO_ROOT, "data")
DEFAULT_SOURCE_PATH = os.path.join(DEFAULT_DATA_DIR, "chatbot.txt")
DEFAULT_COURSES_PATH = os.path.join(DEFAULT_DATA_DIR, "sources", "courses.csv")
DEFAULT_ALIASES_PATH = os.path.join(DEFAULT_DATA_DIR, "sources", "aliases.txt")
DEFAULT_INBOX_DIR = os.path.join(DEFAULT_DATA_DIR, "inbox")

SUPPORTED_INBOX_EXTENSIONS = (".txt", ".pdf", ".docx", ".xlsx", ".csv")

_cache = None
_cache_key = None


@dataclass(frozen=True)
class SourceConfig:
    source_path: str = DEFAULT_SOURCE_PATH
    courses_path: str = DEFAULT_COURSES_PATH
    aliases_path: str = DEFAULT_ALIASES_PATH
    inbox_dir: str = DEFAULT_INBOX_DIR
    embedding_model: str = "bge-m3"
    chunk_size: int = 500
    chunk_overlap: int = 50
    normalizer_version: str = NORMALIZER_VERSION
    legacy_sources: bool = False


def default_config() -> SourceConfig:
    """Read the deployment configuration from environment variables."""

    return SourceConfig(
        source_path=os.environ.get("CHATBOT_SOURCE_PATH", DEFAULT_SOURCE_PATH),
        courses_path=os.environ.get("CHATBOT_COURSES_PATH", DEFAULT_COURSES_PATH),
        aliases_path=os.environ.get("CHATBOT_ALIASES_PATH", DEFAULT_ALIASES_PATH),
        inbox_dir=os.environ.get("CHATBOT_INBOX_DIR", DEFAULT_INBOX_DIR),
        embedding_model=os.environ.get("CHATBOT_EMBEDDING_MODEL", "bge-m3"),
        chunk_size=int(os.environ.get("CHATBOT_CHUNK_SIZE", "500")),
        chunk_overlap=int(os.environ.get("CHATBOT_CHUNK_OVERLAP", "50")),
        legacy_sources=os.environ.get("CHATBOT_LEGACY_SOURCES", "false").strip().lower()
        in {"1", "true", "yes", "on"},
    )


def source_key(config: SourceConfig) -> tuple:
    """Signature of every input the derived source depends on."""

    def _file_entry(candidate):
        try:
            status = os.stat(candidate)
        except OSError:
            return (candidate, None, None)
        return (candidate, status.st_mtime_ns, status.st_size)

    entries = [
        _file_entry(config.source_path),
        _file_entry(config.courses_path),
        _file_entry(config.aliases_path),
    ]
    inbox_files = []
    if os.path.isdir(config.inbox_dir):
        for filename in sorted(os.listdir(config.inbox_dir)):
            candidate = os.path.join(config.inbox_dir, filename)
            if not os.path.isfile(candidate):
                continue
            if not filename.lower().endswith(SUPPORTED_INBOX_EXTENSIONS):
                continue
            status = os.stat(candidate)
            inbox_files.append([filename, status.st_mtime_ns, status.st_size])
    entries.append(("inbox", inbox_files))
    return tuple(entries)


def load_course_inputs(config: SourceConfig):
    """Read courses.csv once per source rebuild."""

    try:
        course_list, course_issues = courses_mod.load_courses(config.courses_path)
    except Exception as exc:
        logger.error("Không đọc được courses.csv; bỏ qua dữ liệu môn: %s", exc)
        course_list, course_issues = [], []
    for issue in course_issues:
        if issue.severity == "error":
            logger.error("courses.csv: [%s] %s", issue.code, issue.message)
        else:
            logger.warning("courses.csv: [%s] %s", issue.code, issue.message)
    return courses_mod, course_list, course_issues


def computed_fact_overrides(courses_mod, course_list) -> dict:
    """Serve computed aggregates through the matching fact placeholders."""

    if not course_list:
        return {}
    aggregated = courses_mod.aggregates(course_list)
    return {
        "gpa-10": f"{aggregated['gpa10']:.2f}",
        "gpa-4": f"{aggregated['gpa4']:.2f}",
        "credits": str(aggregated["credits_total"]),
        "courses-count": str(aggregated["courses_count"]),
        "gpa-major": (
            f"{aggregated['gpa_major']:.2f} "
            f"({aggregated['major_courses_count']} môn, "
            f"{aggregated['major_credits']} tín chỉ)"
        ),
    }


def merge_open_data(config: SourceConfig, derived, courses_mod, course_list, course_issues):
    """Merge courses.csv/aliases.txt into a ``DerivedSource``."""

    try:
        alias_map = aliases_mod.merged_alias_map(course_list, config.aliases_path)
    except Exception as exc:
        logger.error("Không đọc được aliases.txt; bỏ qua bí danh: %s", exc)
        alias_map = {}
    register_aliases(alias_map)

    if not course_list:
        return

    for item in courses_mod.build_course_qa(course_list):
        kb_item = source_format.KBItem(
            id=item["id"],
            topic=item["topic"],
            questions=list(item["questions"]),
            answer=item["answer"],
        )
        derived.kb_items.append(kb_item)
        for question in item["questions"]:
            normalized = normalize_text(question)
            if normalized:
                derived.qa_pairs.append(
                    source_format.QAPair(
                        question=question,
                        normalized_question=normalized,
                        answer=item["answer"],
                        record_id=item["id"],
                    )
                )

    aggregated = courses_mod.aggregates(course_list)
    for issue in courses_mod.check_against_facts(aggregated, derived.facts_map):
        logger.warning("Số tổng hợp: [%s] %s", issue.code, issue.message)

    derived.kb_hash = hashlib.sha256(
        json.dumps(
            [item.as_dict() for item in derived.kb_items],
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def build_derived(config: Optional[SourceConfig] = None, *, facts_override=None):
    """Validate and map the canonical source without any network call."""

    config = config or default_config()
    courses, course_list, course_issues = load_course_inputs(config)
    overrides = computed_fact_overrides(courses, course_list)
    if facts_override:
        overrides.update(facts_override)
    derived = source_format.load_source(
        config.source_path,
        embedding_model=config.embedding_model,
        chunk_size=config.chunk_size,
        chunk_overlap=config.chunk_overlap,
        facts_override=overrides,
    )
    merge_open_data(config, derived, courses, course_list, course_issues)
    return derived


def get_source(config: Optional[SourceConfig] = None, force: bool = False):
    """Return the cached ``DerivedSource``; keep the old one on bad edits."""

    global _cache, _cache_key

    config = config or default_config()
    key = source_key(config)
    if _cache is not None and _cache_key == key and not force:
        return _cache

    try:
        derived = build_derived(config)
    except Exception as exc:
        if _cache is not None:
            logger.error("Tệp nguồn mới không hợp lệ; giữ chỉ mục cũ: %s", exc)
            return _cache
        raise

    _cache = derived
    _cache_key = key
    return derived


def clear_cache() -> None:
    global _cache, _cache_key
    _cache = None
    _cache_key = None


def retrieve_source_qa(question: str, config: Optional[SourceConfig] = None):
    """Return lexical candidates from the unified source (no embeddings)."""

    if not isinstance(question, str) or not normalize_text(question):
        return []
    try:
        source = get_source(config)
    except Exception:
        return []
    pairs = source.qa_pairs
    if not pairs:
        return []
    counts = {}
    for pair in pairs:
        counts[pair.record_id] = counts.get(pair.record_id, 0) + 1
    query = normalize_text(question)
    hits = []
    for pair in pairs:
        score = fuzz.WRatio(query, pair.normalized_question) / 100.0
        if score <= 0:
            continue
        hits.append(
            {
                "source": "kb",
                "item_id": pair.record_id,
                "topic": None,
                "question": pair.question,
                "norm": pair.normalized_question,
                "score": round(score, 4),
                "question_count": counts.get(pair.record_id, 1),
                "answer": pair.answer,
                "answer_bullets": None,
            }
        )
    hits.sort(key=lambda hit: hit["score"], reverse=True)
    return hits[:8]
