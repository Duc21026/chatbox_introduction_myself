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

    add = subparsers.add_parser(
        "add", help="Thêm dữ liệu: add file|fact|qa|course (hoặc add <tệp> kiểu cũ)"
    )
    add.add_argument("input_path", nargs="?")
    add_sub = add.add_subparsers(dest="add_command")

    add_file = add_sub.add_parser("file", help="Thêm một nguồn tài liệu (cũ)")
    add_file.add_argument("input_path")
    add_file.add_argument("--name", default=None)
    add_file.add_argument("--data-dir", default=None)

    add_fact = add_sub.add_parser("fact", help="Thêm/cập nhật một giá trị fact")
    add_fact.add_argument("--id", required=True)
    add_fact.add_argument("--label", required=True)
    add_fact.add_argument("--value", required=True)
    add_fact.add_argument("--snapshot", default=None)
    add_fact.add_argument("--source", default=None)
    add_fact.add_argument("--source-path", default=None)

    add_qa = add_sub.add_parser("qa", help="Thêm một bản ghi hỏi-đáp")
    add_qa.add_argument("--topic", required=True)
    add_qa.add_argument("--q", action="append", default=[], required=True)
    add_qa.add_argument("--a", default=None)
    add_qa.add_argument("--bullets", action="append", default=None)
    add_qa.add_argument("--source-path", default=None)

    add_course = add_sub.add_parser("course", help="Thêm một môn học vào courses.csv")
    add_course.add_argument("--code", required=True)
    add_course.add_argument("--name", required=True)
    add_course.add_argument("--credits", type=int, required=True)
    add_course.add_argument("--score10", type=float, required=True)
    add_course.add_argument("--score4", type=float, default=None)
    add_course.add_argument("--letter", default=None)
    add_course.add_argument("--counts-major", default="yes")
    add_course.add_argument("--aliases", default=None)
    add_course.add_argument("--courses-path", default=None)

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
    list_command.add_argument("--index-dir", default=None)
    list_command.add_argument("--json", action="store_true", dest="as_json")

    ingest = subparsers.add_parser(
        "ingest", help="Nạp tài liệu vào chỉ mục phái sinh"
    )
    ingest.add_argument("path", nargs="?", default=None)
    ingest.add_argument("--data-dir", default=None)
    ingest.add_argument("--index-dir", default=None)
    ingest.add_argument("--recursive", action="store_true")
    ingest.add_argument("--full", action="store_true")
    ingest.add_argument(
        "--inbox",
        action="store_true",
        help="Nạp từ thư mục inbox (từ chối tệp có placeholder/rác)",
    )
    ingest.add_argument("--json", action="store_true", dest="as_json")

    remove = subparsers.add_parser(
        "remove", help="Xoá một tệp khỏi chỉ mục (giữ tệp nguồn)"
    )
    remove.add_argument("source_name")
    remove.add_argument("--index-dir", default=None)
    remove.add_argument("--json", action="store_true", dest="as_json")

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


def _index_class():
    try:
        from backend.doc_index import DocIndex
    except ImportError:
        from doc_index import DocIndex
    return DocIndex


def _doc_index(args):
    index_dir = getattr(args, "index_dir", None)
    return _index_class()(index_dir=index_dir)


def _run_ask(question, debug, data_dir):
    os.environ["CHATBOT_DATA_DIR"] = data_dir
    try:
        from backend import kb_engine
        from backend.assistant import Assistant
        from backend.chatbox import retrieve_rag_documents, retrieve_source_qa
    except ImportError:
        import kb_engine
        from assistant import Assistant
        from chatbox import retrieve_rag_documents, retrieve_source_qa

    try:
        kb_engine.warm_up_kb()
        response = Assistant(
            doc_searcher=_doc_index(args=None),
            rag_searcher=retrieve_rag_documents,
            qa_searcher=retrieve_source_qa,
        ).handle(question)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(response.get("response", ""))
    if not debug:
        return 0

    print(f"type: {response.get('type')}")
    print(f"session_id: {response.get('session_id')}")
    print(f"score: {response.get('score')}")
    print(f"source: {response.get('source') or '-'}")
    print(
        "suggestions: "
        + json.dumps(response.get("suggestions") or [], ensure_ascii=False)
    )
    print("topics: " + json.dumps(response.get("topics") or [], ensure_ascii=False))
    print("sources: " + json.dumps(response.get("sources") or [], ensure_ascii=False))
    return 0


