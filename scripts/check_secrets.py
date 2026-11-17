#!/usr/bin/env python3
"""Fail if a real-looking secret is found in tracked deployment files."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache", "library", "specs"}
TEXT_SUFFIXES = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".yml", ".yaml",
    ".md", ".txt", ".env", ".example", ".toml", ".ini", ".cfg",
}
TOKEN_PATTERN = re.compile(r"(?:CF_API_TOKEN|CF_ACCOUNT_ID)\s*[:=]\s*[\"']?([A-Za-z0-9_\-]{16,})")
PLACEHOLDERS = {"your-token", "your_account_id", "changeme", "replace-me", "..."}


def _iter_files():
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.name in {".env", ".env.local"}:
            continue
        if path.suffix.lower() in TEXT_SUFFIXES or path.name.startswith(".env"):
            yield path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    findings = []
    for path in _iter_files():
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            match = TOKEN_PATTERN.search(line)
            if not match:
                continue
            value = match.group(1)
            if value.lower() in PLACEHOLDERS or value.startswith("<") or value.startswith("$"):
                continue
            findings.append((path.relative_to(ROOT), line_number, match.group(0)[:80]))

    for path, line, preview in findings:
        print(f"{path}:{line}: {preview}", file=sys.stderr)
    if findings:
        print(f"Phát hiện {len(findings)} giá trị giống bí mật.", file=sys.stderr)
        return 1
    if not args.quiet:
        print("Không phát hiện bí mật trong các tệp đã quét.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
