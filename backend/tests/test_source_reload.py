import dataclasses
import os
from pathlib import Path

from backend import chatbox
from backend import source_format


def _source(answer):
    return (
        "CHATBOT-SOURCE v1\n\n"
        "=== RECORD ===\n"
        "kind: qa\n"
        "id: gpa\n"
        "topic: Học tập\n"
        "questions:\n- GPA của bạn?\n"
        f"answer:\n{answer}\n"
        "=== END ===\n"
    )


def _config(tmp_path, monkeypatch):
    config = dataclasses.replace(
        chatbox.config,
        source_path=str(Path(tmp_path) / "chatbot.txt"),
        legacy_sources=False,
        query_rewrite="off",
    )
    monkeypatch.setattr(chatbox, "config", config)
    monkeypatch.setattr(chatbox, "_source_cache", None)
    monkeypatch.setattr(chatbox, "_source_cache_key", None)
    monkeypatch.setattr(chatbox, "_qa_data", None)
    monkeypatch.setattr(chatbox, "_qa_data_signature", None)
    monkeypatch.setattr(chatbox, "_db", None)
    monkeypatch.setattr(chatbox, "_index_signature", None)
    return config


def test_signature_change_reloads_and_same_signature_reuses_cache(
    tmp_path, monkeypatch
):
    config = _config(tmp_path, monkeypatch)
    path = Path(config.source_path)
    path.write_text(_source("8.30"), encoding="utf-8")

    calls = []
    real_load = source_format.load_source

    def counting_load(*args, **kwargs):
        calls.append(args)
        return real_load(*args, **kwargs)

    monkeypatch.setattr(source_format, "load_source", counting_load)

    first = chatbox.get_source()
    second = chatbox.get_source()

    assert len(calls) == 1
    assert first is second
    assert chatbox.get_qa_data()["gpa của bạn?"] == "8.30"

    old_mtime = path.stat().st_mtime_ns
    path.write_text(_source("8.40"), encoding="utf-8")
    os.utime(path, ns=(old_mtime + 1_000_000, old_mtime + 1_000_000))

    changed = chatbox.get_source()

    assert len(calls) == 2
    assert changed is not first
    assert chatbox.get_qa_data()["gpa của bạn?"] == "8.40"


def test_invalid_edit_keeps_previous_index(tmp_path, monkeypatch):
    config = _config(tmp_path, monkeypatch)
    path = Path(config.source_path)
    path.write_text(_source("8.30"), encoding="utf-8")

    good = chatbox.get_source()
    path.write_text("not a source", encoding="utf-8")
    os.utime(path, ns=(path.stat().st_mtime_ns + 1_000_000,) * 2)

    result = chatbox.get_source()

    assert result is good
    assert chatbox.get_qa_data()["gpa của bạn?"] == "8.30"
