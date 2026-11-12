import json

from backend.doc_index import DocIndex
from backend.scripts import manage_docs
from backend.tests.helpers import write_pdf
from backend.tests.test_doc_index import TopicEmbedder


def _install_fake_index(monkeypatch):
    def factory(index_dir=None):
        return DocIndex(index_dir=index_dir, embedder=TopicEmbedder())

    monkeypatch.setattr(manage_docs, "_index_class", lambda: factory)


def test_cli_ingest_list_remove_json(tmp_path, monkeypatch, capsys):
    _install_fake_index(monkeypatch)
    data = tmp_path / "data"
    data.mkdir()
    (data / "cv.txt").write_text("Kinh nghiệm Python ba năm.", encoding="utf-8")
    index_dir = tmp_path / "index"

    code = manage_docs.main(
        [
            "ingest",
            str(data),
            "--data-dir",
            str(data),
            "--index-dir",
            str(index_dir),
            "--json",
        ]
    )
    assert code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["added"][0]["file"] == "cv.txt"
    assert set(report) >= {"added", "updated", "skipped", "failed", "stats"}
    assert (index_dir / "manifest.json").is_file()

    (data / "new.txt").write_text("Chưa nạp.", encoding="utf-8")
    code = manage_docs.main(
        ["list", "--data-dir", str(data), "--index-dir", str(index_dir), "--json"]
    )
    assert code == 0
    rows = json.loads(capsys.readouterr().out)
    statuses = {row["file"]: row["status"] for row in rows}
    assert statuses["cv.txt"] == "indexed"
    assert statuses["new.txt"] == "not-indexed"
    assert next(row for row in rows if row["file"] == "cv.txt")["chunks"] >= 1

    code = manage_docs.main(
        ["remove", "cv.txt", "--index-dir", str(index_dir), "--json"]
    )
    assert code == 0
    removed = json.loads(capsys.readouterr().out)
    assert removed["removed_chunks"] >= 1
    assert (data / "cv.txt").is_file()


def test_cli_recursive_full_and_failures(tmp_path, monkeypatch, capsys):
    _install_fake_index(monkeypatch)
    nested = tmp_path / "data" / "sub"
    nested.mkdir(parents=True)
    (nested / "note.md").write_text("# Học bổng\n\nMục tiêu học bổng.", encoding="utf-8")
    write_pdf(tmp_path / "data" / "scan.pdf", [""])
    index_dir = tmp_path / "index"

    without_recursive = manage_docs.main(
        ["ingest", str(tmp_path / "data"), "--index-dir", str(index_dir), "--json"]
    )
    assert without_recursive in (0, 2)
    capsys.readouterr()

    code = manage_docs.main(
        [
            "ingest",
            str(tmp_path / "data"),
            "--index-dir",
            str(index_dir),
            "--recursive",
            "--json",
        ]
    )
    assert code == 2
    report = json.loads(capsys.readouterr().out)
    assert any(entry["file"] == "note.md" for entry in report["added"])
    assert any(entry["file"] == "scan.pdf" for entry in report["failed"])
    assert report["failed"][0]["error"].startswith("E_NO_TEXT")

    code = manage_docs.main(
        ["list", "--data-dir", str(tmp_path / "data"), "--index-dir", str(index_dir), "--json"]
    )
    assert code == 0
    listed = {row["file"]: row["status"] for row in json.loads(capsys.readouterr().out)}
    assert listed["scan.pdf"] == "failed"

    code = manage_docs.main(
        [
            "ingest",
            str(nested / "note.md"),
            "--index-dir",
            str(index_dir),
            "--full",
            "--json",
        ]
    )
    assert code == 0
    full_report = json.loads(capsys.readouterr().out)
    assert full_report["updated"][0]["file"] == "note.md"
    assert full_report["stats"]["embeddings_computed"] >= 1


def test_cli_missing_path_and_remove_missing(tmp_path, monkeypatch, capsys):
    _install_fake_index(monkeypatch)
    index_dir = tmp_path / "index"

    assert (
        manage_docs.main(
            ["ingest", str(tmp_path / "missing"), "--index-dir", str(index_dir)]
        )
        == 1
    )
    assert "không tồn tại" in capsys.readouterr().err.lower()

    assert (
        manage_docs.main(
            ["remove", "missing.txt", "--index-dir", str(index_dir), "--json"]
        )
        == 1
    )
    assert "không có" in capsys.readouterr().err.lower()
