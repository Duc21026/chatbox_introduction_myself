import hashlib
import json
from pathlib import Path

from backend.scripts import manage_docs


HEADER = "CHATBOT-SOURCE v1\n"


def _digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def test_validate_valid_file_exit_zero(tmp_path, capsys):
    source = tmp_path / "chatbot.txt"
    source.write_text(
        HEADER
        + "=== RECORD ===\n"
        "kind: doc\n"
        "id: intro\n"
        "topic: Giới thiệu\n"
        "content:\nXin chào.\n"
        "=== END ===\n",
        encoding="utf-8",
    )

    code = manage_docs.main(["validate", "--source", str(source)])
    output = capsys.readouterr().out

    assert code == 0
    assert "Tệp hợp lệ." in output
    assert "doc: 1" in output


def test_validate_invalid_file_exit_two_and_json(tmp_path, capsys):
    source = tmp_path / "chatbot.txt"
    source.write_text(
        HEADER
        + "\n=== RECORD ===\n"
        "kind: qa\n"
        "id: broken\n"
        "topic: Test\n"
        "questions:\n- Câu hỏi?\n"
        "=== END ===\n",
        encoding="utf-8",
    )

    code = manage_docs.main(
        ["validate", "--source", str(source), "--json"]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 2
    assert payload["valid"] is False
    assert set(payload) == {"path", "valid", "counts", "errors", "warnings"}
    assert any(issue["code"] == "E_ANSWER" for issue in payload["errors"])
    assert all(issue["line"] is not None for issue in payload["errors"])


def test_migrate_combines_sources_without_touching_originals(tmp_path, capsys):
    kb = tmp_path / "kb.json"
    kb.write_text(
        json.dumps(
            [
                {
                    "id": "gpa",
                    "topic": "Học tập",
                    "questions": ["GPA của bạn?"],
                    "answer": "8.51",
                    "answer_bullets": ["GPA 8.51"],
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    qa = tmp_path / "qa.txt"
    qa.write_text("GPA của bạn?|khác\nEmail?|a@b\n", encoding="utf-8")
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "intro.txt").write_text("Nội dung giới thiệu.", encoding="utf-8")
    target = tmp_path / "out" / "chatbot.txt"

    originals = {path: _digest(path) for path in (kb, qa, data_dir / "intro.txt")}
    code = manage_docs.main(
        [
            "migrate",
            "--to",
            str(target),
            "--kb",
            str(kb),
            "--qa",
            str(qa),
            "--from-data",
            str(data_dir),
        ]
    )
    output = capsys.readouterr().out

    assert code == 0
    assert target.is_file()
    assert "qa: 2" in output
    assert "doc: 1" in output
    assert {path: _digest(path) for path in originals} == originals

    from backend import source_format

    result = source_format.validate_source(target)
    assert result.valid, result.errors
    text = target.read_text(encoding="utf-8")
    assert "GPA của bạn?" in text
    assert "khác" not in text
    assert "Email?" in text

    again = manage_docs.main(
        [
            "migrate",
            "--to",
            str(target),
            "--kb",
            str(kb),
            "--qa",
            str(qa),
            "--from-data",
            str(data_dir),
        ]
    )
    assert again == 1
    assert "đã tồn tại" in capsys.readouterr().err

    forced = manage_docs.main(
        [
            "migrate",
            "--to",
            str(target),
            "--kb",
            str(kb),
            "--qa",
            str(qa),
            "--from-data",
            str(data_dir),
            "--force",
        ]
    )
    assert forced == 0


def test_add_fact_creates_and_updates(tmp_path, capsys):
    source = tmp_path / "chatbot.txt"
    source.write_text(
        HEADER
        + "=== RECORD ===\n"
        "kind: fact\n"
        "id: graduation\n"
        "label: Tốt nghiệp dự kiến\n"
        "value: tháng 8/2028\n"
        "=== END ===\n",
        encoding="utf-8",
    )

    code = manage_docs.main(
        ["add", "fact", "--id", "graduation", "--label", "Tốt nghiệp dự kiến",
         "--value", "tháng 10/2028", "--source-path", str(source)]
    )
    assert code == 0

    text = source.read_text(encoding="utf-8")
    assert "tháng 10/2028" in text
    assert text.count("id: graduation") == 1


def test_add_fact_conflicting_with_qa_record_fails(tmp_path, capsys):
    source = tmp_path / "chatbot.txt"
    source.write_text(
        HEADER
        + "=== RECORD ===\n"
        "kind: qa\n"
        "id: gpa\n"
        "topic: Học tập\n"
        "questions:\n- GPA của bạn?\n"
        "answer:\n8.51\n"
        "=== END ===\n",
        encoding="utf-8",
    )

    code = manage_docs.main(
        ["add", "fact", "--id", "gpa", "--label", "GPA", "--value", "8.51",
         "--source-path", str(source)]
    )
    assert code == 1
    assert "kind: fact" not in source.read_text(encoding="utf-8")


def test_add_qa_new_topic(tmp_path, capsys):
    source = tmp_path / "chatbot.txt"
    source.write_text(
        HEADER
        + "=== RECORD ===\n"
        "kind: doc\n"
        "id: intro\n"
        "topic: Giới thiệu\n"
        "content:\nXin chào.\n"
        "=== END ===\n",
        encoding="utf-8",
    )

    code = manage_docs.main(
        ["add", "qa", "--topic", "Sở thích",
         "--q", "Bạn thích làm gì khi rảnh?",
         "--a", "Mình thích đọc tài liệu về AI.",
         "--source-path", str(source)]
    )
    assert code == 0
    text = source.read_text(encoding="utf-8")
    assert "Sở thích" in text

    from backend import source_format

    result = source_format.validate_source(str(source))
    assert result.valid, result.errors


def test_add_qa_rejects_both_answer_and_bullets(tmp_path, capsys):
    source = tmp_path / "chatbot.txt"
    source.write_text(
        HEADER
        + "=== RECORD ===\n"
        "kind: doc\n"
        "id: intro\n"
        "topic: Giới thiệu\n"
        "content:\nXin chào.\n"
        "=== END ===\n",
        encoding="utf-8",
    )

    code = manage_docs.main(
        ["add", "qa", "--topic", "T", "--q", "Hỏi?",
         "--a", "Trả lời.", "--bullets", "ý 1", "--source-path", str(source)]
    )
    assert code == 1


def test_add_course_appends_row_and_aggregates(tmp_path, capsys):
    courses_path = tmp_path / "courses.csv"
    courses_path.write_text(
        "code,name,credits,score10,score4,letter,counts_major,aliases\n"
        "CSC10001,Môn A,4,10,4,A+,yes,\n",
        encoding="utf-8",
    )

    code = manage_docs.main(
        ["add", "course", "--code", "CSC10002", "--name", "Môn B",
         "--credits", "2", "--score10", "8.0", "--counts-major", "no",
         "--courses-path", str(courses_path)]
    )
    assert code == 0
    text = courses_path.read_text(encoding="utf-8")
    assert "CSC10002,Môn B,2,8.0" in text


def test_add_course_duplicate_code_fails(tmp_path, capsys):
    courses_path = tmp_path / "courses.csv"
    courses_path.write_text(
        "code,name,credits,score10,score4,letter,counts_major,aliases\n"
        "CSC10001,Môn A,4,10,4,A+,yes,\n",
        encoding="utf-8",
    )

    code = manage_docs.main(
        ["add", "course", "--code", "CSC10001", "--name", "Môn khác",
         "--credits", "2", "--score10", "8.0", "--courses-path", str(courses_path)]
    )
    assert code == 1
    text = courses_path.read_text(encoding="utf-8")
    assert "Môn khác" not in text


def test_ingest_inbox_rejects_placeholder_file(tmp_path, capsys):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "cv.txt").write_text("Họ tên: [HỌ VÀ TÊN]\n", encoding="utf-8")
    (inbox / "ok.txt").write_text("Nội dung sạch.\n", encoding="utf-8")

    code = manage_docs.main(
        ["ingest", "--inbox", str(inbox), "--index-dir", str(tmp_path / "idx")]
    )
    out = capsys.readouterr().out

    assert code == 2
    assert "E_PLACEHOLDER" in out


def test_ingest_inbox_clean_file_added(tmp_path, capsys):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "ok.txt").write_text("Nội dung sạch về dự án.\n", encoding="utf-8")

    code = manage_docs.main(
        ["ingest", "--inbox", str(inbox), "--index-dir", str(tmp_path / "idx")]
    )
    out = capsys.readouterr().out

    assert code == 0
    assert "thêm:" in out and "ok.txt" in out


def test_validate_reports_stale_value(tmp_path, capsys):
    source = tmp_path / "chatbot.txt"
    source.write_text(
        HEADER
        + "=== RECORD ===\n"
        "kind: qa\n"
        "id: gpa\n"
        "topic: Học tập\n"
        "questions:\n- GPA của bạn?\n"
        "answer:\n8.30 với 62 tín chỉ\n"
        "=== END ===\n",
        encoding="utf-8",
    )

    code = manage_docs.main(["validate", "--source", str(source), "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 2
    assert any(issue["code"] == "E_STALE_VALUE" for issue in payload["errors"])
