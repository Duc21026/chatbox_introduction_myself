#!/usr/bin/env python3
"""HTTP smoke test for a deployed (or local) chatbot instance."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

CHECKS = [
    ("GPA của bạn là bao nhiêu?", "8.51"),
    ("điểm oop", "6.9"),
    ("mục tiêu", None),
    ("asdf", None),
]


def _request(url: str, payload=None, timeout: float = 20.0):
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method="POST" if data else "GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, help="Ví dụ https://project.vercel.app")
    parser.add_argument("--prefix", default="/api", help="Tiền tố API; dùng '' cho local Flask")
    args = parser.parse_args(argv)
    base = args.base_url.rstrip("/")
    prefix = args.prefix.rstrip("/")

    failures = 0
    try:
        status, health = _request(f"{base}{prefix}/health")
        print(f"health: HTTP {status} status={health.get('status')} vectors={health.get('vectors_loaded')}")
        if status != 200:
            failures += 1
    except Exception as exc:
        print(f"health: LỖI {exc}", file=sys.stderr)
        failures += 1

    for question, expected in CHECKS:
        try:
            status, payload = _request(
                f"{base}{prefix}/chat", {"message": question}
            )
        except urllib.error.HTTPError as exc:
            print(f"chat {question!r}: HTTP {exc.code}", file=sys.stderr)
            failures += 1
            continue
        except Exception as exc:
            print(f"chat {question!r}: LỖI {exc}", file=sys.stderr)
            failures += 1
            continue

        response_type = payload.get("type")
        text = str(payload.get("response") or "")
        print(f"chat {question!r}: HTTP {status} type={response_type}")
        if status != 200 or response_type not in {"answer", "suggest", "clarify"}:
            failures += 1
            continue
        if expected and expected not in text:
            print(f"  thiếu giá trị mong đợi {expected!r}", file=sys.stderr)
            failures += 1
        if question == "mục tiêu":
            suggestions = payload.get("suggestions") or []
            if response_type != "suggest" or len(suggestions) < 2:
                print("  cần ít nhất 2 gợi ý", file=sys.stderr)
                failures += 1
            if not any(action.get("id") == "other" for action in payload.get("actions") or []):
                print("  thiếu nút 'Câu hỏi khác'", file=sys.stderr)
                failures += 1
        if question == "asdf" and "không biết" in text.casefold():
            print("  không được trả lời 'không biết'", file=sys.stderr)
            failures += 1

    print(f"Kết quả: {'PASS' if failures == 0 else f'FAIL ({failures})'}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
