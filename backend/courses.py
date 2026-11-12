"""Course list source — the single source of all academic figures.

``courses.csv`` (8 cột theo ``specs/007-unify-data-facts/contracts/courses-csv.md``)
là nơi duy nhất chứa điểm, tín chỉ và cờ xét chuyên ngành của từng môn. Mọi số
tổng hợp (GPA, tổng tín chỉ, số học phần, GPA xét chuyên ngành, môn cao/thấp
nhất) đều được TÍNH RA từ bảng này, không gõ tay ở nơi khác.

Module thuần Python, không gọi Ollama.
"""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass, field
from typing import Optional

try:
    from .text_normalization import normalize_text
except ImportError:  # direct execution from backend/
    from text_normalization import normalize_text

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_COURSES_PATH = os.path.join(BACKEND_DIR, "data", "sources", "courses.csv")

COLUMNS = (
    "code",
    "name",
    "credits",
    "score10",
    "score4",
    "letter",
    "counts_major",
    "aliases",
)
LETTERS = frozenset({"A+", "A", "B+", "B", "C+", "C", "D+", "D", "F"})
GPA_TOLERANCE = 0.001


def courses_path():
    return os.environ.get("CHATBOT_COURSES_PATH", DEFAULT_COURSES_PATH)


@dataclass(frozen=True)
class CourseIssue:
    severity: str
    code: str
    message: str
    row: Optional[int] = None

    def to_dict(self):
        return {
            "severity": self.severity,
            "code": self.code,
            "row": self.row,
            "message": self.message,
        }


@dataclass(frozen=True)
class Course:
    code: str
    name: str
    credits: int
    score10: float
    score4: Optional[float]
    letter: Optional[str]
    counts_major: bool
    aliases: tuple = ()

    def as_dict(self):
        return {
            "code": self.code,
            "name": self.name,
            "credits": self.credits,
            "score10": self.score10,
            "score4": self.score4,
            "letter": self.letter,
            "counts_major": self.counts_major,
            "aliases": list(self.aliases),
        }

    def score10_text(self):
        return f"{self.score10:.1f}"

    def score4_text(self):
        if self.score4 is None:
            return ""
        return f"{self.score4:.2f}".rstrip("0").rstrip(".")


def _error(code, message, row=None):
    return CourseIssue("error", code, message, row)


def _warning(code, message, row=None):
    return CourseIssue("warning", code, message, row)


def _to_float(value, default=None):
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return None


def _score4_from_score10(score10):
    return round(score10 / 10.0 * 4.0, 2)


def load_courses(path=None):
    """Read and validate ``courses.csv`` → (courses, issues)."""

    path = path or courses_path()
    issues = []
    if not os.path.isfile(path):
        issues.append(
            _error(
                "E_FILE_MISSING",
                f"Không tìm thấy danh sách môn học '{path}'. "
                "Hãy kiểm tra CHATBOT_COURSES_PATH.",
            )
        )
        return [], issues

    courses = []
    seen_codes = {}
    seen_names = {}
    alias_to_course = {}
    try:
        with open(path, encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.reader(handle))
    except OSError as exc:
        issues.append(_error("E_BAD_CSV", f"Không đọc được {path}: {exc}"))
        return [], issues

    if not rows:
        issues.append(_error("E_BAD_CSV", f"Tệp {path} rỗng."))
        return [], issues

    header = [cell.strip() for cell in rows[0]]
    if header != list(COLUMNS):
        issues.append(
            _error(
                "E_BAD_CSV",
                f"Header sai. Đúng thứ tự: {', '.join(COLUMNS)}.",
                1,
            )
        )
        return [], issues

    for index, row in enumerate(rows[1:], start=2):
        if not row or all(not cell.strip() for cell in row):
            continue
        if len(row) < len(COLUMNS):
            row = row + [""] * (len(COLUMNS) - len(row))
        values = dict(zip(COLUMNS, [cell.strip() for cell in row]))

        code = values["code"]
        name = values["name"]
        if not code or not name:
            issues.append(
                _error("E_MISSING_FIELD", "Dòng thiếu 'code' hoặc 'name'.", index)
            )
            continue

        if code in seen_codes:
            issues.append(
                _error(
                    "E_CONFLICT",
                    f"Mã môn '{code}' trùng với dòng {seen_codes[code]}.",
                    index,
                )
            )
            continue
        if name.casefold() in seen_names:
            issues.append(
                _error(
                    "E_CONFLICT",
                    f"Tên môn '{name}' trùng với dòng {seen_names[name.casefold()]}.",
                    index,
                )
            )
            continue

        try:
            credits = int(values["credits"])
        except ValueError:
            credits = -1
        if not 1 <= credits <= 20:
            issues.append(
                _error(
                    "E_BAD_VALUE",
                    f"credits '{values['credits']}' không hợp lệ; "
                    "phải là số nguyên 1–20.",
                    index,
                )
            )
            continue

        score10 = _to_float(values["score10"])
        if score10 is None or not 0 <= score10 <= 10:
            issues.append(
                _error(
                    "E_BAD_VALUE",
                    f"score10 '{values['score10']}' không hợp lệ; phải nằm "
                    "trong 0–10.",
                    index,
                )
            )
            continue

        score4 = _to_float(values["score4"])
        if score4 is not None and not 0 <= score4 <= 4:
            issues.append(
                _error(
                    "E_BAD_VALUE",
                    f"score4 '{values['score4']}' không hợp lệ; phải nằm "
                    "trong 0–4.",
                    index,
                )
            )
            continue
        if score4 is None:
            score4 = _score4_from_score10(score10)

        letter = values["letter"] or None
        if letter is not None and letter not in LETTERS:
            issues.append(
                _error(
                    "E_BAD_ENUM",
                    f"letter '{letter}' không hợp lệ; chỉ nhận "
                    + ", ".join(sorted(LETTERS)) + ".",
                    index,
                )
            )
            continue

        counts_major = values["counts_major"].strip().lower()
        if counts_major not in {"yes", "no"}:
            issues.append(
                _error(
                    "E_BAD_ENUM",
                    f"counts_major '{values['counts_major']}' không hợp lệ; "
                    "chỉ nhận yes hoặc no.",
                    index,
                )
            )
            continue

        aliases = tuple(
            alias.strip()
            for alias in values["aliases"].split("|")
            if alias.strip()
        )
        for alias in aliases:
            key = normalize_text(alias)
            if key in alias_to_course:
                issues.append(
                    _error(
                        "E_CONFLICT",
                        f"Bí danh '{alias}' trùng với bí danh của môn "
                        f"'{alias_to_course[key]}'.",
                        index,
                    )
                )
            elif key == normalize_text(name) or key == code.casefold():
                issues.append(
                    _error(
                        "E_CONFLICT",
                        f"Bí danh '{alias}' trùng với code hoặc tên của môn "
                        "này.",
                        index,
                    )
                )
            else:
                alias_to_course[key] = name

        seen_codes[code] = index
        seen_names[name.casefold()] = index
        courses.append(
            Course(
                code=code,
                name=name,
                credits=credits,
                score10=round(score10, 4),
                score4=round(score4, 4) if score4 is not None else None,
                letter=letter,
                counts_major=counts_major == "yes",
                aliases=aliases,
            )
        )

    if not courses:
        issues.append(_error("E_EMPTY", f"Danh sách môn học '{path}' không có dòng nào."))
    return courses, issues


