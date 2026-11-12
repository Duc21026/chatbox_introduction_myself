import backend.chatbox as chatbox
from backend.doc_index import extractive_answer


def test_extractive_answer_dedupes_keeps_order_and_limits_length(monkeypatch):
    def forbidden():
        raise AssertionError("main document answer must not call the LLM")

    monkeypatch.setattr(chatbox, "get_summary_llm", forbidden)
    hits = [
        {
            "source": "doc",
            "item_id": "chunk-1",
            "file": "CV.pdf",
            "page": 2,
            "sheet": None,
            "row_start": None,
            "row_end": None,
            "heading": "Kinh nghiệm",
            "score": 0.91,
            "text": (
                "Tôi có ba năm kinh nghiệm Python. "
                "Tôi từng làm backend tại công ty A. "
                "Tôi thích viết tài liệu kỹ thuật."
            ),
        },
        {
            "source": "doc",
            "item_id": "chunk-2",
            "file": "CV.pdf",
            "page": 3,
            "sheet": None,
            "row_start": None,
            "row_end": None,
            "heading": "Dự án",
            "score": 0.80,
            "text": (
                "Tôi có ba năm kinh nghiệm Python. "
                "Dự án gần nhất dùng Flask. "
                "Tôi cũng dùng PostgreSQL."
            ),
        },
    ]

    answer = extractive_answer(hits, "kinh nghiệm Python")

    assert 3 <= len(answer["answer_bullets"]) <= 5
    assert len(answer["answer_bullets"]) == len(set(answer["answer_bullets"]))
    assert answer["answer_bullets"][0].startswith("Tôi có ba năm")
    assert len(answer["response"]) <= 600
    assert answer["sources"][0] == {
        "file": "CV.pdf",
        "page": 2,
        "sheet": None,
        "row_start": None,
        "row_end": None,
        "heading": "Kinh nghiệm",
    }
    assert answer["source"] == "CV.pdf, trang 2"


def test_extractive_answer_keeps_table_source_metadata():
    hits = [
        {
            "source": "doc",
            "item_id": "chunk-xlsx",
            "file": "data.xlsx",
            "page": None,
            "sheet": "Điểm",
            "row_start": 2,
            "row_end": 3,
            "heading": None,
            "score": 0.7,
            "text": "Môn: Toán; Điểm: 9. Môn: Lý; Điểm: 8. Môn: Hóa; Điểm: 7.",
        }
    ]

    answer = extractive_answer(hits, "điểm Toán")

    assert answer["sources"][0]["sheet"] == "Điểm"
    assert answer["sources"][0]["row_start"] == 2
    assert answer["sources"][0]["row_end"] == 3
    assert answer["source"] == "data.xlsx, sheet Điểm, dòng 2–3"


def test_extractive_answer_honours_minimum_bullets_for_long_sentences():
    long_sentence = "kinh nghiệm " + ("rất dài " * 50)
    hits = [
        {
            "source": "doc",
            "item_id": "one",
            "file": "long.txt",
            "score": 0.9,
            "text": f"{long_sentence}. {long_sentence} hai. {long_sentence} ba.",
        }
    ]

    answer = extractive_answer(hits, "kinh nghiệm")

    assert len(answer["answer_bullets"]) >= 3
