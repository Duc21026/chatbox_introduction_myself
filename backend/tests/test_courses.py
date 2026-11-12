from pathlib import Path

import pytest

from backend import courses


def _write(tmp_path, text):
    path = Path(tmp_path) / "courses.csv"
    path.write_text(text, encoding="utf-8")
    return path


SAMPLE = """code,name,credits,score10,score4,letter,counts_major,aliases
CSC10004,Cấu trúc dữ liệu và giải thuật,4,5.4,2.2,C,yes,ctdl|dsa
CSC10003,Phương pháp lập trình hướng đối tượng,4,6.9,2.95,B,yes,oop
BAA00004,Pháp luật đại cương,3,8.6,3.8,A,no,
MTH00008,Đại số tuyến tính,4,10,4,A+,yes,dstt
"""


def test_load_valid_file(tmp_path, monkeypatch):
    path = _write(tmp_path, SAMPLE)
    monkeypatch.setenv("CHATBOT_COURSES_PATH", str(path))

    loaded, issues = courses.load_courses()
    assert not issues
    assert [course.code for course in loaded] == [
        "CSC10004", "CSC10003", "BAA00004", "MTH00008",
    ]
    assert loaded[0].aliases == ("ctdl", "dsa")
    assert loaded[2].counts_major is False


def test_duplicate_code_is_conflict(tmp_path):
    path = _write(tmp_path, SAMPLE.replace(
        "MTH00008,Đại số tuyến tính", "CSC10004,Đại số tuyến tính"
    ))
    loaded, issues = courses.load_courses(str(path))

    assert any(issue.code == "E_CONFLICT" for issue in issues)


def test_duplicate_name_is_conflict(tmp_path):
    path = _write(tmp_path, SAMPLE + (
        "MTH00009,Đại số tuyến tính,4,10,4,A+,yes,dstt2\n"
    ))
    loaded, issues = courses.load_courses(str(path))

    assert any(issue.code == "E_CONFLICT" for issue in issues)


def test_bad_header_is_error(tmp_path):
    path = _write(tmp_path, SAMPLE.replace("code,name,credits", "code,ten,credits"))
    loaded, issues = courses.load_courses(str(path))

    assert not loaded
    assert any(issue.code == "E_BAD_CSV" for issue in issues)


def test_out_of_range_values_are_errors(tmp_path):
    path = _write(tmp_path, SAMPLE.replace(
        "MTH00008,Đại số tuyến tính,4,10,4,A+,yes,dstt",
        "MTH00008,Đại số tuyến tính,99,10,4,A+,yes,dstt",
    ))
    loaded, issues = courses.load_courses(str(path))

    assert any(issue.code == "E_BAD_VALUE" for issue in issues)


def test_bad_counts_major_is_error(tmp_path):
    path = _write(tmp_path, SAMPLE.replace("counts_major,yes", "counts_major,1").replace("yes,dstt", "1,dstt"))
    loaded, issues = courses.load_courses(str(path))

    assert any(issue.code == "E_BAD_ENUM" for issue in issues)


def test_missing_file_is_error(tmp_path):
    loaded, issues = courses.load_courses(str(tmp_path / "missing.csv"))

    assert not loaded
    assert any(issue.code == "E_FILE_MISSING" for issue in issues)


def test_aggregates_match_pdf_figures(tmp_path):
    path = Path("data/sources/courses.csv")
    if not path.is_file():
        pytest.skip("courses.csv chưa có")
    loaded, issues = courses.load_courses(str(path))
    assert not issues

    aggregated = courses.aggregates(loaded)
    assert aggregated["courses_count"] == 24
    assert aggregated["credits_total"] == 87
    assert abs(aggregated["gpa10"] - 8.514) < 0.001
    assert abs(aggregated["gpa4"] - 3.634) < 0.001
    assert aggregated["major_courses_count"] == 21
    assert aggregated["major_credits"] == 79
    assert abs(aggregated["gpa_major"] - 8.55) < 0.01
    assert {c.name for c in aggregated["top_subjects"]} == {
        "Đại số tuyến tính", "Vi tích phân 2", "Xác suất thống kê",
    }


def test_generated_qa_uses_full_sentence_format(tmp_path):
    path = _write(tmp_path, SAMPLE)
    loaded, issues = courses.load_courses(str(path))

    items = courses.build_course_qa(loaded)
    oop = next(item for item in items if item["id"] == "course-csc10003")
    assert oop["answer"] == (
        "Điểm Phương pháp lập trình hướng đối tượng là 6.9 (B, 4 tín chỉ)."
    )
    credits_item = next(item for item in items if item["id"] == "course-csc10003-credits")
    assert credits_item["answer"] == (
        "Phương pháp lập trình hướng đối tượng có 4 tín chỉ."
    )
    major_item = next(item for item in items if item["id"] == "course-csc10003-major")
    assert "được tính khi xét chuyên ngành" in major_item["answer"]
    law_item = next(item for item in items if item["id"] == "course-baa00004-major")
    assert "không được tính khi xét chuyên ngành" in law_item["answer"]


def test_score_text_one_decimal(tmp_path):
    path = _write(tmp_path, SAMPLE)
    loaded, issues = courses.load_courses(str(path))

    assert loaded[0].score10_text() == "5.4"
    assert loaded[2].score10_text() == "8.6"
    assert loaded[3].score10_text() == "10.0"


def test_w_conflict_when_aggregate_differs_from_fact():
    aggregated = {
        "credits_total": 87, "courses_count": 24,
        "gpa10": 8.51, "gpa4": 3.63,
        "major_courses_count": 21, "major_credits": 79, "gpa_major": 8.55,
        "top_subjects": [], "bottom_subjects": [],
    }
    facts = {"gpa-10": type("F", (), {"value": "8.30", "id": "gpa-10"})()}
    issues = courses.check_against_facts(aggregated, facts)

    assert issues
    assert issues[0].code == "W_CONFLICT"
    assert issues[0].severity == "warning"
