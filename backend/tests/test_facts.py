from pathlib import Path

import pytest

from backend import source_format


def _write(tmp_path, text):
    path = Path(tmp_path) / "chatbot.txt"
    path.write_text(text, encoding="utf-8")
    return path


def _validate(path):
    return source_format.validate_source(str(path))


FACT_SOURCE = """CHATBOT-SOURCE v1

=== RECORD ===
kind: fact
id: gpa-10
label: GPA tích lũy (thang 10)
value: 8.51
snapshot: 2026-11-07
source: bang-diem.pdf
=== END ===

=== RECORD ===
kind: fact
id: graduation
label: Tốt nghiệp dự kiến
value: tháng 8/2028
=== END ===

=== RECORD ===
kind: qa
id: gpa
topic: Học tập
questions:
- GPA của bạn là bao nhiêu?
answer:
GPA tích lũy của mình là {{gpa-10}}/10 và tốt nghiệp {{graduation}}.
=== END ===
"""


def test_fact_records_parse_and_count(tmp_path):
    path = _write(tmp_path, FACT_SOURCE)
    result = _validate(path)

    assert result.valid, result.errors
    assert result.counts()["fact"] == 2


def test_facts_resolve_placeholders_in_answers(tmp_path):
    path = _write(tmp_path, FACT_SOURCE)
    derived = source_format.load_source(str(path))

    assert derived.facts_map["gpa-10"].value == "8.51"
    item = next(item for item in derived.kb_items if item.id == "gpa")
    assert item.answer == (
        "GPA tích lũy của mình là 8.51/10 và tốt nghiệp tháng 8/2028."
    )


def test_unknown_placeholder_is_error_with_line(tmp_path):
    path = _write(
        tmp_path,
        FACT_SOURCE.replace("{{graduation}}", "{{khong-ton-tai}}"),
    )
    result = _validate(path)

    assert not result.valid
    codes = [issue.code for issue in result.errors]
    assert "E_PLACEHOLDER_UNKNOWN" in codes
    issue = next(
        issue for issue in result.errors if issue.code == "E_PLACEHOLDER_UNKNOWN"
    )
    assert "khong-ton-tai" in issue.message
    assert issue.line is not None


def test_escaped_placeholder_is_literal(tmp_path):
    path = _write(
        tmp_path,
        FACT_SOURCE.replace(
            "{{gpa-10}}/10", "\\{{gpa-10}}/10"
        ),
    )
    result = _validate(path)
    assert result.valid, result.errors

    derived = source_format.load_source(str(path))
    item = next(item for item in derived.kb_items if item.id == "gpa")
    assert "{{gpa-10}}/10" in item.answer


def test_placeholder_to_archived_fact_is_error(tmp_path):
    path = _write(
        tmp_path,
        FACT_SOURCE.replace(
            "kind: fact\nid: gpa-10",
            "kind: fact\nid: gpa-10\nstatus: archived",
        ),
    )
    result = _validate(path)

    assert not result.valid
    assert any(
        issue.code == "E_PLACEHOLDER_UNKNOWN" and "archived" in issue.message
        for issue in result.errors
    )


def test_archived_record_excluded_from_everything(tmp_path):
    source = FACT_SOURCE + """=== RECORD ===
kind: qa
id: gdqp
topic: Giáo dục quốc phòng
questions:
- Giáo dục quốc phòng bao nhiêu điểm?
answer:
Điểm Giáo dục quốc phòng là 7.1.
status: archived
=== END ===
"""
    path = _write(tmp_path, source)
    result = _validate(path)
    assert result.valid, result.errors

    derived = source_format.load_source(str(path))
    assert all(item.id != "gdqp" for item in derived.kb_items)
    assert all("7.1" not in doc.page_content for doc in derived.rag_documents)
    assert all(pair.record_id != "gdqp" for pair in derived.qa_pairs)


def test_fact_missing_value_is_error(tmp_path):
    path = _write(
        tmp_path,
        FACT_SOURCE.replace("value: 8.51", ""),
    )
    result = _validate(path)

    assert not result.valid
    assert any(issue.code == "E_MISSING_FIELD" for issue in result.errors)


def test_fact_with_questions_is_error(tmp_path):
    source = """CHATBOT-SOURCE v1

=== RECORD ===
kind: fact
id: x
label: X
value: 1
questions:
- Hỏi x?
=== END ===
"""
    path = _write(tmp_path, source)
    result = _validate(path)

    assert not result.valid
    assert any(issue.code == "E_FIELD_NOT_ALLOWED" for issue in result.errors)


def test_duplicate_fact_id_is_conflict(tmp_path):
    source = """CHATBOT-SOURCE v1

=== RECORD ===
kind: fact
id: gpa-10
label: GPA
value: 8.51
=== END ===

=== RECORD ===
kind: fact
id: gpa-10
label: GPA khác
value: 8.30
=== END ===
"""
    path = _write(tmp_path, source)
    result = _validate(path)

    assert not result.valid
    assert any(issue.code == "E_CONFLICT" for issue in result.errors)


def test_bad_snapshot_format_is_error(tmp_path):
    path = _write(tmp_path, FACT_SOURCE.replace("2026-11-07", "07/11/2026"))
    result = _validate(path)

    assert not result.valid
    assert any(issue.code == "E_VALUE" for issue in result.errors)


def test_bad_status_is_error(tmp_path):
    path = _write(
        tmp_path,
        FACT_SOURCE.replace(
            "kind: qa\nid: gpa",
            "kind: qa\nid: gpa\nstatus: hidden",
        ),
    )
    result = _validate(path)

    assert not result.valid
    assert any(issue.code == "E_BAD_ENUM" for issue in result.errors)


def test_stale_value_scan_flags_old_numbers(tmp_path):
    source = """CHATBOT-SOURCE v1

=== RECORD ===
kind: qa
id: x
topic: T
questions:
- Hỏi gpa?
answer:
GPA là 8.30 với 62 tín chỉ và 17 môn.
=== END ===
"""
    path = _write(tmp_path, source)
    result = _validate(path)

    assert not result.valid
    assert any(issue.code == "E_STALE_VALUE" for issue in result.errors)


def test_render_source_roundtrip_preserves_facts(tmp_path):
    path = _write(tmp_path, FACT_SOURCE)
    source, issues = source_format.parse_source(str(path))
    rendered = source_format.render_source(source.records)

    again = _write(tmp_path, rendered)
    result = _validate(again)
    assert result.valid, result.errors
    derived = source_format.load_source(str(again))
    assert derived.facts_map["gpa-10"].value == "8.51"
