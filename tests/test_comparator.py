"""
Tests for match class assignment comparator (DED-002).

Acceptance Criteria:
- AC-1: Each claim gets exactly one match_class in {EXACT, NEAR_DUPLICATE,
         SUPPORTING, CONTRADICTING, NEW}.
- AC-2: Total Match Records across all match_groups == total_extracted_claims.
- AC-3: Each MatchRecord includes match_class and similarity in [0..1].
- AC-4: Threshold bands enforced: EXACT >= 0.97, NEAR_DUP [0.85, 0.97), NEW < 0.70.
- AC-5: Same inputs → same similarity scores (determinism).
"""

from __future__ import annotations

import pytest

from mycelium.comparator import (
    CompareResult,
    MatchClass,
    MatchRecord,
    classify_similarity,
    compare_claim,
    compare_claims,
)


# ---------------------------------------------------------------------------
# AC-1: Exactly one match class per claim
# ---------------------------------------------------------------------------

class TestExactlyOneClass:
    """AC-1: Each extracted claim receives exactly one match_class."""

    def test_all_match_classes_valid(self):
        valid = {"EXACT", "NEAR_DUPLICATE", "SUPPORTING", "CONTRADICTING", "NEW"}
        for mc in MatchClass:
            assert mc.value in valid

    def test_classify_returns_single_class(self):
        for sim in [0.0, 0.50, 0.70, 0.85, 0.97, 1.0]:
            result = classify_similarity(sim)
            assert isinstance(result, MatchClass)

    def test_compare_claim_returns_single_record(self):
        record = compare_claim("test claim", [])
        assert isinstance(record, MatchRecord)
        assert isinstance(record.match_class, MatchClass)


# ---------------------------------------------------------------------------
# AC-2: Total records == total claims
# ---------------------------------------------------------------------------

class TestTotalCount:
    """AC-DED-002-1: match records total equals total_extracted_claims."""

    def test_empty_input(self):
        result = compare_claims([], [])
        assert result.total == 0

    def test_single_claim(self):
        result = compare_claims(["claim one"], [])
        assert result.total == 1

    def test_multiple_claims(self):
        claims = ["claim A", "claim B", "claim C"]
        result = compare_claims(claims, [])
        assert result.total == len(claims)

    def test_claims_with_existing(self):
        existing = [{"id": "c1", "text": "claim A"}]
        claims = ["claim A", "claim B", "totally new"]
        result = compare_claims(claims, existing)
        assert result.total == len(claims)

    def test_to_dict_counts_match(self):
        claims = ["x", "y", "z"]
        result = compare_claims(claims, [])
        d = result.to_dict()
        assert d["counts"]["total_extracted_claims"] == len(claims)
        group_sum = sum(
            d["counts"][mc.value] for mc in MatchClass
        )
        assert group_sum == len(claims)


# ---------------------------------------------------------------------------
# AC-3: MatchRecord includes match_class and similarity in [0..1]
# ---------------------------------------------------------------------------

class TestMatchRecordFields:
    """AC-DED-002-2: each record has match_class and similarity in [0..1]."""

    def test_record_has_required_fields(self):
        record = MatchRecord(
            match_class=MatchClass.NEW,
            similarity=0.0,
            extracted_claim_key="h-abc123def456",
        )
        d = record.to_dict()
        assert "match_class" in d
        assert "similarity" in d
        assert "extracted_claim_key" in d

    def test_similarity_in_range(self):
        for sim in [0.0, 0.25, 0.5, 0.75, 1.0]:
            record = MatchRecord(
                match_class=classify_similarity(sim),
                similarity=sim,
                extracted_claim_key="h-000000000000",
            )
            assert 0.0 <= record.similarity <= 1.0

    def test_match_class_is_valid_enum(self):
        record = compare_claim("something", [])
        assert record.match_class.value in {mc.value for mc in MatchClass}

    def test_compare_result_records_all_valid(self):
        claims = ["a", "b"]
        result = compare_claims(claims, [])
        for group_name, records in result.match_groups.items():
            for rec in records:
                assert 0.0 <= rec.similarity <= 1.0
                assert rec.match_class.value == group_name


# ---------------------------------------------------------------------------
# AC-4: Threshold bands
# ---------------------------------------------------------------------------

