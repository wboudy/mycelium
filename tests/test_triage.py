"""
Tests for triage scoring with deterministic formula, buckets, and hysteresis.

Verifies:
  AC-MVP3-1-TRIAGE-1: Score matches formula exactly.
  AC-MVP3-1-TRIAGE-2: Bucket thresholds classify correctly.
  AC-MVP3-1-TRIAGE-3: Dense->mixed requires 2 consecutive sub-0.62 evaluations.
  AC-MVP3-1-TRIAGE-4: Watery->mixed on first evaluation with score >= 0.42.
  AC-MVP3-1-TRIAGE-5: Same input yields identical results (determinism).
"""

from __future__ import annotations

import pytest

from mycelium.triage import (
    HYSTERESIS_DENSE_CONSECUTIVE,
    HYSTERESIS_DENSE_EXIT,
    HYSTERESIS_WATERY_ENTRY,
    THRESHOLD_DENSE,
    THRESHOLD_MIXED_LOW,
    TriageBucket,
    TriageResult,
    TriageState,
    apply_hysteresis,
    clamp01,
    classify_bucket,
    compute_triage_score,
    evaluate_triage,
)


# ─── AC-MVP3-1-TRIAGE-1: Score formula ──────────────────────────────────

class TestScoreFormula:
    """AC-MVP3-1-TRIAGE-1: Score matches formula exactly."""

    def test_all_zeros(self):
        score = compute_triage_score(0.0, 0.0, 0.0, 0.0)
        assert score == 0.0

    def test_all_ones(self):
        score = compute_triage_score(1.0, 1.0, 1.0, 1.0)
        assert score == pytest.approx(1.0)

    def test_known_fixture(self):
        # 0.45*0.6 + 0.25*0.4 + 0.20*0.8 + 0.10*0.3
        # = 0.27 + 0.10 + 0.16 + 0.03 = 0.56
        score = compute_triage_score(0.6, 0.4, 0.8, 0.3)
        assert score == pytest.approx(0.56)

    def test_only_conflict(self):
        score = compute_triage_score(1.0, 0.0, 0.0, 0.0)
        assert score == pytest.approx(0.45)

    def test_only_support_gap(self):
        score = compute_triage_score(0.0, 1.0, 0.0, 0.0)
        assert score == pytest.approx(0.25)

    def test_only_novelty(self):
        score = compute_triage_score(0.0, 0.0, 1.0, 0.0)
        assert score == pytest.approx(0.20)

    def test_only_staleness(self):
        score = compute_triage_score(0.0, 0.0, 0.0, 1.0)
        assert score == pytest.approx(0.10)

    def test_clamped_above_one(self):
        # Even with extreme inputs, clamp to 1.0
        score = compute_triage_score(2.0, 2.0, 2.0, 2.0)
        assert score == 1.0

    def test_clamped_below_zero(self):
        score = compute_triage_score(-1.0, -1.0, -1.0, -1.0)
        assert score == 0.0


# ─── AC-MVP3-1-TRIAGE-2: Bucket classification ──────────────────────────

class TestBucketClassification:
    """AC-MVP3-1-TRIAGE-2: Bucket thresholds classify correctly."""

    def test_dense_at_threshold(self):
        assert classify_bucket(0.67) == TriageBucket.DENSE

    def test_dense_above_threshold(self):
        assert classify_bucket(0.90) == TriageBucket.DENSE

    def test_dense_at_one(self):
        assert classify_bucket(1.0) == TriageBucket.DENSE

    def test_mixed_at_lower_threshold(self):
        assert classify_bucket(0.34) == TriageBucket.MIXED

    def test_mixed_mid(self):
        assert classify_bucket(0.50) == TriageBucket.MIXED

    def test_mixed_just_below_dense(self):
        assert classify_bucket(0.669) == TriageBucket.MIXED

    def test_watery_below_threshold(self):
        assert classify_bucket(0.339) == TriageBucket.WATERY

    def test_watery_at_zero(self):
        assert classify_bucket(0.0) == TriageBucket.WATERY

    def test_watery_low(self):
        assert classify_bucket(0.10) == TriageBucket.WATERY


# ─── AC-MVP3-1-TRIAGE-3: Dense->mixed hysteresis ────────────────────────

class TestDenseHysteresis:
    """AC-MVP3-1-TRIAGE-3: dense->mixed requires 2 consecutive sub-0.62."""

    def test_single_sub062_stays_dense(self):
        """Single sub-0.62 evaluation does NOT transition out of dense."""
        state = TriageState(current_bucket=TriageBucket.DENSE)
        result = apply_hysteresis(state, 0.50)
        assert state.current_bucket == TriageBucket.DENSE
        assert state.consecutive_below_dense_exit == 1

    def test_two_consecutive_transitions(self):
        """Two consecutive sub-0.62 evaluations DO transition out of dense."""
        state = TriageState(current_bucket=TriageBucket.DENSE)
        apply_hysteresis(state, 0.50)
        assert state.current_bucket == TriageBucket.DENSE

        result = apply_hysteresis(state, 0.40)
        assert state.current_bucket != TriageBucket.DENSE

    def test_interrupted_resets_counter(self):
        """A score >= 0.62 between two sub-0.62 resets the counter."""
        state = TriageState(current_bucket=TriageBucket.DENSE)
        apply_hysteresis(state, 0.50)  # sub-0.62, count=1
        assert state.consecutive_below_dense_exit == 1

        apply_hysteresis(state, 0.70)  # above 0.62 (and dense), resets
        assert state.consecutive_below_dense_exit == 0

        apply_hysteresis(state, 0.50)  # sub-0.62 again, count=1
        assert state.current_bucket == TriageBucket.DENSE
        assert state.consecutive_below_dense_exit == 1

    def test_dense_stays_with_high_score(self):
        state = TriageState(current_bucket=TriageBucket.DENSE)
        apply_hysteresis(state, 0.80)
        assert state.current_bucket == TriageBucket.DENSE

    def test_dense_exit_consecutive_count(self):
        assert HYSTERESIS_DENSE_CONSECUTIVE == 2


