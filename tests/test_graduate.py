"""Tests for the graduate command (CMD-GRD-001).

Verifies acceptance criteria from §5.2.5:
  AC-CMD-GRD-001-1: Per-item atomicity — one failure doesn't block others.
  AC-CMD-GRD-001-2: Promoted notes have status:canon in Canonical Scope.
  AC-CMD-GRD-001-3: dry_run=false + strict=false is forbidden.
  AC-CMD-GRD-001-4: from_digest held items remain pending.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from mycelium.graduate import GraduateInput, graduate
from mycelium.note_io import read_note, write_note


def _create_draft_note(
    vault: Path,
    vault_path: str,
    note_type: str = "source",
    note_id: str = "s-001",
    extra_fm: dict[str, Any] | None = None,
    body: str = "Test content.",
) -> None:
    """Helper to create a draft note in the vault."""
    fm: dict[str, Any] = {
        "type": note_type,
        "id": note_id,
        "status": "draft",
        "created": "2026-03-01T00:00:00Z",
        "updated": "2026-03-01T00:00:00Z",
    }
    if extra_fm:
        fm.update(extra_fm)
    write_note(vault / vault_path, fm, body)


# ─── AC-CMD-GRD-001-2: Promoted notes have status:canon ────────────────────

class TestBasicPromotion:
    """AC-CMD-GRD-001-2: On success, each promoted Note has status:canon
    and resides in a Canonical Directory."""

    def test_promote_source_note(self, tmp_path: Path):
        vault = tmp_path
        _create_draft_note(vault, "Inbox/Sources/s-001.md", "source", "s-001")

        result = graduate(
            vault,
            GraduateInput(strict=True),
            [{"queue_id": "q1", "path": "Inbox/Sources/s-001.md", "decision": "approve"}],
        )

        assert result.ok is True
        assert len(result.data["promoted"]) == 1
        assert result.data["promoted"][0]["to_path"] == "Sources/s-001.md"

        # Verify the canonical note has status: canon
        fm, _ = read_note(vault / "Sources" / "s-001.md")
        assert fm["status"] == "canon"

    def test_promote_claim_note(self, tmp_path: Path):
        vault = tmp_path
        _create_draft_note(
            vault, "Inbox/Sources/c-001.md", "claim", "c-001",
            extra_fm={
                "claim_text": "Test claim",
                "claim_type": "empirical",
                "polarity": "supports",
                "provenance": {
                    "source_id": "s-001",
                    "source_ref": "https://example.com",
                    "locator": {"raw_locator": "p1"},
                },
            },
        )

        result = graduate(
            vault,
            GraduateInput(strict=True),
            [{"queue_id": "q1", "path": "Inbox/Sources/c-001.md", "decision": "approve"}],
        )

        assert result.ok is True
        assert result.data["promoted"][0]["to_path"] == "Claims/c-001.md"
        fm, _ = read_note(vault / "Claims" / "c-001.md")
        assert fm["status"] == "canon"

    def test_promote_concept_note(self, tmp_path: Path):
        vault = tmp_path
        _create_draft_note(vault, "Inbox/Sources/con-001.md", "concept", "con-001")

        result = graduate(
            vault,
            GraduateInput(strict=True),
            [{"queue_id": "q1", "path": "Inbox/Sources/con-001.md", "decision": "approve"}],
        )

        assert result.data["promoted"][0]["to_path"] == "Concepts/con-001.md"


# ─── AC-CMD-GRD-001-1: Per-item atomicity ──────────────────────────────────

class TestPerItemAtomicity:
    """AC-CMD-GRD-001-1: If a queue item fails validation, that item results
    in no canonical changes while other valid items may still be promoted."""

    def test_valid_item_promoted_despite_invalid_sibling(self, tmp_path: Path):
        vault = tmp_path
        # Valid note
        _create_draft_note(vault, "Inbox/Sources/good.md", "source", "good")
        # Invalid note (missing required keys — no frontmatter content)
        (vault / "Inbox" / "Sources" / "bad.md").parent.mkdir(parents=True, exist_ok=True)
        (vault / "Inbox" / "Sources" / "bad.md").write_text("no frontmatter")

        result = graduate(
            vault,
            GraduateInput(strict=True),
            [
                {"queue_id": "q1", "path": "Inbox/Sources/good.md", "decision": "approve"},
                {"queue_id": "q2", "path": "Inbox/Sources/bad.md", "decision": "approve"},
            ],
        )

        assert result.ok is True
        assert len(result.data["promoted"]) == 1
        assert len(result.data["rejected"]) == 1
        assert result.data["promoted"][0]["queue_id"] == "q1"
        assert result.data["rejected"][0]["queue_id"] == "q2"

    def test_missing_file_rejected(self, tmp_path: Path):
        result = graduate(
            tmp_path,
            GraduateInput(strict=True),
            [{"queue_id": "q1", "path": "Inbox/Sources/nope.md", "decision": "approve"}],
        )

        assert result.ok is True
        assert len(result.data["rejected"]) == 1
        assert "Cannot read note" in result.data["rejected"][0]["reason"]

    def test_claim_missing_provenance_rejected(self, tmp_path: Path):
        vault = tmp_path
        _create_draft_note(vault, "Inbox/Sources/c-bad.md", "claim", "c-bad")
        # No provenance fields added

        result = graduate(
            vault,
            GraduateInput(strict=True),
            [{"queue_id": "q1", "path": "Inbox/Sources/c-bad.md", "decision": "approve"}],
        )

        assert len(result.data["rejected"]) == 1
        assert "provenance" in result.data["rejected"][0]["reason"].lower()


# ─── AC-CMD-GRD-001-3: dry_run=false + strict=false forbidden ──────────────

class TestStrictConstraint:
    """AC-CMD-GRD-001-3: graduate with dry_run=false rejects strict=false."""

    def test_real_run_strict_false_rejected(self, tmp_path: Path):
        result = graduate(
            tmp_path,
            GraduateInput(dry_run=False, strict=False),
            [],
        )

        assert result.ok is False
        assert len(result.errors) == 1
        assert result.errors[0].code == "ERR_SCHEMA_VALIDATION"
        assert "dry_run=false" in result.errors[0].message

    def test_dry_run_strict_false_allowed(self, tmp_path: Path):
        vault = tmp_path
        _create_draft_note(vault, "Inbox/Sources/s-001.md", "source", "s-001")

        result = graduate(
            vault,
            GraduateInput(dry_run=True, strict=False),
            [{"queue_id": "q1", "path": "Inbox/Sources/s-001.md", "decision": "approve"}],
        )

        assert result.ok is True
        assert len(result.data["promoted"]) == 1
        # Dry run: canonical file should NOT exist
        assert not (vault / "Sources" / "s-001.md").exists()


# ─── AC-CMD-GRD-001-4: held items remain pending ───────────────────────────

class TestHeldItems:
    """AC-CMD-GRD-001-4: from_digest applies only items explicitly approved;
    held items remain pending."""

    def test_held_items_skipped(self, tmp_path: Path):
        vault = tmp_path
        _create_draft_note(vault, "Inbox/Sources/s-001.md", "source", "s-001")

        result = graduate(
            vault,
            GraduateInput(strict=True),
            [
                {"queue_id": "q1", "path": "Inbox/Sources/s-001.md", "decision": "hold"},
            ],
        )

        assert result.ok is True
        assert len(result.data["promoted"]) == 0
        assert len(result.data["skipped"]) == 1
        assert result.data["skipped"][0]["reason"] == "held"
        # Draft note still exists unchanged
        fm, _ = read_note(vault / "Inbox" / "Sources" / "s-001.md")
        assert fm["status"] == "draft"

    def test_rejected_items_skipped(self, tmp_path: Path):
        vault = tmp_path
        _create_draft_note(vault, "Inbox/Sources/s-001.md", "source", "s-001")

        result = graduate(
            vault,
            GraduateInput(strict=True),
            [
                {"queue_id": "q1", "path": "Inbox/Sources/s-001.md", "decision": "reject"},
            ],
        )

        assert result.ok is True
        assert len(result.data["skipped"]) == 1
        assert "rejected" in result.data["skipped"][0]["reason"]

    def test_mixed_decisions(self, tmp_path: Path):
        vault = tmp_path
        _create_draft_note(vault, "Inbox/Sources/a.md", "source", "a")
        _create_draft_note(vault, "Inbox/Sources/b.md", "source", "b")
        _create_draft_note(vault, "Inbox/Sources/c.md", "source", "c")

        result = graduate(
            vault,
            GraduateInput(strict=True),
            [
                {"queue_id": "q1", "path": "Inbox/Sources/a.md", "decision": "approve"},
                {"queue_id": "q2", "path": "Inbox/Sources/b.md", "decision": "hold"},
                {"queue_id": "q3", "path": "Inbox/Sources/c.md", "decision": "reject"},
            ],
        )

        assert result.ok is True
        assert len(result.data["promoted"]) == 1
        assert len(result.data["skipped"]) == 2
        assert result.data["promoted"][0]["queue_id"] == "q1"


# ─── Dry run ───────────────────────────────────────────────────────────────

class TestDryRun:

    def test_dry_run_no_writes(self, tmp_path: Path):
        vault = tmp_path
        _create_draft_note(vault, "Inbox/Sources/s-001.md", "source", "s-001")

        result = graduate(
            vault,
            GraduateInput(dry_run=True, strict=True),
            [{"queue_id": "q1", "path": "Inbox/Sources/s-001.md", "decision": "approve"}],
        )

        assert result.ok is True
        assert len(result.data["promoted"]) == 1
        # No canonical file created
        assert not (vault / "Sources" / "s-001.md").exists()
        # Draft still has draft status
        fm, _ = read_note(vault / "Inbox" / "Sources" / "s-001.md")
        assert fm["status"] == "draft"


# ─── Output envelope ──────────────────────────────────────────────────────

# ─── Overwrite guard ─────────────────────────────────────────────────────

class TestOverwriteGuard:
    """Promotion must not overwrite an existing canonical note."""

    def test_rejects_if_canonical_exists(self, tmp_path: Path):
        vault = tmp_path
        _create_draft_note(vault, "Inbox/Sources/s-001.md", "source", "s-001")
        # Pre-create the canonical note
        (vault / "Sources").mkdir(parents=True, exist_ok=True)
        (vault / "Sources" / "s-001.md").write_text("existing canonical content")

        result = graduate(
            vault,
            GraduateInput(strict=True),
            [{"queue_id": "q1", "path": "Inbox/Sources/s-001.md", "decision": "approve"}],
        )

        assert result.ok is True
        assert len(result.data["rejected"]) == 1
        assert "already exists" in result.data["rejected"][0]["reason"]
        # Original canonical content is untouched
        assert (vault / "Sources" / "s-001.md").read_text() == "existing canonical content"

    def test_promotes_when_canonical_absent(self, tmp_path: Path):
        vault = tmp_path
        _create_draft_note(vault, "Inbox/Sources/s-002.md", "source", "s-002")

        result = graduate(
            vault,
            GraduateInput(strict=True),
            [{"queue_id": "q1", "path": "Inbox/Sources/s-002.md", "decision": "approve"}],
        )

        assert result.ok is True
        assert len(result.data["promoted"]) == 1
        assert (vault / "Sources" / "s-002.md").exists()


# ─── Queue status update ────────────────────────────────────────────────

class TestQueueStatusUpdate:
    """After promotion, the queue item status should be updated to 'approved'."""

    def test_queue_item_updated_on_promote(self, tmp_path: Path):
        import yaml as _yaml

        vault = tmp_path
        _create_draft_note(vault, "Inbox/Sources/s-001.md", "source", "s-001")

        # Create a matching queue item file
        queue_dir = vault / "Inbox" / "ReviewQueue"
        queue_dir.mkdir(parents=True, exist_ok=True)
        queue_item = {
            "queue_id": "q1",
            "run_id": "run-1",
            "item_type": "source_note",
            "target_path": "Inbox/Sources/s-001.md",
            "proposed_action": "promote_to_canon",
            "status": "pending_review",
            "created_at": "2026-03-01T00:00:00Z",
            "checks": {},
        }
        (queue_dir / "q1.yaml").write_text(
            _yaml.safe_dump(queue_item, default_flow_style=False)
        )

        result = graduate(
            vault,
            GraduateInput(strict=True),
            [{"queue_id": "q1", "path": "Inbox/Sources/s-001.md", "decision": "approve"}],
        )

        assert result.ok is True
        assert len(result.data["promoted"]) == 1

        # Queue item should now be "approved"
        updated = _yaml.safe_load((queue_dir / "q1.yaml").read_text())
        assert updated["status"] == "approved"


# ─── Draft cleanup ──────────────────────────────────────────────────────

class TestDraftCleanup:
    """After successful promotion, the original draft file should be removed."""

    def test_draft_removed_after_promotion(self, tmp_path: Path):
        vault = tmp_path
        _create_draft_note(vault, "Inbox/Sources/s-001.md", "source", "s-001")
        assert (vault / "Inbox" / "Sources" / "s-001.md").exists()

        result = graduate(
            vault,
            GraduateInput(strict=True),
            [{"queue_id": "q1", "path": "Inbox/Sources/s-001.md", "decision": "approve"}],
        )

        assert result.ok is True
        assert len(result.data["promoted"]) == 1
        # Draft should be gone
        assert not (vault / "Inbox" / "Sources" / "s-001.md").exists()
        # Canonical should exist
        assert (vault / "Sources" / "s-001.md").exists()

    def test_draft_preserved_on_dry_run(self, tmp_path: Path):
        vault = tmp_path
        _create_draft_note(vault, "Inbox/Sources/s-001.md", "source", "s-001")

        result = graduate(
            vault,
            GraduateInput(dry_run=True, strict=True),
            [{"queue_id": "q1", "path": "Inbox/Sources/s-001.md", "decision": "approve"}],
        )

        assert result.ok is True
        # Draft should still exist (dry run doesn't write or delete)
        assert (vault / "Inbox" / "Sources" / "s-001.md").exists()

    def test_draft_preserved_when_held(self, tmp_path: Path):
        vault = tmp_path
        _create_draft_note(vault, "Inbox/Sources/s-001.md", "source", "s-001")

        result = graduate(
            vault,
            GraduateInput(strict=True),
            [{"queue_id": "q1", "path": "Inbox/Sources/s-001.md", "decision": "hold"}],
        )

        assert result.ok is True
        assert (vault / "Inbox" / "Sources" / "s-001.md").exists()


# ─── Output envelope ──────────────────────────────────────────────────────

class TestOutputEnvelope:

    def test_envelope_has_correct_command(self, tmp_path: Path):
        result = graduate(tmp_path, GraduateInput(strict=True), [])
        assert result.command == "graduate"
        assert result.ok is True

    def test_envelope_data_keys(self, tmp_path: Path):
        result = graduate(tmp_path, GraduateInput(strict=True), [])
        assert "promoted" in result.data
        assert "rejected" in result.data
        assert "skipped" in result.data
        assert "audit_event_ids" in result.data
