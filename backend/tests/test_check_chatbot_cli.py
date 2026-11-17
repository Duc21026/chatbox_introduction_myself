import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VALID = """CHATBOT-SOURCE v1

=== RECORD ===
kind: qa
id: gpa
topic: Học tập
questions:
- GPA của bạn?
answer:
GPA là 8.51.
=== END ===
"""


def _run(path):
    return subprocess.run(
        [sys.executable, "scripts/check_chatbot.py", str(path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_valid_source_exits_zero(tmp_path):
    path = tmp_path / "chatbot.txt"
    path.write_text(VALID, encoding="utf-8")
    result = _run(path)
    assert result.returncode == 0, result.stdout + result.stderr


def test_invalid_source_exits_non_zero(tmp_path):
    path = tmp_path / "chatbot.txt"
    path.write_text("not a source", encoding="utf-8")
    result = _run(path)
    assert result.returncode != 0
    assert "LỖI" in result.stderr
