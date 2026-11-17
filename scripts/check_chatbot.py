#!/usr/bin/env python3
"""Validate the canonical chatbot source and its derived inputs."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend import aliases, courses, source_format  # noqa: E402


def _default_source() -> str:
    return os.environ.get("CHATBOT_SOURCE_PATH", str(ROOT / "data" / "chatbot.txt"))


def _default_courses() -> str:
    return os.environ.get("CHATBOT_COURSES_PATH", str(ROOT / "data" / "sources" / "courses.csv"))


def _default_aliases() -> str:
    return os.environ.get("CHATBOT_ALIASES_PATH", str(ROOT / "data" / "sources" / "aliases.txt"))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", nargs="?", default=_default_source())
    parser.add_argument("--courses", default=_default_courses())
    parser.add_argument("--aliases", default=_default_aliases())
    args = parser.parse_args(argv)

    errors = 0
    warnings = 0

    try:
        result = source_format.validate_source(args.source)
    except Exception as exc:
        print(f"LỖI đọc nguồn: {exc}", file=sys.stderr)
        return 1

    for issue in result.errors:
        suffix = f" (dòng {issue.line})" if issue.line else ""
        print(f"LỖI [{issue.code}]: {issue.message}{suffix}", file=sys.stderr)
        errors += 1
    for issue in result.warnings:
        suffix = f" (dòng {issue.line})" if issue.line else ""
        print(f"CẢNH BÁO [{issue.code}]: {issue.message}{suffix}", file=sys.stderr)
        warnings += 1

    course_list = []
    if os.path.isfile(args.courses):
        course_list, course_issues = courses.load_courses(args.courses)
        for issue in course_issues:
            text = f"[{issue.code}] {issue.message}"
            if issue.row is not None:
                text += f" (dòng {issue.row})"
            if issue.severity == "error":
                print(f"LỖI courses.csv: {text}", file=sys.stderr)
                errors += 1
            else:
                print(f"CẢNH BÁO courses.csv: {text}", file=sys.stderr)
                warnings += 1
        if result.valid and result.source_file is not None:
            from backend import source_format as sf

            derived = sf.map_source(result.source_file)
            for issue in courses.check_against_facts(
                courses.aggregates(course_list), derived.facts_map
            ):
                print(f"CẢNH BÁO tổng hợp: [{issue.code}] {issue.message}", file=sys.stderr)
                warnings += 1
    else:
        print(f"CẢNH BÁO: không tìm thấy courses.csv: {args.courses}", file=sys.stderr)
        warnings += 1

    if os.path.isfile(args.aliases):
        try:
            aliases.load_aliases(args.aliases)
        except Exception as exc:
            print(f"LỖI aliases.txt: {exc}", file=sys.stderr)
            errors += 1
    else:
        print(f"CẢNH BÁO: không tìm thấy aliases.txt: {args.aliases}", file=sys.stderr)
        warnings += 1

    counts = result.counts() if hasattr(result, "counts") else {}
    print(
        f"Đã kiểm tra {args.source}: {errors} lỗi, {warnings} cảnh báo"
        + (f", {counts}" if counts else "")
    )
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
