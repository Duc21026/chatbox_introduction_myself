"""Alias registry: viết tắt / tên gọi khác → tên chuẩn.

Nguồn gộp từ hai nơi:
  - ``sources/aliases.txt`` — mỗi dòng ``bí-danh[, bí-danh…] | tên-chuẩn``
  - cột ``aliases`` của từng dòng trong ``courses.csv`` (đích là tên môn)

Bí danh được áp dụng khi chuẩn hoá câu hỏi (qua ``text_normalization``),
nên ``điểm vtp2``, ``điểm oop``, ``điểm ctdl`` đều trả đúng môn mà không cần
nhân đôi record hỏi-đáp.

Module thuần Python, không gọi Ollama.
"""

from __future__ import annotations

import os

try:
    from . import courses
    from .text_normalization import normalize_text
except ImportError:  # direct execution from backend/
    import courses
    from text_normalization import normalize_text

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ALIASES_PATH = os.path.join(BACKEND_DIR, "data", "sources", "aliases.txt")


def aliases_path():
    return os.environ.get("CHATBOT_ALIASES_PATH", DEFAULT_ALIASES_PATH)


class AliasIssue(RuntimeError):
    def __init__(self, code, message, line=None):
        self.code = code
        self.message = message
        self.line = line
        super().__init__(f"[{code}] {message}")


def load_aliases(path=None):
    """Read ``aliases.txt`` → {alias_norm: target_norm}.

    Format mỗi dòng: ``vtp2 | vi tích phân 2`` hoặc
    ``ctdl, dsa | cấu trúc dữ liệu và giải thuật``.
    """

    path = path or aliases_path()
    if not os.path.isfile(path):
        return {}
    mapping = {}
    with open(path, encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if "|" not in stripped:
                raise AliasIssue(
                    "E_BAD_ALIAS",
                    "Dòng không có dấu '|' (định dạng: bí-danh | tên-chuẩn).",
                    line_number,
                )
            alias_part, target = stripped.split("|", 1)
            target_norm = normalize_text(target.strip())
            if not target_norm:
                raise AliasIssue(
                    "E_BAD_ALIAS", "Tên chuẩn không được để trống.", line_number
                )
            for raw_alias in alias_part.split(","):
                alias_norm = normalize_text(raw_alias.strip())
                if not alias_norm:
                    continue
                if alias_norm in mapping and mapping[alias_norm] != target_norm:
                    raise AliasIssue(
                        "E_CONFLICT",
                        f"Bí danh '{raw_alias.strip()}' đã trỏ tới "
                        f"'{mapping[alias_norm]}'.",
                        line_number,
                    )
                mapping[alias_norm] = target_norm
    return mapping


def merged_alias_map(course_list=None, aliases_path=None):
    """Gộp aliases.txt + cột aliases của courses.csv."""

    mapping = load_aliases(aliases_path)
    for course in course_list or []:
        target = normalize_text(course.name)
        for alias in course.aliases:
            alias_norm = normalize_text(alias)
            if alias_norm and alias_norm not in mapping:
                mapping[alias_norm] = target
    return mapping


def expand_aliases(query_norm, alias_map):
    """Thay bí danh bằng tên chuẩn trong câu hỏi đã chuẩn hoá."""

    if not alias_map or not query_norm:
        return query_norm
    text = query_norm
    for alias in sorted(alias_map, key=len, reverse=True):
        if alias and alias in text:
            text = text.replace(alias, alias_map[alias])
    return text
