"""Persistent offline document index (JSON + NPZ + in-memory FAISS).

The data directory intentionally has the same name as this module
(``backend/doc_index/``).  Never add ``__init__.py`` to that directory:
Python must keep importing this module.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

import numpy as np
from rapidfuzz import fuzz

try:
    from .doc_loaders import (
        DEFAULT_CHUNK_OVERLAP,
        DEFAULT_CHUNK_SIZE,
        DocLoadError,
        chunk_blocks,
        extract_blocks,
        is_supported,
        max_bytes,
    )
    from .text_normalization import NORMALIZER_VERSION, normalize_query, split_sentences, token_overlap
except ImportError:  # direct execution
    from doc_loaders import (
        DEFAULT_CHUNK_OVERLAP,
        DEFAULT_CHUNK_SIZE,
        DocLoadError,
        chunk_blocks,
        extract_blocks,
        is_supported,
        max_bytes,
    )
    from text_normalization import NORMALIZER_VERSION, normalize_query, split_sentences, token_overlap

logger = logging.getLogger(__name__)

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA_VERSION = 1
MANIFEST = "manifest.json"
FILES = "files.json"
CHUNKS = "chunks.json"
VECTORS = "vectors.npz"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise RuntimeError(f"Giá trị env {name} không hợp lệ: {raw!r}") from exc


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"Giá trị env {name} không hợp lệ: {raw!r}") from exc


def doc_threshold() -> float:
    return _env_float("CHATBOT_DOC_THRESHOLD", 0.55)


def _embedding_model() -> str:
    return os.environ.get("CHATBOT_EMBEDDING_MODEL", "bge-m3").strip() or "bge-m3"


def _ollama_base_url() -> str:
    return os.environ.get("CHATBOT_OLLAMA_BASE_URL", "http://127.0.0.1:11434")


def _index_dir() -> Path:
    raw = os.environ.get("CHATBOT_DOC_INDEX_DIR")
    if raw is None or not raw.strip():
        return Path(BACKEND_DIR) / "doc_index"
    path = Path(raw).expanduser()
    if path.is_absolute():
        return path
    # The documented default is relative to the repository root (backend/doc_index).
    repo_root = Path(BACKEND_DIR).parent
    if path.parts and path.parts[0] == Path(BACKEND_DIR).name:
        return repo_root / path
    return Path(BACKEND_DIR) / path


def _chunk_size() -> int:
    return max(100, min(_env_int("CHATBOT_DOC_CHUNK_SIZE", DEFAULT_CHUNK_SIZE), 500))


def _chunk_overlap() -> int:
    return max(0, min(_env_int("CHATBOT_DOC_CHUNK_OVERLAP", DEFAULT_CHUNK_OVERLAP), 250))


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_file_name(name: str) -> str:
    name = str(name or "").strip()
    if not name or "/" in name or "\\" in name or ".." in name or ":" in name:
        raise DocLoadError("E_PATH", f"Tên tệp không hợp lệ: {name!r}")
    return name


def _normalize_matrix(matrix: np.ndarray) -> np.ndarray:
    if matrix.size == 0:
        return matrix.astype(np.float32)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (matrix / norms).astype(np.float32)


def _candidate_question(chunk: dict) -> str:
    heading = (chunk.get("heading") or "").strip()
    file_name = chunk.get("file") or "tài liệu"
    if heading:
        return f"Tài liệu {file_name} nói gì về {heading}?"
    text = (chunk.get("text") or "").strip()
    snippet = " ".join(text.split())[:80].strip()
    if snippet:
        return f"Tài liệu {file_name}: {snippet}?"
    return f"Tài liệu {file_name} có thông tin gì?"


def _source_label(chunk: dict) -> str:
    file_name = chunk.get("file") or "tài liệu"
    if chunk.get("page") is not None:
        return f"{file_name}, trang {chunk['page']}"
    if chunk.get("sheet") is not None:
        start = chunk.get("row_start")
        end = chunk.get("row_end") or start
        if start is not None:
            return f"{file_name}, sheet {chunk['sheet']}, dòng {start}–{end}"
        return f"{file_name}, sheet {chunk['sheet']}"
    if chunk.get("heading"):
        return f"{file_name}, {chunk['heading']}"
    return file_name


def _source_ref(chunk: dict) -> dict:
    return {
        "file": chunk.get("file"),
        "page": chunk.get("page"),
        "sheet": chunk.get("sheet"),
        "row_start": chunk.get("row_start"),
        "row_end": chunk.get("row_end"),
        "heading": chunk.get("heading"),
    }


class DocIndex:
    def __init__(self, index_dir=None, embedder=None):
        self.index_dir = Path(index_dir) if index_dir else _index_dir()
        self.embedder = embedder
        self.files: dict[str, dict] = {}
        self.chunks: dict[str, dict] = {}
        self.vectors: dict[str, np.ndarray] = {}
        self.manifest: dict = {}
        self.status = "empty"
        self.error = None
        self._loaded = False
        self._faiss = None
        self._faiss_ids: list[str] = []
        self._load()

    # ------------------------------------------------------------------
    # Loading / integrity
    # ------------------------------------------------------------------
    def _paths(self):
        return (
            self.index_dir / MANIFEST,
            self.index_dir / FILES,
            self.index_dir / CHUNKS,
            self.index_dir / VECTORS,
        )

    def _load(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        manifest_path, files_path, chunks_path, vectors_path = self._paths()
        if not all(path.is_file() for path in self._paths()):
            self.status = "empty"
            return
        try:
            with open(manifest_path, encoding="utf-8") as handle:
                self.manifest = json.load(handle)
            with open(files_path, encoding="utf-8") as handle:
                self.files = json.load(handle) or {}
            with open(chunks_path, encoding="utf-8") as handle:
                self.chunks = json.load(handle) or {}
        except Exception as exc:
            self._broken(f"Không đọc được JSON chỉ mục: {exc}")
            return

        if not isinstance(self.files, dict) or not isinstance(self.chunks, dict):
            self._broken("files.json/chunks.json phải là object")
            return
        if int(self.manifest.get("schema_version") or 0) != SCHEMA_VERSION:
            self._broken("schema_version không khớp; cần ingest lại")
            return
        expected = {
            "embedding_model": _embedding_model(),
            "normalizer_version": NORMALIZER_VERSION,
            "chunk_size": _chunk_size(),
            "chunk_overlap": _chunk_overlap(),
        }
        for key, value in expected.items():
            if key in self.manifest and self.manifest.get(key) != value:
                self._broken(
                    f"{key} đã thay đổi ({self.manifest.get(key)!r} != {value!r}); "
                    "chạy ingest --full"
                )
                return

        try:
            with np.load(vectors_path, allow_pickle=True) as data:
                ids = [str(item) for item in data["chunk_ids"].tolist()]
                matrix = np.asarray(data["vectors"], dtype=np.float32)
        except Exception as exc:
            self._broken(f"Không đọc được vectors.npz: {exc}")
            return

        if matrix.ndim != 2 or len(ids) != matrix.shape[0]:
            self._broken("vectors.npz lệch số dòng/ID")
            return
        dim = int(self.manifest.get("vector_dim") or (matrix.shape[1] if matrix.ndim == 2 else 0))
        if matrix.shape[1] != dim:
            self._broken("vector_dim không khớp vectors.npz")
            return

        self.vectors = {}
        missing = 0
        orphan = 0
        for index, chunk_id in enumerate(ids):
            if chunk_id not in self.chunks:
                orphan += 1
                continue
            self.vectors[chunk_id] = matrix[index]
        for chunk_id in self.chunks:
            if chunk_id not in self.vectors:
                missing += 1
        total = max(1, len(ids))
        if (missing + orphan) / total > 0.01:
            self._broken("Chunk mồ côi/thiếu vector vượt 1%")
            return

        expected_file_count = int(self.manifest.get("file_count") or 0)
        expected_chunk_count = int(self.manifest.get("chunk_count") or 0)
        if expected_file_count != len(self.files) or expected_chunk_count != len(self.chunks):
            self._broken("manifest.file_count/chunk_count không khớp JSON")
            return

        self.status = "ready"
        self._rebuild_faiss()

    def _broken(self, message: str) -> None:
        self.status = "broken"
        self.error = message
        self.files = {}
        self.chunks = {}
        self.vectors = {}
        self._faiss = None
        logger.error("DocIndex hỏng: %s", message)

    def reload(self) -> None:
        self._loaded = False
        self.status = "empty"
        self.error = None
        self.files = {}
        self.chunks = {}
        self.vectors = {}
        self.manifest = {}
        self._faiss = None
        self._load()

    def is_ready(self) -> bool:
        return self.status in {"empty", "ready"}

    def documents_count(self) -> int:
        return len([f for f in self.files.values() if f.get("status") == "indexed"])

    def chunks_count(self) -> int:
        return len(self.chunks)

    # ------------------------------------------------------------------
    # Embedding / FAISS
    # ------------------------------------------------------------------
    def _get_embedder(self):
        if self.embedder is None:
            from langchain_ollama import OllamaEmbeddings

            self.embedder = OllamaEmbeddings(
                model=_embedding_model(), base_url=_ollama_base_url()
            )
        return self.embedder

    def _embed(self, texts: list[str]) -> np.ndarray:
        embedder = self._get_embedder()
        vectors = []
        batch_size = 32
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            embedded = embedder.embed_documents(batch)
            if len(embedded) != len(batch):
                raise RuntimeError("Embedder trả về sai số vector")
            vectors.extend(embedded)
        matrix = np.asarray(vectors, dtype=np.float32)
        return _normalize_matrix(matrix)

    def _embed_query(self, text: str) -> Optional[np.ndarray]:
        try:
            embedder = self._get_embedder()
            vector = embedder.embed_query(text)
            vector = np.asarray(vector, dtype=np.float32)
            norm = float(np.linalg.norm(vector))
            return vector / norm if norm else vector
        except Exception as exc:
            logger.warning("DocIndex: không embed được câu hỏi: %s", exc)
            return None

    def _rebuild_faiss(self) -> None:
        self._faiss = None
        self._faiss_ids = []
        if not self.chunks or not self.vectors:
            return
        try:
            import faiss
        except Exception as exc:
            logger.warning("DocIndex: FAISS không khả dụng (%s); dùng numpy", exc)
            return
        ids = [chunk_id for chunk_id in self.chunks if chunk_id in self.vectors]
        if not ids:
            return
        matrix = np.asarray([self.vectors[chunk_id] for chunk_id in ids], dtype=np.float32)
        index = faiss.IndexFlatIP(int(matrix.shape[1]))
        index = faiss.IndexIDMap2(index)
        index.add_with_ids(matrix, np.arange(len(ids), dtype=np.int64))
        self._faiss = index
        self._faiss_ids = ids

    # ------------------------------------------------------------------
    # Search / answer
    # ------------------------------------------------------------------
    def _keyword_score(self, query_norm: str, chunk: dict) -> float:
        text = " ".join(
            str(part or "")
            for part in (chunk.get("heading"), chunk.get("text"))
        )
        overlap = token_overlap(query_norm, text)
        fuzzy = fuzz.WRatio(query_norm, normalize_query(text)) / 100.0
        return round(0.6 * overlap + 0.4 * fuzzy, 4)

    def search(
        self,
        query="",
        query_vec=None,
        top_k: int = 6,
        threshold=None,
        k=None,
    ) -> list[dict]:
        if k is not None:
            top_k = int(k)
        if self.status == "broken" or not self.chunks:
            return []
        if isinstance(query, (list, tuple, np.ndarray)) and query_vec is None:
            query_vec = np.asarray(query, dtype=np.float32)
            query = ""
        query_norm = normalize_query(query) if isinstance(query, str) else ""
        if not query_norm and query_vec is None:
            return []
        if query_vec is None:
            query_vec = self._embed_query(query_norm)
        if threshold is None:
            threshold = doc_threshold()

        scores: dict[str, float] = {}
        if query_vec is not None and len(self.vectors):
            vector = np.asarray(query_vec, dtype=np.float32)
            norm = float(np.linalg.norm(vector))
            if norm:
                vector = vector / norm
            if self._faiss is not None:
                try:
                    result_scores, result_ids = self._faiss.search(
                        vector.reshape(1, -1), min(max(top_k, 1), len(self._faiss_ids))
                    )
                    for score, index in zip(result_scores[0], result_ids[0]):
                        if index < 0 or index >= len(self._faiss_ids):
                            continue
                        scores[self._faiss_ids[int(index)]] = float(score)
                except Exception as exc:
                    logger.warning("DocIndex: FAISS search lỗi: %s", exc)
            if not scores:
                for chunk_id, chunk_vec in self.vectors.items():
                    scores[chunk_id] = float(np.dot(vector, chunk_vec))
        if not scores:
            for chunk_id, chunk in self.chunks.items():
                scores[chunk_id] = self._keyword_score(query_norm, chunk)
        else:
            # A little lexical signal helps short/no-diacritic queries.
            for chunk_id, vector_score in list(scores.items()):
                chunk = self.chunks.get(chunk_id)
                if chunk is not None:
                    scores[chunk_id] = 0.8 * vector_score + 0.2 * self._keyword_score(
                        query_norm, chunk
                    )

        hits = []
        for chunk_id, score in sorted(scores.items(), key=lambda item: item[1], reverse=True):
            chunk = self.chunks.get(chunk_id)
            if chunk is None:
                continue
            if threshold is not None and score < threshold:
                continue
            hit = dict(chunk)
            hit.update(
                {
                    "source": "doc",
                    "chunk_id": chunk_id,
                    "item_id": chunk_id,
                    "question": _candidate_question(chunk),
                    "norm": normalize_query(chunk.get("text") or ""),
                    "score": round(float(score), 4),
                    "question_count": 1,
                    "source_label": _source_label(chunk),
                    "source_ref": _source_ref(chunk),
                }
            )
            hits.append(hit)
            if len(hits) >= max(1, int(top_k)):
                break
        return hits

    def candidates_for_topic(self, topic: str, limit: int = 12) -> list[dict]:
        wanted = normalize_query(topic)
        if not wanted:
            return []
        hits = []
        for chunk in self.chunks.values():
            label = normalize_query(
                f"{chunk.get('file') or ''} {chunk.get('heading') or ''}"
            )
            if wanted not in label:
                continue
            hits.append(
                {
                    "source": "doc",
                    "item_id": chunk.get("chunk_id"),
                    "chunk_id": chunk.get("chunk_id"),
                    "file": chunk.get("file"),
                    "type": chunk.get("type"),
                    "page": chunk.get("page"),
                    "sheet": chunk.get("sheet"),
                    "row_start": chunk.get("row_start"),
                    "row_end": chunk.get("row_end"),
                    "heading": chunk.get("heading"),
                    "question": _candidate_question(chunk),
                    "norm": normalize_query(chunk.get("text") or ""),
                    "score": 0.55,
                    "question_count": 1,
                }
            )
            if len(hits) >= limit:
                break
        return hits

    def topics(self) -> list[dict]:
        counts: dict[str, int] = {}
        for chunk in self.chunks.values():
            label = (chunk.get("heading") or "").strip()
            if not label:
                label = os.path.splitext(str(chunk.get("file") or ""))[0]
            if not label:
                continue
            counts[label] = counts.get(label, 0) + 1
        return [
            {"label": label, "count": count}
            for label, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        ]

    def answer_from_hits(self, hits: list[dict], query: str) -> Optional[dict]:
        return extractive_answer(hits, query)

    # ------------------------------------------------------------------
    # Ingest / remove / persistence
    # ------------------------------------------------------------------
    def ingest(self, path: str, recursive: bool = False, full: bool = False) -> dict:
        started = _now()
        report = {
            "started_at": started,
            "finished_at": started,
            "added": [],
            "updated": [],
            "skipped": [],
            "failed": [],
            "stats": {
                "files_total": 0,
                "chunks_added": 0,
                "chunks_reused": 0,
                "chunks_removed": 0,
                "embeddings_computed": 0,
            },
        }
        path = os.path.abspath(os.path.expanduser(str(path or "")))
        if not os.path.exists(path):
            raise FileNotFoundError(path)
        if os.path.isdir(path):
            paths = []
            if recursive:
                for root, _dirs, names in os.walk(path):
                    for name in sorted(names):
                        candidate = os.path.join(root, name)
                        if is_supported(candidate):
                            paths.append(candidate)
            else:
                for name in sorted(os.listdir(path)):
                    candidate = os.path.join(path, name)
                    if os.path.isfile(candidate) and is_supported(candidate):
                        paths.append(candidate)
        else:
            paths = [path]

        seen_names = set()
        for item_path in paths:
            file_name = os.path.basename(item_path)
            if file_name in seen_names:
                error = "E_DUPLICATE: trùng tên tệp khi quét đệ quy"
                report["failed"].append(
                    {
                        "file": file_name,
                        "type": os.path.splitext(file_name)[1].lstrip(".").lower(),
                        "status": "failed",
                        "chunks": 0,
                        "error": error,
                    }
                )
                self._record_failure(
                    file_name,
                    os.path.splitext(file_name)[1].lstrip(".").lower(),
                    error,
                )
                continue
            seen_names.add(file_name)
            self._current_source_path = item_path
            try:
                result = self._ingest_file(item_path, file_name, full=full)
            except DocLoadError as exc:
                error = f"{exc.code}: {exc.message}"
                report["failed"].append(
                    {
                        "file": file_name,
                        "type": os.path.splitext(file_name)[1].lstrip(".").lower(),
                        "status": "failed",
                        "chunks": 0,
                        "error": error,
                    }
                )
                self._record_failure(
                    file_name,
                    os.path.splitext(file_name)[1].lstrip(".").lower(),
                    error,
                )
                continue
            except Exception as exc:
                logger.exception("Ingest lỗi với %s", file_name)
                error = f"E_INGEST: {exc}"
                report["failed"].append(
                    {
                        "file": file_name,
                        "type": os.path.splitext(file_name)[1].lstrip(".").lower(),
                        "status": "failed",
                        "chunks": 0,
                        "error": error,
                    }
                )
                self._record_failure(
                    file_name,
                    os.path.splitext(file_name)[1].lstrip(".").lower(),
                    error,
                )
                continue

            bucket = "skipped" if result["status"] == "skipped" else (
                "added" if result["status"] == "added" else "updated"
            )
            entry = {
                "file": file_name,
                "type": result["type"],
                "status": result["status"],
                "chunks": result["chunks"],
            }
            if bucket == "updated":
                entry["chunks_added"] = result["new_chunks"]
                entry["chunks_reused"] = result["reused_chunks"]
            report[bucket].append(entry)
            for key in ("chunks_added", "chunks_reused", "chunks_removed", "embeddings_computed"):
                report["stats"][key] += result.get(key, 0)

        report["stats"]["files_total"] = len(paths)
        report["finished_at"] = _now()
        return report

    def _record_failure(self, file_name: str, type_name: str, error: str) -> None:
        previous = self.files.get(file_name)
        if previous and previous.get("status") == "indexed":
            # Keep the last successfully indexed version on disk.
            return
        now = _now()
        size = 0
        try:
            source = getattr(self, "_current_source_path", None)
            if source:
                size = os.path.getsize(source)
        except OSError:
            size = 0
        self.files[file_name] = {
            "file": file_name,
            "type": type_name,
            "file_hash": (previous or {}).get("file_hash") or "",
            "size_bytes": size,
            "status": "failed",
            "chunk_ids": [],
            "ingested_at": (previous or {}).get("ingested_at") or now,
            "updated_at": now,
            "error": error,
            "mtime_ns": (previous or {}).get("mtime_ns") or 0,
        }
        try:
            self._save()
        except Exception:
            logger.exception("DocIndex: không lưu được trạng thái lỗi của %s", file_name)

    def _ingest_file(self, path: str, file_name: str, full: bool = False) -> dict:
        file_name = _safe_file_name(file_name)
        type_name = os.path.splitext(file_name)[1].lstrip(".").lower()
        if not is_supported(path):
            raise DocLoadError("E_UNSUPPORTED", f"Định dạng không hỗ trợ: {file_name}")
        size = os.path.getsize(path)
        if size > max_bytes():
            raise DocLoadError(
                "E_SIZE",
                f"Tệp lớn {size} byte; tối đa {max_bytes()} byte: {file_name}",
            )
        file_hash = _sha256_file(path)
        previous = self.files.get(file_name)
        if (
            not full
            and previous
            and previous.get("file_hash") == file_hash
            and previous.get("status") == "indexed"
            and all(chunk_id in self.chunks for chunk_id in previous.get("chunk_ids") or [])
        ):
            return {
                "status": "skipped",
                "type": type_name,
                "chunks": len(previous.get("chunk_ids") or []),
                "new_chunks": 0,
                "reused_chunks": 0,
                "chunks_removed": 0,
                "embeddings_computed": 0,
            }

        blocks = extract_blocks(path)
        chunks = chunk_blocks(
            blocks,
            file_name,
            chunk_size=_chunk_size(),
            chunk_overlap=_chunk_overlap(),
        )
        if not chunks:
            raise DocLoadError("E_NO_TEXT", f"Không tạo được đoạn văn bản từ {file_name}")

        old_ids = set((previous or {}).get("chunk_ids") or [])
        old_by_hash = {}
        for chunk_id in old_ids:
            old_chunk = self.chunks.get(chunk_id)
            vector = self.vectors.get(chunk_id)
            if old_chunk is not None and vector is not None:
                old_by_hash[old_chunk.get("content_hash")] = vector

        new_chunks = []
        new_vectors: dict[str, np.ndarray] = {}
        to_embed = []
        reused = 0
        for chunk in chunks:
            new_chunks.append(chunk)
            chunk_id = chunk["chunk_id"]
            cached = None if full else old_by_hash.get(chunk.get("content_hash"))
            if cached is not None:
                new_vectors[chunk_id] = cached
                reused += 1
            else:
                to_embed.append(chunk)

        if to_embed:
            matrix = self._embed([chunk["embed_text"] for chunk in to_embed])
            for chunk, vector in zip(to_embed, matrix):
                new_vectors[chunk["chunk_id"]] = vector

        new_ids = {chunk["chunk_id"] for chunk in new_chunks}
        removed = len(old_ids - new_ids)

        # Mutate only after all embedding work has succeeded.
        for chunk_id in old_ids - new_ids:
            self.chunks.pop(chunk_id, None)
            self.vectors.pop(chunk_id, None)
        for chunk in new_chunks:
            self.chunks[chunk["chunk_id"]] = chunk
            self.vectors[chunk["chunk_id"]] = new_vectors[chunk["chunk_id"]]

        now = _now()
        created_at = (previous or {}).get("ingested_at") or now
        self.files[file_name] = {
            "file": file_name,
            "type": type_name,
            "file_hash": file_hash,
            "size_bytes": size,
            "status": "indexed",
            "chunk_ids": [chunk["chunk_id"] for chunk in new_chunks],
            "ingested_at": created_at if previous else now,
            "updated_at": now,
            "error": None,
            "mtime_ns": os.stat(path).st_mtime_ns,
        }
        self._save()
        self._rebuild_faiss()
        return {
            "status": "updated" if previous else "added",
            "type": type_name,
            "chunks": len(new_chunks),
            "new_chunks": len(to_embed),
            "reused_chunks": reused,
            "chunks_removed": removed,
            "embeddings_computed": len(to_embed),
        }

    def remove_document(self, file_name: str) -> Optional[int]:
        return self.remove(file_name)

    def list_documents(self, data_dir: Optional[str] = None) -> list[dict]:
        return self.list_files(data_dir)

    def load(self):
        self._load()
        return self

    def remove(self, file_name: str) -> Optional[int]:
        file_name = _safe_file_name(file_name)
        record = self.files.get(file_name)
        if not record:
            return None
        chunk_ids = list(record.get("chunk_ids") or [])
        for chunk_id in chunk_ids:
            self.chunks.pop(chunk_id, None)
            self.vectors.pop(chunk_id, None)
        self.files.pop(file_name, None)
        self._save()
        self._rebuild_faiss()
        return len(chunk_ids)

    def list_files(self, data_dir: Optional[str] = None) -> list[dict]:
        rows = []
        seen = set()
        for file_name, record in self.files.items():
            seen.add(file_name)
            rows.append(
                {
                    "file": file_name,
                    "type": record.get("type"),
                    "status": record.get("status") if record.get("status") != "indexed" else "indexed",
                    "chunks": len(record.get("chunk_ids") or []),
                }
            )
        if data_dir and os.path.isdir(data_dir):
            for entry in sorted(os.listdir(data_dir)):
                full = os.path.join(data_dir, entry)
                if not os.path.isfile(full) or not is_supported(full) or entry in seen:
                    continue
                rows.append(
                    {
                        "file": entry,
                        "type": os.path.splitext(entry)[1].lstrip(".").lower(),
                        "status": "not-indexed",
                        "chunks": 0,
                    }
                )
        rows.sort(key=lambda row: str(row.get("file") or ""))
        return rows

    def _save(self) -> None:
        self.index_dir.mkdir(parents=True, exist_ok=True)
        now = _now()
        created_at = self.manifest.get("created_at") or now
        vector_dim = 0
        for vector in self.vectors.values():
            vector_dim = int(len(vector))
            break
        self.manifest = {
            "schema_version": SCHEMA_VERSION,
            "created_at": created_at,
            "updated_at": now,
            "embedding_model": _embedding_model(),
            "normalizer_version": NORMALIZER_VERSION,
            "chunk_size": _chunk_size(),
            "chunk_overlap": _chunk_overlap(),
            "file_count": len(self.files),
            "chunk_count": len(self.chunks),
            "vector_dim": vector_dim,
        }

        ids = sorted(self.chunks)
        matrix = (
            np.asarray([self.vectors[chunk_id] for chunk_id in ids], dtype=np.float32)
            if ids
            else np.zeros((0, vector_dim), dtype=np.float32)
        )
        self._atomic_npz(
            self.index_dir / VECTORS,
            chunk_ids=np.asarray(ids, dtype=object),
            vectors=matrix,
        )
        self._atomic_json(self.index_dir / CHUNKS, self.chunks)
        self._atomic_json(self.index_dir / FILES, self.files)
        self._atomic_json(self.index_dir / MANIFEST, self.manifest)
        self.status = "ready"

    @staticmethod
    def _atomic_json(path: Path, payload) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(
            prefix=path.name + ".", suffix=".tmp", dir=str(path.parent)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, path)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    @staticmethod
    def _atomic_npz(path: Path, **arrays) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(
            prefix=path.name + ".", suffix=".tmp", dir=str(path.parent)
        )
        os.close(fd)
        try:
            with open(temp_path, "wb") as handle:
                np.savez_compressed(handle, **arrays)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, path)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


def extractive_answer(hits: list[dict], query: str, max_bullets: int = 5) -> Optional[dict]:
    """Select 3–5 relevant source sentences from the best 1–2 chunks.

    Selection is relevance-ranked, but bullets are returned in their original
    order of appearance.  The response is kept near 600 characters.
    """

    if not hits:
        return None
    top_hits = hits[:2]
    candidates = []
    seen = set()
    order = 0
    for hit in top_hits:
        for sentence in split_sentences(hit.get("text") or ""):
            order += 1
            if sentence in seen or len(sentence) < 8:
                continue
            seen.add(sentence)
            score = token_overlap(query, sentence)
            if not score:
                score = 0.05
            candidates.append(
                (score, float(hit.get("score") or 0.0), order, hit, sentence)
            )
    if not candidates:
        text = " ".join((hits[0].get("text") or "").split()).strip()
        if not text:
            return None
        candidates = [(0.0, float(hits[0].get("score") or 0.0), 1, hits[0], text)]

    ranked = sorted(candidates, key=lambda item: (item[0], item[1]), reverse=True)
    selected = []
    total_chars = 0
    for candidate in ranked:
        if len(selected) >= max_bullets:
            break
        sentence = candidate[4]
        extra = len(sentence) + (1 if selected else 0)
        if selected and total_chars + extra > 600:
            continue
        if not selected and extra > 600:
            candidate = (candidate[0], candidate[1], candidate[2], candidate[3], sentence[:600])
            sentence = candidate[4]
            extra = len(sentence)
        selected.append(candidate)
        total_chars += extra

    if len(selected) < 3:
        selected_ids = {candidate[2] for candidate in selected}
        for candidate in sorted(candidates, key=lambda item: item[2]):
            if candidate[2] in selected_ids:
                continue
            selected.append(candidate)
            selected_ids.add(candidate[2])
            if len(selected) >= 3:
                break

    selected.sort(key=lambda item: item[2])
    bullets = []
    sources = []
    seen_sources = set()
    for _sentence_score, _chunk_score, _order, hit, sentence in selected:
        if sentence in bullets:
            continue
        bullets.append(sentence)
        source_ref = _source_ref(hit)
        source_key = (
            source_ref.get("file"),
            source_ref.get("page"),
            source_ref.get("sheet"),
            source_ref.get("row_start"),
            source_ref.get("row_end"),
            source_ref.get("heading"),
        )
        if source_key not in seen_sources:
            seen_sources.add(source_key)
            sources.append(source_ref)
    if not bullets:
        return None
    return {
        "response": " ".join(bullets),
        "answer_bullets": bullets,
        "sources": sources,
        "source": _source_label(top_hits[0]),
        "score": round(float(top_hits[0].get("score") or 0.0), 2),
    }


def get_doc_topics(index: DocIndex) -> list[dict]:
    return index.topics()