# ─── AC-MVP3-1-TRIAGE-4: Watery->mixed hysteresis ───────────────────────

class TestWateryHysteresis:
    """AC-MVP3-1-TRIAGE-4: watery->mixed on first score >= 0.42."""

    def test_first_above_042_transitions(self):
        state = TriageState(current_bucket=TriageBucket.WATERY)
        result = apply_hysteresis(state, 0.42)
        assert state.current_bucket == TriageBucket.MIXED

    def test_above_042_transitions(self):
        state = TriageState(current_bucket=TriageBucket.WATERY)
        result = apply_hysteresis(state, 0.50)
        assert state.current_bucket == TriageBucket.MIXED

    def test_below_042_stays_watery(self):
        state = TriageState(current_bucket=TriageBucket.WATERY)
        result = apply_hysteresis(state, 0.30)
        assert state.current_bucket == TriageBucket.WATERY

    def test_watery_stays_at_zero(self):
        state = TriageState(current_bucket=TriageBucket.WATERY)
        result = apply_hysteresis(state, 0.0)
        assert state.current_bucket == TriageBucket.WATERY


# ─── AC-MVP3-1-TRIAGE-5: Determinism ────────────────────────────────────

class TestDeterminism:
    """AC-MVP3-1-TRIAGE-5: Same input yields identical results."""

    def test_score_deterministic(self):
        s1 = compute_triage_score(0.5, 0.3, 0.7, 0.1)
        s2 = compute_triage_score(0.5, 0.3, 0.7, 0.1)
        assert s1 == s2

    def test_bucket_deterministic(self):
        b1 = classify_bucket(0.55)
        b2 = classify_bucket(0.55)
        assert b1 == b2

    def test_evaluate_deterministic(self):
        r1 = evaluate_triage(0.5, 0.3, 0.7, 0.1)
        r2 = evaluate_triage(0.5, 0.3, 0.7, 0.1)
        assert r1.score == r2.score
        assert r1.bucket == r2.bucket

    def test_repeated_evaluation(self):
        results = [
            evaluate_triage(0.8, 0.6, 0.4, 0.2)
            for _ in range(10)
        ]
        assert all(r.score == results[0].score for r in results)
        assert all(r.bucket == results[0].bucket for r in results)


# ─── Mixed bucket (no hysteresis) ───────────────────────────────────────

class TestMixedBucket:

    def test_mixed_follows_raw(self):
        state = TriageState(current_bucket=TriageBucket.MIXED)
        apply_hysteresis(state, 0.80)
        assert state.current_bucket == TriageBucket.DENSE

    def test_mixed_drops_to_watery(self):
        state = TriageState(current_bucket=TriageBucket.MIXED)
        apply_hysteresis(state, 0.10)
        assert state.current_bucket == TriageBucket.WATERY

    def test_mixed_stays_mixed(self):
        state = TriageState(current_bucket=TriageBucket.MIXED)
        apply_hysteresis(state, 0.50)
        assert state.current_bucket == TriageBucket.MIXED


# ─── Serialization ──────────────────────────────────────────────────────

class TestSerialization:

    def test_triage_result_to_dict(self):
        r = TriageResult(score=0.56, bucket=TriageBucket.MIXED)
        d = r.to_dict()
        assert d == {"score": 0.56, "bucket": "mixed"}

    def test_triage_state_to_dict(self):
        s = TriageState(
            current_bucket=TriageBucket.DENSE,
            consecutive_below_dense_exit=1,
        )
        d = s.to_dict()
        assert d == {
            "current_bucket": "dense",
            "consecutive_below_dense_exit": 1,
        }


# ─── evaluate_triage integration ────────────────────────────────────────

class TestEvaluateTriage:

    def test_returns_result(self):
        r = evaluate_triage(0.6, 0.4, 0.8, 0.3)
        assert isinstance(r, TriageResult)
        assert r.score == pytest.approx(0.56)
        assert r.bucket == TriageBucket.MIXED

    def test_dense_result(self):
        r = evaluate_triage(1.0, 1.0, 1.0, 1.0)
        assert r.bucket == TriageBucket.DENSE

    def test_watery_result(self):
        r = evaluate_triage(0.0, 0.0, 0.0, 0.0)
        assert r.bucket == TriageBucket.WATERY
