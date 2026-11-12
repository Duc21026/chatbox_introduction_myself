from backend.suggestions import (
    build_suggestions,
    build_topics,
    clarify_payload,
    keyword_score,
    suggestion_id,
)


def _candidate(item_id, question, score=0.6, question_count=1, topic="Mục tiêu"):
    return {
        "source": "kb",
        "item_id": item_id,
        "topic": topic,
        "question": question,
        "norm": question.lower(),
        "score": score,
        "question_count": question_count,
    }


def test_suggestion_ids_are_per_question():
    single = _candidate("goal", "Mục tiêu của bạn?", question_count=1)
    multi_a = _candidate("goal", "Mục tiêu nghề nghiệp?", question_count=2)
    multi_b = _candidate("goal", "Mục tiêu học tập?", question_count=2)
    no_item = _candidate(None, "Không có item?")

    assert suggestion_id(single) == "goal"
    assert suggestion_id(multi_a) != suggestion_id(multi_b)
    assert suggestion_id(multi_a).startswith("goal#")
    assert suggestion_id(no_item).startswith("kb:")


def test_suggestions_are_ranked_deduplicated_and_filter_shown():
    candidates = [
        _candidate("a", "Mục tiêu nghề nghiệp?", 0.9),
        _candidate("b", "Mục tiêu học tập?", 0.8),
        _candidate("b", "Mục tiêu học tập?", 0.8),
        _candidate("c", "Mục tiêu tài chính?", 0.7),
    ]

    suggestions = build_suggestions("muc tieu", candidates, [], 2)

    assert len(suggestions) == 2
    assert len({item["id"] for item in suggestions}) == 2
    assert suggestions[0]["score"] >= suggestions[1]["score"]

    again = build_suggestions(
        "muc tieu", candidates, [item["id"] for item in suggestions], 2
    )
    assert all(item["id"] not in {s["id"] for s in suggestions} for item in again)


def test_keyword_score_and_topics():
    candidate = _candidate("goal", "Mục tiêu nghề nghiệp?")
    assert keyword_score("muc tieu", candidate) > 0

    topics = build_topics(
        [
            {"topic": "Kỹ năng", "questions": ["a", "b"]},
            {"topic": "Mục tiêu", "questions": ["c"]},
        ],
        [{"label": "Học bổng", "count": 3}],
    )
    assert topics[0] == "Học bổng"
    assert "Kỹ năng" in topics and "Mục tiêu" in topics


def test_clarify_payload_never_says_khong_biet():
    for level in (1, 2, 3):
        payload = clarify_payload(level, ["A"], ["B?"])
        assert "không biết" not in payload["message"].lower()
        assert payload["message"]
    assert clarify_payload(3, ["A"], ["B?"])["topics"] == []


def test_muc_tieu_gets_multiple_suggestions():
    from backend.text_normalization import normalize_query
    from backend.suggestions import build_suggestions

    candidates = [
        {
            "source": "kb", "item_id": "muc-tieu-hoc-bong",
            "topic": "Mục tiêu", "question": "Mục tiêu học bổng của bạn là gì?",
            "norm": "mục tiêu học bổng của bạn là gì?", "score": 0.85,
            "question_count": 4, "answer": "…", "answer_bullets": None,
        },
        {
            "source": "kb", "item_id": "muc-tieu-ielts",
            "topic": "Mục tiêu", "question": "Mục tiêu IELTS của bạn?",
            "norm": "mục tiêu ielts của bạn?", "score": 0.8,
            "question_count": 3, "answer": "…", "answer_bullets": None,
        },
        {
            "source": "kb", "item_id": "dinh-huong-nghe-nghiep",
            "topic": "Mục tiêu", "question": "Định hướng nghề nghiệp của bạn?",
            "norm": "định hướng nghề nghiệp của bạn?", "score": 0.7,
            "question_count": 3, "answer": "…", "answer_bullets": None,
        },
    ]
    query_norm = normalize_query("mục tiêu")

    suggestions = build_suggestions(query_norm, candidates)
    assert len(suggestions) >= 2
    assert any("học bổng" in s["question"] for s in suggestions)
