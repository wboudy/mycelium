"""
End-to-end validation tests for MVP2 capability bundle (MVP2-001).

Verifies:
  AC-MVP2-001-1: Invalid queue transitions fail with ERR_QUEUE_IMMUTABLE.
  AC-MVP2-001-2: Frontier seeded fixture yields non-empty conflicts and
                  open_questions.
  AC-MVP2-001-3: Frontier fixture yields deterministic scores and ordering
                  across repeated runs.
  AC-MVP2-001-4: Promotion (graduate) writes Notes to Canonical Scope with
                  status: canon and appends audit event with
                  event_type: promotion_applied.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from mycelium.audit import EventType, read_audit_log
from mycelium.commands.frontier import (
    TargetData,
    compute_factors,
    compute_score,
    rank_targets,
)
from mycelium.graduate import GraduateInput, graduate
from mycelium.note_io import read_note, write_note
from mycelium.review_queue import (
    build_queue_item,
    check_mutable,
    load_queue_item,
    save_queue_item,
    update_queue_item,
)
from mycelium.schema import SchemaValidationError


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------

REF_TS = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)


def _valid_frontmatter(**overrides: Any) -> dict[str, Any]:
    """Build a minimal valid note frontmatter for promotion.

    Includes provenance fields required by INV-004 for claim notes.
    """
    fm: dict[str, Any] = {
        "type": "claim",
        "id": overrides.pop("id", "claim-001"),
        "status": "draft",
        "created": "2026-03-01T00:00:00Z",
        "updated": "2026-03-01T00:00:00Z",
        "provenance": {
            "source_id": "src-e2e-001",
            "source_ref": "ref-e2e-001",
            "locator": {
                "url": "https://example.com/test",
                "section": "1",
                "paragraph_index": 0,
                "snippet_hash": "sha256:" + "a" * 64,
            },
        },
    }
    fm.update(overrides)
    return fm


def _draft_note(vault: Path, note_id: str = "claim-001") -> str:
    """Write a draft note to Inbox/Sources/ and return vault-relative path."""
    fm = _valid_frontmatter(id=note_id)
    rel_path = f"Inbox/Sources/{note_id}.md"
    write_note(vault / rel_path, fm, "# Draft Note\n\nSome content.\n")
    return rel_path


def _pending_item(
    vault: Path,
    queue_id: str = "q-001",
    note_id: str = "claim-001",
) -> Path:
    """Create a draft note + pending queue item, return queue item path."""
    draft_path = _draft_note(vault, note_id)
    item = build_queue_item(
        queue_id=queue_id,
        run_id="run-001",
        item_type="claim_note",
        target_path=draft_path,
        proposed_action="promote_to_canon",
        created_at="2026-03-01T00:00:00Z",
        checks={"match_class": "EXACT", "provenance_present": True},
    )
    return save_queue_item(vault, item)


def _frontier_fixtures() -> list[TargetData]:
    """Seeded fixture set with conflicts and open_questions.

    At least one target has contradict_count > 0 (conflict) and
    at least one has support_count == 0 (open question / weak support).
    """
    return [
        TargetData(
            target_id="t-conflict-1",
            contradict_count=3,
            support_count=1,
            project="neuroscience",
            tags=["attention", "fmri"],
            linked_delta_novelty_scores=[0.8, 0.9, 0.7],
            last_reviewed_at=datetime(2026, 1, 15, tzinfo=timezone.utc),
        ),
        TargetData(
            target_id="t-conflict-2",
            contradict_count=2,
            support_count=0,
            project="neuroscience",
            tags=["eeg", "sleep"],
            linked_delta_novelty_scores=[0.5],
            last_reviewed_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        ),
        TargetData(
            target_id="t-weak-support",
            contradict_count=0,
            support_count=0,
            project="ai",
            tags=["transformer", "attention"],
            linked_delta_novelty_scores=[0.3, 0.4],
            last_reviewed_at=datetime(2026, 2, 15, tzinfo=timezone.utc),
        ),
        TargetData(
            target_id="t-stale",
            contradict_count=0,
            support_count=2,
            project="neuroscience",
            tags=["attention"],
            linked_delta_novelty_scores=[],
            last_reviewed_at=datetime(2025, 12, 1, tzinfo=timezone.utc),
        ),
        TargetData(
            target_id="t-fresh",
            contradict_count=1,
            support_count=5,
            project="neuroscience",
            tags=["attention", "fmri", "eeg"],
            linked_delta_novelty_scores=[0.9, 0.95],
            last_reviewed_at=datetime(2026, 2, 28, tzinfo=timezone.utc),
        ),
    ]


# ═══════════════════════════════════════════════════════════════════════
# AC-MVP2-001-1: Invalid queue transitions → ERR_QUEUE_IMMUTABLE
# ═══════════════════════════════════════════════════════════════════════


class TestQueueTransitionEnforcement:
    """AC-MVP2-001-1: Invalid queue transitions fail with ERR_QUEUE_IMMUTABLE."""

    def test_pending_review_is_mutable(self, tmp_path: Path):
        """pending_review items can be mutated."""
        path = _pending_item(tmp_path)
        item = load_queue_item(path)
        check_mutable(item)  # Should not raise

    def test_approved_is_immutable(self, tmp_path: Path):
        """Approved items cannot be mutated."""
        path = _pending_item(tmp_path)
        update_queue_item(
            path, {"status": "approved"}, is_state_transition=True,
        )
        item = load_queue_item(path)
        with pytest.raises(SchemaValidationError, match="ERR_QUEUE_IMMUTABLE"):
            check_mutable(item)

    def test_rejected_is_immutable(self, tmp_path: Path):
        """Rejected items cannot be mutated."""
        path = _pending_item(tmp_path)
        update_queue_item(
            path, {"status": "rejected"}, is_state_transition=True,
        )
        item = load_queue_item(path)
        with pytest.raises(SchemaValidationError, match="ERR_QUEUE_IMMUTABLE"):
            check_mutable(item)

    def test_non_transition_mutation_of_approved_blocked(self, tmp_path: Path):
        """Attempting non-transition mutation of approved item raises."""
        path = _pending_item(tmp_path)
        update_queue_item(
            path, {"status": "approved"}, is_state_transition=True,
        )
        with pytest.raises(SchemaValidationError):
            update_queue_item(path, {"status": "rejected"})

    def test_approved_to_rejected_without_transition_flag(self, tmp_path: Path):
        """Cannot change approved→rejected without is_state_transition=True."""
        path = _pending_item(tmp_path)
        update_queue_item(
            path, {"status": "approved"}, is_state_transition=True,
        )
        with pytest.raises(SchemaValidationError, match="ERR_QUEUE_IMMUTABLE"):
            update_queue_item(
                path, {"status": "rejected"}, is_state_transition=False,
            )

    def test_valid_state_transition_succeeds(self, tmp_path: Path):
        """Explicit state transition from pending_review→approved succeeds."""
        path = _pending_item(tmp_path)
        updated = update_queue_item(
            path, {"status": "approved"}, is_state_transition=True,
        )
        assert updated["status"] == "approved"


# ═══════════════════════════════════════════════════════════════════════
# AC-MVP2-001-2: Frontier fixture yields conflicts and open_questions
# ═══════════════════════════════════════════════════════════════════════


class TestFrontierConflictsAndQuestions:
    """AC-MVP2-001-2: Frontier seeded fixture yields non-empty conflicts
    and open_questions."""

    def test_fixture_has_conflicting_targets(self):
        """At least one target has contradict_count > 0."""
        targets = _frontier_fixtures()
        conflicting = [t for t in targets if t.contradict_count > 0]
        assert len(conflicting) > 0

    def test_fixture_has_weak_support_targets(self):
        """At least one target has support_count == 0 (open question)."""
        targets = _frontier_fixtures()
        weak = [t for t in targets if t.support_count == 0]
        assert len(weak) > 0

    def test_conflict_factor_nonzero_for_conflicting(self):
        """Conflicting targets produce nonzero conflict_factor."""
        targets = _frontier_fixtures()
        for t in targets:
            if t.contradict_count > 0:
                factors = compute_factors(t, REF_TS)
                assert factors.conflict_factor > 0.0

    def test_support_gap_high_for_unsupported(self):
        """Targets with no support have support_gap == 1.0."""
        targets = _frontier_fixtures()
        for t in targets:
            if t.support_count == 0:
                factors = compute_factors(t, REF_TS)
                assert factors.support_gap == 1.0

    def test_ranked_output_non_empty(self):
        """Ranking the fixture yields non-empty reading targets."""
        targets = _frontier_fixtures()
        ranked = rank_targets(targets, REF_TS)
        assert len(ranked) == len(targets)

    def test_conflicting_targets_score_higher(self):
        """Targets with conflicts score higher than targets without."""
        targets = _frontier_fixtures()
        ranked = rank_targets(targets, REF_TS)
        # First target should have conflicts (highest score)
        top = ranked[0]
        assert top.factors.conflict_factor > 0.0

    def test_factors_all_in_range(self):
        """All factor values are in [0..1] for fixture targets."""
        targets = _frontier_fixtures()
        for t in targets:
            factors = compute_factors(t, REF_TS)
            assert 0.0 <= factors.conflict_factor <= 1.0
            assert 0.0 <= factors.support_gap <= 1.0
            assert 0.0 <= factors.goal_relevance <= 1.0
            assert 0.0 <= factors.novelty <= 1.0
            assert 0.0 <= factors.staleness <= 1.0

    def test_scores_in_range(self):
        """All scores are in [0..100]."""
        targets = _frontier_fixtures()
        ranked = rank_targets(targets, REF_TS)
        for rt in ranked:
            assert 0.0 <= rt.score <= 100.0


# ═══════════════════════════════════════════════════════════════════════
# AC-MVP2-001-3: Deterministic scores and ordering
# ═══════════════════════════════════════════════════════════════════════


class TestFrontierDeterminism:
    """AC-MVP2-001-3: Frontier fixture yields deterministic scores
    and ordering across repeated runs."""

    def test_scores_deterministic(self):
        """Same fixture yields identical scores on repeated runs."""
        targets = _frontier_fixtures()
        scores1 = [
            compute_score(compute_factors(t, REF_TS))
            for t in targets
        ]
        scores2 = [
            compute_score(compute_factors(t, REF_TS))
            for t in _frontier_fixtures()
        ]
        assert scores1 == scores2

    def test_ordering_deterministic(self):
        """Same fixture yields identical ranking order."""
        ranked1 = rank_targets(_frontier_fixtures(), REF_TS)
        ranked2 = rank_targets(_frontier_fixtures(), REF_TS)
        ids1 = [rt.target_id for rt in ranked1]
        ids2 = [rt.target_id for rt in ranked2]
        assert ids1 == ids2

    def test_scores_match_across_runs(self):
        """Scores match exactly between two independent ranking calls."""
        ranked1 = rank_targets(_frontier_fixtures(), REF_TS)
        ranked2 = rank_targets(_frontier_fixtures(), REF_TS)
        for r1, r2 in zip(ranked1, ranked2):
            assert r1.score == r2.score

    def test_factors_match_across_runs(self):
        """Factor components match exactly between independent calls."""
        ranked1 = rank_targets(_frontier_fixtures(), REF_TS)
        ranked2 = rank_targets(_frontier_fixtures(), REF_TS)
        for r1, r2 in zip(ranked1, ranked2):
            assert r1.factors.to_dict() == r2.factors.to_dict()

    def test_ordering_with_project_filter_deterministic(self):
        """Ranking with project filter is deterministic."""
        ranked1 = rank_targets(
            _frontier_fixtures(), REF_TS, input_project="neuroscience",
        )
        ranked2 = rank_targets(
            _frontier_fixtures(), REF_TS, input_project="neuroscience",
        )
        ids1 = [rt.target_id for rt in ranked1]
        ids2 = [rt.target_id for rt in ranked2]
        assert ids1 == ids2

    def test_ordering_with_tags_deterministic(self):
        """Ranking with tag filter is deterministic."""
        ranked1 = rank_targets(
            _frontier_fixtures(), REF_TS, input_tags=["attention"],
        )
        ranked2 = rank_targets(
            _frontier_fixtures(), REF_TS, input_tags=["attention"],
        )
        ids1 = [rt.target_id for rt in ranked1]
        ids2 = [rt.target_id for rt in ranked2]
        assert ids1 == ids2

    def test_limit_preserves_order(self):
        """Limiting results preserves the same ordering prefix."""
        ranked_full = rank_targets(_frontier_fixtures(), REF_TS)
        ranked_limited = rank_targets(_frontier_fixtures(), REF_TS, limit=3)
        assert [rt.target_id for rt in ranked_limited] == [
            rt.target_id for rt in ranked_full[:3]
        ]


# ═══════════════════════════════════════════════════════════════════════
# AC-MVP2-001-4: Graduate writes to Canonical Scope + audit events
# ═══════════════════════════════════════════════════════════════════════


class TestGraduatePromotion:
    """AC-MVP2-001-4: Graduate writes promoted Notes to Canonical Scope
    with status: canon and appends audit event."""

    def test_graduate_promotes_to_canonical_scope(self, tmp_path: Path):
        """Graduate writes promoted note to Canonical Scope directory."""
        _draft_note(tmp_path, "claim-promo-001")
        params = GraduateInput(
            queue_id="q-promo-001",
            strict=True,
            actor="user:test",
        )
        queue_items = [{
            "queue_id": "q-promo-001",
            "path": "Inbox/Sources/claim-promo-001.md",
            "decision": "approve",
        }]
        env = graduate(tmp_path, params, queue_items)
        assert env.ok is True
        assert len(env.data["promoted"]) == 1

        # Verify canonical file exists
        promoted = env.data["promoted"][0]
        canon_path = tmp_path / promoted["to_path"]
        assert canon_path.exists()

    def test_promoted_note_has_status_canon(self, tmp_path: Path):
        """Promoted note frontmatter has status: canon."""
        _draft_note(tmp_path, "claim-status-001")
        params = GraduateInput(
            queue_id="q-status-001",
            strict=True,
            actor="user:test",
        )
        queue_items = [{
            "queue_id": "q-status-001",
            "path": "Inbox/Sources/claim-status-001.md",
            "decision": "approve",
        }]
        env = graduate(tmp_path, params, queue_items)
        assert env.ok is True

        promoted = env.data["promoted"][0]
        canon_path = tmp_path / promoted["to_path"]
        fm, _ = read_note(canon_path)
        assert fm["status"] == "canon"

    def test_graduate_emits_audit_event(self, tmp_path: Path):
        """Graduate emits at least one audit event with promotion_applied."""
        _draft_note(tmp_path, "claim-audit-001")
        params = GraduateInput(
            queue_id="q-audit-001",
            strict=True,
            actor="user:test",
        )
        queue_items = [{
            "queue_id": "q-audit-001",
            "path": "Inbox/Sources/claim-audit-001.md",
            "decision": "approve",
        }]
        env = graduate(tmp_path, params, queue_items)
        assert env.ok is True
        assert len(env.data["audit_event_ids"]) >= 1

        # Read audit log and verify
        audit_dir = tmp_path / "Logs" / "Audit"
        assert audit_dir.exists()
        log_files = list(audit_dir.glob("*.jsonl"))
        assert len(log_files) >= 1

        events = read_audit_log(log_files[0])
        promotion_events = [
            e for e in events
            if e.event_type == EventType.PROMOTION_APPLIED.value
        ]
        assert len(promotion_events) >= 1

    def test_audit_event_references_promoted_path(self, tmp_path: Path):
        """Audit event targets include the canonical path."""
        _draft_note(tmp_path, "claim-ref-001")
        params = GraduateInput(
            queue_id="q-ref-001",
            strict=True,
            actor="user:test",
        )
        queue_items = [{
            "queue_id": "q-ref-001",
            "path": "Inbox/Sources/claim-ref-001.md",
            "decision": "approve",
        }]
        env = graduate(tmp_path, params, queue_items)
        promoted = env.data["promoted"][0]

        audit_dir = tmp_path / "Logs" / "Audit"
        log_files = list(audit_dir.glob("*.jsonl"))
        events = read_audit_log(log_files[0])
        promo = [
            e for e in events
            if e.event_type == EventType.PROMOTION_APPLIED.value
        ]
        assert any(promoted["to_path"] in e.targets for e in promo)

    def test_held_items_remain_pending(self, tmp_path: Path):
        """Held items are skipped, not promoted."""
        _draft_note(tmp_path, "claim-hold-001")
        params = GraduateInput(
            queue_id="q-hold-001",
            strict=True,
            actor="user:test",
        )
        queue_items = [{
            "queue_id": "q-hold-001",
            "path": "Inbox/Sources/claim-hold-001.md",
            "decision": "hold",
        }]
        env = graduate(tmp_path, params, queue_items)
        assert env.ok is True
        assert len(env.data["promoted"]) == 0
        assert len(env.data["skipped"]) == 1
        assert env.data["skipped"][0]["reason"] == "held"

    def test_rejected_items_skipped(self, tmp_path: Path):
        """Rejected items are skipped, not promoted."""
        _draft_note(tmp_path, "claim-rej-001")
        params = GraduateInput(
            queue_id="q-rej-001",
            strict=True,
            actor="user:test",
        )
        queue_items = [{
            "queue_id": "q-rej-001",
            "path": "Inbox/Sources/claim-rej-001.md",
            "decision": "reject",
        }]
        env = graduate(tmp_path, params, queue_items)
        assert env.ok is True
        assert len(env.data["promoted"]) == 0
        assert len(env.data["skipped"]) == 1

    def test_dry_run_strict_false_forbidden(self, tmp_path: Path):
        """graduate with dry_run=false and strict=false is rejected."""
        params = GraduateInput(
            dry_run=False,
            strict=False,
            actor="user:test",
        )
        env = graduate(tmp_path, params, [])
        assert env.ok is False
        assert any("strict" in e.message for e in env.errors)

    def test_per_item_atomicity(self, tmp_path: Path):
        """One item's rejection doesn't block another item's promotion."""
        _draft_note(tmp_path, "claim-good-001")
        params = GraduateInput(
            strict=True,
            actor="user:test",
        )
        queue_items = [
            {
                "queue_id": "q-good",
                "path": "Inbox/Sources/claim-good-001.md",
                "decision": "approve",
            },
            {
                "queue_id": "q-bad",
                "path": "Inbox/Sources/nonexistent.md",
                "decision": "approve",
            },
        ]
        env = graduate(tmp_path, params, queue_items)
        assert env.ok is True
        assert len(env.data["promoted"]) == 1
        assert len(env.data["rejected"]) == 1

    def test_multiple_promotions_single_audit(self, tmp_path: Path):
        """Multiple promotions produce at least one audit event."""
        _draft_note(tmp_path, "claim-multi-001")
        _draft_note(tmp_path, "claim-multi-002")
        params = GraduateInput(
            strict=True,
            actor="user:test",
        )
        queue_items = [
            {
                "queue_id": "q-m1",
                "path": "Inbox/Sources/claim-multi-001.md",
                "decision": "approve",
            },
            {
                "queue_id": "q-m2",
                "path": "Inbox/Sources/claim-multi-002.md",
                "decision": "approve",
            },
        ]
        env = graduate(tmp_path, params, queue_items)
        assert env.ok is True
        assert len(env.data["promoted"]) == 2
        assert len(env.data["audit_event_ids"]) >= 1
