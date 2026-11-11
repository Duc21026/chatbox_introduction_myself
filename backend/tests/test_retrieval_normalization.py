import dataclasses
from pathlib import Path

import pytest
from langchain_core.documents import Document

from backend import chatbox
from backend import documents
from backend.tests.helpers import (
    RecordingDB,
    RecordingLLM,
    ollama_ready,
    write_text_source,
)

ROOT = Path(__file__).resolve().parents[1]

READY = ollama_ready(
    chatbox.config.answer_model,
    chatbox.config.embedding_model,
    chatbox.config.ollama_base_url,
)


def _config(monkeypatch, **overrides):
    updated = dataclasses.replace(chatbox.config, **overrides)
    monkeypatch.setattr(chatbox, "config", updated)
    return updated


def _document(text, source="policy.txt", chunk_index=0):
    return Document(
        page_content=text,
        metadata={"source": source, "chunk_index": chunk_index},
    )


def test_query_is_normalized_before_search(monkeypatch):
    db = RecordingDB([(_document("GPA 8.30"), 0.1)])
    monkeypatch.setattr(chatbox, "get_qa_data", lambda: {})
    monkeypatch.setattr(chatbox, "get_db", lambda: db)
    monkeypatch.setattr(chatbox, "get_llm", lambda: RecordingLLM("GPA là 8.30"))
    _config(monkeypatch, query_rewrite="off", top_k=3)

    answer = chatbox.ask_ai("  HELLOOO!!!   GPA?  ")

    assert answer == "GPA là 8.30"
    assert db.queries == [("hello! gpa?", 3)]


def test_original_question_is_preserved_for_the_prompt(monkeypatch):
    llm = RecordingLLM("ok")
    monkeypatch.setattr(chatbox, "get_qa_data", lambda: {})
    monkeypatch.setattr(chatbox, "get_db", lambda: RecordingDB([(_document("x"), 0.1)]))
    monkeypatch.setattr(chatbox, "get_llm", lambda: llm)
    _config(monkeypatch, query_rewrite="off")

    chatbox.ask_ai("  GPA CỦA TÔI?  ")

    assert "GPA CỦA TÔI?" in llm.prompts[0]


def test_empty_normalized_question_requests_rephrase(monkeypatch):
    def fail_db():
        raise AssertionError("Không được tìm kiếm khi câu hỏi rỗng")

    monkeypatch.setattr(chatbox, "get_db", fail_db)

    answer, diagnostic = chatbox.ask_ai_detailed("!!!")

    assert answer == chatbox.REPHRASE
    assert diagnostic.outcome == "rephrase"
    assert diagnostic.normalized_question == ""


def test_qa_keys_and_questions_share_normalization(monkeypatch, tmp_path):
    qa_path = tmp_path / "qa.txt"
    qa_path.write_text("GPA   hiện tại?|8.30\n", encoding="utf-8")
    monkeypatch.setattr(chatbox, "_qa_data", None)
    _config(monkeypatch, qa_path=str(qa_path), query_rewrite="off", legacy_sources=True)
    monkeypatch.setattr(
        chatbox,
        "get_db",
        lambda: (_ for _ in ()).throw(
            AssertionError("QA match phải bỏ qua tìm kiếm")
        ),
    )

    assert chatbox.get_qa_data() == {"gpa hiện tại?": "8.30"}
    assert chatbox.ask_ai("gpa   HIỆN TẠI?") == "8.30"


def test_rewrite_off_never_calls_the_model(monkeypatch):
    calls = []
    monkeypatch.setattr(
        chatbox, "_rewrite_query", lambda question: calls.append(question) or "x"
    )
    _config(monkeypatch, query_rewrite="off")

    prepared = chatbox.prepare_question("nhan vien duoc nghi")

    assert prepared.rewritten is None
    assert prepared.rewrite_applied is False
    assert calls == []


def test_rewrite_always_rewrites_even_a_clean_question(monkeypatch):
    monkeypatch.setattr(
        chatbox, "_rewrite_query", lambda question: "nhân viên được nghỉ"
    )
    _config(monkeypatch, query_rewrite="always")

    prepared = chatbox.prepare_question("nhân viên được nghỉ")

    assert prepared.rewrite_applied is True
    assert prepared.rewritten == "nhân viên được nghỉ"


