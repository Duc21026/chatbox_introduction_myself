from backend import source_store


def test_canonical_source_contains_required_values():
    source = source_store.get_source()
    by_id = {item.id: item for item in source.kb_items}

    assert "8.51" in by_id["gpa"].answer
    assert "3.63" in by_id["gpa"].answer
    assert "87" in by_id["gpa"].answer

    oop = by_id["course-csc10003"]
    assert "6.9" in oop.answer
    assert "4 tín chỉ" in oop.answer

    assert by_id["tot-nghiep"].answer
    assert by_id["muc-tieu-ielts"].answer
    assert any("mục tiêu" in question.casefold() for question in by_id["muc-tieu-hoc-bong"].questions)
