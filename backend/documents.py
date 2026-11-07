"""Source document lifecycle for the local RAG knowledge base."""

import os
import shutil
import tempfile
from dataclasses import dataclass
from typing import Optional

import pandas as pd
from langchain_community.document_loaders import Docx2txtLoader, PyPDFLoader

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATA_DIR = os.path.join(BACKEND_DIR, "data")

SUPPORTED_EXTENSIONS = (".txt", ".pdf", ".docx", ".xlsx", ".csv")
FORMAT_BY_EXTENSION = {
    ".txt": "txt",
    ".pdf": "pdf",
    ".docx": "docx",
    ".xlsx": "xlsx",
    ".csv": "csv",
}


@dataclass(frozen=True)
class SourceInfo:
    source_name: str
    format: str
    size_bytes: int
    modified_ns: int


@dataclass(frozen=True)
class SourceDocument:
    source_name: str
    path: str
    format: str
    content: str
    size_bytes: int
    modified_ns: int


@dataclass(frozen=True)
class IngestionResult:
    action: str
    source_name: str
    status: str
    message: str
    chunks_expected: Optional[int] = None


def is_supported_source(filename):
    name = os.path.basename(filename)
    if not name or name.startswith("."):
        return False
    return os.path.splitext(name)[1].lower() in SUPPORTED_EXTENSIONS


def validate_source_name(source_name):
    if not isinstance(source_name, str):
        raise ValueError("Tên nguồn phải là chuỗi")
    if not source_name or not source_name.strip():
        raise ValueError("Tên nguồn không được để trống")
    if source_name != source_name.strip():
        raise ValueError("Tên nguồn không được có khoảng trắng đầu/cuối")
    if "\x00" in source_name:
        raise ValueError("Tên nguồn chứa ký tự không hợp lệ")
    if source_name.startswith(".") or source_name in {".", ".."}:
        raise ValueError("Tên nguồn không được bắt đầu bằng dấu chấm")
    if (
        os.path.isabs(source_name)
        or "/" in source_name
        or "\\" in source_name
        or ":" in source_name
    ):
        raise ValueError("Tên nguồn phải là tên tệp đơn, không chứa đường dẫn")
    stem, extension = os.path.splitext(source_name)
    if not stem:
        raise ValueError("Tên nguồn phải có phần tên trước phần mở rộng")
    if extension.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            "Phần mở rộng nguồn không được hỗ trợ: "
            f"{extension or '(không có)'}"
        )
    return source_name


def _data_directory(data_dir):
    directory = os.path.abspath(data_dir)
    if not os.path.isdir(directory):
        raise ValueError(f"Không tìm thấy thư mục dữ liệu: {directory}")
    return directory


def _resolve_source_path(directory, source_name):
    validate_source_name(source_name)
    base = os.path.realpath(directory)
    candidate = os.path.realpath(os.path.join(base, source_name))
    try:
        inside = os.path.commonpath([base, candidate]) == base
    except ValueError:
        inside = False
    if not inside:
        raise ValueError("Tên nguồn không được trỏ ra ngoài thư mục dữ liệu")
    return candidate


def _read_text_file(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def extract_segments(path):
    """Return a list of {"text", "page"} segments for a supported source."""

    extension = os.path.splitext(path)[1].lower()

    if extension == ".txt":
        return [{"text": _read_text_file(path), "page": None}]

    if extension == ".docx":
        documents = Docx2txtLoader(path).load()
        return [
            {"text": document.page_content, "page": None}
            for document in documents
        ]

    if extension == ".xlsx":
        frame = pd.read_excel(path)
        segments = []
        for _, row in frame.iterrows():
            text = " | ".join(
                f"{column}: {row[column]}" for column in frame.columns
            )
            segments.append({"text": text, "page": None})
        return segments

    if extension == ".csv":
        frame = pd.read_csv(path)
        segments = []
        for _, row in frame.iterrows():
            text = " | ".join(
                f"{column}: {row[column]}" for column in frame.columns
            )
            segments.append({"text": text, "page": None})
        return segments

    if extension == ".pdf":
        documents = PyPDFLoader(path).load()
        return [
            {
                "text": document.page_content,
                "page": document.metadata.get("page"),
            }
            for document in documents
        ]

    raise ValueError(f"Định dạng nguồn không được hỗ trợ: {extension}")


def extract_text(path):
    return "\n".join(segment["text"] for segment in extract_segments(path))


def _validate_content(text):
    if text is None or not text.strip():
        raise ValueError(
            "Tệp không có nội dung văn bản đọc được; PDF quét ảnh cần OCR trước"
        )
    return text


def _validate_input(input_path, source_name):
    if not os.path.isfile(input_path):
        raise ValueError(f"Không tìm thấy tệp đầu vào: {input_path}")
    input_extension = os.path.splitext(input_path)[1].lower()
    name_extension = os.path.splitext(source_name)[1].lower()
    if input_extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Định dạng đầu vào không được hỗ trợ: {input_extension or '(không có)'}"
        )
    if input_extension != name_extension:
        raise ValueError(
            "Phần mở rộng của tên nguồn phải khớp với định dạng đầu vào"
        )


