"""
Tests for mycelium.review_queue module (SCH-007).

Verifies:
- AC-SCH-007-1: System refuses to mutate non-pending_review items,
  returning ERR_QUEUE_IMMUTABLE.
- AC-SCH-007-2: Validation and persistence roundtrip.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from mycelium.review_queue import (
    ERR_QUEUE_IMMUTABLE,
    ITEM_TYPES,
    PROPOSED_ACTIONS,
    QUEUE_STATUSES,
    REQUIRED_KEYS,
    build_queue_item,
    check_mutable,
    load_queue_item,
    save_queue_item,
    update_queue_item,
    validate_queue_item,
    validate_queue_item_strict,
)
from mycelium.schema import SchemaValidationError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _valid_item(**overrides: Any) -> dict[str, Any]:
    item = build_queue_item(
        queue_id="qi-001",
        run_id="run-001",
        item_type="source_note",
        target_path="Inbox/Sources/draft-note.md",
        proposed_action="create",
        created_at="2026-03-01T00:00:00Z",
    )
    item.update(overrides)
    return item


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class TestValidateQueueItem:

    def test_valid_item(self):
        errors = validate_queue_item(_valid_item())
        assert errors == []

    def test_missing_required_keys(self):
        errors = validate_queue_item({})
        assert any("Missing required keys" in e for e in errors)

    def test_each_required_key(self):
        for key in REQUIRED_KEYS:
            item = _valid_item()
            del item[key]
            errors = validate_queue_item(item)
            assert len(errors) > 0, f"Missing {key} should produce error"

    @pytest.mark.parametrize("item_type", sorted(ITEM_TYPES))
    def test_valid_item_types(self, item_type: str):
        item = _valid_item(item_type=item_type)
        errors = validate_queue_item(item)
        assert errors == []

    def test_invalid_item_type(self):
        item = _valid_item(item_type="invalid_type")
        errors = validate_queue_item(item)
        assert any("item_type" in e for e in errors)

    @pytest.mark.parametrize("action", sorted(PROPOSED_ACTIONS))
    def test_valid_proposed_actions(self, action: str):
        item = _valid_item(proposed_action=action)
        errors = validate_queue_item(item)
        assert errors == []

    def test_invalid_proposed_action(self):
        item = _valid_item(proposed_action="destroy")
        errors = validate_queue_item(item)
        assert any("proposed_action" in e for e in errors)

    @pytest.mark.parametrize("status", sorted(QUEUE_STATUSES))
    def test_valid_statuses(self, status: str):
        item = _valid_item(status=status)
        errors = validate_queue_item(item)
        assert errors == []

    def test_invalid_status(self):
        item = _valid_item(status="in_progress")
        errors = validate_queue_item(item)
        assert any("status" in e for e in errors)

    def test_invalid_created_at(self):
        item = _valid_item(created_at="not-a-date")
        errors = validate_queue_item(item)
        assert any("created_at" in e for e in errors)

    def test_empty_queue_id(self):
        item = _valid_item(queue_id="")
        errors = validate_queue_item(item)
        assert any("queue_id" in e for e in errors)

    def test_empty_target_path(self):
        item = _valid_item(target_path="  ")
        errors = validate_queue_item(item)
        assert any("target_path" in e for e in errors)

    def test_checks_must_be_dict(self):
        item = _valid_item(checks="not-a-dict")
        errors = validate_queue_item(item)
        assert any("checks" in e for e in errors)

    def test_checks_can_have_arbitrary_keys(self):
        item = _valid_item(checks={"schema_valid": True, "custom_check": {"passed": True}})
        errors = validate_queue_item(item)
        assert errors == []

    def test_strict_raises(self):
        with pytest.raises(SchemaValidationError):
            validate_queue_item_strict({})

    def test_strict_passes_valid(self):
        validate_queue_item_strict(_valid_item())


# ---------------------------------------------------------------------------
# AC-SCH-007-1: Immutability guard
# ---------------------------------------------------------------------------

class TestImmutabilityGuard:

    def test_pending_review_is_mutable(self):
        item = _valid_item(status="pending_review")
        check_mutable(item)  # should not raise

    def test_approved_is_immutable(self):
        item = _valid_item(status="approved")
        with pytest.raises(SchemaValidationError) as exc_info:
            check_mutable(item)
        assert ERR_QUEUE_IMMUTABLE in str(exc_info.value)

    def test_rejected_is_immutable(self):
        item = _valid_item(status="rejected")
        with pytest.raises(SchemaValidationError) as exc_info:
            check_mutable(item)
        assert ERR_QUEUE_IMMUTABLE in str(exc_info.value)

    def test_update_rejects_non_pending(self, tmp_path: Path):
        """AC-SCH-007-1: update_queue_item refuses mutation of approved item."""
        item = _valid_item(status="approved")
        path = save_queue_item(tmp_path, item)
        with pytest.raises(SchemaValidationError) as exc_info:
            update_queue_item(path, {"checks": {"extra": True}})
        assert ERR_QUEUE_IMMUTABLE in str(exc_info.value)

    def test_state_transition_bypasses_guard(self, tmp_path: Path):
        """Explicit state transitions can modify non-pending items."""
        item = _valid_item(status="pending_review")
        path = save_queue_item(tmp_path, item)
        updated = update_queue_item(
            path,
            {"status": "approved"},
            is_state_transition=True,
        )
        assert updated["status"] == "approved"

    def test_state_transition_on_approved(self, tmp_path: Path):
        """State transition can modify already-approved items."""
        item = _valid_item(status="approved")
        path = save_queue_item(tmp_path, item)
        updated = update_queue_item(
            path,
            {"status": "rejected"},
            is_state_transition=True,
        )
        assert updated["status"] == "rejected"


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

class TestBuildQueueItem:

    def test_defaults_to_pending_review(self):
        item = build_queue_item(
            queue_id="qi-1",
            run_id="r1",
            item_type="claim_note",
            target_path="Inbox/Sources/claim.md",
            proposed_action="create",
            created_at="2026-01-01T00:00:00Z",
        )
        assert item["status"] == "pending_review"

    def test_defaults_checks_to_empty_dict(self):
        item = build_queue_item(
            queue_id="qi-1",
            run_id="r1",
            item_type="claim_note",
            target_path="Inbox/Sources/claim.md",
            proposed_action="create",
            created_at="2026-01-01T00:00:00Z",
        )
        assert item["checks"] == {}

    def test_all_required_keys_present(self):
        item = build_queue_item(
            queue_id="qi-1",
            run_id="r1",
            item_type="claim_note",
            target_path="Inbox/Sources/claim.md",
            proposed_action="create",
            created_at="2026-01-01T00:00:00Z",
        )
        assert REQUIRED_KEYS <= set(item.keys())

    def test_built_item_validates(self):
        item = build_queue_item(
            queue_id="qi-1",
            run_id="r1",
            item_type="merge_proposal",
            target_path="Claims/claim-a.md",
            proposed_action="merge",
            created_at="2026-01-01T00:00:00Z",
            checks={"schema_valid": True},
        )
        errors = validate_queue_item(item)
        assert errors == []


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

class TestPersistence:

    def test_save_creates_file(self, tmp_path: Path):
        item = _valid_item()
        path = save_queue_item(tmp_path, item)
        assert path.exists()

    def test_save_under_inbox_reviewqueue(self, tmp_path: Path):
        item = _valid_item()
        path = save_queue_item(tmp_path, item)
        assert "Inbox" in path.parts
        assert "ReviewQueue" in path.parts

    def test_filename_contains_queue_id(self, tmp_path: Path):
        item = _valid_item(queue_id="qi-test-id")
        path = save_queue_item(tmp_path, item)
        assert "qi-test-id" in path.name

    def test_roundtrip(self, tmp_path: Path):
        original = _valid_item(checks={"lint": True, "schema": True})
        path = save_queue_item(tmp_path, original)
        loaded = load_queue_item(path)
        assert loaded["queue_id"] == original["queue_id"]
        assert loaded["run_id"] == original["run_id"]
        assert loaded["item_type"] == original["item_type"]
        assert loaded["status"] == original["status"]
        assert loaded["checks"] == original["checks"]

    def test_save_validates(self, tmp_path: Path):
        with pytest.raises(SchemaValidationError):
            save_queue_item(tmp_path, {"invalid": True})

    def test_load_validates(self, tmp_path: Path):
        bad_path = tmp_path / "Inbox" / "ReviewQueue" / "bad.yaml"
        bad_path.parent.mkdir(parents=True)
        bad_path.write_text("invalid: true\n")
        with pytest.raises(SchemaValidationError):
            load_queue_item(bad_path)

    def test_load_file_not_found(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            load_queue_item(tmp_path / "nonexistent.yaml")

    def test_update_pending_item(self, tmp_path: Path):
        item = _valid_item()
        path = save_queue_item(tmp_path, item)
        updated = update_queue_item(path, {"checks": {"lint": True}})
        assert updated["checks"] == {"lint": True}

    def test_update_persists_changes(self, tmp_path: Path):
        item = _valid_item()
        path = save_queue_item(tmp_path, item)
        update_queue_item(path, {"checks": {"updated": True}})
        reloaded = load_queue_item(path)
        assert reloaded["checks"] == {"updated": True}
