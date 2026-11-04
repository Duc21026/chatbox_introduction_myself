import pytest

import chatbox
from tests.helpers import contains_answer, ollama_ready

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
