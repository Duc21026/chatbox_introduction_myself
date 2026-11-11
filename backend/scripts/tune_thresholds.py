"""Threshold tuning helper for the KB Engine.

Reads kb.json and a test-questions JSON file, embeds each question,
computes the hybrid score against all KB candidates, and prints a report
showing which response type would be returned at the given thresholds.

Usage:
    python backend/scripts/tune_thresholds.py \\
        --kb backend/kb.json \\
        --test backend/evaluation/questions.json \\
        --high 0.78 \\
        --mid 0.55

Test questions file format (same as backend/evaluation/questions.json):
    [
        {"question": "GPA của bạn?",           "expected_type": "answer"},
        {"question": "Hôm nay thời tiết thế nào?", "expected_type": "unknown"},
        {"question": "ban biet ngon ngu gi",    "expected_type": "answer"}
    ]

The script does NOT start the Flask server. It calls Ollama directly.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

# Allow running from repo root: python backend/scripts/tune_thresholds.py
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import numpy as np

try:
    from backend.text_normalization import normalize_query
    from backend import kb_engine
except ImportError:
    from text_normalization import normalize_query  # type: ignore
    import kb_engine  # type: ignore

from langchain_ollama import OllamaEmbeddings
from rapidfuzz import fuzz


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    d = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / d) if d else 0.0


def _hybrid(q_emb, c_emb, q_norm, c_norm) -> float:
    return round(0.8 * _cosine(q_emb, c_emb) + 0.2 * fuzz.WRatio(q_norm, c_norm) / 100, 4)


def _decide(score: float, high: float, mid: float) -> str:
    if score >= high:
        return "answer"
    if score >= mid:
        return "suggest"
    return "unknown"


def main():
    parser = argparse.ArgumentParser(description="Tune KB Engine thresholds")
    parser.add_argument("--kb",   default="backend/kb.json",              help="Path to kb.json")
    parser.add_argument("--test", default="backend/evaluation/questions.json", help="Path to test questions JSON")
    parser.add_argument("--high", type=float, default=0.78, help="HIGH threshold (answer)")
    parser.add_argument("--mid",  type=float, default=0.55, help="MID threshold (suggest)")
    args = parser.parse_args()

    # Load KB
    items = kb_engine._load_kb(args.kb)
    questions: list[str] = []
    item_indices: list[int] = []
    for idx, item in enumerate(items):
        for q in item.get("questions", []):
            if isinstance(q, str) and q.strip():
                questions.append(q.strip())
                item_indices.append(idx)

    ollama_url = os.environ.get("CHATBOT_OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    model      = os.environ.get("CHATBOT_EMBEDDING_MODEL", "bge-m3")

    print(f"Embedding {len(questions)} KB questions with {model}…")
    embedder = OllamaEmbeddings(model=model, base_url=ollama_url)
    questions_norm = [normalize_query(q) or q for q in questions]
    kb_embs = np.array(embedder.embed_documents(questions_norm), dtype=np.float32)
    print("Done.\n")

    # Load test questions
    if not os.path.isfile(args.test):
        print(f"Test file not found: {args.test}", file=sys.stderr)
        sys.exit(1)

    with open(args.test, encoding="utf-8") as fh:
        test_qs = json.load(fh)

    # Header
    col_q  = 40
    col_bm = 38
    col_sc = 7
    col_ty = 9
    col_ex = 9
    col_ok = 4
    header = (
        f"{'Question':<{col_q}} {'Best match':<{col_bm}} {'Score':>{col_sc}} "
        f"{'Type':<{col_ty}} {'Expected':<{col_ex}} {'OK'}"
    )
    print(header)
    print("-" * len(header))

    correct = 0
    total = len(test_qs)

    for entry in test_qs:
        q = entry.get("question", "")
        expected = entry.get("expected_type", "?")
        q_norm = normalize_query(q) or q

        q_emb = np.array(embedder.embed_query(q_norm), dtype=np.float32)
        scores = np.array([
            _hybrid(q_emb, kb_embs[i], q_norm, questions_norm[i])
            for i in range(len(questions))
        ])
        best_i = int(np.argmax(scores))
        best_score = float(scores[best_i])
        best_q = questions[best_i]
        got_type = _decide(best_score, args.high, args.mid)
        ok = "✓" if got_type == expected else "✗"
        if got_type == expected:
            correct += 1

        q_disp  = q[:col_q-1].ljust(col_q)
        bm_disp = best_q[:col_bm-1].ljust(col_bm)
        print(
            f"{q_disp} {bm_disp} {best_score:>{col_sc}.4f} "
            f"{got_type:<{col_ty}} {expected:<{col_ex}} {ok}"
        )

    print("-" * len(header))
    pct = 100 * correct / total if total else 0
    print(f"\nAccuracy: {correct}/{total} = {pct:.1f}%")
    print(f"Thresholds used: HIGH={args.high}, MID={args.mid}")
    if pct < 95:
        print("\nTip: Adjust --high and --mid to improve accuracy.")


if __name__ == "__main__":
    main()
