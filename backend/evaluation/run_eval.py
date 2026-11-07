#!/usr/bin/env python3
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MILESTONES = ("original", "embedding-changed", "answer-model-changed")


def load_questions(path):
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload["questions"]


def run_questions(questions):
    import chatbox

    results = []
    for item in questions:
        started = time.perf_counter()
        try:
            answer = chatbox.ask_ai(item["question"])
            error = None
        except Exception as exc:
            answer = ""
            error = str(exc)
        latency = time.perf_counter() - started
        results.append(
            {
                "question_id": item["id"],
                "question": item["question"],
                "category": item["category"],
                "expected_answer": item.get("expected_answer"),
                "expected_refusal": item.get("expected_refusal", False),
                "answer": answer,
                "latency_seconds": round(latency, 3),
                "factual_correct": None,
                "refusal_correct": None,
                "natural_vietnamese": None,
                "notes": "" if error is None else f"error: {error}",
            }
        )
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Chạy bộ câu hỏi đánh giá chatbot cho một mốc cấu hình."
    )
    parser.add_argument("--milestone", required=True, choices=MILESTONES)
    parser.add_argument(
        "--output",
        default=str(ROOT / "evaluation" / "results"),
        help="Thư mục ghi kết quả",
    )
    parser.add_argument(
        "--questions",
        default=str(ROOT / "evaluation" / "questions.json"),
        help="Đường dẫn tệp câu hỏi đánh giá",
    )
    args = parser.parse_args()

    questions = load_questions(args.questions)

    import chatbox

    results = run_questions(questions)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{args.milestone}.json"

    payload = {
        "milestone": args.milestone,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "configuration": {
            "answer_model": chatbox.config.answer_model,
            "embedding_model": chatbox.config.embedding_model,
            "relevance_threshold": chatbox.config.relevance_threshold,
            "fuzzy_match_cutoff": chatbox.config.fuzzy_match_cutoff,
        },
        "results": results,
    }

    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)

    print(f"Đã ghi {len(results)} kết quả vào {output_path}")


if __name__ == "__main__":
    main()
