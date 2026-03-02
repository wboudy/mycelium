"""
Tests for review state transition enforcement (REV-002).

Acceptance Criteria:
- AC-REV-002-1: Illegal transitions return ERR_QUEUE_IMMUTABLE.
- AC-REV-002-2: Review writes Decision Records with actor/reason metadata (SCH-010).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from mycelium.commands.review import (
    ERR_QUEUE_IMMUTABLE,
    ERR_QUEUE_ITEM_INVALID,
    ERR_REVIEW_DECISION_INVALID,
    LEGAL_TRANSITIONS,
    QueueStatus,
    ReviewDecision,
    ReviewInput,
    TransitionResult,
    HoldResult,
    apply_transition,
    review_transition,
    save_decision_record,
    validate_review_input,
    execute_review,
    _build_decision_record,
)
from mycelium.models import ErrorObject


# ---------------------------------------------------------------------------
# apply_transition: legal transitions
# ---------------------------------------------------------------------------

class TestLegalTransitions:
    """AC-REV-002-1: Legal transitions succeed."""

    def test_pending_to_approved(self):
        result = apply_transition(QueueStatus.PENDING_REVIEW, ReviewDecision.APPROVE)
        assert result == QueueStatus.APPROVED

    def test_pending_to_rejected(self):
        result = apply_transition(QueueStatus.PENDING_REVIEW, ReviewDecision.REJECT)
        assert result == QueueStatus.REJECTED

    def test_hold_returns_none(self):
        result = apply_transition(QueueStatus.PENDING_REVIEW, ReviewDecision.HOLD)
        assert result is None


# ---------------------------------------------------------------------------
# apply_transition: illegal transitions → ERR_QUEUE_IMMUTABLE
# ---------------------------------------------------------------------------

class TestIllegalTransitions:
    """AC-REV-002-1: Illegal transitions return ERR_QUEUE_IMMUTABLE."""

    def test_approved_cannot_approve(self):
        result = apply_transition(QueueStatus.APPROVED, ReviewDecision.APPROVE)
        assert isinstance(result, ErrorObject)
        assert result.code == ERR_QUEUE_IMMUTABLE

    def test_approved_cannot_reject(self):
        result = apply_transition(QueueStatus.APPROVED, ReviewDecision.REJECT)
        assert isinstance(result, ErrorObject)
        assert result.code == ERR_QUEUE_IMMUTABLE

    def test_approved_cannot_hold(self):
        result = apply_transition(QueueStatus.APPROVED, ReviewDecision.HOLD)
        assert isinstance(result, ErrorObject)
        assert result.code == ERR_QUEUE_IMMUTABLE

    def test_rejected_cannot_approve(self):
        result = apply_transition(QueueStatus.REJECTED, ReviewDecision.APPROVE)
        assert isinstance(result, ErrorObject)
        assert result.code == ERR_QUEUE_IMMUTABLE

    def test_rejected_cannot_reject(self):
        result = apply_transition(QueueStatus.REJECTED, ReviewDecision.REJECT)
        assert isinstance(result, ErrorObject)
        assert result.code == ERR_QUEUE_IMMUTABLE

    def test_rejected_cannot_hold(self):
        result = apply_transition(QueueStatus.REJECTED, ReviewDecision.HOLD)
        assert isinstance(result, ErrorObject)
        assert result.code == ERR_QUEUE_IMMUTABLE

    def test_error_message_includes_status(self):
        result = apply_transition(QueueStatus.APPROVED, ReviewDecision.APPROVE)
        assert isinstance(result, ErrorObject)
        assert "approved" in result.message
        assert "pending_review" in result.message


# ---------------------------------------------------------------------------
# review_transition: full flow with decision record
# ---------------------------------------------------------------------------

class TestReviewTransition:
    """AC-REV-002-2: review_transition writes decision records."""

    def test_approve_creates_record(self, tmp_path: Path):
        record, env = review_transition(
            queue_id="q-001",
            current_status="pending_review",
            decision=ReviewDecision.APPROVE,
            actor="human-reviewer",
            reason="Verified claim accuracy",
            vault_root=tmp_path,
        )
        assert env.ok is True
        assert record is not None
        assert record["actor"] == "human-reviewer"
        assert record["reason"] == "Verified claim accuracy"
        assert record["mode"] == "direct"
        assert len(record["results"]) == 1
        assert record["results"][0]["old_status"] == "pending_review"
        assert record["results"][0]["new_status"] == "approved"

    def test_reject_creates_record(self, tmp_path: Path):
        record, env = review_transition(
            queue_id="q-002",
            current_status="pending_review",
            decision=ReviewDecision.REJECT,
            actor="reviewer-2",
            vault_root=tmp_path,
        )
        assert env.ok is True
        assert record["results"][0]["new_status"] == "rejected"

    def test_hold_creates_record_with_hold_until(self, tmp_path: Path):
        record, env = review_transition(
            queue_id="q-003",
            current_status="pending_review",
            decision=ReviewDecision.HOLD,
            actor="reviewer-3",
            hold_until="2026-03-15",
            vault_root=tmp_path,
        )
        assert env.ok is True
        assert record["results"][0]["hold_until"] == "2026-03-15"
        assert record["results"][0]["old_status"] == "pending_review"
        assert record["results"][0]["new_status"] == "pending_review"

    def test_illegal_transition_no_record(self):
        record, env = review_transition(
            queue_id="q-004",
            current_status="approved",
            decision=ReviewDecision.APPROVE,
            actor="reviewer",
        )
        assert env.ok is False
        assert record is None
        assert any(e.code == ERR_QUEUE_IMMUTABLE for e in env.errors)

    def test_invalid_status_error(self):
        record, env = review_transition(
            queue_id="q-005",
            current_status="bogus_status",
            decision=ReviewDecision.APPROVE,
            actor="reviewer",
        )
        assert env.ok is False
        assert record is None

    def test_record_persisted_to_disk(self, tmp_path: Path):
        record, env = review_transition(
            queue_id="q-006",
            current_status="pending_review",
            decision=ReviewDecision.APPROVE,
            actor="disk-test",
            reason="Testing persistence",
            vault_root=tmp_path,
        )
        assert env.ok is True
        # File should exist
        path = Path(record["decision_record_path"])
        assert path.exists()
        # Load and verify
        with open(path) as f:
            loaded = yaml.safe_load(f)
        assert loaded["actor"] == "disk-test"
        assert loaded["reason"] == "Testing persistence"
        assert loaded["mode"] == "direct"

    def test_record_has_decision_id(self, tmp_path: Path):
        record, _ = review_transition(
            queue_id="q-007",
            current_status="pending_review",
            decision=ReviewDecision.REJECT,
            actor="test",
            vault_root=tmp_path,
        )
        assert "decision_id" in record
        assert len(record["decision_id"]) > 0

    def test_record_has_created_at(self, tmp_path: Path):
        record, _ = review_transition(
            queue_id="q-008",
            current_status="pending_review",
            decision=ReviewDecision.APPROVE,
            actor="test",
            vault_root=tmp_path,
        )
        assert "created_at" in record

    def test_envelope_data_updated_list(self, tmp_path: Path):
        _, env = review_transition(
            queue_id="q-009",
            current_status="pending_review",
            decision=ReviewDecision.APPROVE,
            actor="test",
            vault_root=tmp_path,
        )
        assert env.ok is True
        assert len(env.data["updated"]) == 1
        assert len(env.data["held"]) == 0

    def test_envelope_data_held_list(self, tmp_path: Path):
        _, env = review_transition(
            queue_id="q-010",
            current_status="pending_review",
            decision=ReviewDecision.HOLD,
            actor="test",
            vault_root=tmp_path,
        )
        assert env.ok is True
        assert len(env.data["updated"]) == 0
        assert len(env.data["held"]) == 1

    def test_reason_null_accepted(self, tmp_path: Path):
        record, env = review_transition(
            queue_id="q-011",
            current_status="pending_review",
            decision=ReviewDecision.APPROVE,
            actor="test",
            reason=None,
            vault_root=tmp_path,
        )
        assert env.ok is True
        assert record["reason"] is None


# ---------------------------------------------------------------------------
# save_decision_record
# ---------------------------------------------------------------------------

class TestSaveDecisionRecord:

    def test_creates_directory(self, tmp_path: Path):
        record = _build_decision_record(
            mode="direct",
            actor="test",
            reason=None,
            results=[],
        )
        path = save_decision_record(tmp_path, record)
        assert path.exists()
        assert path.parent.name == "ReviewDigest"

    def test_round_trip(self, tmp_path: Path):
        record = _build_decision_record(
            mode="digest",
            actor="batch-runner",
            reason="Batch approval",
            results=[{"queue_id": "q-1", "old_status": "pending_review", "new_status": "approved"}],
        )
        path = save_decision_record(tmp_path, record)
        with open(path) as f:
            loaded = yaml.safe_load(f)
        assert loaded["actor"] == "batch-runner"
        assert loaded["results"][0]["queue_id"] == "q-1"


# ---------------------------------------------------------------------------
# validate_review_input
# ---------------------------------------------------------------------------

class TestValidateReviewInput:

    def test_valid_direct_input(self):
        result = validate_review_input({"queue_id": "q-1", "decision": "approve"})
        assert isinstance(result, ReviewInput)
        assert result.decision == ReviewDecision.APPROVE

    def test_missing_decision_direct(self):
        result = validate_review_input({"queue_id": "q-1"})
        assert isinstance(result, ErrorObject)
        assert result.code == ERR_REVIEW_DECISION_INVALID

    def test_invalid_decision(self):
        result = validate_review_input({"queue_id": "q-1", "decision": "yolo"})
        assert isinstance(result, ErrorObject)
        assert result.code == ERR_REVIEW_DECISION_INVALID

    def test_no_mode_specified(self):
        result = validate_review_input({})
        assert isinstance(result, ErrorObject)
        assert result.code == ERR_QUEUE_ITEM_INVALID

    def test_multiple_modes(self):
        result = validate_review_input({"queue_id": "q-1", "digest_path": "/x", "decision": "approve"})
        assert isinstance(result, ErrorObject)

    def test_digest_mode(self):
        result = validate_review_input({"digest_path": "/some/path"})
        assert isinstance(result, ReviewInput)
        assert result.is_digest_mode() is True


# ---------------------------------------------------------------------------
# TransitionResult / HoldResult
# ---------------------------------------------------------------------------

class TestResultModels:

    def test_transition_result_to_dict(self):
        tr = TransitionResult(queue_id="q-1", old_status="pending_review", new_status="approved")
        d = tr.to_dict()
        assert d == {"queue_id": "q-1", "old_status": "pending_review", "new_status": "approved"}

    def test_hold_result_to_dict(self):
        hr = HoldResult(queue_id="q-2", hold_until="2026-04-01")
        d = hr.to_dict()
        assert d == {"queue_id": "q-2", "hold_until": "2026-04-01"}