class TestThresholdBands:
    """AC-4: Similarity thresholds produce correct classifications."""

    @pytest.mark.parametrize(
        "similarity, expected_class",
        [
            (1.0, MatchClass.EXACT),
            (0.99, MatchClass.EXACT),
            (0.97, MatchClass.EXACT),
            (0.969, MatchClass.NEAR_DUPLICATE),
            (0.90, MatchClass.NEAR_DUPLICATE),
            (0.85, MatchClass.NEAR_DUPLICATE),
            (0.849, MatchClass.SUPPORTING),
            (0.75, MatchClass.SUPPORTING),
            (0.70, MatchClass.SUPPORTING),
            (0.699, MatchClass.NEW),
            (0.50, MatchClass.NEW),
            (0.0, MatchClass.NEW),
        ],
        ids=[
            "exact-1.0", "exact-0.99", "exact-boundary-0.97",
            "near-dup-0.969", "near-dup-0.90", "near-dup-boundary-0.85",
            "supporting-0.849", "supporting-0.75", "supporting-boundary-0.70",
            "new-0.699", "new-0.50", "new-0.0",
        ],
    )
    def test_classify_threshold(self, similarity: float, expected_class: MatchClass):
        assert classify_similarity(similarity) == expected_class

    def test_invalid_similarity_too_high(self):
        with pytest.raises(ValueError, match="similarity must be in"):
            classify_similarity(1.01)

    def test_invalid_similarity_negative(self):
        with pytest.raises(ValueError, match="similarity must be in"):
            classify_similarity(-0.01)


# ---------------------------------------------------------------------------
# AC-5: Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    """AC-5: Same inputs → same similarity scores and classifications."""

    def test_classify_deterministic(self):
        for sim in [0.0, 0.5, 0.7, 0.85, 0.97, 1.0]:
            results = [classify_similarity(sim) for _ in range(10)]
            assert len(set(results)) == 1

    def test_compare_claim_deterministic(self):
        existing = [{"id": "c1", "text": "the quick brown fox"}]
        text = "the quick brown fox"
        records = [compare_claim(text, existing) for _ in range(5)]
        sims = [r.similarity for r in records]
        classes = [r.match_class for r in records]
        assert len(set(sims)) == 1
        assert len(set(classes)) == 1

    def test_compare_claims_deterministic(self):
        claims = ["alpha", "beta"]
        existing = [{"id": "c1", "text": "alpha"}]
        r1 = compare_claims(claims, existing)
        r2 = compare_claims(claims, existing)
        assert r1.to_dict() == r2.to_dict()


# ---------------------------------------------------------------------------
# Integration: compare_claim with similarity
# ---------------------------------------------------------------------------

class TestCompareClaim:

    def test_exact_match(self):
        """Identical text → EXACT class."""
        existing = [{"id": "c1", "text": "The earth is round."}]
        record = compare_claim("The earth is round.", existing)
        assert record.match_class == MatchClass.EXACT
        assert record.similarity == 1.0
        assert record.existing_claim_id == "c1"

    def test_no_existing_claims(self):
        """No existing claims → NEW."""
        record = compare_claim("brand new claim", [])
        assert record.match_class == MatchClass.NEW
        assert record.similarity == 0.0
        assert record.existing_claim_id is None

    def test_whitespace_variant_is_exact(self):
        """Canonicalization makes whitespace variants exact matches."""
        existing = [{"id": "c1", "text": "hello world"}]
        record = compare_claim("hello   world", existing)
        assert record.match_class == MatchClass.EXACT
        assert record.similarity == 1.0

    def test_custom_similarity_fn(self):
        """Custom similarity function is used when provided."""
        def always_half(a: str, b: str) -> float:
            return 0.5

        existing = [{"id": "c1", "text": "anything"}]
        record = compare_claim("test", existing, similarity_fn=always_half)
        assert record.similarity == 0.5
        assert record.match_class == MatchClass.NEW  # 0.5 < 0.70

    def test_best_match_selected(self):
        """When multiple existing claims, best similarity wins."""
        existing = [
            {"id": "c1", "text": "completely different topic"},
            {"id": "c2", "text": "the quick brown fox jumps"},
        ]
        record = compare_claim("the quick brown fox leaps", existing)
        assert record.existing_claim_id == "c2"
        assert record.similarity > 0.0


# ---------------------------------------------------------------------------
# CompareResult grouping
# ---------------------------------------------------------------------------

class TestCompareResult:

    def test_groups_initialized(self):
        result = CompareResult()
        for mc in MatchClass:
            assert mc.value in result.match_groups

    def test_add_record(self):
        result = CompareResult()
        rec = MatchRecord(
            match_class=MatchClass.NEW,
            similarity=0.0,
            extracted_claim_key="h-aabbccddeeff",
        )
        result.add(rec)
        assert result.total == 1
        assert len(result.match_groups["NEW"]) == 1

    def test_to_dict_structure(self):
        result = CompareResult()
        rec = MatchRecord(
            match_class=MatchClass.EXACT,
            similarity=1.0,
            extracted_claim_key="h-112233445566",
            existing_claim_id="c1",
        )
        result.add(rec)
        d = result.to_dict()
        assert "match_groups" in d
        assert "counts" in d
        assert d["counts"]["total_extracted_claims"] == 1
        assert d["counts"]["EXACT"] == 1
