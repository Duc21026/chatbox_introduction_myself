import pytest

from backend.doc_loaders import DocLoadError, chunk_blocks, extract_blocks
from backend.tests.helpers import write_csv, write_docx, write_pdf, write_xlsx


def test_pdf_text_layer_and_chunks(tmp_path):
    path = write_pdf(tmp_path / "cv.pdf", ["Backend developer.", "Python and Flask."])

    blocks = extract_blocks(str(path))
    chunks = chunk_blocks(blocks, "cv.pdf")

    assert [block.page for block in blocks] == [1, 2]
    assert all(chunk["text"] for chunk in chunks)
    assert chunks[0]["embed_text"].startswith("[cv.pdf > trang 1]")


def test_docx_heading_and_table(tmp_path):
    path = write_docx(
        tmp_path / "cv.docx",
        ["Kinh nghiệm", "Ba năm làm backend.", ("heading", "Học vấn")],
        table=[["Trường", "Năm"], ["Đại học A", "2020"]],
    )

    blocks = extract_blocks(str(path))
    chunks = chunk_blocks(blocks, "cv.docx")

    text = " ".join(chunk["text"] for chunk in chunks)
    assert "Ba năm" in text
    assert "Trường: Đại học A" in text
    assert any(chunk["heading"] == "Học vấn" for chunk in chunks)


def test_xlsx_all_sheets_with_row_metadata(tmp_path):
    path = write_xlsx(
        tmp_path / "data.xlsx",
        {
            "Điểm": [["Môn", "Điểm"], ["Toán", 9]],
            "Kỹ năng": [["Tên", "Mức"], ["Python", "Tốt"]],
        },
    )

    blocks = extract_blocks(str(path))
    chunks = chunk_blocks(blocks, "data.xlsx")

    sheets = {chunk["sheet"] for chunk in chunks}
    assert sheets == {"Điểm", "Kỹ năng"}
    assert any(
        "Python" in chunk["text"] and "Tốt" in chunk["text"]
        for chunk in chunks
    )
    assert all(chunk["row_start"] >= 2 for chunk in chunks)
    assert "dòng 2–2" in " ".join(chunk["embed_text"] for chunk in chunks)


def test_csv_cp1258_fallback(tmp_path):
    path = write_csv(
        tmp_path / "diem.csv",
        [["Môn", "Toán"], ["Toán", "9"]],
        encoding="cp1258",
    )

    blocks = extract_blocks(str(path))
    chunks = chunk_blocks(blocks, "diem.csv")

    assert "Toán" in chunks[0]["text"]
    assert chunks[0]["sheet"] == "diem"


def test_long_text_chunks_are_bounded(tmp_path):
    path = tmp_path / "long.txt"
    path.write_text(" ".join(f"câu {index}" for index in range(400)), encoding="utf-8")

    chunks = chunk_blocks(extract_blocks(str(path)), "long.txt", 500, 50)

    assert len(chunks) > 1
    assert all(0 < chunk["char_count"] <= 500 for chunk in chunks)


def test_unsupported_and_oversized_files(tmp_path, monkeypatch):
    unsupported = tmp_path / "notes.xyz"
    unsupported.write_text("data", encoding="utf-8")
    with pytest.raises(DocLoadError) as error:
        extract_blocks(str(unsupported))
    assert error.value.code == "E_UNSUPPORTED"

    text = tmp_path / "big.txt"
    text.write_text("a" * 50, encoding="utf-8")
    monkeypatch.setenv("CHATBOT_DOC_MAX_BYTES", "10")
    with pytest.raises(DocLoadError) as error:
        extract_blocks(str(text))
    assert error.value.code == "E_SIZE"


def test_empty_pdf_reports_no_text(tmp_path):
    path = write_pdf(tmp_path / "scan.pdf", [""])
    with pytest.raises(DocLoadError) as error:
        extract_blocks(str(path))
    assert error.value.code == "E_NO_TEXT"
