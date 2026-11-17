import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_vercel_services_config():
    config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    services = config["services"]
    assert services["backend"]["framework"] == "flask"
    assert services["backend"]["root"] == "."
    assert services["frontend"]["framework"] == "vite"
    assert services["frontend"]["root"] == "frontend"
    assert services["frontend"]["outputDirectory"] == "dist"

    backend_files = services["backend"]["functions"]["app.py"]["includeFiles"]
    assert "backend/**" in backend_files
    assert "data/**" in backend_files
    assert "backend/tests/**" in services["backend"]["functions"]["app.py"]["excludeFiles"]

    # Services mode: build/runtime keys belong to services, not the top level.
    for key in ("functions", "installCommand", "buildCommand", "outputDirectory", "framework"):
        assert key not in config

    rewrites = config["rewrites"]
    assert rewrites[0]["source"] == "/api/(.*)"
    assert rewrites[0]["destination"] == {"service": "backend"}
    assert rewrites[-1]["source"] == "/(.*)"
    assert rewrites[-1]["destination"] == {"service": "frontend"}
    assert "bindings" not in services["backend"]
    assert "bindings" not in services["frontend"]


def test_python_runtime_is_pinned():
    assert (ROOT / ".python-version").read_text(encoding="utf-8").strip() == "3.12"


def test_deploy_requirements_exclude_legacy_runtime():
    text = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
    for forbidden in ("langchain", "faiss", "ollama"):
        assert forbidden not in text
    assert "flask" in text
    assert "numpy" in text
    assert "rapidfuzz" in text