def test_auto_rewrites_when_diacritics_are_missing(monkeypatch):
    calls = []
    monkeypatch.setattr(
        chatbox, "_rewrite_query", lambda question: calls.append(question) or None
    )
    _config(monkeypatch, query_rewrite="auto")

    prepared = chatbox.prepare_question("nhan vien duoc nghi")

    assert calls == ["nhan vien duoc nghi"]
    assert prepared.rewritten is None


def test_auto_rewrites_when_raw_input_has_noise(monkeypatch):
    calls = []
    monkeypatch.setattr(
        chatbox, "_rewrite_query", lambda question: calls.append(question) or None
    )
    _config(monkeypatch, query_rewrite="auto")

    chatbox.prepare_question("nhânnn viên được nghỉ")

    assert calls == ["nhânnn viên được nghỉ"]


def test_auto_skips_rewrite_for_a_clean_question(monkeypatch):
    monkeypatch.setattr(
        chatbox,
        "_rewrite_query",
        lambda question: (_ for _ in ()).throw(
            AssertionError("Câu sạch không được viết lại")
        ),
    )
    _config(monkeypatch, query_rewrite="auto")

    prepared = chatbox.prepare_question("nhân viên được nghỉ")

    assert prepared.rewritten is None


def test_rewritten_text_is_normalized_again(monkeypatch):
    monkeypatch.setattr(
        chatbox, "_rewrite_query", lambda question: "  NHÂNNN VIÊN  "
    )
    _config(monkeypatch, query_rewrite="always")

    prepared = chatbox.prepare_question("nhan vien")

    assert prepared.rewritten == "nhân viên"


def test_rewrite_falls_back_when_response_is_empty(monkeypatch):
    _config(monkeypatch, query_rewrite="always")
    monkeypatch.setattr(chatbox, "get_llm", lambda: RecordingLLM("   "))

    assert chatbox._rewrite_query("nhan vien duoc nghi") is None


def test_rewrite_falls_back_when_response_is_unreasonably_long(monkeypatch):
    _config(monkeypatch, query_rewrite="always")
    monkeypatch.setattr(chatbox, "get_llm", lambda: RecordingLLM("x" * 500))

    assert chatbox._rewrite_query("ngắn") is None


def test_diagnostics_report_selected_sources_and_pieces(monkeypatch):
    db = RecordingDB(
        [
            (_document("Nội dung liên quan", source="a.txt", chunk_index=0), 0.5),
            (_document("Nội dung lạc đề", source="b.txt", chunk_index=0), 5.0),
        ]
    )
    llm = RecordingLLM("câu trả lời")
    monkeypatch.setattr(chatbox, "get_qa_data", lambda: {})
    monkeypatch.setattr(chatbox, "get_db", lambda: db)
    monkeypatch.setattr(chatbox, "get_llm", lambda: llm)
    _config(monkeypatch, query_rewrite="off", relevance_threshold=1.0)

    answer, diagnostic = chatbox.ask_ai_detailed("nội dung liên quan là gì")

    assert answer == "câu trả lời"
    assert diagnostic.outcome == "answered"
    assert diagnostic.passed_threshold is True
    assert diagnostic.source_names == ["a.txt"]
    assert len(diagnostic.pieces) == 1
    assert diagnostic.pieces[0]["source_name"] == "a.txt"
    assert diagnostic.pieces[0]["chunk_index"] == 0
    assert diagnostic.pieces[0]["score"] == 0.5


def test_diagnostics_refuse_when_no_piece_passes_the_threshold(monkeypatch):
    def fail_llm():
        raise AssertionError("Không được gọi LLM khi không có đoạn liên quan")

    monkeypatch.setattr(chatbox, "get_qa_data", lambda: {})
    monkeypatch.setattr(
        chatbox,
        "get_db",
        lambda: RecordingDB([(_document("lạc đề"), 9.0)]),
    )
    monkeypatch.setattr(chatbox, "get_llm", fail_llm)
    _config(monkeypatch, query_rewrite="off", relevance_threshold=1.0)

    answer, diagnostic = chatbox.ask_ai_detailed("câu hỏi")

    assert answer == chatbox.REFUSAL
    assert diagnostic.outcome == "refused"
    assert diagnostic.passed_threshold is False
    assert diagnostic.pieces == []