def _run_ingest(args):
    index = _doc_index(args)
    path = args.path or _data_dir(args)

    inbox_flag = getattr(args, "inbox", False)
    if inbox_flag or _is_inbox_target(args.path):
        return _run_ingest_inbox(args, index)

    try:
        report = index.ingest(path, recursive=args.recursive, full=args.full)
    except FileNotFoundError:
        print(f"Đường dẫn không tồn tại: {path}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Không nạp được tài liệu: {exc}", file=sys.stderr)
        return 1

    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_ingest_report(path, report)
    return 2 if report["failed"] else 0


def _print_ingest_report(path, report):
    print(f"Nạp tài liệu từ {os.path.abspath(path)}")
    for entry in report["added"]:
        print(f"  thêm:     {entry['file']} ({entry['type']}, {entry['chunks']} đoạn)")
    for entry in report["updated"]:
        print(
            f"  cập nhật: {entry['file']} ({entry['type']}, "
            f"{entry['chunks']} đoạn, {entry.get('chunks_added', 0)} đoạn mới, "
            f"{entry.get('chunks_reused', 0)} đoạn tái dùng)"
        )
    for entry in report["skipped"]:
        print(f"  bỏ qua:   {entry['file']}")
    for entry in report["failed"]:
        print(f"  lỗi:      {entry['file']} — {entry['error']}")
    stats = report["stats"]
    print(
        f"\nTổng: {stats['files_total']} tệp | thêm {len(report['added'])} | "
        f"cập nhật {len(report['updated'])} | bỏ qua {len(report['skipped'])} | "
        f"lỗi {len(report['failed'])}"
    )
    print(
        f"Đoạn: +{stats['chunks_added']} mới, {stats['chunks_reused']} tái dùng, "
        f"{stats['chunks_removed']} xoá | Vector đã tính: "
        f"{stats['embeddings_computed']}"
    )


def _empty_ingest_report():
    started = "now"
    return {
        "started_at": started,
        "finished_at": started,
        "added": [],
        "updated": [],
        "skipped": [],
        "failed": [],
        "stats": {
            "files_total": 0,
            "chunks_added": 0,
            "chunks_reused": 0,
            "chunks_removed": 0,
            "embeddings_computed": 0,
        },
    }


def _inbox_noise_check(path):
    """Return (ok, error).  Từ chối tệp còn placeholder hoặc chuỗi rác."""

    import re as re_module

    from doc_loaders import extract_blocks
    from documents import is_supported_source

    if not is_supported_source(os.path.basename(path)):
        return False, "[E_UNSUPPORTED] Định dạng không được hỗ trợ."
    try:
        blocks = extract_blocks(path)
    except Exception as exc:
        return False, f"[E_NOISE] Không trích xuất được: {exc}"
    text = "\n".join(block.text for block in blocks)
    if re_module.search(r"\[[^\]\n]{1,80}\]", text):
        return False, "[E_PLACEHOLDER] Tệp còn placeholder [...] chưa điền."
    lower = text.lower()
    for noise in ("nan", "unnamed", "about:blank"):
        if noise in lower:
            return False, f"[E_NOISE] Tệp còn chuỗi rác '{noise}'."
    for stale in ("8.30", "8.3 ", "62 tín chỉ", "62 tc", "17 môn", "3.7/4.0"):
        if stale in lower or stale in text:
            return False, f"[E_STALE_VALUE] Tệp còn giá trị cũ '{stale}'."
    return True, ""


def _inbox_dir():
    return os.environ.get(
        "CHATBOT_INBOX_DIR",
        os.path.join(BACKEND_DIR, "data", "inbox"),
    )


def _is_inbox_target(path):
    """True when ``ingest <path>`` points at the inbox directory or a file."""

    if not path:
        return False
    normal = str(path).replace("\\", "/")
    if normal.rstrip("/") == "inbox" or normal.startswith("inbox/"):
        return True
    inbox_dir = os.path.abspath(_inbox_dir())
    candidate = os.path.abspath(path)
    return candidate == inbox_dir or candidate.startswith(inbox_dir + os.sep)


