"""
Tests for deterministic novelty scoring (DEL-002).

Acceptance Criteria:
- AC-1 (AC-DEL-002-1): Recomputed formula matches stored score within 1e-9.
- AC-2 (AC-DEL-002-2): novelty_score == 0 when total_extracted_claims == 0.
- AC-3: novelty_score always in [0..1].
- AC-4: Uses only new_count + contradicting_count from counts.
- AC-5: Edge cases: all-new, all-exact, mixed, zero-claims.
"""

from __future__ import annotations

import pytest

from mycelium.novelty import compute_novelty_score


# ---------------------------------------------------------------------------
# AC-1: Formula verification
# ---------------------------------------------------------------------------

class TestFormulaMatch:
    """AC-DEL-002-1: recomputed formula matches expected score."""

    def test_basic_computation(self):
        score = compute_novelty_score(new_count=3, contradicting_count=2, total_extracted_claims=10)
        expected = (3 + 2) / max(1, 10)
        assert abs(score - expected) < 1e-9

    def test_exact_formula(self):
        """Verify exact formula: (new + contradicting) / max(1, total)."""
        for new, contra, total in [
            (0, 0, 10),
            (5, 0, 10),
            (0, 3, 10),
            (7, 3, 10),
            (1, 0, 1),
            (100, 50, 200),
        ]:
            score = compute_novelty_score(new, contra, total)
            expected = (new + contra) / max(1, total)
            assert abs(score - expected) < 1e-9, (
                f"Mismatch for new={new}, contra={contra}, total={total}: "
                f"got {score}, expected {expected}"
            )

    def test_deterministic_repeated_calls(self):
        scores = [compute_novelty_score(5, 3, 20) for _ in range(10)]
        assert len(set(scores)) == 1


# ---------------------------------------------------------------------------
# AC-2: Zero claims → score 0
# ---------------------------------------------------------------------------

class TestZeroClaims:
    """AC-DEL-002-2: novelty_score == 0 when total_extracted_claims == 0."""

    def test_zero_total(self):
        assert compute_novelty_score(0, 0, 0) == 0.0

    def test_zero_total_returns_float(self):
        result = compute_novelty_score(0, 0, 0)
        assert isinstance(result, float)


# ---------------------------------------------------------------------------
# AC-3: Score in [0, 1]
# ---------------------------------------------------------------------------

class TestRange:
    """AC-3: novelty_score is always in [0..1]."""

    @pytest.mark.parametrize(
        "new, contra, total",
        [
            (0, 0, 10),    # 0.0
            (5, 5, 10),    # 1.0
            (10, 0, 10),   # 1.0
            (0, 10, 10),   # 1.0
            (3, 2, 100),   # 0.05
            (0, 0, 0),     # 0.0
        ],
    )
    def test_in_range(self, new: int, contra: int, total: int):
        score = compute_novelty_score(new, contra, total)
        assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# AC-4: Only uses new_count + contradicting_count
# ---------------------------------------------------------------------------

class TestInputsOnly:
    """AC-4: computation uses only new_count + contradicting_count."""

    def test_exact_count_irrelevant(self):
        """Changing exact/near_dup/supporting counts doesn't affect score
        as long as new + contradicting + total stay the same."""
        # Same new, contradicting, total → same score regardless of
        # how the remaining claims are distributed.
        score = compute_novelty_score(new_count=2, contradicting_count=1, total_extracted_claims=10)
        expected = 3 / 10
        assert abs(score - expected) < 1e-9


# ---------------------------------------------------------------------------
# AC-5: Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """AC-5: all-new, all-exact, mixed, zero-claims."""

    def test_all_new(self):
        """All claims are NEW → score 1.0."""
        score = compute_novelty_score(10, 0, 10)
        assert abs(score - 1.0) < 1e-9

    def test_all_exact(self):
        """All claims are EXACT (none new/contradicting) → score 0.0."""
        score = compute_novelty_score(0, 0, 10)
        assert abs(score - 0.0) < 1e-9

    def test_all_contradicting(self):
        """All claims are CONTRADICTING → score 1.0."""
        score = compute_novelty_score(0, 10, 10)
        assert abs(score - 1.0) < 1e-9

    def test_mixed(self):
        """Mix of new and contradicting with other types."""
        # 3 new + 2 contradicting out of 20 total
        score = compute_novelty_score(3, 2, 20)
        assert abs(score - 0.25) < 1e-9

    def test_single_claim_new(self):
        score = compute_novelty_score(1, 0, 1)
        assert abs(score - 1.0) < 1e-9

    def test_single_claim_exact(self):
        score = compute_novelty_score(0, 0, 1)
        assert abs(score - 0.0) < 1e-9

    def test_negative_count_raises(self):
        with pytest.raises(ValueError, match="non-negative"):
            compute_novelty_score(-1, 0, 10)

    def test_negative_contradicting_raises(self):
        with pytest.raises(ValueError, match="non-negative"):
            compute_novelty_score(0, -1, 10)

    def test_negative_total_raises(self):
        with pytest.raises(ValueError, match="non-negative"):
            compute_novelty_score(0, 0, -1)
