import csv
import hashlib
import json
import os
import unicodedata
import urllib.request
from types import SimpleNamespace


def _comparable(text):
    return (
        unicodedata.normalize("NFC", str(text))
        .replace("–", "-")
        .replace("—", "-")
        .replace("−", "-")
        .casefold()
    )


def _model_present(model, installed):
    if model in installed:
        return True
    base = model.split(":", 1)[0]
    for name in installed:
        if name == model or name.startswith(model + "-"):
            return True
        if ":" not in model and name.split(":", 1)[0] == base:
            return True
    return False


def ollama_ready(answer_model, embedding_model, base_url, timeout=2):
    try:
        url = base_url.rstrip("/") + "/api/tags"
        with urllib.request.urlopen(url, timeout=timeout) as response:
            payload = json.load(response)
    except Exception:
        return False
    installed = {item.get("name", "") for item in payload.get("models", [])}
    return _model_present(answer_model, installed) and _model_present(
        embedding_model, installed
    )


def contains_answer(answer, expected):
    if expected is None:
        return False
    if _comparable(expected) in _comparable(answer):
        return True
    try:
        expected_number = float(expected)
    except ValueError:
        return False
    for token in answer.replace(",", ".").split():
        try:
            if abs(float(token) - expected_number) < 1e-9:
                return True
        except ValueError:
            continue
    return False


def write_text_source(directory, name, content):
    path = os.path.join(str(directory), name)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)
    return path


class FakeEmbeddings:
    def embed_documents(self, texts):
        return [[float(len(text)), 1.0, 0.0] for text in texts]

    def embed_query(self, text):
        return [float(len(text)), 1.0, 0.0]


class RecordingDB:
    def __init__(self, results):
        self.results = results
        self.queries = []

    def similarity_search_with_score(self, query, k=2):
        self.queries.append((query, k))
        return self.results


class RecordingLLM:
    def __init__(self, content):
        self.content = content
        self.prompts = []

    def invoke(self, prompt):
        self.prompts.append(prompt)
        return SimpleNamespace(content=self.content)


class ExplodingDB:
    def similarity_search_with_score(self, query, k=2):
        raise AssertionError("Không được gọi tìm kiếm khi không cần thiết")


class FakeEmbedder:
    """Deterministic embedder used by document/index tests (no Ollama)."""

    def __init__(self, dimension=8):
        self.dimension = dimension

    def _vector(self, text):
        digest = hashlib.sha256(str(text).encode("utf-8")).digest()
        values = []
        for index in range(self.dimension):
            byte = digest[index % len(digest)]
            values.append((byte / 127.5) - 1.0)
        return values

    def embed_documents(self, texts):
        return [self._vector(text) for text in texts]

    def embed_query(self, text):
        return self._vector(text)


def write_pdf(path, pages):
    from pypdf import PdfWriter
    from pypdf.generic import (
        DecodedStreamObject,
        DictionaryObject,
        NameObject,
    )

    writer = PdfWriter()
    for text in pages:
        page = writer.add_blank_page(width=300, height=300)
        safe = str(text).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 10 Tf 20 250 Td ({safe}) Tj ET".encode("latin-1", "replace"))
        page[NameObject("/Contents")] = writer._add_object(stream)
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        page[NameObject("/Resources")] = DictionaryObject(
            {
                NameObject("/Font"): DictionaryObject(
                    {NameObject("/F1"): writer._add_object(font)}
                )
            }
        )
    with open(path, "wb") as handle:
        writer.write(handle)
    return path


def write_docx(path, paragraphs, table=None):
    from docx import Document

    document = Document()
    for item in paragraphs:
        if isinstance(item, tuple) and item[0] == "heading":
            document.add_heading(item[1], level=1)
        else:
            document.add_paragraph(str(item))
    if table:
        rows = list(table)
        if rows:
            table_obj = document.add_table(rows=len(rows), cols=len(rows[0]))
            for row_index, row in enumerate(rows):
                for column_index, value in enumerate(row):
                    table_obj.cell(row_index, column_index).text = str(value)
    document.save(path)
    return path


def write_xlsx(path, sheets):
    from openpyxl import Workbook

    workbook = Workbook()
    workbook.remove(workbook.active)
    for name, rows in sheets.items():
        worksheet = workbook.create_sheet(title=name)
        for row in rows:
            worksheet.append(list(row))
    workbook.save(path)
    return path


def write_csv(path, rows, encoding="utf-8"):
    with open(path, "w", encoding=encoding, newline="") as handle:
        writer = csv.writer(handle)
        writer.writerows(rows)
    return path
