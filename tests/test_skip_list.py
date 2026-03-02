"""
Tests for skip-list lifecycle with entry criteria, safety cap, and auto-resurface.

Verifies:
  AC-MVP3-1-SKIP-1: Entry enforces all 5 conditions simultaneously.
  AC-MVP3-1-SKIP-2: Removal triggers on each of 4 events.
  AC-MVP3-1-SKIP-3: Safety cap at 20% is enforced.
  AC-MVP3-1-SKIP-4: Skipped targets retrievable with include_skip=True.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from mycelium.skip_list import (
    CONSECUTIVE_WATERY_REQUIRED,
    DEFAULT_SKIP_DURATION_DAYS,
    MIN_TARGET_AGE_DAYS,
    SAFETY_CAP_RATIO,
    EntryCheck,
    SkipEntry,
    SkipList,
    TargetState,
    check_entry_criteria,
    check_removal_triggers,
    filter_targets,
    process_removals,
)


def _eligible_target(target_id: str = "t1") -> TargetState:
    """Build a target that meets all entry criteria."""
    return TargetState(
        target_id=target_id,
        consecutive_watery=3,
        conflict_factor=0.0,
        open_question_count=0,
        manually_pinned=False,
        target_age_days=14,
    )


# ─── AC-MVP3-1-SKIP-1: Entry criteria ───────────────────────────────────

class TestEntryCriteria:
    """AC-MVP3-1-SKIP-1: All 5 conditions enforced simultaneously."""

    def test_eligible_target(self):
        check = check_entry_criteria(_eligible_target())
        assert check.eligible is True
        assert check.violations == []

    def test_insufficient_watery(self):
        t = _eligible_target()
        t.consecutive_watery = 2
        check = check_entry_criteria(t)
        assert check.eligible is False
        assert any("consecutive_watery" in v for v in check.violations)

    def test_nonzero_conflict_factor(self):
        t = _eligible_target()
        t.conflict_factor = 0.1
        check = check_entry_criteria(t)
        assert check.eligible is False
        assert any("conflict_factor" in v for v in check.violations)

    def test_open_questions_present(self):
        t = _eligible_target()
        t.open_question_count = 1
        check = check_entry_criteria(t)
        assert check.eligible is False
        assert any("open_question_count" in v for v in check.violations)

    def test_manually_pinned(self):
        t = _eligible_target()
        t.manually_pinned = True
        check = check_entry_criteria(t)
        assert check.eligible is False
        assert any("pinned" in v for v in check.violations)

    def test_too_young(self):
        t = _eligible_target()
        t.target_age_days = 13
        check = check_entry_criteria(t)
        assert check.eligible is False
        assert any("target_age_days" in v for v in check.violations)

    def test_multiple_violations(self):
        t = TargetState(
            target_id="t1",
            consecutive_watery=1,
            conflict_factor=0.5,
            open_question_count=2,
            manually_pinned=True,
            target_age_days=5,
        )
        check = check_entry_criteria(t)
        assert check.eligible is False
        assert len(check.violations) == 5

    def test_entry_check_to_dict(self):
        check = EntryCheck(eligible=True, violations=[])
        d = check.to_dict()
        assert d == {"eligible": True, "violations": []}


class TestSkipListAdd:

    def test_add_eligible_target(self):
        sl = SkipList()
        t = _eligible_target()
        result = sl.add(t, date(2026, 3, 1), total_active_targets=10)
        assert isinstance(result, SkipEntry)
        assert result.skip_since == "2026-03-01"
        assert result.next_review_at == "2026-03-31"
        assert sl.size() == 1
        assert t.skipped is True

    def test_add_ineligible_target_fails(self):
        sl = SkipList()
        t = _eligible_target()
        t.consecutive_watery = 0
        result = sl.add(t, date(2026, 3, 1), total_active_targets=10)
        assert isinstance(result, str)
        assert "Entry criteria" in result
        assert sl.size() == 0

    def test_default_skip_duration(self):
        assert DEFAULT_SKIP_DURATION_DAYS == 30


# ─── AC-MVP3-1-SKIP-2: Removal triggers ─────────────────────────────────

class TestRemovalTriggers:
    """AC-MVP3-1-SKIP-2: Removal on 4 events."""

    def _setup(self) -> tuple[SkipList, str]:
        sl = SkipList()
        t = _eligible_target("t1")
        sl.add(t, date(2026, 3, 1), total_active_targets=10)
        return sl, "t1"

    def test_new_conflict_reference(self):
        sl, tid = self._setup()
        reason = check_removal_triggers(sl, tid, has_new_conflict=True)
        assert reason == "new_conflict_reference"

    def test_new_open_question_reference(self):
        sl, tid = self._setup()
        reason = check_removal_triggers(sl, tid, has_new_question=True)
        assert reason == "new_open_question_reference"

    def test_manual_unskip(self):
        sl, tid = self._setup()
        reason = check_removal_triggers(sl, tid, manual_unskip=True)
        assert reason == "manual_unskip"

    def test_next_review_at_reached(self):
        sl, tid = self._setup()
        reason = check_removal_triggers(
            sl, tid, current_date=date(2026, 3, 31)
        )
        assert reason == "next_review_at_reached"

    def test_no_trigger(self):
        sl, tid = self._setup()
        reason = check_removal_triggers(
            sl, tid, current_date=date(2026, 3, 15)
        )
        assert reason is None

    def test_not_in_skip_list(self):
        sl = SkipList()
        reason = check_removal_triggers(sl, "t-unknown", has_new_conflict=True)
        assert reason is None

    def test_process_removals_removes(self):
        sl, tid = self._setup()
        reason = process_removals(sl, tid, has_new_conflict=True)
        assert reason == "new_conflict_reference"
        assert not sl.contains(tid)

    def test_process_removals_no_action(self):
        sl, tid = self._setup()
        reason = process_removals(sl, tid, current_date=date(2026, 3, 15))
        assert reason is None
        assert sl.contains(tid)

    def test_priority_conflict_over_question(self):
        """Conflict takes priority when both triggers fire."""
        sl, tid = self._setup()
        reason = check_removal_triggers(
            sl, tid, has_new_conflict=True, has_new_question=True
        )
        assert reason == "new_conflict_reference"


# ─── AC-MVP3-1-SKIP-3: Safety cap ───────────────────────────────────────

class TestSafetyCap:
    """AC-MVP3-1-SKIP-3: Safety cap at 20% enforced."""

    def test_cap_ratio(self):
        assert SAFETY_CAP_RATIO == 0.20

    def test_cap_enforced(self):
        sl = SkipList()
        # 5 active targets -> max 1 skipped (20% of 5 = 1)
        t1 = _eligible_target("t1")
        result1 = sl.add(t1, date(2026, 3, 1), total_active_targets=5)
        assert isinstance(result1, SkipEntry)

        t2 = _eligible_target("t2")
        result2 = sl.add(t2, date(2026, 3, 1), total_active_targets=5)
        assert isinstance(result2, str)
        assert "Safety cap" in result2

    def test_cap_with_more_targets(self):
        sl = SkipList()
        # 10 active targets -> max 2 skipped
        for i in range(2):
            t = _eligible_target(f"t{i}")
            result = sl.add(t, date(2026, 3, 1), total_active_targets=10)
            assert isinstance(result, SkipEntry)

        t3 = _eligible_target("t3")
        result = sl.add(t3, date(2026, 3, 1), total_active_targets=10)
        assert isinstance(result, str)

    def test_cap_minimum_one(self):
        """Even with very few targets, at least 1 can be skipped."""
        sl = SkipList()
        t = _eligible_target("t1")
        result = sl.add(t, date(2026, 3, 1), total_active_targets=1)
        assert isinstance(result, SkipEntry)

    def test_cap_rechecked_per_add(self):
        """After removal, new entries can be added within cap."""
        sl = SkipList()
        t1 = _eligible_target("t1")
        sl.add(t1, date(2026, 3, 1), total_active_targets=5)
        sl.remove("t1")

        t2 = _eligible_target("t2")
        result = sl.add(t2, date(2026, 3, 1), total_active_targets=5)
        assert isinstance(result, SkipEntry)


# ─── AC-MVP3-1-SKIP-4: include_skip filtering ───────────────────────────

class TestFiltering:
    """AC-MVP3-1-SKIP-4: Skipped targets retrievable with include_skip=True."""

    def test_exclude_by_default(self):
        sl = SkipList()
        sl.entries["t1"] = SkipEntry("t1", "2026-03-01", "auto", "2026-03-31")
        targets = [
            TargetState("t1", skipped=True),
            TargetState("t2"),
        ]
        result = filter_targets(targets, sl)
        assert len(result) == 1
        assert result[0].target_id == "t2"

    def test_include_with_flag(self):
        sl = SkipList()
        sl.entries["t1"] = SkipEntry("t1", "2026-03-01", "auto", "2026-03-31")
        targets = [
            TargetState("t1", skipped=True),
            TargetState("t2"),
        ]
        result = filter_targets(targets, sl, include_skip=True)
        assert len(result) == 2

    def test_empty_skip_list(self):
        sl = SkipList()
        targets = [TargetState("t1"), TargetState("t2")]
        result = filter_targets(targets, sl)
        assert len(result) == 2


# ─── Serialization ──────────────────────────────────────────────────────

class TestSerialization:

    def test_skip_entry_to_dict(self):
        e = SkipEntry("t1", "2026-03-01", "auto", "2026-03-31")
        d = e.to_dict()
        assert d == {
            "target_id": "t1",
            "skip_since": "2026-03-01",
            "skip_reason": "auto",
            "next_review_at": "2026-03-31",
        }

    def test_skip_list_to_list(self):
        sl = SkipList()
        sl.entries["t1"] = SkipEntry("t1", "2026-03-01", "auto", "2026-03-31")
        lst = sl.to_list()
        assert len(lst) == 1
        assert lst[0]["target_id"] == "t1"

    def test_target_state_to_dict(self):
        t = _eligible_target()
        d = t.to_dict()
        assert d["target_id"] == "t1"
        assert d["consecutive_watery"] == 3

    def test_skip_list_contains(self):
        sl = SkipList()
        assert sl.contains("t1") is False
        sl.entries["t1"] = SkipEntry("t1", "2026-03-01", "auto", "2026-03-31")
        assert sl.contains("t1") is True

    def test_skip_list_remove(self):
        sl = SkipList()
        sl.entries["t1"] = SkipEntry("t1", "2026-03-01", "auto", "2026-03-31")
        assert sl.remove("t1") is True
        assert sl.remove("t1") is False
