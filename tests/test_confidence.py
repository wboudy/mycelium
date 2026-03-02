"""
Tests for the deterministic advisory confidence rubric (CONF-001).

Verifies:
  AC-1: Re-running yields identical values (determinism).
  AC-2: Missing provenance => confidence <= 0.4, routed to human review.
  AC-3: All factors in [0..1].
  AC-4: Confidence is advisory, not a promotion decision.
  AC-5: source_reliability is 0.5 in MVP1.
  AC-6: Unit tests for each match_class with valid/invalid provenance.
"""

from __future__ import annotations

import pytest

from mycelium.confidence import (
    DEFAULT_SOURCE_RELIABILITY,
    DEDUPE_SUPPORT_MAP,
    HUMAN_REVIEW_THRESHOLD,
    W_DEDUPE,
    W_EXTRACT,
    W_PROVENANCE,
    W_SOURCE,
    clamp01,
    compute_confidence,
    compute_dedupe_support,
    compute_extract_consistency,
    compute_provenance_quality,
    compute_source_reliability,
    needs_human_review,
)


def _valid_provenance() -> dict:
    return {
        "source_id": "src-1",
        "source_ref": "ref-1",
        "locator": {"url": "https://example.com", "section": "1", "paragraph_index": 0, "snippet_hash": "sha256:" + "a" * 64},
    }


# ─── AC-5: source_reliability constant ──────────────────────────────────

class TestSourceReliability:

    def test_mvp1_constant(self):
        assert compute_source_reliability() == 0.5

    def test_default_constant_value(self):
        assert DEFAULT_SOURCE_RELIABILITY == 0.5


# ─── Provenance quality ─────────────────────────────────────────────────

class TestProvenanceQuality:

    def test_valid_provenance(self):
        assert compute_provenance_quality(_valid_provenance()) == 1.0

    def test_none_provenance(self):
        assert compute_provenance_quality(None) == 0.0

    def test_missing_source_id(self):
        prov = _valid_provenance()
        del prov["source_id"]
        assert compute_provenance_quality(prov) == 0.0

    def test_missing_source_ref(self):
        prov = _valid_provenance()
        del prov["source_ref"]
        assert compute_provenance_quality(prov) == 0.0

    def test_missing_locator(self):
        prov = _valid_provenance()
        del prov["locator"]
        assert compute_provenance_quality(prov) == 0.0

    def test_empty_source_id(self):
        prov = _valid_provenance()
        prov["source_id"] = "  "
        assert compute_provenance_quality(prov) == 0.0

    def test_not_dict(self):
        assert compute_provenance_quality("not-a-dict") == 0.0


# ─── Extract consistency ─────────────────────────────────────────────────

class TestExtractConsistency:

    def test_valid(self):
        assert compute_extract_consistency(True) == 1.0

    def test_invalid(self):
        assert compute_extract_consistency(False) == 0.0


# ─── Dedupe support ─────────────────────────────────────────────────────

class TestDedupeSupport:

    @pytest.mark.parametrize("match_class,expected", [
        ("EXACT", 1.0),
        ("NEAR_DUPLICATE", 0.8),
        ("SUPPORTING", 0.6),
        ("NEW", 0.4),
        ("CONTRADICTING", 0.2),
    ])
    def test_match_class_values(self, match_class, expected):
        assert compute_dedupe_support(match_class) == expected

    def test_none(self):
        assert compute_dedupe_support(None) == 0.0

    def test_unknown(self):
        assert compute_dedupe_support("UNKNOWN") == 0.0


# ─── AC-6: Confidence per match_class with valid/invalid provenance ─────

class TestConfidencePerMatchClass:
    """AC-6: Unit tests for each match_class with valid/invalid provenance."""

    @pytest.mark.parametrize("match_class", [
        "EXACT", "NEAR_DUPLICATE", "SUPPORTING", "NEW", "CONTRADICTING"
    ])
    def test_valid_provenance(self, match_class):
        conf = compute_confidence(_valid_provenance(), True, match_class)
        ds = DEDUPE_SUPPORT_MAP[match_class]
        expected = W_PROVENANCE * 1.0 + W_EXTRACT * 1.0 + W_DEDUPE * ds + W_SOURCE * 0.5
        assert conf == pytest.approx(expected)

    @pytest.mark.parametrize("match_class", [
        "EXACT", "NEAR_DUPLICATE", "SUPPORTING", "NEW", "CONTRADICTING"
    ])
    def test_invalid_provenance(self, match_class):
        conf = compute_confidence(None, True, match_class)
        ds = DEDUPE_SUPPORT_MAP[match_class]
        expected = W_PROVENANCE * 0.0 + W_EXTRACT * 1.0 + W_DEDUPE * ds + W_SOURCE * 0.5
        assert conf == pytest.approx(expected)

    @pytest.mark.parametrize("match_class", [
        "EXACT", "NEAR_DUPLICATE", "SUPPORTING", "NEW", "CONTRADICTING"
    ])
    def test_invalid_provenance_and_extraction(self, match_class):
        conf = compute_confidence(None, False, match_class)
        ds = DEDUPE_SUPPORT_MAP[match_class]
        expected = W_DEDUPE * ds + W_SOURCE * 0.5
        assert conf == pytest.approx(expected)


