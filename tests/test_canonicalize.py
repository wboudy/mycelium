"""
Tests for deterministic claim canonicalization (DED-001).

Acceptance Criteria:
- AC-1 (AC-DED-001-1): Same input → byte-identical canonical output across runs.
- AC-2 (AC-DED-001-2): Whitespace collapse + Unicode normalization produce
  identical canonical forms for cosmetically different golden pairs.
- AC-3: extracted_claim_key = "h-" + first_12_hex(sha256(canonical_utf8)).
- AC-4 (AC-DED-001-3): Golden pairs with identical canonical form produce
  matching extracted_claim_key.
- AC-5: At least 3 golden pairs covering whitespace, Unicode, case/punctuation.
"""

from __future__ import annotations

import hashlib

import pytest

from mycelium.canonicalize import canonicalize, extracted_claim_key


# ---------------------------------------------------------------------------
# Golden pairs (AC-5: whitespace, Unicode normalization, case/punctuation)
# ---------------------------------------------------------------------------

GOLDEN_PAIRS: list[tuple[str, str, str]] = [
    # (variant_a, variant_b, description)

    # 1. Whitespace variants
    (
        "The  quick\tbrown   fox\njumps over the lazy dog.",
        "The quick brown fox jumps over the lazy dog.",
        "whitespace-collapse",
    ),
    # 2. Unicode normalization (composed vs decomposed é)
    (
        "caf\u00e9 latt\u00e9",      # NFC: é as single code point
        "cafe\u0301 latte\u0301",     # NFD: e + combining acute
        "unicode-normalization",
    ),
    # 3. Case and punctuation variants (curly quotes, em dash, ellipsis)
    (
        "It\u2019s a \u201cTest\u201d \u2014 really\u2026",
        "IT'S A \"TEST\" - REALLY...",
        "case-punctuation",
    ),
]


# ---------------------------------------------------------------------------
# AC-1: Determinism — same input → byte-identical output
# ---------------------------------------------------------------------------

class TestDeterminism:
    """AC-DED-001-1: canonicalization is deterministic."""

    def test_same_input_same_output(self):
        text = "Machine learning models require careful evaluation."
        assert canonicalize(text) == canonicalize(text)

    def test_repeated_calls_identical(self):
        text = "  Spaces   and\ttabs\nand newlines  "
        results = [canonicalize(text) for _ in range(10)]
        assert len(set(results)) == 1

    def test_extracted_key_deterministic(self):
        text = "Deterministic hashing is critical."
        assert extracted_claim_key(text) == extracted_claim_key(text)


# ---------------------------------------------------------------------------
# AC-2: Whitespace + Unicode normalization
# ---------------------------------------------------------------------------

class TestNormalization:
    """AC-DED-001-2: cosmetic differences produce identical canonical forms."""

    @pytest.mark.parametrize(
        "variant_a, variant_b, desc",
        GOLDEN_PAIRS,
        ids=[p[2] for p in GOLDEN_PAIRS],
    )
    def test_golden_pair_canonical_match(self, variant_a: str, variant_b: str, desc: str):
        assert canonicalize(variant_a) == canonicalize(variant_b), (
            f"Golden pair '{desc}' did not produce matching canonical forms"
        )

    def test_leading_trailing_whitespace_stripped(self):
        assert canonicalize("  hello  ") == canonicalize("hello")

    def test_mixed_whitespace_collapsed(self):
        assert canonicalize("a  b\tc\nd") == "a b c d"

    def test_non_breaking_space_normalized(self):
        assert canonicalize("hello\u00a0world") == canonicalize("hello world")


# ---------------------------------------------------------------------------
# AC-3: Key formula
# ---------------------------------------------------------------------------

class TestExtractedClaimKey:
    """extracted_claim_key = 'h-' + first_12_hex(sha256(canonical_utf8))."""

    def test_key_format(self):
        key = extracted_claim_key("test claim")
        assert key.startswith("h-")
        assert len(key) == 14  # "h-" + 12 hex chars

    def test_key_matches_manual_computation(self):
        text = "The earth orbits the sun."
        canonical = canonicalize(text)
        expected_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]
        assert extracted_claim_key(text) == f"h-{expected_hash}"

    def test_key_hex_characters_only(self):
        key = extracted_claim_key("anything at all")
        hex_part = key[2:]
        assert all(c in "0123456789abcdef" for c in hex_part)


# ---------------------------------------------------------------------------
# AC-4: Golden pairs produce matching keys
# ---------------------------------------------------------------------------

class TestGoldenPairKeys:
    """AC-DED-001-3: golden pairs with identical canonical form → same key."""

    @pytest.mark.parametrize(
        "variant_a, variant_b, desc",
        GOLDEN_PAIRS,
        ids=[p[2] for p in GOLDEN_PAIRS],
    )
    def test_golden_pair_key_match(self, variant_a: str, variant_b: str, desc: str):
        assert extracted_claim_key(variant_a) == extracted_claim_key(variant_b), (
            f"Golden pair '{desc}' did not produce matching extracted_claim_key"
        )


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_empty_string(self):
        canonical = canonicalize("")
        assert canonical == ""
        # Key should still be computable
        key = extracted_claim_key("")
        assert key.startswith("h-")

    def test_only_whitespace(self):
        assert canonicalize("   \t\n  ") == ""

    def test_already_canonical(self):
        text = "already canonical text."
        assert canonicalize(text) == text

    def test_unicode_emoji_preserved(self):
        """Non-punctuation Unicode should pass through after NFC + lowercase."""
        result = canonicalize("Hello 🌍 World")
        assert "🌍" in result
        assert result == "hello 🌍 world"
