#!/usr/bin/env python3
"""Grid-search retrieval thresholds against real evaluation questions."""

from __future__ import annotations

import argparse
import itertools
import json
import os
import sys
from pathlib import Path

import numpy as np
from rapidfuzz import fuzz

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend import embedding_provider, source_store, vector_store  # noqa: E402
from backend.text_normalization import normalize_query  # noqa: E402


def _cosine(a, b) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0.0:
        return 0.0
    return float(np.dot(a, b) / denom)


def _contains(answer: str, expected: str) -> bool:
    if not expected:
        return True
    return expected.casefold() in answer.casefold()


def _load_cases(path: str):
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload.get("questions", payload) if isinstance(payload, dict) else payload


def _answers_by_item():
    try:
        source = source_store.get_source(source_store.default_config())
    except Exception:
        return {}
    answers = {}
    for item in source.kb_items:
        parts = [item.answer or ""]
        parts.extend(item.answer_bullets or [])
        answers[item.id] = " ".join(part for part in parts if part)
    return answers


def evaluate(cases, entries, vectors, answers, fuzzy_w, high, mid):
    hits = 0
    answered = 0
    for case, vector in zip(cases, vectors):
        scores = []
        for entry in entries:
            cosine = _cosine(vector, np.asarray(entry.vector, dtype=np.float32))
            fuzzy = fuzz.WRatio(
                normalize_query(case["question"]), entry.norm
            ) / 100.0
            scores.append((1.0 - fuzzy_w) * cosine + fuzzy_w * fuzzy)
        order = np.argsort(scores)[::-1]
        top1 = float(scores[order[0]]) if len(order) else 0.0
        top2 = float(scores[order[1]]) if len(order) > 1 else 0.0
        ambiguous = (top1 - top2) < 0.05
        is_answer = top1 >= high and not ambiguous
        if is_answer:
            answered += 1

        category = str(case.get("category") or "")
        expected = str(case.get("expected_answer") or "")
        refusal = bool(case.get("expected_refusal")) or category == "off_topic"
        if refusal:
            success = not is_answer
        elif expected:
            best = entries[int(order[0])] if len(order) else None
            success = bool(
                is_answer
                and best is not None
                and _contains(answers.get(best.item_id, best.question), expected)
            )
        else:
            success = is_answer
        hits += 1 if success else 0
    accuracy = hits / len(cases) if cases else 0.0
    coverage = answered / len(cases) if cases else 0.0
    return accuracy, coverage


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--questions",
        default=str(ROOT / "backend" / "evaluation" / "deploy_questions.json"),
    )
    parser.add_argument(
        "--vectors",
        default=os.environ.get("CHATBOT_VECTORS_PATH", str(ROOT / "data" / "vectors.json")),
    )
    args = parser.parse_args(argv)

    try:
        cases = _load_cases(args.questions)
    except Exception as exc:
        print(f"LỖI đọc bộ câu hỏi: {exc}", file=sys.stderr)
        return 1
    index = vector_store.load(args.vectors)
    if index is None:
        print("LỖI: không đọc được chỉ mục vector hợp lệ.", file=sys.stderr)
        return 1

    queries = [normalize_query(case["question"]) or case["question"] for case in cases]
    vectors = embedding_provider.embed_texts(queries, timeout=30.0)
    if vectors is None or len(vectors) != len(cases):
        print("LỖI: không tạo được vector cho bộ câu hỏi.", file=sys.stderr)
        return 1
    arrays = [np.asarray(vector, dtype=np.float32) for vector in vectors]
    answers = _answers_by_item()

    best = None
    for fuzzy_w, high, mid in itertools.product(
        (0.0, 0.1, 0.2, 0.3, 0.4),
        (0.70, 0.75, 0.78, 0.80, 0.85, 0.90),
        (0.40, 0.45, 0.50, 0.55, 0.60, 0.65),
    ):
        if mid >= high:
            continue
        accuracy, coverage = evaluate(cases, index.entries, arrays, answers, fuzzy_w, high, mid)
        candidate = (accuracy, coverage, -abs(high - 0.78) - abs(mid - 0.55), fuzzy_w, high, mid)
        if best is None or candidate > best:
            best = candidate

    if best is None:
        print("LỖI: không có tổ hợp ngưỡng hợp lệ.", file=sys.stderr)
        return 1
    accuracy, coverage, _, fuzzy_w, high, mid = best
    print(
        f"Đề xuất: FUZZY_W={fuzzy_w:.1f} HIGH={high:.2f} MID={mid:.2f} "
        f"(accuracy={accuracy:.1%}, answered={coverage:.1%}, cases={len(cases)})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