def aggregates(courses):
    """Compute all aggregate figures from the course list."""

    credits_total = sum(course.credits for course in courses)
    courses_count = len(courses)
    gpa10 = (
        sum(course.score10 * course.credits for course in courses)
        / credits_total
        if credits_total
        else 0.0
    )
    gpa4 = (
        sum((course.score4 or 0.0) * course.credits for course in courses)
        / credits_total
        if credits_total
        else 0.0
    )
    major_courses = [course for course in courses if course.counts_major]
    major_credits = sum(course.credits for course in major_courses)
    gpa_major = (
        sum(course.score10 * course.credits for course in major_courses)
        / major_credits
        if major_credits
        else 0.0
    )
    if courses:
        top_score = max(course.score10 for course in courses)
        bottom_score = min(course.score10 for course in courses)
    else:
        top_score = bottom_score = None
    top_subjects = [
        course for course in courses if course.score10 == top_score
    ]
    bottom_subjects = [
        course for course in courses if course.score10 == bottom_score
    ]
    return {
        "credits_total": credits_total,
        "courses_count": courses_count,
        "gpa10": gpa10,
        "gpa4": gpa4,
        "major_courses_count": len(major_courses),
        "major_credits": major_credits,
        "gpa_major": gpa_major,
        "top_subjects": top_subjects,
        "bottom_subjects": bottom_subjects,
    }


def check_against_facts(aggregated, facts_map):
    """Compare aggregates with fact values; mismatch → W_CONFLICT."""

    issues = []
    mapping = {
        "gpa-10": ("gpa10", "GPA tích lũy (thang 10)"),
        "gpa-4": ("gpa4", "GPA tích lũy (thang 4)"),
        "credits": ("credits_total", "Tổng tín chỉ"),
        "courses-count": ("courses_count", "Số học phần"),
    }
    for fact_id, (key, label) in mapping.items():
        fact = facts_map.get(fact_id)
        if fact is None:
            continue
        try:
            expected = float(str(fact.value).replace(",", "."))
        except ValueError:
            continue
        actual = float(aggregated[key])
        decimals = 0
        if "." in str(fact.value):
            decimals = len(str(fact.value).split(".", 1)[1])
        if abs(round(actual, decimals) - expected) > 1e-6:
            issues.append(
                _warning(
                    "W_CONFLICT",
                    f"{label} tính từ danh sách môn là {actual:.4f} nhưng fact "
                    f"'{fact_id}' ghi {fact.value}.",
                )
            )
    return issues


def build_course_qa(courses):
    """Generate per-course Q&A: điểm, số tín chỉ, xét chuyên ngành."""

    items = []
    for course in courses:
        score_text = course.score10_text()
        letter = course.letter or ""
        items.append(
            {
                "id": f"course-{course.code.lower()}",
                "topic": "Học tập & Điểm số",
                "questions": [
                    f"điểm {course.name}",
                    f"điểm {course.name} bao nhiêu",
                    f"{course.name} bao nhiêu điểm",
                    f"điểm {course.code}",
                ],
                "answer": (
                    f"Điểm {course.name} là {score_text}"
                    + (f" ({letter}, {course.credits} tín chỉ)." if letter else ".")
                ),
            }
        )
        items.append(
            {
                "id": f"course-{course.code.lower()}-credits",
                "topic": "Học tập & Điểm số",
                "questions": [
                    f"{course.name} mấy tín chỉ",
                    f"{course.name} bao nhiêu tín chỉ",
                ],
                "answer": f"{course.name} có {course.credits} tín chỉ.",
            }
        )
        yes_no = "được" if course.counts_major else "không được"
        items.append(
            {
                "id": f"course-{course.code.lower()}-major",
                "topic": "Học tập & Điểm số",
                "questions": [
                    f"{course.name} xét chuyên ngành không",
                    f"{course.name} có tính vào xét chuyên ngành không",
                ],
                "answer": (
                    f"{'Có' if course.counts_major else 'Không'}, môn "
                    f"{course.name} {yes_no} tính khi xét chuyên ngành."
                ),
            }
        )
    return items
