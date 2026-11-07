#!/usr/bin/env python3
"""Operator CLI for the local RAG knowledge base."""

import argparse
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def _data_dir(args):
    default = os.path.join(REPO_ROOT, "data")
    return args.data_dir or os.environ.get("CHATBOT_DATA_DIR", default)


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


def main(argv=None):
    parser = _build_parser()
    args = parser.parse_args(argv)
    data_dir = _data_dir(args)

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
