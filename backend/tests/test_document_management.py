from pathlib import Path

import pytest
from pypdf import PdfWriter

from backend import documents
from backend.tests.helpers import write_text_source

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def data_dir(tmp_path):
    directory = tmp_path / "kb"
    directory.mkdir()
    return directory


@pytest.fixture
def input_dir(tmp_path):
    directory = tmp_path / "in"
    directory.mkdir()
    return directory


def test_add_text_source(data_dir, input_dir):
    source = write_text_source(input_dir, "nghi-phep.txt", "Nghỉ 12 ngày.")

    result = documents.add_source(source, data_dir=str(data_dir))

    assert result.status == "success"
    assert result.action == "add"
    destination = data_dir / "nghi-phep.txt"
    assert destination.read_text(encoding="utf-8") == "Nghỉ 12 ngày."
    assert [item.source_name for item in documents.list_sources(str(data_dir))] == [
        "nghi-phep.txt"
    ]


def test_add_uses_input_basename_when_name_is_omitted(data_dir, input_dir):
    source = write_text_source(input_dir, "quydinh.txt", "Quy định.")

    result = documents.add_source(source, data_dir=str(data_dir))

    assert result.status == "success"
    assert (data_dir / "quydinh.txt").is_file()


def test_add_again_is_an_upsert_without_duplicates(data_dir, input_dir):
    first = write_text_source(input_dir, "policy.txt", "Bản cũ 12 ngày.")
    second = write_text_source(input_dir, "policy-new.txt", "Bản mới 15 ngày.")

    assert (
        documents.add_source(
            first, source_name="policy.txt", data_dir=str(data_dir)
        ).status
        == "success"
    )
    result = documents.add_source(
        second, source_name="policy.txt", data_dir=str(data_dir)
    )

    assert result.status == "success"
    assert (data_dir / "policy.txt").read_text(encoding="utf-8") == "Bản mới 15 ngày."
    assert len(list(data_dir.iterdir())) == 1


@pytest.mark.parametrize("content", ["", "   \n\t "])
def test_empty_or_whitespace_source_is_rejected(data_dir, input_dir, content):
    source = write_text_source(input_dir, "empty.txt", content)

    result = documents.add_source(source, data_dir=str(data_dir))

    assert result.status == "failed"
    assert list(data_dir.iterdir()) == []


def test_unreadable_source_is_rejected(data_dir):
    result = documents.add_source(
        str(Path(data_dir).parent / "missing.txt"), data_dir=str(data_dir)
    )

    assert result.status == "failed"
    assert list(data_dir.iterdir()) == []


@pytest.mark.parametrize(
    "name",
    [
        "../evil.txt",
        "/tmp/evil.txt",
        "sub/evil.txt",
        "sub\\evil.txt",
        "..",
        ".hidden.txt",
        "",
        "bad.exe",
    ],
)
def test_invalid_source_names_are_rejected(name):
    with pytest.raises(ValueError):
        documents.validate_source_name(name)


def test_extension_must_match_input_format(data_dir, input_dir):
    source = write_text_source(input_dir, "policy.txt", "Nội dung.")

    result = documents.add_source(
        source, source_name="policy.pdf", data_dir=str(data_dir)
    )

    assert result.status == "failed"
    assert list(data_dir.iterdir()) == []


def test_replace_requires_an_existing_source(data_dir, input_dir):
    source = write_text_source(input_dir, "new.txt", "Nội dung mới.")

    result = documents.replace_source(
        source, "missing.txt", data_dir=str(data_dir)
    )

    assert result.status == "failed"
    assert list(data_dir.iterdir()) == []


def test_replace_removes_the_old_content(data_dir, input_dir):
    first = write_text_source(input_dir, "old.txt", "Nhân viên được 12 ngày.")
    second = write_text_source(input_dir, "new.txt", "Nhân viên được 15 ngày.")
    documents.add_source(first, source_name="policy.txt", data_dir=str(data_dir))

    result = documents.replace_source(
        second, "policy.txt", data_dir=str(data_dir)
    )

    assert result.status == "success"
    assert (data_dir / "policy.txt").read_text(encoding="utf-8") == (
        "Nhân viên được 15 ngày."
    )
    assert len(list(data_dir.iterdir())) == 1


def test_failed_replace_keeps_the_previous_version(data_dir, input_dir):
    first = write_text_source(input_dir, "old.txt", "Nội dung cũ.")
    empty = write_text_source(input_dir, "empty.txt", "   ")
    documents.add_source(first, source_name="policy.txt", data_dir=str(data_dir))

    result = documents.replace_source(
        empty, "policy.txt", data_dir=str(data_dir)
    )

    assert result.status == "failed"
    assert (data_dir / "policy.txt").read_text(encoding="utf-8") == "Nội dung cũ."


def test_delete_removes_the_source(data_dir, input_dir):
    source = write_text_source(input_dir, "policy.txt", "Nội dung.")
    documents.add_source(source, data_dir=str(data_dir))

    result = documents.delete_source("policy.txt", data_dir=str(data_dir))

    assert result.status == "success"
    assert list(data_dir.iterdir()) == []


def test_delete_missing_source_is_reported(data_dir):
    result = documents.delete_source("missing.txt", data_dir=str(data_dir))

    assert result.status == "failed"
    assert "không tồn tại" in result.message


def test_text_pdf_is_accepted_and_extracted(data_dir):
    source = ROOT / "research_paper_ai_education.pdf"

    result = documents.add_source(
        str(source), source_name="research-paper.pdf", data_dir=str(data_dir)
    )

    assert result.status == "success"
    assert (data_dir / "research-paper.pdf").is_file()
    extracted = documents.extract_text(str(data_dir / "research-paper.pdf"))
    assert "Artificial Intelligence" in extracted


def test_scanned_pdf_is_rejected(data_dir, input_dir):
    scanned = input_dir / "scanned.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    with open(scanned, "wb") as handle:
        writer.write(handle)

    result = documents.add_source(
        str(scanned), source_name="scanned.pdf", data_dir=str(data_dir)
    )

    assert result.status == "failed"
    assert "OCR" in result.message
    assert list(data_dir.iterdir()) == []
