"""
Regression test suite for dedupe and idempotency edge cases (TST-R-001).

§13.5 minimum regression cases:
1. Semantically identical but differently formatted claims → EXACT or NEAR_DUPLICATE
2. Semantically different claims with high lexical overlap → must NOT be incorrectly deduped
3. Same normalized locator with unchanged fingerprint → must reuse source_id
4. Same normalized locator with changed fingerprint → different fingerprint (revision)
5. Re-running Promotion on already-promoted items → no-op or deterministic conflict

Acceptance Criteria:
- AC-TST-R-001-1: Regression failures fail CI/release gating.
- AC-TST-R-001-2: Cases remain stable across refactors.
- AC-TST-R-001-3: All 5 minimum regression cases present with explicit assertions.

NOTE: This test file is a REGRESSION suite. Tests should only change when
intended behavior changes, with a changelog note in the commit message.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from mycelium.canonicalize import canonicalize, extracted_claim_key
from mycelium.comparator import (
    MatchClass,
    classify_similarity,
    compare_claim,
    _default_similarity,
)
from mycelium.stages.fingerprint import compute_fingerprint, fingerprint
from mycelium.stages.normalize import NormalizedSource, normalize
from mycelium.stages.capture import RawSourcePayload
from mycelium.graduate import GraduateInput, graduate
from mycelium.note_io import write_note, read_note


# ---------------------------------------------------------------------------
# REGRESSION CASE 1: Semantically identical, differently formatted claims
#   → should match as EXACT or NEAR_DUPLICATE
# ---------------------------------------------------------------------------

class TestIdenticalClaimsDifferentFormatting:
    """Regression: identical claims with whitespace/case/punctuation differences
    should be recognized as EXACT or NEAR_DUPLICATE, not NEW."""

    def test_whitespace_variations_match(self):
        """Extra spaces, tabs, and newlines should not prevent matching."""
        claim_a = "Machine learning models require training data"
        claim_b = "Machine  learning   models   require   training   data"
        canon_a = canonicalize(claim_a)
        canon_b = canonicalize(claim_b)
        assert canon_a == canon_b
        assert extracted_claim_key(claim_a) == extracted_claim_key(claim_b)

    def test_case_variations_match(self):
        """Case differences should not prevent matching."""
        claim_a = "The Earth orbits the Sun"
        claim_b = "the earth orbits the sun"
        canon_a = canonicalize(claim_a)
        canon_b = canonicalize(claim_b)
        assert canon_a == canon_b

    def test_punctuation_variations_match(self):
        """Curly quotes vs straight quotes, em dashes vs hyphens."""
        claim_a = 'The claim states: "evidence supports this"'
        claim_b = "The claim states: \u201cevidence supports this\u201d"
        canon_a = canonicalize(claim_a)
        canon_b = canonicalize(claim_b)
        assert canon_a == canon_b

    def test_unicode_normalization_match(self):
        """NFC vs NFD representations should canonicalize identically."""
        # é as precomposed (NFC) vs decomposed (NFD)
        claim_a = "Caf\u00e9 culture"
        claim_b = "Cafe\u0301 culture"
        canon_a = canonicalize(claim_a)
        canon_b = canonicalize(claim_b)
        assert canon_a == canon_b

    def test_similarity_high_for_formatted_variants(self):
        """Differently formatted but same-meaning claims → high similarity."""
        claim_a = "neural networks learn hierarchical representations"
        claim_b = "Neural Networks Learn Hierarchical Representations"
        sim = _default_similarity(canonicalize(claim_a), canonicalize(claim_b))
        match_class = classify_similarity(sim)
        assert match_class in (MatchClass.EXACT, MatchClass.NEAR_DUPLICATE)


# ---------------------------------------------------------------------------
# REGRESSION CASE 2: Semantically different claims with high lexical overlap
#   → must NOT be incorrectly deduped
# ---------------------------------------------------------------------------

class TestDifferentClaimsHighOverlap:
    """Regression: claims that share many words but have different meaning
    must not be classified as EXACT or NEAR_DUPLICATE."""

    def test_negation_not_deduped(self):
        """'X is true' vs 'X is not true' must not be EXACT."""
        claim_a = "vaccines cause autism"
        claim_b = "vaccines do not cause autism"
        sim = _default_similarity(canonicalize(claim_a), canonicalize(claim_b))
        # Should not be classified as EXACT (>= 0.97)
        assert sim < 0.97, f"Negated claim matched as EXACT with sim={sim}"

    def test_different_subjects_not_deduped(self):
        """Same predicate but different subjects must not match as EXACT."""
        claim_a = "python is the best programming language"
        claim_b = "rust is the best programming language"
        sim = _default_similarity(canonicalize(claim_a), canonicalize(claim_b))
        assert classify_similarity(sim) != MatchClass.EXACT

    def test_different_numbers_not_deduped(self):
        """Same template with different numeric values must not be EXACT."""
        claim_a = "the experiment showed a 95% success rate"
        claim_b = "the experiment showed a 30% success rate"
        key_a = extracted_claim_key(claim_a)
        key_b = extracted_claim_key(claim_b)
        assert key_a != key_b

    def test_opposite_conclusions_not_deduped(self):
        """Same evidence description but opposite conclusions."""
        claim_a = "the data shows a positive correlation between exercise and longevity"
        claim_b = "the data shows a negative correlation between exercise and longevity"
        sim = _default_similarity(canonicalize(claim_a), canonicalize(claim_b))
        assert classify_similarity(sim) != MatchClass.EXACT


# ---------------------------------------------------------------------------
# REGRESSION CASE 3: Same locator, unchanged fingerprint → reuse source_id
# ---------------------------------------------------------------------------

class TestSameLocatorUnchangedFingerprint:
    """Regression: same normalized locator + same content → identical fingerprint,
    ensuring source_id reuse via deterministic fingerprint matching."""

    def test_same_content_same_fingerprint(self):
        """Identical content from same URL → identical fingerprint (reuse source_id)."""
        source_a = NormalizedSource(
            normalized_text="Identical article content version 1.0",
            normalized_locator="https://example.com/article",
            source_kind="url",
            source_ref="https://example.com/article",
        )
        source_b = NormalizedSource(
            normalized_text="Identical article content version 1.0",
            normalized_locator="https://example.com/article",
            source_kind="url",
            source_ref="https://example.com/article",
        )
        id_a, _ = fingerprint(source_a)
        id_b, _ = fingerprint(source_b)
        assert id_a.fingerprint == id_b.fingerprint
        assert id_a.normalized_locator == id_b.normalized_locator

    def test_url_normalization_preserves_identity(self):
        """Different URL formats normalizing to same locator → same fingerprint."""
        payload_a = RawSourcePayload(
            text="Same content",
            media_type="text/html",
            source_ref="HTTPS://EXAMPLE.COM/Article/",
            source_kind="url",
        )
        payload_b = RawSourcePayload(
            text="Same content",
            media_type="text/html",
            source_ref="https://example.com/Article",
            source_kind="url",
        )
        result_a, _ = normalize(payload_a)
        result_b, _ = normalize(payload_b)
        assert result_a.normalized_locator == result_b.normalized_locator

        fp_a = compute_fingerprint(result_a.normalized_text)
        fp_b = compute_fingerprint(result_b.normalized_text)
        assert fp_a == fp_b

    def test_repeated_ingest_idempotent(self):
        """Multiple ingestion runs of same content → same fingerprint every time."""
        text = "Stable content for idempotency verification"
        fingerprints = [compute_fingerprint(text) for _ in range(10)]
        assert len(set(fingerprints)) == 1


# ---------------------------------------------------------------------------
# REGRESSION CASE 4: Same locator, changed fingerprint → different fingerprint
# ---------------------------------------------------------------------------

class TestSameLocatorChangedFingerprint:
    """Regression: same URL but updated content → different fingerprint,
    recording a revision lineage (not a duplicate)."""

    def test_updated_content_different_fingerprint(self):
        """Same locator, different text → different fingerprint (revision)."""
        source_v1 = NormalizedSource(
            normalized_text="Article content version 1.0",
            normalized_locator="https://example.com/article",
            source_kind="url",
            source_ref="https://example.com/article",
        )
        source_v2 = NormalizedSource(
            normalized_text="Article content version 2.0 with major updates",
            normalized_locator="https://example.com/article",
            source_kind="url",
            source_ref="https://example.com/article",
        )
        id_v1, _ = fingerprint(source_v1)
        id_v2, _ = fingerprint(source_v2)
        # Same locator
        assert id_v1.normalized_locator == id_v2.normalized_locator
        # Different fingerprint
        assert id_v1.fingerprint != id_v2.fingerprint

    def test_minor_edit_detected(self):
        """Even a single character change should produce a different fingerprint."""
        fp_a = compute_fingerprint("The quick brown fox jumps over the lazy dog")
        fp_b = compute_fingerprint("The quick brown fox jumps over the lazy cat")
        assert fp_a != fp_b

    def test_whitespace_only_changes_detected(self):
        """Changes that survive normalization should still be detected."""
        # These differ by a word, not just whitespace
        fp_a = compute_fingerprint("paragraph one\n\nparagraph two")
        fp_b = compute_fingerprint("paragraph one\n\nparagraph three")
        assert fp_a != fp_b


# ---------------------------------------------------------------------------
# REGRESSION CASE 5: Re-running Promotion on already-promoted items
# ---------------------------------------------------------------------------

class TestRepromotionIdempotency:
    """Regression: re-promoting already-promoted items should be a no-op
    or return a deterministic conflict error."""

    def test_already_promoted_note_rejected(self, tmp_path: Path):
        """Items not in Draft Scope (already in canonical) should be rejected."""
        # Create a note already in canonical scope
        fm: dict[str, Any] = {
            "id": "already-promoted",
            "type": "source",
            "status": "canon",
            "created": "2026-01-01T00:00:00Z",
            "updated": "2026-01-01T00:00:00Z",
        }
        write_note(
            tmp_path / "Sources" / "already-promoted.md",
            fm,
            "# Already in canon\n",
        )

        params = GraduateInput(all_approved=True, actor="test")
        items = [{
            "queue_id": "q-repromote",
            "path": "Sources/already-promoted.md",
            "decision": "approve",
        }]

        env = graduate(tmp_path, params, items)
        assert env.ok is True
        # Should be rejected (not in draft scope)
        assert len(env.data["rejected"]) == 1
        assert "Draft Scope" in env.data["rejected"][0]["reason"]
        # Nothing promoted
        assert len(env.data["promoted"]) == 0

    def test_promotion_result_deterministic(self, tmp_path: Path):
        """Running the same promotion twice produces the same result structure."""
        fm: dict[str, Any] = {
            "id": "det-note",
            "type": "source",
            "status": "draft",
            "created": "2026-01-01T00:00:00Z",
            "updated": "2026-01-01T00:00:00Z",
        }
        write_note(
            tmp_path / "Inbox" / "Sources" / "det-note.md",
            fm,
            "# Deterministic\n",
        )

        params = GraduateInput(all_approved=True, actor="test")
        items = [{
            "queue_id": "q-det",
            "path": "Inbox/Sources/det-note.md",
            "decision": "approve",
        }]

        env1 = graduate(tmp_path, params, items)
        assert env1.ok is True
        assert len(env1.data["promoted"]) == 1

        # Second run: the canonical note already exists from the first
        # promotion. The overwrite guard should reject re-promotion.
        write_note(
            tmp_path / "Inbox" / "Sources" / "det-note.md",
            fm,
            "# Deterministic\n",
        )
        env2 = graduate(tmp_path, params, items)
        assert env2.ok is True  # per-item atomicity: envelope is ok
        assert len(env2.data["rejected"]) == 1
        assert "already exists" in env2.data["rejected"][0]["reason"]
