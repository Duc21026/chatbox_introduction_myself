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
                    "answer": "8.30",
                    "answer_bullets": ["GPA 8.30"],
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
