import numpy as np

from backend import vector_store
from scripts import tune_weights


def _entry(item_id, question, norm, vector):
    return vector_store.VectorEntry(
        id=f"{item_id}#0",
        item_id=item_id,
        source_type="qa",
        question=question,
        norm=norm,
        vector=vector,
    )


def test_evaluate_prefers_correct_answer():
    entries = [
        _entry("gpa", "GPA của bạn?", "gpa cua ban", [1.0, 0.0]),
        _entry("skills", "Kỹ năng của bạn?", "ky nang cua ban", [0.0, 1.0]),
    ]
    cases = [
        {
            "question": "GPA của bạn?",
            "category": "direct",
            "expected_answer": "8.51",
        }
    ]
    vectors = [np.array([1.0, 0.0], dtype=np.float32)]
    answers = {"gpa": "8.51", "skills": "Python"}

    accuracy, coverage = tune_weights.evaluate(
        cases, entries, vectors, answers, fuzzy_w=0.2, high=0.78, mid=0.55
    )
    assert accuracy == 1.0
    assert coverage == 1.0


def test_evaluate_penalizes_answering_off_topic():
    entries = [_entry("gpa", "GPA của bạn?", "gpa cua ban", [1.0, 0.0])]
    cases = [
        {"question": "Giá vàng hôm nay?", "category": "off_topic", "expected_answer": None}
    ]
    vectors = [np.array([1.0, 0.0], dtype=np.float32)]
    answers = {"gpa": "8.51"}

    accuracy, _ = tune_weights.evaluate(
        cases, entries, vectors, answers, fuzzy_w=0.0, high=0.78, mid=0.55
    )
    assert accuracy == 0.0
