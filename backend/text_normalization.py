"""Shared Vietnamese text normalization used for indexing and search."""

import re
import unicodedata

_REPEATED_CHARACTER = re.compile(r"(.)\1{2,}", re.DOTALL)
_REPEATED_PUNCTUATION = re.compile(r"([!?.,])\1+")
_WHITESPACE = re.compile(r"\s+")


def normalize_text(text, lowercase=True):
    """Return the normalized form of Vietnamese text.

    The pipeline follows contracts/retrieval-normalization.md:
    NFC, collapse runs of 3+ identical characters, lowercase (search form
    only), collapse repeated sentence punctuation, collapse whitespace, and
    treat a form with no remaining letter or digit as unsearchable.

    Documents are indexed with ``lowercase=False`` so their original casing
    remains available, while questions use the fully lowercased search form.
    """

    if not isinstance(text, str):
        raise TypeError("text phải là chuỗi")

    normalized = unicodedata.normalize("NFC", text)
    normalized = _REPEATED_CHARACTER.sub(r"\1", normalized)
    if lowercase:
        normalized = normalized.lower()
    normalized = _REPEATED_PUNCTUATION.sub(r"\1", normalized)
    normalized = _WHITESPACE.sub(" ", normalized).strip()

    if not any(character.isalnum() for character in normalized):
        return ""
    return normalized
