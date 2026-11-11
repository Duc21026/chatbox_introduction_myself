from pathlib import Path

from backend import source_format


HEADER = "CHATBOT-SOURCE v1\n"


def _write(tmp_path, text, name="chatbot.txt"):
    path = Path(tmp_path) / name
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def _codes(result):
    return {issue.code for issue in result.errors}


def _record(kind="qa", record_id="gpa", topic="Học tập", extra=""):
    questions = "questions:\n- GPA của bạn?\n" if kind == "qa" else ""
    answer = "answer:\n8.30\n" if kind == "qa" else ""
    content = "content:\nNội dung RAG.\n" if kind == "doc" else ""
    return (
        "=== RECORD ===\n"
        f"kind: {kind}\n"
        f"id: {record_id}\n"
        f"topic: {topic}\n"
        f"{questions}{answer}{content}{extra}"
        "=== END ===\n"
    )


def test_valid_template_and_escaping(tmp_path):
    path = _write(
        tmp_path,
        HEADER
        + "=== RECORD ===\n"
        "kind: doc\n"
        "id: escape-check\n"
        "topic: Escape\n"
        "content:\n"
        "\\=== END ===\n"
        "\\# đây là nội dung\n"
        "\\id: nội dung\n"
        "\\\\ bắt đầu bằng gạch chéo\n"
        "source: template.txt\n"
        "=== END ===\n",
    )

    result = source_format.validate_source(path)

    assert result.valid, result.errors
    content = result.source_file.records[0].content
    assert "=== END ===" in content
    assert "# đây là nội dung" in content
    assert "id: nội dung" in content
    assert "\\ bắt đầu bằng gạch chéo" in content


def test_missing_header(tmp_path):
    path = _write(tmp_path, "hello\n" + _record())

    result = source_format.validate_source(path)

    assert not result.valid
    assert "E_HEADER" in _codes(result)


def test_bom_is_rejected(tmp_path):
    path = Path(tmp_path) / "chatbot.txt"
    path.write_bytes(b"\xef\xbb\xbf" + (HEADER + _record()).encode("utf-8"))

    result = source_format.validate_source(path)

    assert not result.valid
    assert "E_BOM" in _codes(result)


def test_size_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(source_format, "MAX_BYTES", 10)
    path = _write(tmp_path, HEADER)

    result = source_format.validate_source(path)

    assert not result.valid
    assert "E_SIZE" in _codes(result)


def test_missing_end(tmp_path):
    path = _write(
        tmp_path,
        HEADER
        + "=== RECORD ===\n"
        "kind: doc\n"
        "id: missing-end\n"
        "topic: Test\n"
        "content:\nNội dung\n",
    )

    result = source_format.validate_source(path)

    assert not result.valid
    assert "E_RECORD_EOF" in _codes(result)


def test_invalid_id_and_duplicate_id(tmp_path):
    path = _write(
        tmp_path,
        HEADER
        + _record(record_id="Bad ID")
        + _record(record_id="gpa"),
    )

    result = source_format.validate_source(path)

    assert not result.valid
    assert "E_ID_FORMAT" in _codes(result)


def test_duplicate_id_reports_both_lines(tmp_path):
    path = _write(tmp_path, HEADER + _record() + _record())

    result = source_format.validate_source(path)

    duplicate = [issue for issue in result.errors if issue.code == "E_DUP_ID"]
    assert duplicate
    assert "dòng 2" in duplicate[0].message
    assert duplicate[0].line == 11


def test_invalid_kind(tmp_path):
    path = _write(tmp_path, HEADER + _record(kind="faq"))

    result = source_format.validate_source(path)

    assert not result.valid
    assert "E_KIND" in _codes(result)


def test_qa_requires_answer_or_bullets(tmp_path):
    path = _write(
        tmp_path,
        HEADER
        + "=== RECORD ===\n"
        "kind: qa\n"
        "id: broken\n"
        "topic: Test\n"
        "questions:\n- Câu hỏi?\n"
        "=== END ===\n",
    )

    result = source_format.validate_source(path)

    assert not result.valid
    assert "E_ANSWER" in _codes(result)


def test_doc_requires_content(tmp_path):
    path = _write(
        tmp_path,
        HEADER
        + "=== RECORD ===\n"
        "kind: doc\n"
        "id: empty-doc\n"
        "topic: Test\n"
        "=== END ===\n",
    )

    result = source_format.validate_source(path)

    assert not result.valid
    assert "E_CONTENT" in _codes(result)


def test_question_length_limit(tmp_path):
    path = _write(
        tmp_path,
        HEADER
        + _record(extra="").replace(
            "- GPA của bạn?", "- " + ("x" * 201)
        ),
    )

    result = source_format.validate_source(path)

    assert not result.valid
    assert "E_QUESTION_ITEM" in _codes(result)


def test_unknown_field_is_a_warning(tmp_path):
    path = _write(
        tmp_path,
        HEADER
        + "=== RECORD ===\n"
        "kind: doc\n"
        "id: future\n"
        "topic: Test\n"
        "foo: bar\n"
        "content:\nNội dung\n"
        "=== END ===\n",
    )

    result = source_format.validate_source(path)

    assert result.valid
    assert any(issue.code == "W_UNKNOWN_FIELD" for issue in result.warnings)


def test_empty_file_is_rejected(tmp_path):
    path = _write(tmp_path, HEADER)

    result = source_format.validate_source(path)

    assert not result.valid
    assert "E_EMPTY" in _codes(result)
