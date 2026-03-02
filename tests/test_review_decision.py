"""
Tests for Review Decision Record schema validation (SCH-010).

Verifies:
  AC-SCH-010-1: Validates against the schema (required keys, enums, formats).
  AC-SCH-010-2: Hold decisions have new_status=pending_review and hold_until present.
"""

from __future__ import annotations

import pytest

from mycelium.review_decision import (
    DECISION_MODES,
    QUEUE_STATUSES,
    REQUIRED_KEYS,
    RESULT_REQUIRED_KEYS,
    SchemaValidationError,
    validate_review_decision,
    validate_review_decision_strict,
)


def _valid_record(**overrides) -> dict:
    """Build a minimal valid Review Decision Record."""
    base = {
        "decision_id": "dec-001",
        "created_at": "2026-03-01T12:00:00Z",
        "mode": "direct",
        "actor": "user@example.com",
        "reason": "Reviewed and approved",
        "results": [
            {
                "queue_id": "q-001",
                "old_status": "pending_review",
                "new_status": "approved",
            }
        ],
    }
    base.update(overrides)
    return base


def _hold_result(**overrides) -> dict:
    """Build a hold result entry (pending_review -> pending_review)."""
    base = {
        "queue_id": "q-002",
        "old_status": "pending_review",
        "new_status": "pending_review",
        "hold_until": "2026-04-01",
    }
    base.update(overrides)
    return base


# ─── Valid records ────────────────────────────────────────────────────────

class TestValidRecord:

    def test_minimal_valid(self):
        errors = validate_review_decision(_valid_record())
        assert errors == []

    def test_with_null_reason(self):
        errors = validate_review_decision(_valid_record(reason=None))
        assert errors == []

    def test_with_empty_results(self):
        errors = validate_review_decision(_valid_record(results=[]))
        assert errors == []

    def test_digest_mode(self):
        errors = validate_review_decision(_valid_record(mode="digest"))
        assert errors == []

    def test_unknown_keys_ignored(self):
        rec = _valid_record(extra_field="ignored")
        errors = validate_review_decision(rec)
        assert errors == []


# ─── Required keys ────────────────────────────────────────────────────────

class TestRequiredKeys:

    @pytest.mark.parametrize("key", REQUIRED_KEYS)
    def test_missing_required_key(self, key):
        rec = _valid_record()
        del rec[key]
        errors = validate_review_decision(rec)
        assert any(key in e for e in errors)

    def test_empty_decision_id(self):
        errors = validate_review_decision(_valid_record(decision_id=""))
        assert any("decision_id" in e for e in errors)

    def test_empty_actor(self):
        errors = validate_review_decision(_valid_record(actor="  "))
        assert any("actor" in e for e in errors)


# ─── Field validation ────────────────────────────────────────────────────

class TestFieldValidation:

    def test_invalid_created_at(self):
        errors = validate_review_decision(_valid_record(created_at="not-a-date"))
        assert any("created_at" in e for e in errors)

    def test_invalid_mode(self):
        errors = validate_review_decision(_valid_record(mode="batch"))
        assert any("mode" in e for e in errors)

    def test_invalid_reason_type(self):
        errors = validate_review_decision(_valid_record(reason=123))
        assert any("reason" in e for e in errors)

    def test_results_not_array(self):
        errors = validate_review_decision(_valid_record(results="not-array"))
        assert any("results" in e and "array" in e for e in errors)


# ─── Results entry validation ─────────────────────────────────────────────