def _atomic_copy(source_path, destination):
    directory = os.path.dirname(destination)
    handle, temporary = tempfile.mkstemp(
        prefix=".tmp-", suffix=".part", dir=directory
    )
    os.close(handle)
    try:
        with open(source_path, "rb") as source, open(
            temporary, "wb"
        ) as target:
            shutil.copyfileobj(source, target)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, destination)
        temporary = None
    finally:
        if temporary and os.path.exists(temporary):
            os.remove(temporary)


def _failure(action, source_name, message):
    return IngestionResult(
        action=action,
        source_name=source_name,
        status="failed",
        message=message,
    )


def add_source(input_path, source_name=None, data_dir=None):
    name = source_name or os.path.basename(input_path)
    try:
        directory = _data_directory(data_dir or DEFAULT_DATA_DIR)
        validate_source_name(name)
        _validate_input(input_path, name)
        _validate_content(extract_text(input_path))
        destination = _resolve_source_path(directory, name)
        _atomic_copy(input_path, destination)
    except Exception as exc:
        return _failure("add", name, str(exc))

    return IngestionResult(
        action="add",
        source_name=name,
        status="success",
        message=f"Đã thêm nguồn {name}",
        chunks_expected=None,
    )


def replace_source(input_path, source_name, data_dir=None):
    try:
        if not source_name:
            raise ValueError("Thao tác thay thế yêu cầu --name")
        directory = _data_directory(data_dir or DEFAULT_DATA_DIR)
        validate_source_name(source_name)
        _validate_input(input_path, source_name)
        destination = _resolve_source_path(directory, source_name)
        if not os.path.isfile(destination):
            raise ValueError(
                f"Nguồn {source_name} không tồn tại; không thể thay thế"
            )
        _validate_content(extract_text(input_path))
        _atomic_copy(input_path, destination)
    except Exception as exc:
        return _failure("replace", source_name or "", str(exc))

    return IngestionResult(
        action="replace",
        source_name=source_name,
        status="success",
        message=f"Đã thay thế nguồn {source_name}",
        chunks_expected=None,
    )


def delete_source(source_name, data_dir=None):
    try:
        directory = _data_directory(data_dir or DEFAULT_DATA_DIR)
        validate_source_name(source_name)
        destination = _resolve_source_path(directory, source_name)
        if not os.path.isfile(destination):
            raise ValueError(f"Nguồn {source_name} không tồn tại")
        os.remove(destination)
    except (ValueError, OSError) as exc:
        return _failure("delete", source_name, str(exc))

    return IngestionResult(
        action="delete",
        source_name=source_name,
        status="success",
        message=f"Đã xóa nguồn {source_name}",
        chunks_expected=None,
    )


def list_sources(data_dir=None):
    directory = _data_directory(data_dir or DEFAULT_DATA_DIR)
    sources = []
    for filename in sorted(os.listdir(directory)):
        if not is_supported_source(filename):
            continue
        path = os.path.join(directory, filename)
        if not os.path.isfile(path):
            continue
        status = os.stat(path)
        sources.append(
            SourceInfo(
                source_name=filename,
                format=FORMAT_BY_EXTENSION[
                    os.path.splitext(filename)[1].lower()
                ],
                size_bytes=status.st_size,
                modified_ns=status.st_mtime_ns,
            )
        )
    return sources
