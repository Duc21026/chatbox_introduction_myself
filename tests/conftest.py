import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session")
def project_root():
    return ROOT


@pytest.fixture(scope="session")
def evaluation_questions(project_root):
    path = project_root / "evaluation" / "questions.json"
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)["questions"]


@pytest.fixture
def questions_by_category(evaluation_questions):
    grouped = {}
    for item in evaluation_questions:
        grouped.setdefault(item["category"], []).append(item)
    return grouped
