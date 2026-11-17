import ast
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_api_chat_import_does_not_load_legacy_runtime():
    script = (
        "import sys; import api.chat; "
        "bad=[m for m in sys.modules if m in {'chatbox'} or m.startswith('langchain') "
        "or m.startswith('faiss') or m.startswith('langchain_ollama')]; "
        "print(','.join(sorted(bad)))"
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    env["CHATBOT_RUNTIME"] = "deployment"
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == ""


def test_api_files_expose_app():
    for path in (ROOT / "api" / "chat.py", ROOT / "api" / "health.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = {
            target.id
            for node in tree.body
            if isinstance(node, ast.Assign)
            for target in node.targets
            if isinstance(target, ast.Name)
        }
        names.update(
            alias.asname or alias.name
            for node in tree.body
            if isinstance(node, ast.ImportFrom)
            for alias in node.names
        )
        assert "app" in names
