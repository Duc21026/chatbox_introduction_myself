#!/usr/bin/env python3
"""Build ``data/vectors.json`` from the canonical chatbot source."""

from __future__ import annotations

import argparse
import dataclasses
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend import embedding_provider, source_store, vector_store  # noqa: E402
from backend.text_normalization import NORMALIZER_VERSION, normalize_query  # noqa: E402


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build(source: str, output: str, batch_size: int, timeout: float) -> int:
    config = dataclasses.replace(source_store.default_config(), source_path=source)
    try:
        derived = source_store.build_derived(config)
    except Exception as exc:
        print(f"LỖI nguồn dữ liệu: {exc}", file=sys.stderr)
        return 1

    entries = []
    pending = []
    for item in derived.kb_items:
        for index, question in enumerate(item.questions):
            norm = normalize_query(question) or question
            entries.append(
                {
                    "id": f"{item.id}#{index}",
                    "item_id": item.id,
                    "source_type": "qa",
                    "topic": item.topic,
                    "question": question,
                    "norm": norm,
                }
            )
            pending.append(norm)

    if not pending:
        print("LỖI: nguồn không có câu hỏi qa active để tạo vector.", file=sys.stderr)
        return 1

    vectors = []
    for start in range(0, len(pending), max(1, batch_size)):
        batch = pending[start : start + max(1, batch_size)]
        result = embedding_provider.embed_texts(batch, timeout=timeout)
        if result is None or len(result) != len(batch):
            print(
                f"LỖI: provider không trả vector cho lô {start}–{start + len(batch) - 1}; "
                "không ghi tệp.",
                file=sys.stderr,
            )
            return 1
        vectors.extend(result)

    if len(vectors) != len(entries):
        print("LỖI: số vector không khớp số câu hỏi; không ghi tệp.", file=sys.stderr)
        return 1

    model = embedding_provider.model_name()
    dim = len(vectors[0]) if vectors else 0
    for entry, vector in zip(entries, vectors):
        if len(vector) != dim:
            print("LỖI: vector lệch số chiều; không ghi tệp.", file=sys.stderr)
            return 1
        entry["vector"] = [round(float(value), 5) for value in vector]

    index = vector_store.VectorIndex(
        model=model,
        dim=dim,
        normalizer_version=NORMALIZER_VERSION,
        source_sha256=derived.source_file.content_hash,
        source_kb_hash=derived.kb_hash,
        question_count=len(entries),
        built_at=_now(),
        entries=[vector_store.VectorEntry(**entry) for entry in entries],
    )
    path = vector_store.save(index, output)
    print(
        f"Đã ghi {path}: {len(entries)} vector, model={model}, dim={dim}, "
        f"source_sha256={index.source_sha256[:12]}, kb_hash={index.source_kb_hash[:12]}"
    )
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        default=os.environ.get("CHATBOT_SOURCE_PATH", str(ROOT / "data" / "chatbot.txt")),
    )
    parser.add_argument(
        "--output",
        default=os.environ.get("CHATBOT_VECTORS_PATH", str(ROOT / "data" / "vectors.json")),
    )
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args(argv)
    return build(args.source, args.output, args.batch_size, args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())
