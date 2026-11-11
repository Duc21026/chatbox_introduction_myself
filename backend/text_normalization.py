"""Shared Vietnamese text normalization used for indexing and search."""

import re
import unicodedata

NORMALIZER_VERSION = "1"

_REPEATED_CHARACTER = re.compile(r"(.)\1{2,}", re.DOTALL)
_REPEATED_PUNCTUATION = re.compile(r"([!?.,])\1+")
_WHITESPACE = re.compile(r"\s+")

# ---------------------------------------------------------------------------
# normalize_query() additions
# ---------------------------------------------------------------------------

# Teencode / abbreviation mapping (applied with word boundaries)
_TEENCODE: dict[str, str] = {
    "ko": "không",
    "k": "không",
    "hok": "không",
    "hông": "không",
    "dc": "được",
    "đc": "được",
    "ok": "được",
    "oke": "được",
    "okie": "được",
    "j": "gì",
    "ntn": "như thế nào",
    "bn": "bạn",
    "mk": "mình",
    "mik": "mình",
    "wa": "quá",
    "lh": "liên hệ",
    "cv": "công việc",
    "btw": "nhân tiện",
    "vs": "với",
    "trc": "trước",
}

# Build a single regex that matches whole words, longest match first
_sorted_teencode_keys = sorted(_TEENCODE.keys(), key=len, reverse=True)
_TEENCODE_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in _sorted_teencode_keys) + r")\b"
)

# Filler words removed when they appear as independent tokens
_FILLER_WORDS = frozenset(
    ["ơi", "nhỉ", "vậy", "à", "nhé", "nha", "ha", "hả", "ạ"]
)

# Keep Unicode letters, digits, Vietnamese punctuation ?!.,
_KEEP_CHARS = re.compile(r"[^\w\s?!.,]", re.UNICODE)


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


def normalize_query(text: str) -> str:
    """Full 10-step normalization pipeline for user queries.

    Extends normalize_text() with teencode expansion and filler-word removal.
    Used exclusively for user input; never for document indexing.

    Pipeline (order is part of the contract — do not reorder):
      1. Truncate to 200 characters
      2. Unicode NFC
      3. Lowercase
      4. Strip leading/trailing whitespace
      5. Collapse runs of 3+ identical characters
      6. Remove emoji and special characters (keep Unicode letters, digits, ?!.,)
      7. Expand teencode / abbreviations (word-boundary substitution)
      8. Remove filler words (ơi, nhỉ, vậy, à, nhé, nha, ha, hả, ạ)
      9. Collapse multiple spaces to one
      10. Guard: return "" if no alphanumeric characters remain
    """

    if not isinstance(text, str):
        raise TypeError("text phải là chuỗi")

    # Step 1 — truncate
    text = text[:200]

    # Step 2 — NFC
    text = unicodedata.normalize("NFC", text)

    # Step 3 — lowercase
    text = text.lower()

    # Step 4 — strip
    text = text.strip()

    # Step 5 — collapse repeated characters (3+)
    text = _REPEATED_CHARACTER.sub(r"\1", text)

    # Step 6 — remove emoji / special characters; keep \w (letters+digits+_),
    #           spaces, and Vietnamese sentence punctuation ?!.,
    text = _KEEP_CHARS.sub(" ", text)
    # Also remove lone underscores that slipped through \w
    text = text.replace("_", " ")

    # Step 7 — teencode expansion
    text = _TEENCODE_PATTERN.sub(lambda m: _TEENCODE[m.group(1)], text)

    # Step 8 — remove filler words (independent tokens only)
    tokens = text.split()
    tokens = [t for t in tokens if t not in _FILLER_WORDS]
    text = " ".join(tokens)

    # Step 9 — collapse whitespace
    text = _WHITESPACE.sub(" ", text).strip()

    # Step 10 — guard
    if not any(c.isalnum() for c in text):
        return ""
    return text
