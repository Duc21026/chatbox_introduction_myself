import json

import numpy as np

from backend.doc_index import DocIndex, extractive_answer


class TopicEmbedder:
    """Small deterministic embedder that maps keywords to distinct vectors."""

    def __init__(self):
        self.topics = {
            "hoc bong": np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32),
            "học bổng": np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32),
            "kinh nghiem": np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float32),
            "kinh nghiệm": np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float32),
            "python": np.array([0.0, 0.0, 1.0, 0.0], dtype=np.float32),
            "toan": np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32),
            "toán": np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32),
        }

    def _vector(self, text):
        lowered = str(text).lower()
        for keyword, vector in self.topics.items():
            if keyword in lowered:
                return vector
        return np.array([0.5, 0.5, 0.5, 0.5], dtype=np.float32)

    def embed_documents(self, texts):
        return [self._vector(text) for text in texts]

    def embed_query(self, text):
        return self._vector(text)


def _dataset(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "cv.txt").write_text(
        "Kinh nghiệm backend ba năm. Tôi dùng Python mỗi ngày.", encoding="utf-8"
    )
    (data / "scholarship.md").write_text(
        "# Học bổng\n\nMục tiêu săn học bổng toàn phần Thạc sĩ tại Đức. "
        "Tôi đã chuẩn bị hồ sơ từ năm ngoái. "
        "Tôi cần chứng chỉ IELTS 7.0.",
        encoding="utf-8",
    )
    (data / "diem.csv").write_text("Môn,Điểm\nToán,9\n", encoding="utf-8")
    return data


def _index(tmp_path):
    index = DocIndex(index_dir=tmp_path / "index", embedder=TopicEmbedder())
    return index


def test_ingest_persists_schema_and_skips_unchanged(tmp_path):
    data = _dataset(tmp_path)
    index = _index(tmp_path)

    report = index.ingest(str(data))

    assert not report["failed"]
    assert len(report["added"]) == 3
    assert index.status == "ready"
    assert index.files and index.chunks
    assert len(index.vectors) == len(index.chunks)
    for name in ("manifest.json", "files.json", "chunks.json", "vectors.npz"):
        assert (tmp_path / "index" / name).is_file()

    manifest = json.loads((tmp_path / "index" / "manifest.json").read_text())
    assert manifest["schema_version"] == 1
    assert manifest["file_count"] == len(index.files)
    assert manifest["chunk_count"] == len(index.chunks)

    again = index.ingest(str(data))
    assert len(again["skipped"]) == 3
    assert again["stats"]["embeddings_computed"] == 0


def test_search_and_extractive_answer_with_sources(tmp_path):
    data = _dataset(tmp_path)
    index = _index(tmp_path)
    index.ingest(str(data))

    hits = index.search("học bổng toàn phần", top_k=4)

    assert hits
    assert hits[0]["file"] == "scholarship.md"
    assert hits[0]["heading"] == "Học bổng"
    assert hits[0]["score"] >= 0.55

    answer = extractive_answer(hits, "học bổng toàn phần")
    assert answer is not None
    assert 3 <= len(answer["answer_bullets"]) <= 5
    assert answer["sources"][0]["file"] == "scholarship.md"


def test_incremental_update_reembeds_changed_chunks(tmp_path):
    data = _dataset(tmp_path)
    index = _index(tmp_path)
    index.ingest(str(data))
    before = index.files["scholarship.md"]["file_hash"]

    path = data / "scholarship.md"
    path.write_text(
        "# Học bổng\n\nMục tiêu săn học bổng toàn phần. Cập nhật mới.",
        encoding="utf-8",
    )
    report = index.ingest(str(path))

    assert len(report["updated"]) == 1
    assert report["stats"]["embeddings_computed"] >= 1
    assert index.files["scholarship.md"]["file_hash"] != before

    fresh = DocIndex(index_dir=tmp_path / "index", embedder=TopicEmbedder())
    assert fresh.status == "ready"
    assert fresh.files["scholarship.md"]["file_hash"] == index.files["scholarship.md"]["file_hash"]


def test_remove_only_touches_index(tmp_path):
    data = _dataset(tmp_path)
    index = _index(tmp_path)
    index.ingest(str(data))

    source = data / "cv.txt"
    removed = index.remove("cv.txt")

    assert removed is not None and removed > 0
    assert source.is_file()
    assert "cv.txt" not in index.files
    assert all(chunk["file"] != "cv.txt" for chunk in index.chunks.values())


def test_broken_manifest_is_non_fatal(tmp_path):
    data = _dataset(tmp_path)
    index = _index(tmp_path)
    index.ingest(str(data))

    manifest_path = tmp_path / "index" / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["schema_version"] = 99
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    broken = DocIndex(index_dir=tmp_path / "index", embedder=TopicEmbedder())
    assert broken.status == "broken"
    assert broken.is_ready() is False
    assert broken.search("học bổng") == []
    assert broken.files == {}
