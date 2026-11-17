"""Persistent precomputed embedding index (``data/vectors.json``).

The index is produced by ``scripts/build_vectors.py`` and bundled with the
Vercel function.  Loading is strict: a stale or malformed index is ignored so
the runtime falls back to lexical matching instead of mixing old vectors with
new questions.
"""

from __future__ import annotations

import json
import logging
import math
import os
import tempfile
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(BACKEND_DIR)
DEFAULT_VECTORS_PATH = os.path.join(REPO_ROOT, "data", "vectors.json")


def vectors_path() -> str:
    return os.environ.get("CHATBOT_VECTORS_PATH", DEFAULT_VECTORS_PATH)


@dataclass
class VectorEntry:
    id: str
    item_id: str
    source_type: str
    question: str
    norm: str
    vector: list[float]
    topic: Optional[str] = None

    def to_dict(self) -> dict:
        payload = {
            "id": self.id,
            "item_id": self.item_id,
            "source_type": self.source_type,
            "question": self.question,
            "norm": self.norm,
            "vector": self.vector,
        }
        if self.topic:
            payload["topic"] = self.topic
        return payload


@dataclass
class VectorIndex:
    model: str
    dim: int
    normalizer_version: str
    source_sha256: str
    source_kb_hash: str
    question_count: int
    built_at: str
    entries: list[VectorEntry] = field(default_factory=list)
    schema_version: int = SCHEMA_VERSION

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "model": self.model,
            "dim": self.dim,
            "normalizer_version": self.normalizer_version,
            "source_sha256": self.source_sha256,
            "source_kb_hash": self.source_kb_hash,
            "question_count": self.question_count,
            "built_at": self.built_at,
            "entries": [entry.to_dict() for entry in self.entries],
        }

    def matches_source(self, source) -> bool:
        return bool(source) and self.source_kb_hash == getattr(source, "kb_hash", None)

    def matches_config(self, *, model: str, normalizer_version: str) -> bool:
        return self.model == model and self.normalizer_version == normalizer_version


def _invalid(reason: str) -> None:
    logger.warning("Chỉ mục vector không dùng được (%s).", reason)


def _parse_entry(raw: dict) -> Optional[VectorEntry]:
    required = ("id", "item_id", "source_type", "question", "norm", "vector")
    if not isinstance(raw, dict) or any(key not in raw for key in required):
        return None
    vector = raw.get("vector")
    if not isinstance(vector, list) or not vector:
        return None
    values = []
    for value in vector:
        if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            return None
        values.append(float(value))
    return VectorEntry(
        id=str(raw["id"]),
        item_id=str(raw["item_id"]),
        source_type=str(raw["source_type"]),
        question=str(raw["question"]),
        norm=str(raw["norm"]),
        vector=values,
        topic=str(raw["topic"]) if raw.get("topic") else None,
    )


def load(path: Optional[str] = None, *, expected_model: Optional[str] = None,
         expected_normalizer: Optional[str] = None) -> Optional[VectorIndex]:
    """Load and validate the index; return ``None`` on any problem."""

    path = path or vectors_path()
    if not os.path.isfile(path):
        _invalid("không tìm thấy tệp")
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        _invalid(f"không đọc được tệp: {exc}")
        return None

    if not isinstance(raw, dict):
        _invalid("root phải là object")
        return None
    if raw.get("schema_version") != SCHEMA_VERSION:
        _invalid("schema_version không khớp")
        return None
    model = raw.get("model")
    dim = raw.get("dim")
    normalizer_version = raw.get("normalizer_version")
    if not isinstance(model, str) or not isinstance(dim, int) or dim <= 0:
        _invalid("model/dim thiếu hoặc sai")
        return None
    if expected_model and model != expected_model:
        _invalid("model không khớp cấu hình")
        return None
    if expected_normalizer and normalizer_version != expected_normalizer:
        _invalid("normalizer_version không khớp")
        return None

    raw_entries = raw.get("entries")
    if not isinstance(raw_entries, list) or not raw_entries:
        _invalid("entries rỗng hoặc sai")
        return None
    entries = []
    seen_ids = set()
    for item in raw_entries:
        entry = _parse_entry(item)
        if entry is None or len(entry.vector) != dim:
            _invalid("entry sai cấu trúc hoặc sai số chiều")
            return None
        if entry.id in seen_ids:
            _invalid("entry id trùng")
            return None
        if not any(value != 0.0 for value in entry.vector):
            _invalid("vector toàn 0")
            return None
        seen_ids.add(entry.id)
        entries.append(entry)

    count = raw.get("question_count")
    if count is not None and count != len(entries):
        _invalid("question_count không khớp entries")
        return None

    return VectorIndex(
        model=model,
        dim=dim,
        normalizer_version=str(normalizer_version or ""),
        source_sha256=str(raw.get("source_sha256") or ""),
        source_kb_hash=str(raw.get("source_kb_hash") or ""),
        question_count=len(entries),
        built_at=str(raw.get("built_at") or ""),
        entries=entries,
        schema_version=SCHEMA_VERSION,
    )


def save(index: VectorIndex, path: Optional[str] = None) -> str:
    """Write the index atomically and return the final path."""

    path = path or vectors_path()
    directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(directory, exist_ok=True)
    payload = json.dumps(index.to_dict(), ensure_ascii=False, indent=2) + "\n"
    fd, temp_path = tempfile.mkstemp(prefix=".vectors-", suffix=".json", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    return path


def matches_entries(index: VectorIndex, source) -> bool:
    """Every entry's item must still exist in the current KB."""

    if not index or not source:
        return False
    ids = {item.id for item in source.kb_items}
    return all(entry.item_id in ids for entry in index.entries)


def inspect(path: Optional[str] = None) -> dict:
    """Return metadata useful for health reporting; never raises."""

    index = load(path)
    if index is None:
        return {
            "vectors_loaded": False,
            "vector_count": 0,
            "model": None,
            "dim": 0,
            "normalizer_version": None,
            "source_kb_hash": None,
        }
    return {
        "vectors_loaded": True,
        "vector_count": index.question_count,
        "model": index.model,
        "dim": index.dim,
        "normalizer_version": index.normalizer_version,
        "source_kb_hash": index.source_kb_hash,
    }