class TestResultEntry:

    @pytest.mark.parametrize("key", RESULT_REQUIRED_KEYS)
    def test_missing_result_key(self, key):
        result = {
            "queue_id": "q-001",
            "old_status": "pending_review",
            "new_status": "approved",
        }
        del result[key]
        errors = validate_review_decision(_valid_record(results=[result]))
        assert any(key in e for e in errors)

    def test_invalid_old_status(self):
        result = {
            "queue_id": "q-001",
            "old_status": "unknown",
            "new_status": "approved",
        }
        errors = validate_review_decision(_valid_record(results=[result]))
        assert any("old_status" in e for e in errors)

    def test_invalid_new_status(self):
        result = {
            "queue_id": "q-001",
            "old_status": "pending_review",
            "new_status": "unknown",
        }
        errors = validate_review_decision(_valid_record(results=[result]))
        assert any("new_status" in e for e in errors)

    def test_result_not_object(self):
        errors = validate_review_decision(_valid_record(results=["not-obj"]))
        assert any("object" in e for e in errors)

    def test_empty_queue_id(self):
        result = {
            "queue_id": "",
            "old_status": "pending_review",
            "new_status": "approved",
        }
        errors = validate_review_decision(_valid_record(results=[result]))
        assert any("queue_id" in e for e in errors)

    def test_multiple_results(self):
        results = [
            {"queue_id": "q-1", "old_status": "pending_review", "new_status": "approved"},
            {"queue_id": "q-2", "old_status": "pending_review", "new_status": "rejected"},
        ]
        errors = validate_review_decision(_valid_record(results=results))
        assert errors == []


# ─── AC-SCH-010-2: Hold decisions ────────────────────────────────────────

class TestHoldDecisions:
    """AC-SCH-010-2: hold decisions have new_status=pending_review and hold_until."""

    def test_valid_hold(self):
        rec = _valid_record(results=[_hold_result()])
        errors = validate_review_decision(rec)
        assert errors == []

    def test_hold_missing_hold_until(self):
        result = _hold_result()
        del result["hold_until"]
        errors = validate_review_decision(_valid_record(results=[result]))
        assert any("hold_until" in e for e in errors)

    def test_hold_null_hold_until(self):
        result = _hold_result(hold_until=None)
        errors = validate_review_decision(_valid_record(results=[result]))
        assert any("hold_until" in e for e in errors)

    def test_hold_invalid_date_format(self):
        result = _hold_result(hold_until="March 1, 2026")
        errors = validate_review_decision(_valid_record(results=[result]))
        assert any("YYYY-MM-DD" in e for e in errors)

    def test_non_hold_no_hold_until_required(self):
        """Approve/reject transitions don't require hold_until."""
        result = {
            "queue_id": "q-001",
            "old_status": "pending_review",
            "new_status": "approved",
        }
        errors = validate_review_decision(_valid_record(results=[result]))
        assert errors == []

    def test_hold_with_details(self):
        result = _hold_result(details={"reason": "needs more evidence"})
        errors = validate_review_decision(_valid_record(results=[result]))
        assert errors == []


# ─── Strict mode ──────────────────────────────────────────────────────────

class TestStrictMode:

    def test_valid_does_not_raise(self):
        validate_review_decision_strict(_valid_record())

    def test_invalid_raises(self):
        rec = _valid_record()
        del rec["decision_id"]
        with pytest.raises(SchemaValidationError) as exc_info:
            validate_review_decision_strict(rec)
        assert "decision_id" in str(exc_info.value)

    def test_error_contains_all_failures(self):
        rec = {}
        with pytest.raises(SchemaValidationError) as exc_info:
            validate_review_decision_strict(rec)
        assert len(exc_info.value.errors) >= len(REQUIRED_KEYS)


# ─── Enum coverage ───────────────────────────────────────────────────────

class TestEnumCoverage:

    def test_all_modes_valid(self):
        for mode in DECISION_MODES:
            errors = validate_review_decision(_valid_record(mode=mode))
            assert errors == [], f"mode={mode} should be valid"

    def test_all_statuses_valid_as_old(self):
        for st in QUEUE_STATUSES:
            result = {
                "queue_id": "q-1",
                "old_status": st,
                "new_status": "approved",
            }
            rec = _valid_record(results=[result])
            errors = validate_review_decision(rec)
            status_errors = [e for e in errors if "old_status" in e]
            assert status_errors == [], f"old_status={st} should be valid"

    def test_all_statuses_valid_as_new(self):
        for st in QUEUE_STATUSES:
            # Skip pending_review->pending_review (hold) without hold_until
            if st == "pending_review":
                continue
            result = {
                "queue_id": "q-1",
                "old_status": "pending_review",
                "new_status": st,
            }
            rec = _valid_record(results=[result])
            errors = validate_review_decision(rec)
            status_errors = [e for e in errors if "new_status" in e]
            assert status_errors == [], f"new_status={st} should be valid"
