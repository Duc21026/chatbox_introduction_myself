import time
from pathlib import Path

from backend import source_format


def test_parse_and_validate_one_megabyte_under_one_second(tmp_path):
    line = "Nội dung học bổng và kế hoạch học tập tại Đức. " * 2
    content = "\n".join(line.strip() for _ in range(12_000))
    source = (
        "CHATBOT-SOURCE v1\n\n"
        "=== RECORD ===\n"
        "kind: doc\n"
        "id: large-doc\n"
        "topic: Tài liệu lớn\n"
        "content:\n"
        f"{content}\n"
        "=== END ===\n"
    )
    path = Path(tmp_path) / "chatbot.txt"
    path.write_text(source, encoding="utf-8")
    assert path.stat().st_size > 1024 * 1024

    started = time.perf_counter()
    result = source_format.validate_source(path)
    elapsed = time.perf_counter() - started

    assert result.valid, result.errors
    assert elapsed < 1.0


def test_assistant_three_branches_stay_within_budget(monkeypatch):
    import statistics

    import backend.assistant as assistant_module
    from backend.assistant import Assistant
    from backend.kb_engine import QueryEvaluation
    from backend.session import SessionStore
    from backend.suggestions import build_suggestions
    from backend.text_normalization import normalize_query

    items = [
        {
            "id": "goal",
            "topic": "Mục tiêu",
            "questions": ["Mục tiêu nghề nghiệp?", "Mục tiêu học tập?"],
            "answer": "Backend developer",
        },
        {
            "id": "skills",
            "topic": "Kỹ năng",
            "questions": ["Bạn giỏi gì?", "Kỹ năng chính?"],
            "answer": "Python",
        },
    ]
    monkeypatch.setattr(assistant_module.kb_engine, "get_items", lambda: items)
    candidates = [
        {
            "source": "kb",
            "item_id": "goal",
            "topic": "Mục tiêu",
            "question": "Mục tiêu nghề nghiệp?",
            "norm": "muc tieu nghe nghiep",
            "score": 0.6,
            "question_count": 2,
        },
        {
            "source": "kb",
            "item_id": "skills",
            "topic": "Kỹ năng",
            "question": "Bạn giỏi gì?",
            "norm": "ban gioi gi",
            "score": 0.5,
            "question_count": 2,
        },
    ]

    calls = [0]

    def evaluator(question):
        calls[0] += 1
        index = calls[0] % 3
        if index == 0:
            return QueryEvaluation(
                norm=question.lower(), word_count=2, query_vec=None,
                top1=0.9, top2=0.1, candidates=[],
                answer_item={"id": "goal", "answer": "Backend"}, embeddings_ready=True,
            )
        if index == 1:
            return QueryEvaluation(
                norm=question.lower(), word_count=2, query_vec=None,
                top1=0.6, top2=0.5, candidates=candidates,
                answer_item=None, embeddings_ready=True,
            )
        return QueryEvaluation(
            norm=question.lower(), word_count=2, query_vec=None,
            top1=0.1, top2=0.0, candidates=[],
            answer_item=None, embeddings_ready=True,
        )

    assistant = Assistant(
        evaluator=evaluator,
        session_store=SessionStore(ttl=60, max_sessions=100),
    )

    preprocess = []
    lookup = []
    suggestion_times = []
    latencies = []
    for index in range(60):
        started = time.perf_counter()
        normalize_query(f"mục tiêu {index}")
        preprocess.append(time.perf_counter() - started)

        started = time.perf_counter()
        evaluator(f"mục tiêu {index}")
        lookup.append(time.perf_counter() - started)

        started = time.perf_counter()
        build_suggestions("muc tieu", candidates, [], 4)
        suggestion_times.append(time.perf_counter() - started)

        started = time.perf_counter()
        response = assistant.handle(f"mục tiêu {index}")
        latencies.append(time.perf_counter() - started)
        assert response["type"] in {"answer", "suggest", "clarify"}
        assert response["type"] != "unknown"

    assert statistics.median(preprocess) < 0.001
    assert statistics.median(lookup) < 0.020
    assert statistics.median(suggestion_times) < 0.005
    assert statistics.median(latencies) < 0.300
    assert sorted(latencies)[int(len(latencies) * 0.95) - 1] < 0.500
