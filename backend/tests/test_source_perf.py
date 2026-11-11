import time
from pathlib import Path

from backend import source_format


def test_parse_and_validate_one_megabyte_under_one_second(tmp_path):
    line = "Nội dung học bổng và kế hoạch học tập tại Đức. " * 2
    content = "\n".join(line.strip() for _ in range(12_000))
    source = (
        "CHATBOT-SOURCE v1\n\n"
        "=== RECORD ===\n"
        "kind: doc\n"
        "id: large-doc\n"
        "topic: Tài liệu lớn\n"
        "content:\n"
        f"{content}\n"
        "=== END ===\n"
    )
    path = Path(tmp_path) / "chatbot.txt"
    path.write_text(source, encoding="utf-8")
    assert path.stat().st_size > 1024 * 1024

    started = time.perf_counter()
    result = source_format.validate_source(path)
    elapsed = time.perf_counter() - started

    assert result.valid, result.errors
    assert elapsed < 1.0
