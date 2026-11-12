import pytest

from backend import chatbox
from backend.tests.helpers import contains_answer, ollama_ready

READY = ollama_ready(
    chatbox.config.answer_model,
    chatbox.config.embedding_model,
    chatbox.config.ollama_base_url,
)


@pytest.mark.skipif(not READY, reason="Ollama hoặc model chưa sẵn sàng")
@pytest.mark.parametrize(
    "categories",
    [["direct", "paraphrase", "no_diacritics", "pronoun_variant"]],
)
def test_in_domain_answers_contain_expected_facts(
    questions_by_category, categories
):
    questions = [
        item
        for category in categories
        for item in questions_by_category[category]
    ]

    for item in questions:
        answer = chatbox.ask_ai(item["question"])
        assert answer and answer != chatbox.REFUSAL, (
            f"Bị từ chối nhầm cho câu {item['question']}"
        )
        assert contains_answer(answer, item["expected_answer"]), (
            f"Thiếu {item['expected_answer']} trong câu trả lời: {answer}"
        )


def _served_texts():
    source = chatbox.get_source()
    texts = []
    for item in source.kb_items:
        if item.answer:
            texts.append(item.answer)
        for bullet in item.answer_bullets or []:
            texts.append(bullet)
    for document in source.rag_documents:
        texts.append(document.page_content)
    return source, texts


def test_served_answers_use_first_person_minh_only():
    _, texts = _served_texts()

    offenders = [text for text in texts if "tôi" in text.casefold()]
    assert not offenders, offenders[:3]


def test_greeting_matches_approved_wording():
    source = chatbox.get_source()

    greeting = next(item for item in source.kb_items if item.id == "greeting")
    assert greeting.answer == (
        "Xin chào! Mình là Đức (bản chatbot). "
        "Bạn muốn biết gì về mình nào?"
    )


def test_archived_gdqp_never_served():
    source, texts = _served_texts()

    joined = " ".join(texts).casefold()
    assert "giáo dục quốc phòng" not in joined
    assert all(not item.id.startswith("gdqp") for item in source.kb_items)


def test_every_course_answer_has_standard_score_format():
    from backend import courses

    source = chatbox.get_source()
    by_id = {item.id: item for item in source.kb_items}
    course_list, issues = courses.load_courses()
    assert not issues

    for course in course_list:
        item = by_id[f"course-{course.code.lower()}"]
        expected = (
            f"Điểm {course.name} là {course.score10_text()} "
            f"({course.letter}, {course.credits} tín chỉ)."
        )
        assert item.answer == expected