@pytest.mark.skipif(not READY, reason="Ollama hoặc model chưa sẵn sàng")
def test_add_ask_replace_delete_lifecycle(tmp_path, monkeypatch):
    knowledge_base = tmp_path / "kb"
    knowledge_base.mkdir()
    input_dir = tmp_path / "in"
    input_dir.mkdir()

    _config(monkeypatch, data_dir=str(knowledge_base), query_rewrite="off", legacy_sources=True)
    monkeypatch.setattr(chatbox, "_db", None)
    monkeypatch.setattr(chatbox, "_index_signature", None)
    monkeypatch.setattr(chatbox, "_qa_data", None)
    monkeypatch.setattr(chatbox, "get_qa_data", lambda: {})

    first = write_text_source(
        input_dir,
        "nghi-phep.txt",
        "Chính sách riêng: nhân viên được nghỉ 12 ngày phép mỗi năm.",
    )
    assert documents.add_source(first, data_dir=str(knowledge_base)).status == "success"

    question = "Chính sách nghỉ phép riêng quy định bao nhiêu ngày phép?"
    _, diagnostic = chatbox.ask_ai_detailed(question)
    assert diagnostic.passed_threshold is True
    assert "nghi-phep.txt" in diagnostic.source_names

    second = write_text_source(
        input_dir,
        "nghi-phep-moi.txt",
        "Chính sách riêng: nhân viên được nghỉ 15 ngày phép mỗi năm.",
    )
    assert (
        documents.replace_source(
            second, "nghi-phep.txt", data_dir=str(knowledge_base)
        ).status
        == "success"
    )

    _, replaced = chatbox.ask_ai_detailed(question)
    excerpts = " ".join(piece["excerpt"] for piece in replaced.pieces)
    assert "15" in excerpts

    assert (
        documents.delete_source("nghi-phep.txt", data_dir=str(knowledge_base)).status
        == "success"
    )
    answer, deleted = chatbox.ask_ai_detailed(question)
    assert answer == chatbox.REFUSAL
    assert deleted.outcome == "refused"


@pytest.mark.skipif(not READY, reason="Ollama hoặc model chưa sẵn sàng")
def test_noisy_variants_retrieve_the_same_content(tmp_path, monkeypatch):
    knowledge_base = tmp_path / "kb"
    knowledge_base.mkdir()
    input_dir = tmp_path / "in"
    input_dir.mkdir()

    _config(monkeypatch, data_dir=str(knowledge_base), query_rewrite="off", legacy_sources=True)
    monkeypatch.setattr(chatbox, "_db", None)
    monkeypatch.setattr(chatbox, "_index_signature", None)
    monkeypatch.setattr(chatbox, "_qa_data", None)
    monkeypatch.setattr(chatbox, "get_qa_data", lambda: {})

    source = write_text_source(
        input_dir,
        "nghi-phep.txt",
        "Chính sách riêng: nhân viên được nghỉ 12 ngày phép mỗi năm.",
    )
    assert documents.add_source(source, data_dir=str(knowledge_base)).status == "success"

    _, clean = chatbox.ask_ai_detailed(
        "Chính sách riêng quy định bao nhiêu ngày phép?"
    )
    _, noisy = chatbox.ask_ai_detailed(
        "Chínhhh sáchhh riênggg quy địnnhh bao nhiêu ngàyyy phéppp?"
    )

    assert clean.source_names == noisy.source_names
    assert [piece["excerpt"] for piece in clean.pieces] == [
        piece["excerpt"] for piece in noisy.pieces
    ]


@pytest.mark.skipif(not READY, reason="Ollama hoặc model chưa sẵn sàng")
def test_text_pdf_can_be_imported_and_retrieved(tmp_path, monkeypatch):
    knowledge_base = tmp_path / "kb"
    knowledge_base.mkdir()

    _config(monkeypatch, data_dir=str(knowledge_base), query_rewrite="off", legacy_sources=True)
    monkeypatch.setattr(chatbox, "_db", None)
    monkeypatch.setattr(chatbox, "_index_signature", None)
    monkeypatch.setattr(chatbox, "_qa_data", None)
    monkeypatch.setattr(chatbox, "get_qa_data", lambda: {})

    source = ROOT / "research_paper_ai_education.pdf"
    assert (
        documents.add_source(
            str(source),
            source_name="research-paper.pdf",
            data_dir=str(knowledge_base),
        ).status
        == "success"
    )

    _, diagnostic = chatbox.ask_ai_detailed(
        "What is this paper about artificial intelligence and personalized learning?"
    )

    assert diagnostic.passed_threshold is True
    assert "research-paper.pdf" in diagnostic.source_names
