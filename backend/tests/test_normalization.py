import unicodedata

from backend.text_normalization import normalize_text


def test_nfc_normalizes_decomposed_diacritics():
    decomposed = unicodedata.normalize("NFD", "được")
    assert decomposed != "được"
    assert normalize_text(decomposed) == "được"


def test_repeated_characters_are_collapsed():
    assert normalize_text("choooo") == "cho"
    assert normalize_text("đượcccc") == "được"


def test_legitimate_double_letters_are_preserved():
    assert normalize_text("xoong") == "xoong"
    assert normalize_text("boong") == "boong"


def test_case_punctuation_and_whitespace_are_normalized():
    assert normalize_text("  HELLO!!!   World??  ") == "hello! world?"


def test_decomposed_diacritics_are_lowercased_and_trimmed():
    decomposed = unicodedata.normalize("NFD", "  ĐƯỢC  ")
    assert normalize_text(decomposed) == "được"


def test_punctuation_only_normalizes_to_empty():
    assert normalize_text("!!!") == ""
    assert normalize_text("... ??? ,,,") == ""
    assert normalize_text("   ") == ""


def test_digits_keep_the_form_searchable():
    assert normalize_text("!!! 8.30 ???") == "! 8.30 ?"


def test_normalization_does_not_mutate_the_original_text():
    original = "  CHOOOO!!!  "
    normalized = normalize_text(original)
    assert original == "  CHOOOO!!!  "
    assert normalized == "cho!"
