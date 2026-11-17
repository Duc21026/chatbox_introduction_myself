import math
from types import SimpleNamespace

import pytest

from backend import vector_store


def _index(**overrides):
    values = {
        "model": "@cf/baai/bge-m3",
        "dim": 2,
        "normalizer_version": "2",
        "source_sha256": "a" * 64,
        "source_kb_hash": "b" * 64,
        "question_count": 1,
        "built_at": "2026-11-17T00:00:00Z",
        "entries": [
            vector_store.VectorEntry(
                id="gpa#0",
                item_id="gpa",
                source_type="qa",
                question="GPA?",
                norm="gpa",
                vector=[0.1, 0.2],
            )
        ],
    }
    values.update(overrides)
    return vector_store.VectorIndex(**values)


def test_save_and_load_roundtrip(tmp_path):
    path = tmp_path / "vectors.json"
    vector_store.save(_index(), str(path))
    loaded = vector_store.load(str(path), expected_model="@cf/baai/bge-m3", expected_normalizer="2")

    assert loaded is not None
    assert loaded.question_count == 1
    assert loaded.entries[0].vector == [0.1, 0.2]


def test_model_mismatch_rejected(tmp_path):
    path = tmp_path / "vectors.json"
    vector_store.save(_index(), str(path))
    assert vector_store.load(str(path), expected_model="other") is None


def test_normalizer_mismatch_rejected(tmp_path):
    path = tmp_path / "vectors.json"
    vector_store.save(_index(), str(path))
    assert vector_store.load(str(path), expected_normalizer="1") is None


def test_bad_dimension_rejected(tmp_path):
    path = tmp_path / "vectors.json"
    index = _index()
    index.entries[0].vector = [0.1]
    vector_store.save(index, str(path))
    assert vector_store.load(str(path)) is None


def test_non_finite_value_rejected(tmp_path):
    path = tmp_path / "vectors.json"
    index = _index()
    index.entries[0].vector = [math.nan, 0.2]
    vector_store.save(index, str(path))
    assert vector_store.load(str(path)) is None


def test_source_hash_match_and_entry_membership():
    source = SimpleNamespace(
        kb_hash="b" * 64,
        kb_items=[SimpleNamespace(id="gpa"), SimpleNamespace(id="skills")],
    )
    index = _index()
    assert index.matches_source(source)
    assert vector_store.matches_entries(index, source)

    other = SimpleNamespace(
        kb_hash="c" * 64,
        kb_items=[SimpleNamespace(id="skills")],
    )
    assert not index.matches_source(other)
    assert not vector_store.matches_entries(index, other)


def test_missing_file_inspect_is_degraded(tmp_path):
    info = vector_store.inspect(str(tmp_path / "missing.json"))
    assert info["vectors_loaded"] is False
    assert info["vector_count"] == 0
