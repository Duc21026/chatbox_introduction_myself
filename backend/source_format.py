"""Parser, validator and mapper for the unified ``chatbot.txt`` source.

The file format is line-oriented.  Contract::

    CHATBOT-SOURCE v1
    === RECORD ===
    kind: qa|doc
    id: slug
    topic: text
    questions:
    - câu hỏi
    answer:
    ...
    bullets:
    - ý
    content:
    ...
    source: label
    === END ===

Everything in this module is pure Python and does not contact Ollama.  The
functions are used by ``chatbox``, ``kb_engine`` and ``manage_docs.py``.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Optional

try:
    from .text_normalization import NORMALIZER_VERSION, normalize_text
except ImportError:  # direct execution from backend/
    from text_normalization import NORMALIZER_VERSION, normalize_text

HEADER = "CHATBOT-SOURCE v1"
RECORD_START = "=== RECORD ==="
RECORD_END = "=== END ==="
MAX_BYTES = 20 * 1024 * 1024
MAX_TOPIC = 120
MAX_QUESTION = 200
MAX_ANSWER = 4000
MAX_BULLET = 300
MAX_SOURCE = 300
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
PAGE_PATTERN = re.compile(r"#page=(\d+)")

FIELD_ORDER = (
    "kind",
    "id",
    "topic",
    "questions",
    "answer",
    "bullets",
    "content",
    "source",
)
BLOCK_FIELDS = frozenset({"questions", "answer", "bullets", "content"})
INLINE_FIELDS = frozenset({"kind", "id", "topic", "source"})
FIELD_INDEX = {name: index for index, name in enumerate(FIELD_ORDER)}
RESERVED_PREFIXES = tuple(f"{name}:" for name in FIELD_ORDER) + (
    RECORD_START,
    RECORD_END,
    "#",
)
_UNKNOWN_FIELD = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*:")


@dataclass(frozen=True)
class ValidationIssue:
    severity: str
    code: str
    message: str
    line: Optional[int] = None
    record_id: Optional[str] = None

    def to_dict(self):
        return {
            "severity": self.severity,
            "code": self.code,
            "line": self.line,
            "record_id": self.record_id,
            "message": self.message,
        }


@dataclass
class SourceRecord:
    kind: str
    id: str
    topic: str
    questions: list[str] = field(default_factory=list)
    answer: Optional[str] = None
    bullets: list[str] = field(default_factory=list)
    content: Optional[str] = None
    source: Optional[str] = None
    line_start: int = 0
    line_end: int = 0


@dataclass
class SourceFile:
    path: str
    version: str
    encoding: str
    text: str
    size_bytes: int
    content_hash: str
    mtime_ns: int
    records: list[SourceRecord] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)


@dataclass(frozen=True)
class QAPair:
    question: str
    normalized_question: str
    answer: str
    record_id: str


@dataclass(frozen=True)
class KBItem:
    id: str
    topic: str
    questions: list[str]
    answer: Optional[str] = None
    answer_bullets: Optional[list[str]] = None

    def as_dict(self):
        return {
            "id": self.id,
            "topic": self.topic,
            "questions": list(self.questions),
            "answer": self.answer,
            "answer_bullets": list(self.answer_bullets)
            if self.answer_bullets is not None
            else None,
        }


@dataclass(frozen=True)
class RAGDocument:
    page_content: str
    metadata: dict


@dataclass(frozen=True)
class SourceSignature:
    path: str
    mtime_ns: int
    size_bytes: int
    content_hash: str
    embedding_model: str
    chunk_size: int
    chunk_overlap: int
    normalizer_version: str


@dataclass
class DerivedSource:
    source_file: SourceFile
    qa_pairs: list[QAPair] = field(default_factory=list)
    kb_items: list[KBItem] = field(default_factory=list)
    rag_documents: list[RAGDocument] = field(default_factory=list)
    kb_hash: str = ""
    signature: Optional[SourceSignature] = None


@dataclass
class ValidationResult:
    path: str
    source_file: Optional[SourceFile]
    errors: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)

    @property
    def valid(self):
        return not self.errors

    def counts(self):
        source = self.source_file
        records = source.records if source else []
        return {
            "records": len(records),
            "qa": sum(1 for record in records if record.kind == "qa"),
            "doc": sum(1 for record in records if record.kind == "doc"),
        }

    def to_dict(self):
        return {
            "path": self.path,
            "valid": self.valid,
            "counts": self.counts(),
            "errors": [issue.to_dict() for issue in self.errors],
            "warnings": [issue.to_dict() for issue in self.warnings],
        }


class SourceValidationError(RuntimeError):
    """Raised when a source file cannot be loaded without partial state."""

    def __init__(self, path, issues):
        self.path = path
        self.issues = list(issues)
        first = self.issues[0] if self.issues else None
        if first is None:
            message = f"Tệp nguồn không hợp lệ: {path}"
        else:
            location = f"dòng {first.line}" if first.line else "không xác định dòng"
            message = (
                f"Tệp nguồn không hợp lệ: {path} — "
                f"[{first.code}] {location}: {first.message}"
            )
        super().__init__(message)


def _error(code, message, line=None, record_id=None):
    return ValidationIssue("error", code, message, line, record_id)


def _warning(code, message, line=None, record_id=None):
    return ValidationIssue("warning", code, message, line, record_id)


def _label_of(line):
    for name in FIELD_ORDER:
        prefix = f"{name}:"
        if line == prefix or line.startswith(prefix):
            return name
    return None


def _unescape_line(line):
    """Return (content, was_unnecessary).  Unescapes one leading backslash."""

    if not line.startswith("\\"):
        return line, False
    rest = line[1:]
    necessary = rest.startswith(RESERVED_PREFIXES) or rest.startswith("\\")
    return rest, not necessary


def _validate_text(text, path, size_bytes, mtime_ns, content_hash):
    issues = []
    if text.startswith("\ufeff"):
        issues.append(
            _error(
                "E_BOM",
                "Tệp có BOM. Hãy lưu lại dưới dạng UTF-8 không BOM.",
                1,
            )
        )
        text = text[1:]
    if "\r" in text:
        issues.append(
            _error(
                "E_ENCODING",
                "Tệp dùng CRLF. Hãy chuyển sang xuống dòng LF (\\n).",
                None,
            )
        )
        text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = unicodedata.normalize("NFC", text)
    source = SourceFile(
        path=os.path.abspath(path),
        version="1",
        encoding="utf-8",
        text=text,
        size_bytes=size_bytes,
        content_hash=content_hash,
        mtime_ns=mtime_ns,
    )
    return source, issues


def _parse_record(lines, start):
    """Parse one record starting at ``start`` (0-based)."""

    issues = []
    values = {}
    field_lines = {}
    seen = set()
    current = None
    last_order = -1
    index = start + 1
    line_start = start + 1
    line_end = None

    while index < len(lines):
        raw = lines[index]
        line_number = index + 1

        if raw == RECORD_END:
            line_end = line_number
            index += 1
            break

        if raw.startswith("\\") and current in BLOCK_FIELDS:
            content, unnecessary = _unescape_line(raw)
            if unnecessary:
                issues.append(
                    _warning(
                        "W_ESCAPE",
                        "Dấu '\\' không cần thiết; parser đã bỏ một ký tự.",
                        line_number,
                        values.get("id"),
                    )
                )
            values[current].append(content)
            index += 1
            continue

        label = _label_of(raw)
        if label is not None:
            if label in seen:
                issues.append(
                    _error(
                        "E_FIELD_ORDER",
                        f"Trường '{label}' bị lặp lại trong cùng bản ghi.",
                        line_number,
                        values.get("id"),
                    )
                )
            order = FIELD_INDEX[label]
            if order < last_order:
                issues.append(
                    _error(
                        "E_FIELD_ORDER",
                        f"Trường '{label}' sai thứ tự. Thứ tự đúng: "
                        + ", ".join(FIELD_ORDER),
                        line_number,
                        values.get("id"),
                    )
                )
            last_order = max(last_order, order)
            seen.add(label)
            field_lines[label] = line_number
            current = label
            inline = raw[len(label) + 1 :].strip()
            if label in BLOCK_FIELDS:
                values[label] = [inline] if inline else []
            else:
                values[label] = inline
            index += 1
            continue

        if current in BLOCK_FIELDS:
            values[current].append(raw)
            index += 1
            continue

        if current is None or current in INLINE_FIELDS:
            if _UNKNOWN_FIELD.match(raw):
                issues.append(
                    _warning(
                        "W_UNKNOWN_FIELD",
                        f"Trường '{raw.split(':', 1)[0]}' không được hỗ trợ, "
                        "đã bỏ qua.",
                        line_number,
                    )
                )
                index += 1
                continue
            if raw.strip() == "":
                index += 1
                continue
            issues.append(
                _error(
                    "E_FIELD_ORDER",
                    "Dòng không thuộc trường hợp lệ nào. Kiểm tra thứ tự "
                    "kind, id, topic, questions, answer, bullets, content, source.",
                    line_number,
                    values.get("id"),
                )
            )
            index += 1
            continue

        index += 1

    if line_end is None:
        issues.append(
            _error(
                "E_RECORD_EOF",
                f"Thiếu dòng '{RECORD_END}' cho bản ghi bắt đầu ở dòng "
                f"{line_start}.",
                line_start,
                values.get("id"),
            )
        )
        line_end = len(lines)

    record = SourceRecord(
        kind=str(values.get("kind") or "").strip(),
        id=str(values.get("id") or "").strip(),
        topic=str(values.get("topic") or "").strip(),
        questions=_question_items(values, "questions"),
        answer=_text_block(values, "answer"),
        bullets=_bullet_items(values),
        content=_text_block(values, "content"),
        source=str(values.get("source") or "").strip() or None,
        line_start=line_start,
        line_end=line_end,
    )
    issues.extend(_validate_record(record, field_lines))
    return record, index, issues


def _question_items(values, name):
    lines = values.get(name)
    if not lines:
        return []
    items = []
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if line.startswith("- "):
            items.append(line[2:].strip())
        elif line.startswith("-"):
            items.append(line[1:].strip())
        else:
            items.append(line)
    return items


def _bullet_items(values):
    return _question_items(values, "bullets")


def _text_block(values, name):
    lines = values.get(name)
    if not lines:
        return None
    text = "\n".join(lines).strip()
    return text or None


def _validate_record(record, field_lines):
    issues = []
    rid = record.id or None
    line_of = lambda name: field_lines.get(name, record.line_start)  # noqa: E731

    if not record.kind:
        issues.append(
            _error(
                "E_FIELD_ORDER",
                "Thiếu trường 'kind' bắt buộc.",
                record.line_start,
                rid,
            )
        )
    elif record.kind not in {"qa", "doc"}:
        issues.append(
            _error(
                "E_KIND",
                f"Giá trị kind '{record.kind}' không hợp lệ; chỉ nhận qa hoặc doc.",
                line_of("kind"),
                rid,
            )
        )

    if not record.id:
        issues.append(
            _error(
                "E_FIELD_ORDER",
                "Thiếu trường 'id' bắt buộc.",
                record.line_start,
                rid,
            )
        )
    elif not ID_PATTERN.match(record.id):
        issues.append(
            _error(
                "E_ID_FORMAT",
                f"id '{record.id}' sai định dạng; dùng chữ thường, số, '_' "
                "hoặc '-', bắt đầu bằng chữ/số, tối đa 64 ký tự.",
                line_of("id"),
                rid,
            )
        )

    if not record.topic:
        issues.append(
            _error(
                "E_TOPIC",
                "Trường 'topic' không được để trống.",
                line_of("topic"),
                rid,
            )
        )
    elif len(record.topic) > MAX_TOPIC:
        issues.append(
            _error(
                "E_TOPIC",
                f"topic dài {len(record.topic)} ký tự; tối đa {MAX_TOPIC}.",
                line_of("topic"),
                rid,
            )
        )

    if record.kind == "qa":
        if not record.questions:
            issues.append(
                _error(
                    "E_QUESTIONS",
                    "Bản ghi qa phải có ít nhất một câu hỏi trong 'questions'.",
                    line_of("questions"),
                    rid,
                )
            )
        seen_questions = set()
        for question in record.questions:
            if not question:
                issues.append(
                    _error(
                        "E_QUESTION_ITEM",
                        "Câu hỏi không được để trống.",
                        line_of("questions"),
                        rid,
                    )
                )
                continue
            if len(question) > MAX_QUESTION:
                issues.append(
                    _error(
                        "E_QUESTION_ITEM",
                        f"Câu hỏi dài {len(question)} ký tự; tối đa "
                        f"{MAX_QUESTION}.",
                        line_of("questions"),
                        rid,
                    )
                )
            folded = question.casefold()
            if folded in seen_questions:
                issues.append(
                    _error(
                        "E_QUESTION_ITEM",
                        f"Câu hỏi trùng trong cùng bản ghi: '{question}'.",
                        line_of("questions"),
                        rid,
                    )
                )
            seen_questions.add(folded)

        if not record.answer and not record.bullets:
            issues.append(
                _error(
                    "E_ANSWER",
                    "Bản ghi qa phải có 'answer' hoặc 'bullets'.",
                    line_of("answer") if "answer" in field_lines else record.line_start,
                    rid,
                )
            )
    elif record.kind == "doc":
        if not record.content:
            issues.append(
                _error(
                    "E_CONTENT",
                    "Bản ghi doc phải có 'content' không rỗng.",
                    line_of("content") if "content" in field_lines else record.line_start,
                    rid,
                )
            )
        if record.answer:
            issues.append(
                _error(
                    "E_FIELD_ORDER",
                    "Trường 'answer' chỉ dùng cho bản ghi qa.",
                    line_of("answer"),
                    rid,
                )
            )
        if record.bullets:
            issues.append(
                _error(
                    "E_FIELD_ORDER",
                    "Trường 'bullets' chỉ dùng cho bản ghi qa.",
                    line_of("bullets"),
                    rid,
                )
            )

    if record.answer and len(record.answer) > MAX_ANSWER:
        issues.append(
            _error(
                "E_ANSWER",
                f"answer dài {len(record.answer)} ký tự; tối đa {MAX_ANSWER}.",
                line_of("answer"),
                rid,
            )
        )
    for bullet in record.bullets:
        if not bullet:
            issues.append(
                _error(
                    "E_ANSWER",
                    "Bullet không được để trống.",
                    line_of("bullets"),
                    rid,
                )
            )
        elif len(bullet) > MAX_BULLET:
            issues.append(
                _error(
                    "E_ANSWER",
                    f"Bullet dài {len(bullet)} ký tự; tối đa {MAX_BULLET}.",
                    line_of("bullets"),
                    rid,
                )
            )
    if record.source and len(record.source) > MAX_SOURCE:
        issues.append(
            _error(
                "E_FIELD_ORDER",
                f"source dài {len(record.source)} ký tự; tối đa {MAX_SOURCE}.",
                line_of("source"),
                rid,
            )
        )
    return issues


def parse_source(path):
    """Parse a source file and return ``(SourceFile | None, issues)``."""

    if not os.path.isfile(path):
        return None, [
            _error(
                "E_FILE_MISSING",
                f"Không tìm thấy tệp nguồn '{path}'. Hãy kiểm tra "
                "CHATBOT_SOURCE_PATH.",
            )
        ]

    status = os.stat(path)
    if status.st_size > MAX_BYTES:
        return None, [
            _error(
                "E_SIZE",
                f"Tệp nguồn lớn {status.st_size} byte; tối đa {MAX_BYTES} byte "
                "(20 MB).",
            )
        ]

    with open(path, "rb") as handle:
        payload = handle.read()
    content_hash = hashlib.sha256(payload).hexdigest()
    try:
        raw_text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        return None, [
            _error(
                "E_ENCODING",
                f"Không đọc được tệp dưới dạng UTF-8: {exc}.",
            )
        ]

    source, issues = _validate_text(
        raw_text, path, status.st_size, status.st_mtime_ns, content_hash
    )
    lines = source.text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()

    if not lines or lines[0] != HEADER:
        issues.append(
            _error(
                "E_HEADER",
                f"Dòng đầu tiên phải là '{HEADER}'.",
                1,
            )
        )
        start = 0
    else:
        start = 1

    records = []
    index = start
    while index < len(lines):
        raw = lines[index]
        line_number = index + 1
        if raw.strip() == "" or raw.startswith("#"):
            index += 1
            continue
        if raw == RECORD_START:
            record, index, record_issues = _parse_record(lines, index)
            records.append(record)
            issues.extend(record_issues)
            continue
        if raw == RECORD_END:
            issues.append(
                _error(
                    "E_FIELD_ORDER",
                    f"'{RECORD_END}' xuất hiện ngoài bản ghi.",
                    line_number,
                )
            )
        else:
            issues.append(
                _error(
                    "E_FIELD_ORDER",
                    "Nội dung ngoài bản ghi không hợp lệ; chỉ cho phép dòng "
                    "trống, chú thích '#' hoặc '=== RECORD ==='.",
                    line_number,
                )
            )
        index += 1

    if not records:
        issues.append(
            _error("E_EMPTY", "Tệp nguồn không có bản ghi nào.")
        )

    seen_ids = {}
    for record in records:
        if not record.id:
            continue
        if record.id in seen_ids:
            issues.append(
                _error(
                    "E_DUP_ID",
                    f"id '{record.id}' trùng với bản ghi ở dòng "
                    f"{seen_ids[record.id]}.",
                    record.line_start,
                    record.id,
                )
            )
        else:
            seen_ids[record.id] = record.line_start

    source.records = records
    source.warnings = [issue for issue in issues if issue.severity == "warning"]
    return source, issues


def validate_source(path):
    """Validate a source file without contacting Ollama."""

    source, issues = parse_source(path)
    errors = [issue for issue in issues if issue.severity == "error"]
    warnings = [issue for issue in issues if issue.severity == "warning"]
    return ValidationResult(
        path=os.path.abspath(path),
        source_file=source,
        errors=errors,
        warnings=warnings,
    )


def _format_qa_text(record):
    if record.content:
        return record.content
    parts = [record.topic]
    if record.questions:
        parts.append("Câu hỏi: " + " | ".join(record.questions))
    if record.answer:
        parts.append("Trả lời: " + record.answer)
    elif record.bullets:
        parts.append("Trả lời: " + ", ".join(record.bullets))
    return "\n".join(parts).strip()


def _metadata_for(record):
    metadata = {
        "source": record.source or record.id,
        "record_id": record.id,
        "kind": record.kind,
        "topic": record.topic,
    }
    if record.source:
        match = PAGE_PATTERN.search(record.source)
        if match:
            metadata["page"] = int(match.group(1))
    return metadata


def map_source(source_file):
    """Map a validated ``SourceFile`` to ``DerivedSource``."""

    qa_pairs = []
    kb_items = []
    rag_documents = []

    for record in source_file.records:
        if record.kind == "qa":
            answer = record.answer
            if not answer and record.bullets:
                answer = ", ".join(record.bullets)
            answer = answer or ""
            for question in record.questions:
                normalized = normalize_text(question)
                if not normalized:
                    continue
                qa_pairs.append(
                    QAPair(
                        question=question,
                        normalized_question=normalized,
                        answer=answer,
                        record_id=record.id,
                    )
                )
            kb_items.append(
                KBItem(
                    id=record.id,
                    topic=record.topic,
                    questions=list(record.questions),
                    answer=record.answer,
                    answer_bullets=list(record.bullets) or None,
                )
            )
            rag_documents.append(
                RAGDocument(
                    page_content=_format_qa_text(record),
                    metadata=_metadata_for(record),
                )
            )
        elif record.kind == "doc":
            rag_documents.append(
                RAGDocument(
                    page_content=record.content or "",
                    metadata=_metadata_for(record),
                )
            )

    kb_payload = [item.as_dict() for item in kb_items]
    kb_hash = hashlib.sha256(
        json.dumps(kb_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return DerivedSource(
        source_file=source_file,
        qa_pairs=qa_pairs,
        kb_items=kb_items,
        rag_documents=rag_documents,
        kb_hash=kb_hash,
    )


def load_source(path, *, embedding_model="", chunk_size=500, chunk_overlap=50):
    """Validate and map a source file, or raise ``SourceValidationError``."""

    result = validate_source(path)
    if not result.valid or result.source_file is None:
        raise SourceValidationError(path, result.errors)
    derived = map_source(result.source_file)
    source = result.source_file
    derived.signature = SourceSignature(
        path=source.path,
        mtime_ns=source.mtime_ns,
        size_bytes=source.size_bytes,
        content_hash=source.content_hash,
        embedding_model=embedding_model,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        normalizer_version=NORMALIZER_VERSION,
    )
    return derived


def render_source(records):
    """Serialize ``SourceRecord`` items into the unified text format."""

    lines = [HEADER, ""]
    for record in records:
        lines.append(RECORD_START)
        lines.append(f"kind: {record.kind}")
        lines.append(f"id: {record.id}")
        lines.append(f"topic: {record.topic}")
        if record.questions:
            lines.append("questions:")
            for question in record.questions:
                lines.append(f"- {_single_line(question)}")
        if record.answer:
            lines.append("answer:")
            lines.extend(_escape_block(record.answer))
        if record.bullets:
            lines.append("bullets:")
            for bullet in record.bullets:
                lines.append(f"- {_single_line(bullet)}")
        if record.content:
            lines.append("content:")
            lines.extend(_escape_block(record.content))
        if record.source:
            lines.append(f"source: {_single_line(record.source)}")
        lines.append(RECORD_END)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _single_line(text):
    return " ".join(str(text).splitlines()).strip()


def _escape_block(text):
    escaped = []
    for line in str(text).splitlines():
        if line.startswith(RESERVED_PREFIXES) or line.startswith("\\"):
            escaped.append("\\" + line)
        else:
            escaped.append(line)
    return escaped or [""]
