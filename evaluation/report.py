#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESULTS = ROOT / "evaluation" / "results"
MILESTONES = ("original", "embedding-changed", "answer-model-changed")


def _rate(values):
    scored = [value for value in values if value is not None]
    if not scored:
        return None
    return round(sum(1 for value in scored if value) / len(scored), 4)


def summarize(payload):
    results = payload.get("results", [])
    in_domain = [item for item in results if not item.get("expected_refusal")]
    out_of_scope = [item for item in results if item.get("expected_refusal")]
    latencies = [item["latency_seconds"] for item in results]
    return {
        "milestone": payload.get("milestone", ""),
        "configuration": payload.get("configuration", {}),
        "factual_accuracy": _rate(
            [item.get("factual_correct") for item in in_domain]
        ),
        "refusal_rate": _rate(
            [item.get("refusal_correct") for item in out_of_scope]
        ),
        "naturalness_rate": _rate(
            [item.get("natural_vietnamese") for item in results]
        ),
        "average_latency": (
            round(sum(latencies) / len(latencies), 3) if latencies else None
        ),
    }


def _format_rate(value):
    if value is None:
        return "chưa chấm"
    return f"{value:.2%}"


def _format_latency(value):
    if value is None:
        return "chưa có"
    return f"{value:.3f}"


def render_table(summaries, selected):
    header = (
        "| Milestone | Factual accuracy | Refusal rate | Naturalness | "
        "Avg latency (s) | Selected |\n"
        "|-----------|------------------|--------------|-------------|"
        "-----------------|----------|"
    )
    rows = [header]
    for item in summaries:
        rows.append(
            "| {milestone} | {factual} | {refusal} | {natural} | {latency} | {selected} |".format(
                milestone=item["milestone"],
                factual=_format_rate(item["factual_accuracy"]),
                refusal=_format_rate(item["refusal_rate"]),
                natural=_format_rate(item["naturalness_rate"]),
                latency=_format_latency(item["average_latency"]),
                selected="yes" if item["milestone"] == selected else "",
            )
        )
    return "\n".join(rows)


def main():
    parser = argparse.ArgumentParser(
        description="Tổng hợp kết quả đánh giá thành bảng so sánh."
    )
    parser.add_argument("--results-dir", default=str(DEFAULT_RESULTS))
    parser.add_argument("--selected", choices=MILESTONES, default=None)
    parser.add_argument(
        "--output", default=str(DEFAULT_RESULTS / "comparison.md")
    )
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    summaries = []
    missing = []
    for milestone in MILESTONES:
        path = results_dir / f"{milestone}.json"
        if not path.is_file():
            missing.append(str(path))
            continue
        with open(path, encoding="utf-8") as handle:
            summaries.append(summarize(json.load(handle)))

    table = render_table(summaries, args.selected)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as handle:
        handle.write("# So sánh cấu hình model\n\n")
        handle.write(table + "\n")
        if missing:
            handle.write("\n## Thiếu kết quả\n\n")
            for path in missing:
                handle.write(f"- {path}\n")
        if args.selected:
            handle.write(
                f"\nCấu hình được giữ lại: **{args.selected}**\n"
            )

    print(table)
    if missing:
        print("\nThiếu kết quả: " + ", ".join(missing))
    print(f"\nĐã ghi bảng so sánh vào {output}")


if __name__ == "__main__":
    main()
