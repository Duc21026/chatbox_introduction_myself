import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_no_secret_found_in_frontend_sources():
    result = subprocess.run(
        [sys.executable, "scripts/check_secrets.py", "--quiet"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
