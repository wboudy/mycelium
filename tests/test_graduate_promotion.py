"""
Tests for promotion semantics (REV-003).

Acceptance Criteria:
- AC-REV-003-1: After successful Promotion, every promoted Note validates
  and has status: canon.
- AC-REV-003-2: Audit log contains entry listing promoted paths and actor.
- AC-REV-003-3: graduate with dry_run=false, strict=false fails with
  ERR_SCHEMA_VALIDATION.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from mycelium.audit import read_audit_log
from mycelium.graduate import (
    GraduateInput,
    PromotionResult,
    RejectionResult,
    _resolve_canonical_path,
    _validate_queue_item,
    graduate,
)
from mycelium.note_io import read_note, write_note


def _create_draft_note(
    vault_root: Path,
    vault_path: str,
    *,
    note_type: str = "source",
    note_id: str = "test-note",
    status: str = "draft",
    extra_fm: dict[str, Any] | None = None,
) -> Path:
    """Helper to create a valid draft note for testing."""
    fm: dict[str, Any] = {
        "id": note_id,
        "type": note_type,
        "status": status,
        "created": "2026-01-01T00:00:00Z",
        "updated": "2026-01-01T00:00:00Z",
    }
    if extra_fm:
        fm.update(extra_fm)

    full_path = vault_root / vault_path
    write_note(full_path, fm, "# Test Note\n\nSome content.\n")
    return full_path


# ---------------------------------------------------------------------------
# AC-REV-003-1: Promoted notes have status: canon
# ---------------------------------------------------------------------------

class TestPromotionStatus:

    def test_promoted_note_has_canon_status(self, tmp_path: Path):
        _create_draft_note(
            tmp_path, "Inbox/Sources/test-note.md",
            note_id="test-note", note_type="source",
        )
        params = GraduateInput(all_approved=True, actor="test-user")
        items = [{"queue_id": "q-1", "path": "Inbox/Sources/test-note.md", "decision": "approve"}]

        env = graduate(tmp_path, params, items)
        assert env.ok is True
        assert len(env.data["promoted"]) == 1

        # Read the promoted note and verify status
        canonical_path = tmp_path / "Sources" / "test-note.md"
        assert canonical_path.exists()
        fm, _ = read_note(canonical_path)
        assert fm["status"] == "canon"

    def test_promoted_note_validates(self, tmp_path: Path):
        _create_draft_note(
            tmp_path, "Inbox/Sources/valid-note.md",
            note_id="valid-note", note_type="source",
        )
        params = GraduateInput(all_approved=True, actor="tester")
        items = [{"queue_id": "q-2", "path": "Inbox/Sources/valid-note.md", "decision": "approve"}]

        env = graduate(tmp_path, params, items)
        assert env.ok is True
        # The note was successfully promoted (no validation errors)
        assert len(env.data["rejected"]) == 0

    def test_multiple_items_per_item_atomicity(self, tmp_path: Path):
        # Create one valid and one invalid note
        _create_draft_note(
            tmp_path, "Inbox/Sources/good.md",
            note_id="good", note_type="source",
        )
        # Invalid: not in draft scope
        _create_draft_note(
            tmp_path, "Sources/bad.md",
            note_id="bad", note_type="source",
        )

        params = GraduateInput(all_approved=True, actor="tester")
        items = [
            {"queue_id": "q-good", "path": "Inbox/Sources/good.md", "decision": "approve"},
            {"queue_id": "q-bad", "path": "Sources/bad.md", "decision": "approve"},
        ]

        env = graduate(tmp_path, params, items)
        assert env.ok is True
        # Good item promoted, bad item rejected
        assert len(env.data["promoted"]) == 1
        assert len(env.data["rejected"]) == 1
        assert env.data["promoted"][0]["queue_id"] == "q-good"


# ---------------------------------------------------------------------------
# AC-REV-003-2: Audit log contains entry with promoted paths and actor
# ---------------------------------------------------------------------------

class TestPromotionAudit:

    def test_audit_entry_written(self, tmp_path: Path):
        _create_draft_note(
            tmp_path, "Inbox/Sources/audit-test.md",
            note_id="audit-test", note_type="source",
        )
        params = GraduateInput(all_approved=True, actor="auditor-user")
        items = [{"queue_id": "q-a", "path": "Inbox/Sources/audit-test.md", "decision": "approve"}]

        env = graduate(tmp_path, params, items)
        assert env.ok is True
        assert len(env.data["audit_event_ids"]) == 1

        # Read audit log
        audit_files = list((tmp_path / "Logs" / "Audit").glob("*.jsonl"))
        assert len(audit_files) == 1
        events = read_audit_log(audit_files[0])
        assert len(events) >= 1

        promotion_events = [e for e in events if e.event_type == "promotion_applied"]
        assert len(promotion_events) == 1
        evt = promotion_events[0]
        assert evt.actor == "auditor-user"
        assert "Sources/audit-test.md" in evt.targets
        assert evt.details["promoted_count"] == 1

    def test_audit_includes_actor(self, tmp_path: Path):
        _create_draft_note(
            tmp_path, "Inbox/Sources/actor-test.md",
            note_id="actor-test", note_type="source",
        )
        params = GraduateInput(all_approved=True, actor="specific-reviewer")
        items = [{"queue_id": "q-b", "path": "Inbox/Sources/actor-test.md", "decision": "approve"}]

        env = graduate(tmp_path, params, items)
        audit_files = list((tmp_path / "Logs" / "Audit").glob("*.jsonl"))
        events = read_audit_log(audit_files[0])
        promotion_events = [e for e in events if e.event_type == "promotion_applied"]
        assert promotion_events[0].actor == "specific-reviewer"

    def test_dry_run_no_audit(self, tmp_path: Path):
        _create_draft_note(
            tmp_path, "Inbox/Sources/dry-run.md",
            note_id="dry-run", note_type="source",
        )
        params = GraduateInput(all_approved=True, dry_run=True, actor="dry-user")
        items = [{"queue_id": "q-dry", "path": "Inbox/Sources/dry-run.md", "decision": "approve"}]

        env = graduate(tmp_path, params, items)
        assert env.ok is True
        assert len(env.data["promoted"]) == 1
        # No audit files should exist (dry run)
        audit_dir = tmp_path / "Logs" / "Audit"
        assert not audit_dir.exists() or len(list(audit_dir.glob("*.jsonl"))) == 0


# ---------------------------------------------------------------------------
# AC-REV-003-3: dry_run=false + strict=false → ERR_SCHEMA_VALIDATION
# ---------------------------------------------------------------------------

class TestStrictRequirement:

    def test_non_strict_non_dry_run_fails(self, tmp_path: Path):
        params = GraduateInput(all_approved=True, dry_run=False, strict=False)
        env = graduate(tmp_path, params, [])
        assert env.ok is False
        assert any(e.code == "ERR_SCHEMA_VALIDATION" for e in env.errors)

    def test_strict_non_dry_run_allowed(self, tmp_path: Path):
        params = GraduateInput(all_approved=True, dry_run=False, strict=True)
        env = graduate(tmp_path, params, [])
        assert env.ok is True

    def test_non_strict_dry_run_allowed(self, tmp_path: Path):
        params = GraduateInput(all_approved=True, dry_run=True, strict=False)
        env = graduate(tmp_path, params, [])
        assert env.ok is True


# ---------------------------------------------------------------------------
# Held and rejected items
# ---------------------------------------------------------------------------

class TestHeldAndRejected:

    def test_held_items_skipped(self, tmp_path: Path):
        _create_draft_note(
            tmp_path, "Inbox/Sources/held.md",
            note_id="held", note_type="source",
        )
        params = GraduateInput(all_approved=True, actor="test")
        items = [{"queue_id": "q-held", "path": "Inbox/Sources/held.md", "decision": "hold"}]

        env = graduate(tmp_path, params, items)
        assert env.ok is True
        assert len(env.data["promoted"]) == 0
        assert len(env.data["skipped"]) == 1
        assert env.data["skipped"][0]["reason"] == "held"

    def test_rejected_items_skipped(self, tmp_path: Path):
        params = GraduateInput(all_approved=True, actor="test")
        items = [{"queue_id": "q-rej", "path": "Inbox/Sources/rej.md", "decision": "reject"}]

        env = graduate(tmp_path, params, items)
        assert env.ok is True
        assert len(env.data["skipped"]) == 1

    def test_missing_note_rejected(self, tmp_path: Path):
        params = GraduateInput(all_approved=True, actor="test")
        items = [{"queue_id": "q-miss", "path": "Inbox/Sources/missing.md", "decision": "approve"}]

        env = graduate(tmp_path, params, items)
        assert env.ok is True
        assert len(env.data["rejected"]) == 1
        assert "Cannot read note" in env.data["rejected"][0]["reason"]


# ---------------------------------------------------------------------------
# _resolve_canonical_path
# ---------------------------------------------------------------------------

class TestResolveCanonicalPath:

    def test_source(self):
        assert _resolve_canonical_path("source", "my-note") == "Sources/my-note.md"

    def test_claim(self):
        assert _resolve_canonical_path("claim", "c-1") == "Claims/c-1.md"

    def test_concept(self):
        assert _resolve_canonical_path("concept", "x") == "Concepts/x.md"

    def test_question(self):
        assert _resolve_canonical_path("question", "q") == "Questions/q.md"

    def test_unknown_defaults_to_sources(self):
        assert _resolve_canonical_path("unknown_type", "u") == "Sources/u.md"
