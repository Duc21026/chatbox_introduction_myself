#!/usr/bin/env python3
"""Operator CLI for the local RAG knowledge base."""

import argparse
import json
import os
import re
import sys
import tempfile
import unicodedata

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(BACKEND_DIR)
for _path in (REPO_ROOT, BACKEND_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

DEFAULT_SOURCE = os.path.join(BACKEND_DIR, "data", "chatbot.txt")
DEFAULT_QA = os.path.join(BACKEND_DIR, "qa.txt")
DEFAULT_KB = os.path.join(BACKEND_DIR, "kb.json")
DEFAULT_DATA = os.path.join(BACKEND_DIR, "data")
TARGET_NAME = "chatbot.txt"


def _data_dir(args):
    default = os.path.join(BACKEND_DIR, "data")
    return getattr(args, "data_dir", None) or os.environ.get(
        "CHATBOT_DATA_DIR", default
    )


def _source_path(value):
    return (
        value
        or os.environ.get("CHATBOT_SOURCE_PATH")
        or DEFAULT_SOURCE
    )


def _build_parser():
    parser = argparse.ArgumentParser(
        description="Quản lý nguồn tài liệu cho chatbot RAG"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    add = subparsers.add_parser("add", help="Thêm hoặc cập nhật một nguồn")
    add.add_argument("input_path")
    add.add_argument("--name", default=None)
    add.add_argument("--data-dir", default=None)

    replace = subparsers.add_parser(
        "replace", help="Thay thế một nguồn đã tồn tại"
    )
    replace.add_argument("input_path")
    replace.add_argument("--name", required=True)
    replace.add_argument("--data-dir", default=None)

    delete = subparsers.add_parser("delete", help="Xóa một nguồn")
    delete.add_argument("source_name")
    delete.add_argument("--data-dir", default=None)

    list_command = subparsers.add_parser("list", help="Liệt kê các nguồn")
    list_command.add_argument("--data-dir", default=None)

    ask = subparsers.add_parser("ask", help="Hỏi chatbot")
    ask.add_argument("question")
    ask.add_argument("--debug", action="store_true")
    ask.add_argument("--data-dir", default=None)

    validate = subparsers.add_parser(
        "validate", help="Kiểm tra tệp nguồn hợp nhất"
    )
    validate.add_argument("--source", default=None)
    validate.add_argument("--json", action="store_true", dest="as_json")

    migrate = subparsers.add_parser(
        "migrate", help="Chuyển dữ liệu cũ sang tệp nguồn hợp nhất"
    )
    migrate.add_argument("--to", default=None)
    migrate.add_argument("--from-data", default=DEFAULT_DATA, dest="from_data")
    migrate.add_argument("--qa", default=DEFAULT_QA)
    migrate.add_argument("--kb", default=DEFAULT_KB)
    migrate.add_argument("--force", action="store_true")

    return parser


def _print_result(result):
    if result.status == "success":
        print(result.message)
        return 0
    print(result.message, file=sys.stderr)
    return 1


def _run_ask(question, debug, data_dir):
    os.environ["CHATBOT_DATA_DIR"] = data_dir
    import chatbox

    try:
        answer, diagnostic = chatbox.ask_ai_detailed(question)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(answer)
    if not debug:
        return 0

    print(f"original_question: {diagnostic.original_question}")
    print(f"normalized_question: {diagnostic.normalized_question}")
    print(f"rewritten_question: {diagnostic.rewritten_question or '-'}")
    print(f"sources: {', '.join(diagnostic.source_names) or '-'}")
    for piece in diagnostic.pieces:
        print(
            "piece: "
            f"source={piece['source_name']} "
            f"chunk={piece['chunk_index']} "
            f"score={piece['score']} "
            f"excerpt={piece['excerpt']}"
        )
    print(f"passed_threshold: {str(diagnostic.passed_threshold).lower()}")
    print(f"outcome: {diagnostic.outcome}")
    return 0


def _issue_line(issue):
    parts = [f"[{issue.severity}] {issue.code}"]
    if issue.line is not None:
        parts.append(f"dòng {issue.line}")
    if issue.record_id:
        parts.append(f"id={issue.record_id}")
    parts.append(issue.message)
    return " ".join(parts)


def _run_validate(source, as_json):
    from source_format import validate_source

    try:
        result = validate_source(source)
    except Exception as exc:
        print(f"Không kiểm tra được tệp {source}: {exc}", file=sys.stderr)
        return 1

    if as_json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        counts = result.counts()
        print(f"Tệp: {result.path}")
        print(
            f"Bản ghi: {counts['records']} "
            f"(qa: {counts['qa']}, doc: {counts['doc']})"
        )
        for issue in result.errors:
            print(_issue_line(issue))
        for issue in result.warnings:
            print(_issue_line(issue))
        if result.valid:
            print("Tệp hợp lệ.")
        else:
            print(f"Tệp không hợp lệ: {len(result.errors)} lỗi.")

    return 0 if result.valid else 2


def _slugify(value):
    normalized = unicodedata.normalize("NFD", str(value))
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    slug = slug or "record"
    return slug[:64]


def _unique_id(candidate, used):
    base = candidate[:64].strip("-") or "record"
    if base[0] not in "abcdefghijklmnopqrstuvwxyz0123456789":
        base = "record-" + base
        base = base[:64]
    value = base
    index = 2
    while value in used:
        suffix = f"-{index}"
        value = base[: 64 - len(suffix)] + suffix
        index += 1
    used.add(value)
    return value


def _load_kb_records(path, used_ids, seen_questions):
    from source_format import SourceRecord

    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as handle:
        raw = json.load(handle)
    if not isinstance(raw, list):
        raise ValueError(f"{path} phải là một JSON array")
    records = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            print(f"Bỏ qua mục {index} trong {path}: không phải object", file=sys.stderr)
            continue
        topic = item.get("topic")
        questions = item.get("questions")
        if not isinstance(topic, str) or not topic.strip():
            print(f"Bỏ qua mục {index} trong {path}: thiếu topic", file=sys.stderr)
            continue
        if not isinstance(questions, list) or not questions:
            print(f"Bỏ qua mục {index} trong {path}: thiếu questions", file=sys.stderr)
            continue
        clean_questions = [
            str(question).strip()
            for question in questions
            if isinstance(question, str) and question.strip()
        ]
        if not clean_questions:
            print(f"Bỏ qua mục {index} trong {path}: questions rỗng", file=sys.stderr)
            continue
        answer = item.get("answer")
        bullets = item.get("answer_bullets")
        clean_bullets = [
            str(bullet).strip()
            for bullet in bullets
            if isinstance(bullet, str) and bullet.strip()
        ] if isinstance(bullets, list) else []
        if (not isinstance(answer, str) or not answer.strip()) and not clean_bullets:
            print(
                f"Bỏ qua mục {index} trong {path}: thiếu answer/bullets",
                file=sys.stderr,
            )
            continue
        item_id = item.get("id")
        candidate = (
            item_id
            if isinstance(item_id, str)
            and re.match(r"^[a-z0-9][a-z0-9_-]{0,63}$", item_id)
            else _slugify(item_id or topic)
        )
        record_id = _unique_id(candidate, used_ids)
        for question in clean_questions:
            from text_normalization import normalize_text

            normalized = normalize_text(question)
            if normalized:
                seen_questions.add(normalized)
        records.append(
            SourceRecord(
                kind="qa",
                id=record_id,
                topic=topic.strip()[:120],
                questions=clean_questions,
                answer=answer.strip() if isinstance(answer, str) and answer.strip() else None,
                bullets=clean_bullets,
            )
        )
    return records


def _load_qa_records(path, used_ids, seen_questions):
    from source_format import SourceRecord
    from text_normalization import normalize_text

    if not os.path.isfile(path):
        return []
    records = []
    with open(path, encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line or "|" not in line:
                continue
            question, answer = line.split("|", 1)
            question = question.strip()
            answer = answer.strip()
            if not question or not answer:
                continue
            normalized = normalize_text(question)
            if not normalized or normalized in seen_questions:
                continue
            seen_questions.add(normalized)
            record_id = _unique_id(_slugify(question), used_ids)
            records.append(
                SourceRecord(
                    kind="qa",
                    id=record_id,
                    topic="Câu hỏi thường gặp",
                    questions=[question[:200]],
                    answer=answer[:4000],
                )
            )
    return records


def _load_doc_records(data_dir, target_path, used_ids):
    from documents import is_supported_source, extract_segments
    from source_format import SourceRecord

    if not os.path.isdir(data_dir):
        return []
    records = []
    target = os.path.abspath(target_path)
    for filename in sorted(os.listdir(data_dir)):
        path = os.path.join(data_dir, filename)
        if not os.path.isfile(path) or not is_supported_source(filename):
            continue
        if os.path.abspath(path) == target or filename == TARGET_NAME:
            continue
        try:
            segments = extract_segments(path)
        except Exception as exc:
            print(f"Bỏ qua {path}: {exc}", file=sys.stderr)
            continue
        extension = os.path.splitext(filename)[1].lower()
        topic = os.path.splitext(filename)[0][:120] or filename
        if extension == ".pdf":
            for segment in segments:
                text = (segment.get("text") or "").strip()
                if not text:
                    continue
                page = segment.get("page")
                source = (
                    f"{filename}#page={page}" if page is not None else filename
                )
                record_id = _unique_id(
                    _slugify(f"{os.path.splitext(filename)[0]}-page-{page or 1}"),
                    used_ids,
                )
                records.append(
                    SourceRecord(
                        kind="doc",
                        id=record_id,
                        topic=(f"{topic} (trang {page})" if page is not None else topic)[:120],
                        content=text,
                        source=source[:300],
                    )
                )
            continue

        text = "\n\n".join(
            (segment.get("text") or "").strip()
            for segment in segments
            if (segment.get("text") or "").strip()
        )
        if not text:
            continue
        record_id = _unique_id(_slugify(topic), used_ids)
        records.append(
            SourceRecord(
                kind="doc",
                id=record_id,
                topic=topic,
                content=text,
                source=filename[:300],
            )
        )
    return records


def _write_atomic(path, text):
    from source_format import validate_source

    destination = os.path.abspath(path)
    directory = os.path.dirname(destination) or "."
    os.makedirs(directory, exist_ok=True)
    handle, temporary = tempfile.mkstemp(
        prefix=".tmp-", suffix=".part", dir=directory
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as target:
            target.write(text)
            target.flush()
            os.fsync(target.fileno())
        result = validate_source(temporary)
        if not result.valid:
            for issue in result.errors:
                print(_issue_line(issue), file=sys.stderr)
            return False
        os.replace(temporary, destination)
        temporary = None
    finally:
        if temporary and os.path.exists(temporary):
            os.remove(temporary)
    return True


def _run_migrate(args):
    from source_format import render_source

    destination = os.path.abspath(_source_path(args.to))
    if os.path.exists(destination) and not args.force:
        print(
            f"Tệp đích {destination} đã tồn tại; dùng --force để ghi đè.",
            file=sys.stderr,
        )
        return 1

    used_ids = set()
    seen_questions = set()
    try:
        kb_records = _load_kb_records(args.kb, used_ids, seen_questions)
        qa_records = _load_qa_records(args.qa, used_ids, seen_questions)
        doc_records = _load_doc_records(args.from_data, destination, used_ids)
    except Exception as exc:
        print(f"Không migrate được: {exc}", file=sys.stderr)
        return 1

    records = kb_records + qa_records + doc_records
    if not _write_atomic(destination, render_source(records)):
        print("Tệp sinh ra không hợp lệ; không ghi đè tệp đích.", file=sys.stderr)
        return 1

    qa_count = sum(1 for record in records if record.kind == "qa")
    doc_count = sum(1 for record in records if record.kind == "doc")
    print(f"Đã ghi {len(records)} bản ghi vào {destination}")
    print(f"  qa: {qa_count}")
    print(f"  doc: {doc_count}")
    return 0


def main(argv=None):
    parser = _build_parser()
    args = parser.parse_args(argv)
    data_dir = _data_dir(args)

    if args.command == "validate":
        return _run_validate(_source_path(args.source), args.as_json)

    if args.command == "migrate":
        return _run_migrate(args)

    if args.command == "ask":
        return _run_ask(args.question, args.debug, data_dir)

    from documents import add_source, delete_source, list_sources, replace_source

    if args.command == "add":
        return _print_result(
            add_source(
                args.input_path, source_name=args.name, data_dir=data_dir
            )
        )

    if args.command == "replace":
        return _print_result(
            replace_source(
                args.input_path, args.name, data_dir=data_dir
            )
        )

    if args.command == "delete":
        return _print_result(delete_source(args.source_name, data_dir=data_dir))

    try:
        sources = list_sources(data_dir)
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    for source in sources:
        print(f"{source.source_name}\t{source.format}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
