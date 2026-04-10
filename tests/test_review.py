"""
Tests for the review command contract (CMD-REV-001).

Verifies:
  AC-CMD-REV-001-1: Legal transitions limited to pending_review -> approved/rejected.
  AC-CMD-REV-001-2: Hold does not mutate queue status.
  AC-CMD-REV-001-3: Digest mode maps packet decisions to queue outcomes.
"""

from __future__ import annotations

import pytest

from mycelium.commands.review import (
    ERR_QUEUE_IMMUTABLE,
    ERR_QUEUE_ITEM_INVALID,
    ERR_REVIEW_DECISION_INVALID,
    HoldResult,
    LEGAL_TRANSITIONS,
    QueueStatus,
    ReviewDecision,
    ReviewInput,
    TransitionResult,
    apply_transition,
    execute_review,
    validate_review_input,
)
from mycelium.models import ErrorObject


# ─── ReviewDecision / QueueStatus enums ───────────────────────────────────

class TestEnums:

    def test_decision_values(self):
        assert set(d.value for d in ReviewDecision) == {"approve", "reject", "hold"}

    def test_queue_status_values(self):
        assert set(s.value for s in QueueStatus) == {
            "pending_review", "approved", "rejected"
        }


# ─── Input validation ────────────────────────────────────────────────────

class TestValidateReviewInput:

    def test_missing_all_inputs(self):
        result = validate_review_input({})
        assert isinstance(result, ErrorObject)
        assert result.code == ERR_QUEUE_ITEM_INVALID

    def test_multiple_inputs_rejected(self):
        result = validate_review_input({
            "queue_id": "q1",
            "digest_path": "/path/to/digest.md",
            "decision": "approve",
        })
        assert isinstance(result, ErrorObject)
        assert result.code == ERR_QUEUE_ITEM_INVALID

    def test_direct_mode_requires_decision(self):
        result = validate_review_input({"queue_id": "q1"})
        assert isinstance(result, ErrorObject)
        assert result.code == ERR_REVIEW_DECISION_INVALID

    def test_invalid_decision_value(self):
        result = validate_review_input({"queue_id": "q1", "decision": "maybe"})
        assert isinstance(result, ErrorObject)
        assert result.code == ERR_REVIEW_DECISION_INVALID
        assert "maybe" in result.message

    def test_valid_direct_mode_queue_id(self):
        result = validate_review_input({
            "queue_id": "q1",
            "decision": "approve",
            "reason": "looks good",
            "actor": "human",
        })
        assert isinstance(result, ReviewInput)
        assert result.queue_id == "q1"
        assert result.decision == ReviewDecision.APPROVE
        assert result.reason == "looks good"
        assert result.actor == "human"
        assert result.is_direct_mode()
        assert not result.is_digest_mode()

    def test_valid_direct_mode_paths(self):
        result = validate_review_input({
            "queue_item_paths": ["/path/a.md", "/path/b.md"],
            "decision": "reject",
        })
        assert isinstance(result, ReviewInput)
        assert result.queue_item_paths == ["/path/a.md", "/path/b.md"]
        assert result.decision == ReviewDecision.REJECT

    def test_valid_digest_mode(self):
        result = validate_review_input({
            "digest_path": "/Inbox/ReviewDigest/2026-03-01.md",
        })
        assert isinstance(result, ReviewInput)
        assert result.digest_path == "/Inbox/ReviewDigest/2026-03-01.md"
        assert result.decision is None
        assert not result.is_direct_mode()
        assert result.is_digest_mode()

    def test_hold_decision(self):
        result = validate_review_input({
            "queue_id": "q1",
            "decision": "hold",
        })
        assert isinstance(result, ReviewInput)
        assert result.decision == ReviewDecision.HOLD


# ─── AC-CMD-REV-001-1: Legal transitions ─────────────────────────────────

