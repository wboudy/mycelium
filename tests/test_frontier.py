"""
Tests for the frontier command scoring engine (CMD-FRN-001, CMD-FRN-002).

Verifies:
  AC-CMD-FRN-001-1: Conflicts and open questions surfaced.
  AC-CMD-FRN-001-2: reading_targets sorted by numeric score.
  AC-CMD-FRN-002-1: Deterministic ordering for same inputs.
  AC-CMD-FRN-002-2: Each target includes factors with all five components in [0..1].
  AC-CMD-FRN-002-3: Tie-break ordering follows spec.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from mycelium.commands.frontier import (
    ERR_NO_FRONTIER_DATA,
    NEUTRAL_RELEVANCE,
    ReadingTarget,
    ScoringFactors,
    TargetData,
    clamp01,
    compute_conflict_factor,
    compute_factors,
    compute_goal_relevance,
    compute_novelty,
    compute_score,
    compute_staleness,
    compute_support_gap,
    execute_frontier,
    p75,
    rank_targets,
    validate_frontier_input,
)
from mycelium.models import ErrorObject


NOW = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)


# ─── Utilities ────────────────────────────────────────────────────────────

class TestClamp01:
    def test_in_range(self):
        assert clamp01(0.5) == 0.5

    def test_below_zero(self):
        assert clamp01(-0.1) == 0.0

    def test_above_one(self):
        assert clamp01(1.5) == 1.0

    def test_boundaries(self):
        assert clamp01(0.0) == 0.0
        assert clamp01(1.0) == 1.0


class TestP75:
    def test_empty(self):
        assert p75([]) == 0.0

    def test_single_value(self):
        assert p75([0.5]) == 0.5

    def test_two_values(self):
        # ceil(0.75*2)-1 = ceil(1.5)-1 = 2-1 = 1 -> second element
        assert p75([0.2, 0.8]) == 0.8

    def test_four_values(self):
        # ceil(0.75*4)-1 = ceil(3)-1 = 2 -> third element (0-indexed)
        assert p75([0.1, 0.2, 0.7, 0.9]) == 0.7

    def test_unsorted_input(self):
        assert p75([0.9, 0.1, 0.7, 0.2]) == 0.7

    def test_all_same(self):
        assert p75([0.5, 0.5, 0.5, 0.5]) == 0.5


# ─── Factor derivations ──────────────────────────────────────────────────

class TestConflictFactor:

    def test_no_conflicts_no_support(self):
        td = TargetData(target_id="t1", contradict_count=0, support_count=0)
        assert compute_conflict_factor(td) == 0.0

    def test_all_conflicts(self):
        td = TargetData(target_id="t1", contradict_count=5, support_count=0)
        assert compute_conflict_factor(td) == 1.0

    def test_mixed(self):
        td = TargetData(target_id="t1", contradict_count=2, support_count=3)
        assert compute_conflict_factor(td) == pytest.approx(0.4)

    def test_all_support(self):
        td = TargetData(target_id="t1", contradict_count=0, support_count=5)
        assert compute_conflict_factor(td) == 0.0


class TestSupportGap:

    def test_no_support(self):
        td = TargetData(target_id="t1", support_count=0)
        assert compute_support_gap(td) == 1.0

    def test_full_support(self):
        td = TargetData(target_id="t1", support_count=3)
        assert compute_support_gap(td) == 0.0

    def test_excess_support_clamped(self):
        td = TargetData(target_id="t1", support_count=10)
        assert compute_support_gap(td) == 0.0

    def test_partial_support(self):
        td = TargetData(target_id="t1", support_count=1)
        assert compute_support_gap(td) == pytest.approx(1.0 - 1.0/3.0)


class TestGoalRelevance:

    def test_no_inputs_neutral(self):
        td = TargetData(target_id="t1")
        assert compute_goal_relevance(td, None, None) == NEUTRAL_RELEVANCE

    def test_empty_tags_neutral(self):
        td = TargetData(target_id="t1")
        assert compute_goal_relevance(td, None, []) == NEUTRAL_RELEVANCE

    def test_project_match(self):
        td = TargetData(target_id="t1", project="proj-a")
        result = compute_goal_relevance(td, "proj-a", None)
        # project_match=1.0, tag_overlap=0.5 (omitted)
        # 0.6*1.0 + 0.4*0.5 = 0.8
        assert result == pytest.approx(0.8)

    def test_project_mismatch(self):
        td = TargetData(target_id="t1", project="proj-b")
        result = compute_goal_relevance(td, "proj-a", None)
        # project_match=0.0, tag_overlap=0.5
        # 0.6*0.0 + 0.4*0.5 = 0.2
        assert result == pytest.approx(0.2)

    def test_project_absent_on_target(self):
        td = TargetData(target_id="t1", project=None)
        result = compute_goal_relevance(td, "proj-a", None)
        # project_match=0.5, tag_overlap=0.5
        assert result == pytest.approx(0.5)

    def test_full_tag_overlap(self):
        td = TargetData(target_id="t1", tags=["a", "b", "c"])
        result = compute_goal_relevance(td, None, ["a", "b", "c"])
        # project=0.5, tag_overlap=1.0
        # 0.6*0.5 + 0.4*1.0 = 0.7
        assert result == pytest.approx(0.7)

    def test_partial_tag_overlap(self):
        td = TargetData(target_id="t1", tags=["a", "b"])
        result = compute_goal_relevance(td, None, ["a", "c"])
        # project=0.5, tag_overlap=1/2=0.5
        # 0.6*0.5 + 0.4*0.5 = 0.5
        assert result == pytest.approx(0.5)

    def test_no_tag_overlap(self):
        td = TargetData(target_id="t1", tags=["x"])
        result = compute_goal_relevance(td, None, ["a", "b"])
        # project=0.5, tag_overlap=0/2=0.0
        # 0.6*0.5 + 0.4*0.0 = 0.3
        assert result == pytest.approx(0.3)


class TestNovelty:

    def test_empty_scores(self):
        td = TargetData(target_id="t1", linked_delta_novelty_scores=[])
        assert compute_novelty(td) == 0.0

    def test_single_score(self):
        td = TargetData(target_id="t1", linked_delta_novelty_scores=[0.6])
        assert compute_novelty(td) == pytest.approx(0.6)

    def test_p75_of_multiple(self):
        td = TargetData(target_id="t1",
                        linked_delta_novelty_scores=[0.1, 0.2, 0.7, 0.9])
        assert compute_novelty(td) == pytest.approx(0.7)

    def test_clamped_above_one(self):
        td = TargetData(target_id="t1", linked_delta_novelty_scores=[1.5])
        assert compute_novelty(td) == 1.0


class TestStaleness:

    def test_just_reviewed(self):
        td = TargetData(target_id="t1", last_reviewed_at=NOW)
        assert compute_staleness(td, NOW) == 0.0

    def test_max_stale(self):
        td = TargetData(target_id="t1",
                        last_reviewed_at=NOW - timedelta(days=90))
        assert compute_staleness(td, NOW) == 1.0

    def test_half_stale(self):
        td = TargetData(target_id="t1",
                        last_reviewed_at=NOW - timedelta(days=22.5))
        assert compute_staleness(td, NOW) == pytest.approx(0.5)

    def test_no_review_ts_max_stale(self):
        td = TargetData(target_id="t1")
        assert compute_staleness(td, NOW) == 1.0

    def test_uses_updated_as_fallback(self):
        td = TargetData(target_id="t1",
                        updated=NOW - timedelta(days=9))
        assert compute_staleness(td, NOW) == pytest.approx(9.0 / 45.0)


# ─── compute_score ────────────────────────────────────────────────────────

class TestComputeScore:

    def test_all_zeros(self):
        f = ScoringFactors(0, 0, 0, 0, 0)
        assert compute_score(f) == 0.0

    def test_all_ones(self):
        f = ScoringFactors(1, 1, 1, 1, 1)
        assert compute_score(f) == 100.0

    def test_only_conflict(self):
        f = ScoringFactors(conflict_factor=1.0, support_gap=0,
                           goal_relevance=0, novelty=0, staleness=0)
        assert compute_score(f) == pytest.approx(35.0)

    def test_clamped_to_100(self):
        # Even with all 1.0 factors, max is 100
        f = ScoringFactors(1, 1, 1, 1, 1)
        assert compute_score(f) <= 100.0


# ─── AC-CMD-FRN-002-2: Factors in [0..1] ─────────────────────────────────

class TestFactorsRange:
    """AC-CMD-FRN-002-2: Each factor must be in [0..1]."""

    def test_all_factors_in_range(self):
        td = TargetData(
            target_id="t1",
            contradict_count=3,
            support_count=2,
            project="p",
            tags=["a"],
            linked_delta_novelty_scores=[0.3, 0.8],
            last_reviewed_at=NOW - timedelta(days=10),
        )
        f = compute_factors(td, NOW, "p", ["a", "b"])
        for name in ("conflict_factor", "support_gap", "goal_relevance",
                      "novelty", "staleness"):
            val = getattr(f, name)
            assert 0.0 <= val <= 1.0, f"{name}={val} out of [0,1]"

    def test_factors_dict_has_all_five(self):
        td = TargetData(target_id="t1")
        f = compute_factors(td, NOW)
        d = f.to_dict()
        assert set(d.keys()) == {
            "conflict_factor", "support_gap", "goal_relevance",
            "novelty", "staleness"
        }


# ─── AC-CMD-FRN-002-1: Deterministic ordering ────────────────────────────

class TestDeterministicOrdering:
    """AC-CMD-FRN-002-1: Repeated runs produce identical ordering."""

    def _make_targets(self):
        return [
            TargetData("t1", contradict_count=3, support_count=1,
                        last_reviewed_at=NOW - timedelta(days=20)),
            TargetData("t2", contradict_count=1, support_count=2,
                        last_reviewed_at=NOW - timedelta(days=5)),
            TargetData("t3", contradict_count=2, support_count=0,
                        last_reviewed_at=NOW - timedelta(days=30)),
        ]

    def test_repeated_runs_identical(self):
        targets = self._make_targets()
        r1 = rank_targets(targets, NOW)
        r2 = rank_targets(targets, NOW)
        assert [rt.target_id for rt in r1] == [rt.target_id for rt in r2]
        assert [rt.score for rt in r1] == [rt.score for rt in r2]

    def test_order_is_stable(self):
        """Multiple runs with shuffled input order produce same output."""
        targets = self._make_targets()
        r1 = rank_targets(targets, NOW)
        targets_reversed = list(reversed(targets))
        r2 = rank_targets(targets_reversed, NOW)
        assert [rt.target_id for rt in r1] == [rt.target_id for rt in r2]


# ─── AC-CMD-FRN-001-2: Sorted by score ───────────────────────────────────

class TestSortedByScore:
    """AC-CMD-FRN-001-2: reading_targets sorted by score descending."""

    def test_highest_score_first(self):
        targets = [
            TargetData("low", contradict_count=0, support_count=3,
                        last_reviewed_at=NOW),
            TargetData("high", contradict_count=5, support_count=0,
                        last_reviewed_at=NOW - timedelta(days=45)),
        ]
        result = rank_targets(targets, NOW)
        assert result[0].target_id == "high"
        assert result[0].score >= result[1].score


# ─── AC-CMD-FRN-002-3: Tie-breaking ──────────────────────────────────────

class TestTieBreaking:
    """AC-CMD-FRN-002-3: Equal score breaks by conflict_factor, then
    older review_ts, then lexical target_id."""

    def test_tiebreak_by_conflict_factor(self):
        targets = [
            TargetData("a", contradict_count=1, support_count=1,
                        last_reviewed_at=NOW),
            TargetData("b", contradict_count=2, support_count=0,
                        last_reviewed_at=NOW),
        ]
        # Both may have similar overall scores but different conflict_factor
        result = rank_targets(targets, NOW)
        # Higher conflict_factor should come first among equal scores
        assert result[0].factors.conflict_factor >= result[1].factors.conflict_factor

    def test_tiebreak_by_lexical_id(self):
        """Identical data → lexical target_id breaks tie."""
        targets = [
            TargetData("z-target"),
            TargetData("a-target"),
        ]
        result = rank_targets(targets, NOW)
        # Same score, same conflict_factor, same review_ts → lexical
        assert result[0].target_id == "a-target"
        assert result[1].target_id == "z-target"


# ─── Limit ────────────────────────────────────────────────────────────────

class TestLimit:

    def test_limit_applied(self):
        targets = [TargetData(f"t{i}") for i in range(10)]
        result = rank_targets(targets, NOW, limit=3)
        assert len(result) == 3

    def test_limit_none_returns_all(self):
        targets = [TargetData(f"t{i}") for i in range(5)]
        result = rank_targets(targets, NOW, limit=None)
        assert len(result) == 5


# ─── ReadingTarget serialization ──────────────────────────────────────────

class TestReadingTarget:

    def test_to_dict(self):
        f = ScoringFactors(0.5, 0.3, 0.7, 0.1, 0.4)
        rt = ReadingTarget(
            target_id="t1", score=42.0, factors=f,
            rationale="test", citations=["c1"],
        )
        d = rt.to_dict()
        assert d["target"] == "t1"
        assert d["score"] == 42.0
        assert d["rationale"] == "test"
        assert d["citations"] == ["c1"]
        assert set(d["factors"].keys()) == {
            "conflict_factor", "support_gap", "goal_relevance",
            "novelty", "staleness"
        }


# ─── execute_frontier ────────────────────────────────────────────────────

class TestExecuteFrontier:

    def test_valid_input_returns_envelope(self):
        env = execute_frontier({})
        assert env.ok is True
        assert env.command == "frontier"

    def test_output_data_structure(self):
        env = execute_frontier({})
        assert "conflicts" in env.data
        assert "weak_support" in env.data
        assert "open_questions" in env.data
        assert "reading_targets" in env.data
        assert "explanations" in env.data

    def test_invalid_limit(self):
        env = execute_frontier({"limit": 0})
        assert env.ok is False

    def test_invalid_tags_type(self):
        env = execute_frontier({"tags": "not-a-list"})
        assert env.ok is False

    def test_envelope_keys(self):
        env = execute_frontier({})
        d = env.to_dict()
        assert set(d.keys()) == {
            "ok", "command", "timestamp", "data",
            "errors", "warnings", "trace"
        }
