"""Offline document extraction and chunking for the document index.

Supported formats: PDF (text layer), DOCX, XLSX, CSV, TXT, MD and legacy DOC
(via LibreOffice when available).  The module never contacts Ollama.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Iterable, Optional

try:
    from .text_normalization import normalize_text
except ImportError:  # direct execution
    from text_normalization import normalize_text

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".csv", ".txt", ".md", ".doc"}
DEFAULT_MAX_BYTES = 20 * 1024 * 1024
DEFAULT_CHUNK_SIZE = 500
DEFAULT_CHUNK_OVERLAP = 50

_ABOUT_BLANK = re.compile(r"about:blank\s*\d+\s*/\s*\d+", re.IGNORECASE)
_NOISE_FLOAT = re.compile(r"(\d+\.\d{1,4})\d{2,}")
_UNNAMED_COLUMN = re.compile(r"^Unnamed(?::\s*\d+)?$", re.IGNORECASE)


def _trim_noise_float(match):
    value = match.group(1)
    if "." in value:
        value = value.rstrip("0").rstrip(".")
    return value or match.group(1)


def clean_noise(text: str) -> str:
    """Remove extraction noise: ``about:blank`` footers, float artifacts and
    consecutive duplicate lines (repeated headers/footers)."""

    text = _ABOUT_BLANK.sub(" ", str(text))
    text = _NOISE_FLOAT.sub(_trim_noise_float, text)
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            lines.append(line)
            continue
        if lines and lines[-1].strip() == stripped:
            continue
        lines.append(line)
    return "\n".join(lines).strip()


class DocLoadError(RuntimeError):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


@dataclass
class Block:
    text: str
    type: str
    page: Optional[int] = None
    sheet: Optional[str] = None
    row_start: Optional[int] = None
    row_end: Optional[int] = None
    heading: Optional[str] = None


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(
            f"Giá trị biến môi trường {name} không hợp lệ: {raw!r}"
        ) from exc


def max_bytes() -> int:
    return _env_int("CHATBOT_DOC_MAX_BYTES", DEFAULT_MAX_BYTES)


def file_type(path: str) -> str:
    return os.path.splitext(path)[1].lower().lstrip(".")


def is_supported(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in SUPPORTED_EXTENSIONS


def _check_file(path: str) -> str:
    if not os.path.isfile(path):
        raise DocLoadError("E_FILE_MISSING", f"Không tìm thấy tệp {path}")
    if not is_supported(path):
        raise DocLoadError(
            "E_UNSUPPORTED", f"Định dạng không được hỗ trợ: {path}"
        )
    size = os.path.getsize(path)
    limit = max_bytes()
    if size <= 0:
        raise DocLoadError("E_EMPTY", f"Tệp rỗng: {path}")
    if size > limit:
        raise DocLoadError(
            "E_SIZE",
            f"Tệp lớn {size} byte; tối đa {limit} byte (20 MB): {path}",
        )
    return file_type(path)


def _pdf_blocks(path: str) -> list[Block]:
    from pypdf import PdfReader

    try:
        reader = PdfReader(path)
    except Exception as exc:
        raise DocLoadError("E_PDF", f"Không đọc được PDF: {exc}") from exc

    blocks = []
    for page_number, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        text = text.strip()
        if text:
            blocks.append(Block(text=text, type="pdf", page=page_number))
    if not blocks:
        raise DocLoadError(
            "E_NO_TEXT",
            "PDF không có lớp văn bản (PDF scan cần OCR, ngoài phạm vi v1).",
        )
    return blocks


def _docx_blocks(path: str) -> list[Block]:
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    try:
        document = Document(path)
    except Exception as exc:
        raise DocLoadError("E_DOCX", f"Không đọc được DOCX: {exc}") from exc

    blocks = []
    current_heading = None

    def add_paragraph(paragraph):
        nonlocal current_heading
        text = (paragraph.text or "").strip()
        style = (paragraph.style.name if paragraph.style else "") or ""
        if style.lower().startswith(("heading", "title")):
            current_heading = text or current_heading
        if text:
            blocks.append(
                Block(
                    text=text,
                    type="docx",
                    heading=current_heading,
                )
            )

    def add_table(table: Table):
        rows = []
        for row in table.rows:
            values = [(cell.text or "").strip() for cell in row.cells]
            if any(values):
                rows.append(values)
        if not rows:
            return
        header = rows[0]
        data_rows = rows[1:] if len(rows) > 1 else rows
        for values in data_rows:
            parts = []
            for index, value in enumerate(values):
                if not value:
                    continue
                label = header[index] if index < len(header) and header[index] else f"cột {index + 1}"
                parts.append(f"{label}: {value}")
            text = "; ".join(parts).strip()
            if text:
                blocks.append(
                    Block(
                        text=text,
                        type="docx",
                        heading=current_heading,
                    )
                )

    try:
        contents = document.iter_inner_content()
    except AttributeError:  # older python-docx
        contents = list(document.paragraphs) + list(document.tables)

    for item in contents:
        if isinstance(item, Paragraph):
            add_paragraph(item)
        elif isinstance(item, Table):
            add_table(item)
    if not blocks:
        raise DocLoadError("E_NO_TEXT", "DOCX không có nội dung văn bản.")
    return blocks


def _rows_to_blocks(rows: Iterable[tuple], sheet: Optional[str], type_name: str):
    blocks = []
    for row_index, row in enumerate(rows, start=1):
        parts = []
        for column, value in row:
            if _UNNAMED_COLUMN.match(str(column).strip()):
                continue
            text = str(value).strip()
            if not text or text.lower() in {"nan", "none"}:
                continue
            parts.append(f"{column}: {text}")
        if not parts:
            continue
        prefix = f'Sheet "{sheet}" | ' if sheet else ""
        blocks.append(
            Block(
                text=prefix + "; ".join(parts),
                type=type_name,
                sheet=sheet,
                row_start=row_index,
                row_end=row_index,
            )
        )
    return blocks


def _xlsx_blocks(path: str) -> list[Block]:
    import pandas as pd

    try:
        sheets = pd.read_excel(path, sheet_name=None)
    except Exception as exc:
        raise DocLoadError("E_XLSX", f"Không đọc được XLSX: {exc}") from exc

    blocks = []
    for sheet_name, frame in sheets.items():
        frame = frame.fillna("")
        rows = []
        for _index, row in frame.iterrows():
            rows.append(list(row.items()))
        # Header is Excel row 1; data starts at row 2.
        for block in _rows_to_blocks(rows, str(sheet_name), "xlsx"):
            block.row_start = (block.row_start or 0) + 1
            block.row_end = (block.row_end or 0) + 1
            blocks.append(block)
    if not blocks:
        raise DocLoadError("E_NO_TEXT", "XLSX không có dữ liệu văn bản.")
    return blocks


def _read_csv(path: str):
    import pandas as pd

    last_error = None
    for encoding in ("utf-8-sig", "utf-8", "cp1258", "latin-1"):
        try:
            return pd.read_csv(path, encoding=encoding)
        except (UnicodeDecodeError, UnicodeError) as exc:
            last_error = exc
        except Exception as exc:
            last_error = exc
    raise DocLoadError("E_CSV", f"Không đọc được CSV: {last_error}")


def _csv_blocks(path: str) -> list[Block]:
    frame = _read_csv(path).fillna("")
    rows = [list(row.items()) for _index, row in frame.iterrows()]
    blocks = _rows_to_blocks(rows, os.path.splitext(os.path.basename(path))[0], "csv")
    for block in blocks:
        block.row_start = (block.row_start or 0) + 1
        block.row_end = (block.row_end or 0) + 1
    if not blocks:
        raise DocLoadError("E_NO_TEXT", "CSV không có dữ liệu văn bản.")
    return blocks


def _text_blocks(path: str, type_name: str) -> list[Block]:
    try:
        with open(path, encoding="utf-8-sig") as handle:
            text = handle.read()
    except UnicodeDecodeError:
        try:
            with open(path, encoding="cp1258") as handle:
                text = handle.read()
        except Exception as exc:
            raise DocLoadError("E_ENCODING", f"Không đọc được văn bản: {exc}") from exc

    blocks = []
    if type_name == "md":
        heading = None
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                heading = stripped.lstrip("#").strip() or heading
                continue
            if stripped:
                blocks.append(Block(text=stripped, type="md", heading=heading))
    else:
        for paragraph in text.split("\n\n"):
            paragraph = paragraph.strip()
            if paragraph:
                blocks.append(Block(text=paragraph, type="txt"))
    if not blocks and text.strip():
        blocks.append(Block(text=text.strip(), type=type_name))
    if not blocks:
        raise DocLoadError("E_NO_TEXT", "Tệp văn bản không có nội dung.")
    return blocks


def _doc_blocks(path: str) -> list[Block]:
    executable = shutil.which("libreoffice") or shutil.which("soffice")
    if not executable:
        raise DocLoadError(
            "E_DOC_CONVERT",
            "Cần LibreOffice để chuyển DOC sang DOCX (không tìm thấy libreoffice).",
        )
    with tempfile.TemporaryDirectory() as directory:
        try:
            subprocess.run(
                [
                    executable,
                    "--headless",
                    "--convert-to",
                    "docx",
                    "--outdir",
                    directory,
                    path,
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=120,
            )
        except Exception as exc:
            raise DocLoadError("E_DOC_CONVERT", f"Không chuyển được DOC: {exc}") from exc
        converted = os.path.join(
            directory, os.path.splitext(os.path.basename(path))[0] + ".docx"
        )
        if not os.path.isfile(converted):
            raise DocLoadError("E_DOC_CONVERT", "LibreOffice không tạo được DOCX.")
        return _docx_blocks(converted)


def extract_blocks(path: str) -> list[Block]:
    """Extract ordered text blocks with source metadata from ``path``."""

    type_name = _check_file(path)
    if type_name == "pdf":
        blocks = _pdf_blocks(path)
    elif type_name == "docx":
        blocks = _docx_blocks(path)
    elif type_name == "doc":
        blocks = _doc_blocks(path)
    elif type_name == "xlsx":
        blocks = _xlsx_blocks(path)
    elif type_name == "csv":
        blocks = _csv_blocks(path)
    else:
        blocks = _text_blocks(path, type_name)

    cleaned = []
    for block in blocks:
        text = clean_noise(block.text or "")
        if not text:
            continue
        block.text = text
        cleaned.append(block)
    return cleaned


def _split_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    text = " ".join(text.split())
    if len(text) <= chunk_size:
        return [text] if text else []
    chunks = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        if end < len(text):
            boundary = text.rfind(" ", start, end)
            if boundary > start + chunk_size // 2:
                end = boundary
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


def _prefix(file_name: str, block: Block, group) -> str:
    parts = [file_name]
    if group.get("heading"):
        parts.append(str(group["heading"]))
    if group.get("page") is not None:
        parts.append(f"trang {group['page']}")
    elif group.get("sheet") is not None:
        if group.get("row_start") is not None:
            start = group["row_start"]
            end = group.get("row_end") or start
            parts.append(f'sheet "{group["sheet"]}", dòng {start}–{end}')
        else:
            parts.append(f'sheet "{group["sheet"]}"')
    return "[" + " > ".join(parts) + "]"


def chunk_blocks(
    blocks: Iterable[Block],
    file_name: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[dict]:
    """Group blocks by location/heading and split into ~300–500 char chunks."""

    chunk_size = max(100, min(int(chunk_size or DEFAULT_CHUNK_SIZE), 500))
    chunk_overlap = max(0, min(int(chunk_overlap or DEFAULT_CHUNK_OVERLAP), chunk_size // 2))

    groups: dict[tuple, dict] = {}
    for block in blocks:
        text = (block.text or "").strip()
        if not text:
            continue
        key = (block.type, block.page, block.sheet, block.heading)
        group = groups.get(key)
        if group is None:
            group = {
                "type": block.type,
                "page": block.page,
                "sheet": block.sheet,
                "heading": block.heading,
                "row_start": block.row_start,
                "row_end": block.row_end,
                "texts": [],
            }
            groups[key] = group
        group["texts"].append(text)
        if block.row_start is not None:
            group["row_start"] = (
                block.row_start
                if group["row_start"] is None
                else min(group["row_start"], block.row_start)
            )
        if block.row_end is not None:
            group["row_end"] = (
                block.row_end
                if group["row_end"] is None
                else max(group["row_end"], block.row_end)
            )

    chunks = []
    for group in groups.values():
        combined = "\n".join(group["texts"]).strip()
        prefix = _prefix(file_name, None, group)
        for part in _split_text(combined, chunk_size, chunk_overlap):
            normalized = normalize_text(part, lowercase=False)
            if not normalized:
                continue
            embed_text = f"{prefix} {normalized}".strip()
            content_hash = hashlib.sha256(embed_text.encode("utf-8")).hexdigest()
            location = "|".join(
                str(group.get(field) or "")
                for field in (
                    "page",
                    "sheet",
                    "row_start",
                    "row_end",
                    "heading",
                    "content_hash",
                )
            )
            chunk_id = hashlib.sha1(
                f"{file_name}|{location}".encode("utf-8")
            ).hexdigest()
            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "file": file_name,
                    "type": group["type"],
                    "page": group.get("page"),
                    "sheet": group.get("sheet"),
                    "row_start": group.get("row_start"),
                    "row_end": group.get("row_end"),
                    "heading": group.get("heading"),
                    "text": part,
                    "embed_text": embed_text,
                    "content_hash": content_hash,
                    "char_count": len(part),
                }
            )
    return chunks