class TestApplyTransition:
    """AC-CMD-REV-001-1: Legal transitions limited to
    pending_review -> approved and pending_review -> rejected."""

    def test_pending_approve_transitions(self):
        result = apply_transition(QueueStatus.PENDING_REVIEW, ReviewDecision.APPROVE)
        assert result == QueueStatus.APPROVED

    def test_pending_reject_transitions(self):
        result = apply_transition(QueueStatus.PENDING_REVIEW, ReviewDecision.REJECT)
        assert result == QueueStatus.REJECTED

    def test_approved_approve_is_immutable(self):
        result = apply_transition(QueueStatus.APPROVED, ReviewDecision.APPROVE)
        assert isinstance(result, ErrorObject)
        assert result.code == ERR_QUEUE_IMMUTABLE

    def test_approved_reject_is_immutable(self):
        result = apply_transition(QueueStatus.APPROVED, ReviewDecision.REJECT)
        assert isinstance(result, ErrorObject)
        assert result.code == ERR_QUEUE_IMMUTABLE

    def test_rejected_approve_is_immutable(self):
        result = apply_transition(QueueStatus.REJECTED, ReviewDecision.APPROVE)
        assert isinstance(result, ErrorObject)
        assert result.code == ERR_QUEUE_IMMUTABLE

    def test_rejected_reject_is_immutable(self):
        result = apply_transition(QueueStatus.REJECTED, ReviewDecision.REJECT)
        assert isinstance(result, ErrorObject)
        assert result.code == ERR_QUEUE_IMMUTABLE

    def test_approved_hold_is_immutable(self):
        result = apply_transition(QueueStatus.APPROVED, ReviewDecision.HOLD)
        assert isinstance(result, ErrorObject)
        assert result.code == ERR_QUEUE_IMMUTABLE

    def test_rejected_hold_is_immutable(self):
        result = apply_transition(QueueStatus.REJECTED, ReviewDecision.HOLD)
        assert isinstance(result, ErrorObject)
        assert result.code == ERR_QUEUE_IMMUTABLE


# ─── AC-CMD-REV-001-2: Hold does not mutate status ───────────────────────

class TestHoldSemantics:
    """AC-CMD-REV-001-2: decision=hold does not mutate queue status."""

    def test_hold_returns_none_status(self):
        """Hold on pending_review returns None (no transition)."""
        result = apply_transition(QueueStatus.PENDING_REVIEW, ReviewDecision.HOLD)
        assert result is None

    def test_hold_in_legal_transitions(self):
        """Hold is in the legal transitions table with None target."""
        key = (QueueStatus.PENDING_REVIEW, ReviewDecision.HOLD)
        assert key in LEGAL_TRANSITIONS
        assert LEGAL_TRANSITIONS[key] is None


# ─── AC-CMD-REV-001-3: Digest mode deterministic mapping ─────────────────

class TestDigestMode:
    """AC-CMD-REV-001-3: Digest mode maps packet decisions to outcomes."""

    def test_digest_mode_returns_envelope(self):
        env = execute_review({
            "digest_path": "/Inbox/ReviewDigest/2026-03-01.md",
        })
        assert env.ok is True
        assert env.command == "review"
        assert "updated" in env.data
        assert "held" in env.data
        assert "decision_record_path" in env.data


# ─── execute_review integration ───────────────────────────────────────────

class TestExecuteReview:

    def test_invalid_input_returns_error_envelope(self):
        env = execute_review({})
        assert env.ok is False
        assert len(env.errors) >= 1
        assert env.errors[0].code == ERR_QUEUE_ITEM_INVALID

    def test_direct_mode_nonexistent_queue_item(self):
        env = execute_review({
            "queue_id": "q-nonexistent",
            "decision": "approve",
        })
        assert env.ok is False
        assert env.errors[0].code == ERR_QUEUE_ITEM_INVALID

    def test_envelope_has_required_keys(self):
        env = execute_review({"queue_id": "q-nonexistent", "decision": "reject"})
        d = env.to_dict()
        assert set(d.keys()) == {"ok", "command", "timestamp", "data", "errors", "warnings", "trace"}


# ─── Data models ──────────────────────────────────────────────────────────

class TestTransitionResult:

    def test_to_dict(self):
        tr = TransitionResult(
            queue_id="q1",
            old_status="pending_review",
            new_status="approved",
        )
        assert tr.to_dict() == {
            "queue_id": "q1",
            "old_status": "pending_review",
            "new_status": "approved",
        }


class TestHoldResult:

    def test_to_dict(self):
        hr = HoldResult(queue_id="q1", hold_until="2026-03-15")
        assert hr.to_dict() == {
            "queue_id": "q1",
            "hold_until": "2026-03-15",
        }

    def test_to_dict_no_hold_until(self):
        hr = HoldResult(queue_id="q1")
        assert hr.to_dict()["hold_until"] is None