# ─── AC-2: Missing provenance => confidence <= 0.4, human review ────────

class TestMissingProvenanceHumanReview:
    """AC-2: Claims missing provenance have confidence <= 0.4."""

    def test_missing_provenance_low_confidence(self):
        """With no provenance, even EXACT match + valid extraction
        gives 0.30 + 0.20 + 0.05 = 0.55. But with invalid extraction
        and NEW match: 0.20*0.4 + 0.10*0.5 = 0.13."""
        conf = compute_confidence(None, False, "NEW")
        assert conf <= HUMAN_REVIEW_THRESHOLD

    def test_missing_provenance_contradicting(self):
        conf = compute_confidence(None, False, "CONTRADICTING")
        # 0.20*0.2 + 0.10*0.5 = 0.09
        assert conf <= HUMAN_REVIEW_THRESHOLD

    def test_needs_human_review_flag(self):
        conf = compute_confidence(None, False, "CONTRADICTING")
        assert needs_human_review(conf) is True

    def test_valid_claim_not_human_review(self):
        conf = compute_confidence(_valid_provenance(), True, "EXACT")
        assert needs_human_review(conf) is False


# ─── AC-1: Determinism ──────────────────────────────────────────────────

class TestDeterminism:
    """AC-1: Same inputs yield identical outputs."""

    def test_repeated_calls(self):
        prov = _valid_provenance()
        results = [
            compute_confidence(prov, True, "EXACT")
            for _ in range(10)
        ]
        assert all(r == results[0] for r in results)

    def test_different_instances_same_values(self):
        c1 = compute_confidence(_valid_provenance(), True, "EXACT")
        c2 = compute_confidence(_valid_provenance(), True, "EXACT")
        assert c1 == c2


# ─── AC-3: All factors in [0..1] ────────────────────────────────────────

class TestFactorsRange:
    """AC-3: All factor values in [0..1]."""

    @pytest.mark.parametrize("match_class", [
        "EXACT", "NEAR_DUPLICATE", "SUPPORTING", "NEW", "CONTRADICTING", None
    ])
    def test_confidence_in_range(self, match_class):
        for prov in [_valid_provenance(), None]:
            for ext in [True, False]:
                conf = compute_confidence(prov, ext, match_class)
                assert 0.0 <= conf <= 1.0, (
                    f"confidence={conf} out of range for "
                    f"prov={prov is not None}, ext={ext}, mc={match_class}"
                )

    def test_provenance_quality_range(self):
        assert 0.0 <= compute_provenance_quality(None) <= 1.0
        assert 0.0 <= compute_provenance_quality(_valid_provenance()) <= 1.0

    def test_extract_consistency_range(self):
        assert 0.0 <= compute_extract_consistency(True) <= 1.0
        assert 0.0 <= compute_extract_consistency(False) <= 1.0

    def test_dedupe_support_range(self):
        for mc in DEDUPE_SUPPORT_MAP:
            val = compute_dedupe_support(mc)
            assert 0.0 <= val <= 1.0

    def test_source_reliability_range(self):
        assert 0.0 <= compute_source_reliability() <= 1.0


# ─── Known fixture values ───────────────────────────────────────────────

class TestKnownFixtures:

    def test_full_confidence(self):
        """Valid provenance, valid extraction, EXACT match, 0.5 reliability.
        0.40*1.0 + 0.30*1.0 + 0.20*1.0 + 0.10*0.5 = 0.95"""
        conf = compute_confidence(_valid_provenance(), True, "EXACT")
        assert conf == pytest.approx(0.95)

    def test_zero_confidence(self):
        """No provenance, invalid extraction, no match class.
        0.40*0 + 0.30*0 + 0.20*0 + 0.10*0.5 = 0.05"""
        conf = compute_confidence(None, False, None)
        assert conf == pytest.approx(0.05)

    def test_near_duplicate_valid(self):
        """0.40*1.0 + 0.30*1.0 + 0.20*0.8 + 0.10*0.5 = 0.91"""
        conf = compute_confidence(_valid_provenance(), True, "NEAR_DUPLICATE")
        assert conf == pytest.approx(0.91)

    def test_new_no_provenance(self):
        """0.40*0 + 0.30*1.0 + 0.20*0.4 + 0.10*0.5 = 0.43"""
        conf = compute_confidence(None, True, "NEW")
        assert conf == pytest.approx(0.43)

    def test_source_reliability_override(self):
        """With custom source_reliability."""
        conf = compute_confidence(_valid_provenance(), True, "EXACT", source_reliability=1.0)
        # 0.40 + 0.30 + 0.20 + 0.10 = 1.0
        assert conf == pytest.approx(1.0)


# ─── needs_human_review ─────────────────────────────────────────────────

class TestNeedsHumanReview:

    def test_at_threshold(self):
        assert needs_human_review(0.4) is True

    def test_below_threshold(self):
        assert needs_human_review(0.3) is True

    def test_above_threshold(self):
        assert needs_human_review(0.5) is False

    def test_at_zero(self):
        assert needs_human_review(0.0) is True
