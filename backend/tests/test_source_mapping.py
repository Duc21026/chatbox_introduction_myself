from pathlib import Path

from backend import source_format


SOURCE = """CHATBOT-SOURCE v1

=== RECORD ===
kind: qa
id: gpa
topic: Học tập & Điểm số
questions:
- GPA của bạn là bao nhiêu?
- Điểm trung bình của bạn?
answer:
GPA hiện tại là 8.51 / 10.
bullets:
- GPA 8.51/10
- 87 tín chỉ
source: BẢNG ĐIỂM.pdf#page=2
=== END ===

=== RECORD ===
kind: qa
id: contact
topic: Liên hệ
questions:
- Làm sao để liên hệ?
answer:
email: minhvan9602@gmail.com
=== END ===

=== RECORD ===
kind: doc
id: scholarship
topic: Học bổng
content:
Mục tiêu săn học bổng Thạc sĩ tại Đức.
source: data.txt
=== END ===
"""


def _load(tmp_path):
    path = Path(tmp_path) / "chatbot.txt"
    path.write_text(SOURCE, encoding="utf-8")
    return source_format.load_source(
        path, embedding_model="bge-m3", chunk_size=500, chunk_overlap=50
    )


def test_qa_record_maps_to_kb_qa_and_rag(tmp_path):
    derived = _load(tmp_path)

    assert [item.id for item in derived.kb_items] == ["gpa", "contact"]
    assert len(derived.qa_pairs) == 3
    gpa_pair = derived.qa_pairs[0]
    assert gpa_pair.normalized_question == "gpa của bạn là bao nhiêu?"
    assert gpa_pair.answer == "GPA hiện tại là 8.51 / 10."
    assert gpa_pair.record_id == "gpa"

    qa_documents = [
        document
        for document in derived.rag_documents
        if document.metadata["kind"] == "qa"
    ]
    assert qa_documents[0].metadata["record_id"] == "gpa"
    assert qa_documents[0].metadata["page"] == 2
    assert "GPA hiện tại là 8.51 / 10." in qa_documents[0].page_content


def test_doc_record_maps_only_to_rag(tmp_path):
    derived = _load(tmp_path)

    doc_documents = [
        document
        for document in derived.rag_documents
        if document.metadata["kind"] == "doc"
    ]
    assert len(doc_documents) == 1
    assert doc_documents[0].metadata["source"] == "data.txt"
    assert doc_documents[0].page_content.startswith("Mục tiêu săn học bổng")
    assert all(item.id != "scholarship" for item in derived.kb_items)


def test_qa_content_fallback_uses_topic_questions_and_answer(tmp_path):
    derived = _load(tmp_path)
    contact_document = [
        document
        for document in derived.rag_documents
        if document.metadata["record_id"] == "contact"
    ][0]

    assert "Liên hệ" in contact_document.page_content
    assert "Làm sao để liên hệ?" in contact_document.page_content
    assert "minhvan9602@gmail.com" in contact_document.page_content


def test_kb_hash_is_stable_and_changes_with_kb_content(tmp_path):
    first = _load(tmp_path)
    second = _load(tmp_path)
    assert first.kb_hash == second.kb_hash

    path = Path(tmp_path) / "chatbot.txt"
    path.write_text(
        SOURCE.replace("GPA hiện tại là 8.51 / 10.", "GPA hiện tại là 8.40 / 10."),
        encoding="utf-8",
    )
    changed = source_format.load_source(path)
    assert changed.kb_hash != first.kb_hash


def test_signature_contains_normalizer_and_chunk_config(tmp_path):
    derived = _load(tmp_path)

    assert derived.signature.embedding_model == "bge-m3"
    assert derived.signature.chunk_size == 500
    assert derived.signature.chunk_overlap == 50
    assert derived.signature.normalizer_version == source_format.NORMALIZER_VERSION
