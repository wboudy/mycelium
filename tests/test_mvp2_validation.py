"""MVP2 end-to-end validation tests (MVP2-001).

Validates acceptance criteria:
  AC-MVP2-001-1: Integration test enforces invalid queue transitions fail
                 with ERR_QUEUE_IMMUTABLE.
  AC-MVP2-001-2: Frontier seeded fixture yields non-empty conflicts and
                 open_questions.
  AC-MVP2-001-3: Frontier fixture yields deterministic scores and ordering
                 across repeated runs.
  AC-MVP2-001-4: Promotion test verifies graduate writes promoted Notes to
                 Canonical Scope with status: canon and appends at least one
                 audit event with event_type: promotion_applied.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from mycelium.audit import EventType, read_audit_log
from mycelium.commands.frontier import (
    ReadingTarget,
    ScoringFactors,
    TargetData,
    compute_factors,
    compute_score,
    rank_targets,
)
from mycelium.commands.review import (
    ERR_QUEUE_IMMUTABLE,
    QueueStatus,
    ReviewDecision,
    apply_transition,
    review_transition,
)
from mycelium.graduate import GraduateInput, graduate
from mycelium.note_io import read_note, write_note
from mycelium.review_queue import (
    build_queue_item,
    check_mutable,
    save_queue_item,
    update_queue_item,
)
from mycelium.schema import SchemaValidationError


# ═══════════════════════════════════════════════════════════════════════
# AC-MVP2-001-1: Invalid queue transitions fail with ERR_QUEUE_IMMUTABLE
# ═══════════════════════════════════════════════════════════════════════

class TestInvalidQueueTransitions:
    """AC-MVP2-001-1: Integration test enforces invalid queue transitions
    fail with ERR_QUEUE_IMMUTABLE."""

    def _create_and_approve_item(self, vault: Path) -> tuple[Path, dict[str, Any]]:
        """Create a pending item and transition it to approved."""
        item = build_queue_item(
            queue_id="q-transition-001",
            run_id="run-001",
            item_type="claim_note",
            target_path="Inbox/Sources/c-001.md",
            proposed_action="promote_to_canon",
            created_at="2026-03-01T00:00:00Z",
        )
        path = save_queue_item(vault, item)
        updated = update_queue_item(
            path, {"status": "approved"}, is_state_transition=True,
        )
        return path, updated

    def test_approved_to_approved_blocked(self, tmp_path: Path):
        result = apply_transition(QueueStatus.APPROVED, ReviewDecision.APPROVE)
        assert hasattr(result, "code")
        assert result.code == ERR_QUEUE_IMMUTABLE

    def test_approved_to_rejected_blocked(self, tmp_path: Path):
        result = apply_transition(QueueStatus.APPROVED, ReviewDecision.REJECT)
        assert hasattr(result, "code")
        assert result.code == ERR_QUEUE_IMMUTABLE

    def test_rejected_to_approved_blocked(self, tmp_path: Path):
        result = apply_transition(QueueStatus.REJECTED, ReviewDecision.APPROVE)
        assert hasattr(result, "code")
        assert result.code == ERR_QUEUE_IMMUTABLE

    def test_approved_item_immutable_via_check(self, tmp_path: Path):
        _, item = self._create_and_approve_item(tmp_path)
        with pytest.raises(SchemaValidationError, match="ERR_QUEUE_IMMUTABLE"):
            check_mutable(item)

    def test_approved_item_mutation_blocked(self, tmp_path: Path):
        path, _ = self._create_and_approve_item(tmp_path)
        with pytest.raises(SchemaValidationError):
            update_queue_item(path, {"status": "rejected"})

    def test_review_transition_on_approved_fails(self):
        record, env = review_transition(
            queue_id="q-immutable",
            current_status="approved",
            decision=ReviewDecision.REJECT,
            actor="test-reviewer",
        )
        assert env.ok is False
        assert record is None
        assert any(e.code == ERR_QUEUE_IMMUTABLE for e in env.errors)

    def test_review_transition_on_rejected_fails(self):
        record, env = review_transition(
            queue_id="q-immutable-2",
            current_status="rejected",
            decision=ReviewDecision.APPROVE,
            actor="test-reviewer",
        )
        assert env.ok is False
        assert record is None

    def test_full_lifecycle_transition_enforcement(self, tmp_path: Path):
        """Full lifecycle: create → approve → verify immutable → attempt reject."""
        item = build_queue_item(
            queue_id="q-lifecycle",
            run_id="run-lifecycle",
            item_type="claim_note",
            target_path="Inbox/Sources/lifecycle.md",
            proposed_action="promote_to_canon",
            created_at="2026-03-01T00:00:00Z",
        )
        path = save_queue_item(tmp_path, item)

        # Transition: pending_review → approved
        updated = update_queue_item(
            path, {"status": "approved"}, is_state_transition=True,
        )
        assert updated["status"] == "approved"

        # Attempt: approved → rejected (should fail)
        with pytest.raises(SchemaValidationError):
            update_queue_item(path, {"status": "rejected"})


# ═══════════════════════════════════════════════════════════════════════
# AC-MVP2-001-2: Frontier seeded fixture yields non-empty results
# ═══════════════════════════════════════════════════════════════════════

class TestFrontierSeededFixture:
    """AC-MVP2-001-2: Frontier seeded fixture yields non-empty conflicts
    and open_questions."""

    NOW = datetime(2026, 3, 1, tzinfo=timezone.utc)

    def _seeded_targets(self) -> list[TargetData]:
        """Build a seeded fixture with conflicting and weakly-supported targets."""
        return [
            # High conflict target
            TargetData(
                target_id="conflict-target-1",
                contradict_count=5,
                support_count=1,
                project="research",
                tags=["biology", "health"],
                linked_delta_novelty_scores=[0.8, 0.9, 0.7],
                last_reviewed_at=self.NOW - timedelta(days=30),
            ),
            # Weakly supported target (open question candidate)
            TargetData(
                target_id="weak-support-1",
                contradict_count=0,
                support_count=0,
                project=None,
                tags=[],
                linked_delta_novelty_scores=[0.5],
                last_reviewed_at=None,
            ),
            # Another conflict target
            TargetData(
                target_id="conflict-target-2",
                contradict_count=3,
                support_count=2,
                project="research",
                tags=["chemistry"],
                linked_delta_novelty_scores=[0.6, 0.4],
                last_reviewed_at=self.NOW - timedelta(days=10),
            ),
            # Well-supported target (low conflict, high support)
            TargetData(
                target_id="well-supported-1",
                contradict_count=0,
                support_count=5,
                project="research",
                tags=["biology"],
                linked_delta_novelty_scores=[0.2],
                last_reviewed_at=self.NOW - timedelta(days=2),
            ),
        ]

    def test_rank_produces_non_empty_results(self):
        targets = self._seeded_targets()
        results = rank_targets(targets, self.NOW)
        assert len(results) > 0

    def test_conflict_targets_scored_higher(self):
        targets = self._seeded_targets()
        results = rank_targets(targets, self.NOW)
        # Find conflict and non-conflict targets
        conflict_ids = {"conflict-target-1", "conflict-target-2"}
        conflict_scores = [r.score for r in results if r.target_id in conflict_ids]
        non_conflict_scores = [r.score for r in results if r.target_id not in conflict_ids]
        assert max(conflict_scores) > min(non_conflict_scores)

    def test_conflict_factor_positive(self):
        targets = self._seeded_targets()
        results = rank_targets(targets, self.NOW)
        conflict_results = [r for r in results if "conflict" in r.target_id]
        for r in conflict_results:
            assert r.factors.conflict_factor > 0

    def test_weak_support_has_high_support_gap(self):
        targets = self._seeded_targets()
        results = rank_targets(targets, self.NOW)
        weak = [r for r in results if r.target_id == "weak-support-1"]
        assert len(weak) == 1
        # support_count=0 → support_gap=1.0
        assert weak[0].factors.support_gap == 1.0

    def test_never_reviewed_maximally_stale(self):
        targets = self._seeded_targets()
        results = rank_targets(targets, self.NOW)
        weak = [r for r in results if r.target_id == "weak-support-1"]
        assert len(weak) == 1
        # Never reviewed → staleness=1.0
        assert weak[0].factors.staleness == 1.0

    def test_all_factors_in_unit_range(self):
        targets = self._seeded_targets()
        results = rank_targets(targets, self.NOW)
        for r in results:
            assert 0.0 <= r.factors.conflict_factor <= 1.0
            assert 0.0 <= r.factors.support_gap <= 1.0
            assert 0.0 <= r.factors.goal_relevance <= 1.0
            assert 0.0 <= r.factors.novelty <= 1.0
            assert 0.0 <= r.factors.staleness <= 1.0

    def test_all_scores_in_range(self):
        targets = self._seeded_targets()
        results = rank_targets(targets, self.NOW)
        for r in results:
            assert 0.0 <= r.score <= 100.0


# ═══════════════════════════════════════════════════════════════════════
# AC-MVP2-001-3: Deterministic frontier scores and ordering
# ═══════════════════════════════════════════════════════════════════════

class TestFrontierDeterminism:
    """AC-MVP2-001-3: Frontier fixture yields deterministic scores and
    ordering across repeated runs."""

    NOW = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)

    def _fixture_targets(self) -> list[TargetData]:
        """Build a fixture with varied targets for determinism testing."""
        return [
            TargetData(
                target_id="det-alpha",
                contradict_count=3,
                support_count=1,
                project="proj-A",
                tags=["tag1", "tag2"],
                linked_delta_novelty_scores=[0.5, 0.7, 0.9],
                last_reviewed_at=self.NOW - timedelta(days=20),
            ),
            TargetData(
                target_id="det-beta",
                contradict_count=1,
                support_count=3,
                project="proj-B",
                tags=["tag1"],
                linked_delta_novelty_scores=[0.3],
                last_reviewed_at=self.NOW - timedelta(days=5),
            ),
            TargetData(
                target_id="det-gamma",
                contradict_count=2,
                support_count=2,
                project="proj-A",
                tags=["tag2", "tag3"],
                linked_delta_novelty_scores=[0.6, 0.8],
                last_reviewed_at=self.NOW - timedelta(days=40),
            ),
        ]

    def test_identical_scores_across_runs(self):
        targets = self._fixture_targets()
        r1 = rank_targets(targets, self.NOW, input_project="proj-A", input_tags=["tag1"])
        r2 = rank_targets(targets, self.NOW, input_project="proj-A", input_tags=["tag1"])

        scores1 = [r.score for r in r1]
        scores2 = [r.score for r in r2]
        assert scores1 == scores2

    def test_identical_ordering_across_runs(self):
        targets = self._fixture_targets()
        r1 = rank_targets(targets, self.NOW)
        r2 = rank_targets(targets, self.NOW)

        ids1 = [r.target_id for r in r1]
        ids2 = [r.target_id for r in r2]
        assert ids1 == ids2

    def test_identical_factors_across_runs(self):
        targets = self._fixture_targets()
        r1 = rank_targets(targets, self.NOW)
        r2 = rank_targets(targets, self.NOW)

        for a, b in zip(r1, r2):
            assert a.factors.to_dict() == b.factors.to_dict()

    def test_deterministic_with_limit(self):
        targets = self._fixture_targets()
        r1 = rank_targets(targets, self.NOW, limit=2)
        r2 = rank_targets(targets, self.NOW, limit=2)
        assert len(r1) == 2
        assert [r.target_id for r in r1] == [r.target_id for r in r2]

    def test_results_sorted_by_score_descending(self):
        targets = self._fixture_targets()
        results = rank_targets(targets, self.NOW)
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_ten_runs_identical(self):
        """Run 10 times and verify all produce identical output."""
        targets = self._fixture_targets()
        first = rank_targets(targets, self.NOW)
        first_ids = [r.target_id for r in first]
        first_scores = [r.score for r in first]

        for _ in range(9):
            result = rank_targets(targets, self.NOW)
            assert [r.target_id for r in result] == first_ids
            assert [r.score for r in result] == first_scores


# ═══════════════════════════════════════════════════════════════════════
# AC-MVP2-001-4: Graduate promotes with status: canon + audit event
# ═══════════════════════════════════════════════════════════════════════

class TestGraduatePromotion:
    """AC-MVP2-001-4: Promotion test verifies graduate writes promoted Notes
    to Canonical Scope with status: canon and appends at least one audit
    event with event_type: promotion_applied."""

    def _create_draft_note(
        self,
        vault: Path,
        path: str,
        *,
        note_type: str = "source",
        note_id: str = "test-note",
    ) -> Path:
        fm: dict[str, Any] = {
            "id": note_id,
            "type": note_type,
            "status": "draft",
            "created": "2026-03-01T00:00:00Z",
            "updated": "2026-03-01T00:00:00Z",
        }
        full_path = vault / path
        write_note(full_path, fm, "# Test Note\n\nContent for testing.\n")
        return full_path

    def test_promoted_note_in_canonical_scope(self, tmp_path: Path):
        self._create_draft_note(
            tmp_path, "Inbox/Sources/promo-src.md",
            note_id="promo-src", note_type="source",
        )
        params = GraduateInput(all_approved=True, actor="reviewer")
        items = [{
            "queue_id": "q-promo-1",
            "path": "Inbox/Sources/promo-src.md",
            "decision": "approve",
        }]
        env = graduate(tmp_path, params, items)
        assert env.ok is True
        assert len(env.data["promoted"]) == 1

        # Verify note exists in canonical scope
        canonical = tmp_path / "Sources" / "promo-src.md"
        assert canonical.exists()

    def test_promoted_note_has_status_canon(self, tmp_path: Path):
        self._create_draft_note(
            tmp_path, "Inbox/Sources/canon-check.md",
            note_id="canon-check", note_type="source",
        )
        params = GraduateInput(all_approved=True, actor="reviewer")
        items = [{
            "queue_id": "q-canon",
            "path": "Inbox/Sources/canon-check.md",
            "decision": "approve",
        }]
        env = graduate(tmp_path, params, items)
        assert env.ok is True

        canonical = tmp_path / "Sources" / "canon-check.md"
        fm, _ = read_note(canonical)
        assert fm["status"] == "canon"

    def test_audit_event_promotion_applied(self, tmp_path: Path):
        self._create_draft_note(
            tmp_path, "Inbox/Sources/audit-promo.md",
            note_id="audit-promo", note_type="source",
        )
        params = GraduateInput(all_approved=True, actor="audit-reviewer")
        items = [{
            "queue_id": "q-audit",
            "path": "Inbox/Sources/audit-promo.md",
            "decision": "approve",
        }]
        env = graduate(tmp_path, params, items)
        assert env.ok is True
        assert len(env.data["audit_event_ids"]) >= 1

        # Read audit log and verify promotion_applied event
        audit_files = list((tmp_path / "Logs" / "Audit").glob("*.jsonl"))
        assert len(audit_files) >= 1
        events = read_audit_log(audit_files[0])
        promotion_events = [
            e for e in events if e.event_type == "promotion_applied"
        ]
        assert len(promotion_events) >= 1

    def test_audit_event_has_actor(self, tmp_path: Path):
        self._create_draft_note(
            tmp_path, "Inbox/Sources/actor-promo.md",
            note_id="actor-promo", note_type="source",
        )
        params = GraduateInput(all_approved=True, actor="alice-reviewer")
        items = [{
            "queue_id": "q-actor",
            "path": "Inbox/Sources/actor-promo.md",
            "decision": "approve",
        }]
        env = graduate(tmp_path, params, items)

        audit_files = list((tmp_path / "Logs" / "Audit").glob("*.jsonl"))
        events = read_audit_log(audit_files[0])
        promo = [e for e in events if e.event_type == "promotion_applied"][0]
        assert promo.actor == "alice-reviewer"

    def test_audit_event_has_promoted_paths(self, tmp_path: Path):
        self._create_draft_note(
            tmp_path, "Inbox/Sources/paths-promo.md",
            note_id="paths-promo", note_type="source",
        )
        params = GraduateInput(all_approved=True, actor="reviewer")
        items = [{
            "queue_id": "q-paths",
            "path": "Inbox/Sources/paths-promo.md",
            "decision": "approve",
        }]
        env = graduate(tmp_path, params, items)

        audit_files = list((tmp_path / "Logs" / "Audit").glob("*.jsonl"))
        events = read_audit_log(audit_files[0])
        promo = [e for e in events if e.event_type == "promotion_applied"][0]
        assert "Sources/paths-promo.md" in promo.targets

    def test_claim_note_promotes_to_claims_dir(self, tmp_path: Path):
        # Claims need a provenance object for promotion (INV-004)
        fm: dict[str, Any] = {
            "id": "claim-001",
            "type": "claim",
            "status": "draft",
            "created": "2026-03-01T00:00:00Z",
            "updated": "2026-03-01T00:00:00Z",
            "provenance": {
                "source_id": "src-test",
                "source_ref": "test-source",
                "locator": "p.1",
            },
        }
        write_note(
            tmp_path / "Inbox" / "Sources" / "claim-001.md",
            fm, "# Claim\n\nTest claim content.\n",
        )
        params = GraduateInput(all_approved=True, actor="reviewer")
        items = [{
            "queue_id": "q-claim",
            "path": "Inbox/Sources/claim-001.md",
            "decision": "approve",
        }]
        env = graduate(tmp_path, params, items)
        assert env.ok is True

        canonical = tmp_path / "Claims" / "claim-001.md"
        assert canonical.exists()
        fm, _ = read_note(canonical)
        assert fm["status"] == "canon"

    def test_multiple_promotions_single_audit(self, tmp_path: Path):
        """Multiple items promoted → single audit event with all targets."""
        self._create_draft_note(
            tmp_path, "Inbox/Sources/multi-1.md",
            note_id="multi-1", note_type="source",
        )
        self._create_draft_note(
            tmp_path, "Inbox/Sources/multi-2.md",
            note_id="multi-2", note_type="source",
        )
        params = GraduateInput(all_approved=True, actor="batch-reviewer")
        items = [
            {"queue_id": "q-m1", "path": "Inbox/Sources/multi-1.md", "decision": "approve"},
            {"queue_id": "q-m2", "path": "Inbox/Sources/multi-2.md", "decision": "approve"},
        ]
        env = graduate(tmp_path, params, items)
        assert env.ok is True
        assert len(env.data["promoted"]) == 2

        audit_files = list((tmp_path / "Logs" / "Audit").glob("*.jsonl"))
        events = read_audit_log(audit_files[0])
        promo = [e for e in events if e.event_type == "promotion_applied"]
        assert len(promo) == 1
        assert len(promo[0].targets) == 2

    def test_dry_run_no_canonical_writes(self, tmp_path: Path):
        """Dry run should not write to canonical scope."""
        self._create_draft_note(
            tmp_path, "Inbox/Sources/dry-note.md",
            note_id="dry-note", note_type="source",
        )
        params = GraduateInput(all_approved=True, dry_run=True, actor="dry-runner")
        items = [{
            "queue_id": "q-dry",
            "path": "Inbox/Sources/dry-note.md",
            "decision": "approve",
        }]
        env = graduate(tmp_path, params, items)
        assert env.ok is True
        assert len(env.data["promoted"]) == 1

        # No file in canonical scope
        assert not (tmp_path / "Sources" / "dry-note.md").exists()
        # No audit event
        audit_dir = tmp_path / "Logs" / "Audit"
        assert not audit_dir.exists() or len(list(audit_dir.glob("*.jsonl"))) == 0
