from pathlib import Path

import pytest

from backend import aliases, courses
from backend.text_normalization import normalize_query, register_aliases


def _write(tmp_path, text):
    path = Path(tmp_path) / "aliases.txt"
    path.write_text(text, encoding="utf-8")
    return path


def test_load_aliases_single_and_grouped():
    mapping = aliases.load_aliases(str(_write(
        Path("/tmp/opencode"), "vtp2 | vi tích phân 2\nctdl, dsa | cấu trúc dữ liệu và giải thuật\n"
    )))
    assert mapping["vtp2"] == "vi tích phân 2"
    assert mapping["ctdl"] == "cấu trúc dữ liệu và giải thuật"
    assert mapping["dsa"] == "cấu trúc dữ liệu và giải thuật"


def test_missing_pipe_raises():
    with pytest.raises(aliases.AliasIssue):
        aliases.load_aliases(str(_write(Path("/tmp/opencode"), "vtp2 vi tích phân 2\n")))


def test_conflicting_alias_raises():
    with pytest.raises(aliases.AliasIssue):
        aliases.load_aliases(str(_write(
            Path("/tmp/opencode"),
            "vtp2 | vi tích phân 2\nvtp2 | vi tích phân 1\n",
        )))


def test_merge_course_aliases_with_file(tmp_path):
    path = Path("data/sources/courses.csv")
    if not path.is_file():
        pytest.skip("courses.csv chưa có")
    course_list, issues = courses.load_courses(str(path))
    assert not issues

    mapping = aliases.merged_alias_map(course_list, str(_write(
        tmp_path, "vtp1 | vi tích phân 1\n"
    )))
    assert mapping["vtp1"] == "vi tích phân 1"
    assert mapping["oop"] == "phương pháp lập trình hướng đối tượng"
    assert mapping["ctdl"] == "cấu trúc dữ liệu và giải thuật"


def test_expand_aliases_in_query(tmp_path):
    path = Path("data/sources/courses.csv")
    if not path.is_file():
        pytest.skip("courses.csv chưa có")
    course_list, issues = courses.load_courses(str(path))
    mapping = aliases.merged_alias_map(course_list)

    register_aliases(mapping)
    assert normalize_query("điểm vtp2") == "điểm vi tích phân 2"
    assert normalize_query("oop bao nhiêu") == (
        "phương pháp lập trình hướng đối tượng bao nhiêu"
    )
    assert normalize_query("điểm ctdl") == "điểm cấu trúc dữ liệu và giải thuật"
    assert normalize_query("điểm xstk") == "điểm xác suất thống kê"
    register_aliases({})