def _resolve_inbox_path(path):
    """Map ``inbox/ten.pdf`` to the configured inbox directory."""

    if os.path.exists(path):
        return path
    inbox_dir = _inbox_dir()
    candidates = [
        os.path.join(inbox_dir, os.path.basename(path)),
        os.path.join(os.path.dirname(inbox_dir), path),
        os.path.join(inbox_dir, path),
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return path


def _run_ingest_inbox(args, index):
    from documents import is_supported_source

    raw_path = args.path
    if raw_path and os.path.isdir(raw_path):
        inbox_dir = raw_path
        target = None
    elif raw_path and os.path.isfile(raw_path):
        target = raw_path
        inbox_dir = os.path.dirname(raw_path)
    else:
        inbox_dir = _inbox_dir()
        target = _resolve_inbox_path(raw_path) if raw_path else None

    if not os.path.isdir(inbox_dir):
        print(f"Không tìm thấy thư mục inbox: {inbox_dir}", file=sys.stderr)
        return 1

    if target and os.path.isfile(target):
        files = [target]
    else:
        files = sorted(
            os.path.join(inbox_dir, name)
            for name in os.listdir(inbox_dir)
            if os.path.isfile(os.path.join(inbox_dir, name))
            and is_supported_source(name)
        )
    if not files:
        print(f"Thư mục inbox {inbox_dir} không có tệp nào.")
        return 0

    merged = _empty_ingest_report()
    for path in files:
        ok, error = _inbox_noise_check(path)
        if not ok:
            merged["failed"].append(
                {"file": os.path.basename(path), "error": error}
            )
            continue
        try:
            report = index.ingest(path)
        except Exception as exc:
            merged["failed"].append(
                {"file": os.path.basename(path), "error": str(exc)}
            )
            continue
        for key in ("added", "updated", "skipped", "failed"):
            merged[key].extend(report.get(key) or [])
        for key in (
            "files_total",
            "chunks_added",
            "chunks_reused",
            "chunks_removed",
            "embeddings_computed",
        ):
            stats = report.get("stats") or {}
            merged["stats"][key] += int(stats.get(key) or 0)

    if args.as_json:
        print(json.dumps(merged, ensure_ascii=False, indent=2))
    else:
        _print_ingest_report(inbox_dir, merged)
    return 2 if merged["failed"] else 0


def _run_list_docs(args):
    try:
        index = _doc_index(args)
        rows = index.list_files(_data_dir(args))
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.as_json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        for row in rows:
            print(
                f"{row['file']}\t{row.get('type') or ''}\t"
                f"{row.get('status')}\t{row.get('chunks', 0)}"
            )
    return 0


def _run_remove(args):
    try:
        index = _doc_index(args)
        count = index.remove(args.source_name)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if count is None:
        print(f"Không có {args.source_name} trong chỉ mục.", file=sys.stderr)
        return 1
    if args.as_json:
        print(
            json.dumps(
                {"file": args.source_name, "removed_chunks": count},
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(f"Đã xoá {args.source_name} khỏi chỉ mục ({count} đoạn).")
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

    _append_open_data_issues(result)

    if as_json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        counts = result.counts()
        print(f"Tệp: {result.path}")
        print(
            f"Bản ghi: {counts['records']} "
            f"(qa: {counts['qa']}, doc: {counts['doc']}, fact: {counts['fact']})"
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


def _append_open_data_issues(result):
    """Validate courses.csv + aliases.txt and merge issues into the result.

    Course rows are reported with ``line`` = row number in the CSV.
    """

    from source_format import ValidationIssue

    try:
        import courses as courses_mod
    except ImportError:
        from backend import courses as courses_mod
    try:
        import aliases as aliases_mod
    except ImportError:
        from backend import aliases as aliases_mod

    try:
        course_list, course_issues = courses_mod.load_courses(
            courses_mod.courses_path()
        )
    except Exception as exc:
        result.errors.append(
            ValidationIssue(
                "error", "E_FILE_MISSING", f"courses.csv: {exc}", None, None
            )
        )
        course_list = []
    else:
        for issue in course_issues:
            result.errors.append(
                ValidationIssue(
                    issue.severity, issue.code, f"courses.csv: {issue.message}",
                    issue.row, None,
                )
            )

    if course_list:
        facts_map = {}
        if result.source_file:
            facts_map = {
                record.id: record
                for record in result.source_file.records
                if record.kind == "fact" and record.status == "active"
            }
        aggregated = courses_mod.aggregates(course_list)
        for issue in courses_mod.check_against_facts(aggregated, facts_map):
            result.warnings.append(
                ValidationIssue(
                    issue.severity, issue.code, f"courses.csv: {issue.message}",
                    issue.row, None,
                )
            )

    try:
        aliases_mod.load_aliases(aliases_mod.aliases_path())
    except Exception as exc:
        result.errors.append(
            ValidationIssue(
                "error", "E_BAD_ALIAS", f"aliases.txt: {exc}", None, None
            )
        )


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
    """Ghi nguyên tử: tệp tạm cùng thư mục → validate → ``os.replace``."""

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
        os.replace(temporary, destination)
        temporary = None
    finally:
        if temporary and os.path.exists(temporary):
            os.remove(temporary)
    return True


def _parse_source_or_fail(source_path):
    from source_format import parse_source

    source, issues = parse_source(source_path)
    errors = [issue for issue in issues if issue.severity == "error"]
    if source is None or errors:
        for issue in errors:
            print(_issue_line(issue), file=sys.stderr)
        print("Tệp nguồn hiện tại không hợp lệ; sửa trước khi thêm.", file=sys.stderr)
        return None
    return source


def _run_add_fact(args):
    from source_format import SourceRecord, render_source, validate_source

    source_path = _source_path(args.source_path)
    source = _parse_source_or_fail(source_path)
    if source is None:
        return 1

    records = list(source.records)
    for record in records:
        if record.id != args.id:
            continue
        if record.kind != "fact":
            print(
                f"id '{args.id}' đang là bản ghi {record.kind}; không thể "
                "chuyển thành fact.",
                file=sys.stderr,
            )
            return 1
        record.label = args.label.strip()[:120]
        record.value = args.value.strip()[:4000]
        record.snapshot = (args.snapshot or "").strip() or record.snapshot
        record.source = (args.source or "").strip() or record.source
        break
    else:
        records.append(
            SourceRecord(
                kind="fact",
                id=args.id.strip(),
                topic="",
                label=args.label.strip()[:120],
                value=args.value.strip()[:4000],
                snapshot=(args.snapshot or "").strip() or None,
                source=(args.source or "").strip() or None,
            )
        )

    text = render_source(records)
    temporary = source_path + ".part"
    with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    result = validate_source(temporary)
    if not result.valid:
        for issue in result.errors:
            print(_issue_line(issue), file=sys.stderr)
        os.remove(temporary)
        print("Dữ liệu mới không hợp lệ; không ghi gì.", file=sys.stderr)
        return 1
    os.replace(temporary, source_path)
    print(f"Đã ghi fact '{args.id}' = {args.value} vào {source_path}")
    return 0


def _run_add_qa(args):
    from source_format import SourceRecord, render_source, validate_source

    questions = [question.strip() for question in args.q if question.strip()]
    if not 1 <= len(questions) <= 5:
        print("Cần 1–5 câu hỏi (--q).", file=sys.stderr)
        return 1
    for question in questions:
        if len(question) > 200:
            print(f"Câu hỏi quá dài (tối đa 200 ký tự): {question[:40]}…", file=sys.stderr)
            return 1
    if args.a and args.bullets:
        print("Không dùng đồng thời --a và --bullets.", file=sys.stderr)
        return 1
    answer = (args.a or "").strip() or None
    bullets = [bullet.strip() for bullet in (args.bullets or []) if bullet.strip()] or None
    if not answer and not bullets:
        print("Cần --a hoặc --bullets.", file=sys.stderr)
        return 1

    source_path = _source_path(args.source_path)
    source = _parse_source_or_fail(source_path)
    if source is None:
        return 1

    used_ids = {record.id for record in source.records}
    record_id = _unique_id(_slugify(args.topic), used_ids)
    records = list(source.records)
    records.append(
        SourceRecord(
            kind="qa",
            id=record_id,
            topic=args.topic.strip()[:120],
            questions=questions,
            answer=answer,
            bullets=bullets or [],
        )
    )

    text = render_source(records)
    temporary = source_path + ".part"
    with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    result = validate_source(temporary)
    if not result.valid:
        for issue in result.errors:
            print(_issue_line(issue), file=sys.stderr)
        os.remove(temporary)
        print("Dữ liệu mới không hợp lệ; không ghi gì.", file=sys.stderr)
        return 1
    os.replace(temporary, source_path)
    print(f"Đã thêm hỏi-đáp '{record_id}' (chủ đề: {args.topic}) vào {source_path}")
    return 0


def _run_add_course(args):
    import csv as csv_module

    try:
        import courses as courses_mod
    except ImportError:
        from backend import courses as courses_mod

    path = args.courses_path or courses_mod.courses_path()
    loaded, issues = courses_mod.load_courses(path)
    if any(issue.severity == "error" for issue in issues):
        for issue in issues:
            print(f"[{issue.severity}] {issue.code}: {issue.message}", file=sys.stderr)
        print("Danh sách môn hiện tại có lỗi; sửa trước khi thêm.", file=sys.stderr)
        return 1

    for course in loaded:
        if course.code == args.code:
            print(f"Mã môn '{args.code}' đã tồn tại.", file=sys.stderr)
            return 1
        if course.name.casefold() == args.name.casefold():
            print(f"Tên môn '{args.name}' đã tồn tại.", file=sys.stderr)
            return 1

    row = [
        args.code,
        args.name,
        str(args.credits),
        f"{args.score10:.1f}",
        f"{args.score4:.4g}" if args.score4 is not None else "",
        args.letter or "",
        args.counts_major,
        args.aliases or "",
    ]
    directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(directory, exist_ok=True)
    handle, temporary = tempfile.mkstemp(
        prefix=".tmp-", suffix=".part", dir=directory
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as target:
            csv_module.writer(target).writerow(list(courses_mod.COLUMNS))
            for course in loaded:
                csv_module.writer(target).writerow(
                    [
                        course.code,
                        course.name,
                        str(course.credits),
                        f"{course.score10:.4g}",
                        f"{course.score4:.4g}" if course.score4 is not None else "",
                        course.letter or "",
                        "yes" if course.counts_major else "no",
                        "|".join(course.aliases),
                    ]
                )
            csv_module.writer(target).writerow(row)
            target.flush()
            os.fsync(target.fileno())
        check, check_issues = courses_mod.load_courses(temporary)
        if any(issue.severity == "error" for issue in check_issues):
            for issue in check_issues:
                print(f"[{issue.severity}] {issue.code}: {issue.message}", file=sys.stderr)
            print("Môn mới không hợp lệ; không ghi gì.", file=sys.stderr)
            return 1
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary and os.path.exists(temporary):
            os.remove(temporary)

    aggregated = courses_mod.aggregates(check)
    facts_map = {}
    try:
        source = _parse_source_or_fail(_source_path(None))
        if source is not None:
            facts_map = {
                record.id: record
                for record in source.records
                if record.kind == "fact" and record.status == "active"
            }
    except Exception:
        pass
    for issue in courses_mod.check_against_facts(aggregated, facts_map):
        print(f"[{issue.severity}] {issue.code}: {issue.message}")

    print(f"Đã thêm môn '{args.code} – {args.name}' vào {path}")
    return 0


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
    from source_format import render_source, validate_source

    text = render_source(records)
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
            print("Tệp sinh ra không hợp lệ; không ghi đè tệp đích.", file=sys.stderr)
            return 1
        os.replace(temporary, destination)
        temporary = None
    finally:
        if temporary and os.path.exists(temporary):
            os.remove(temporary)

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

    if args.command == "ingest":
        return _run_ingest(args)

    if args.command == "remove":
        return _run_remove(args)

    if args.command == "list":
        return _run_list_docs(args)

    from documents import add_source, delete_source, list_sources, replace_source

    if args.command == "add":
        sub = getattr(args, "add_command", None)
        if sub == "fact":
            return _run_add_fact(args)
        if sub == "qa":
            return _run_add_qa(args)
        if sub == "course":
            return _run_add_course(args)
        # legacy `add <tệp>` (sub is None hoặc "file")
        input_path = getattr(args, "input_path", None)
        if not input_path:
            print("Dùng: add fact|qa|course ... hoặc add <tệp>", file=sys.stderr)
            return 1
        return _print_result(
            add_source(input_path, source_name=args.name, data_dir=data_dir)
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
