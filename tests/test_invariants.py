"""Tests for system invariant enforcement (§3).

Verifies acceptance criteria for:
  INV-002:
    AC-INV-002-1: Running ingestion and other commands without Promotion produces
                  no diffs under Canonical Scope and does not change any Note
                  with status: canon.
    AC-INV-002-2: Attempted writes targeting Canonical Scope without Promotion
                  return ERR_CANON_WRITE_FORBIDDEN and produce no file mutation.
  INV-003:
    AC-INV-003-1: For any ingestion run that generates Notes, all newly created
                  Notes are status: draft and located in Draft Scope.
    AC-INV-003-2: Dry Run mode produces no filesystem writes and returns planned
                  operations instead.
  INV-004:
    AC-INV-004-1: Schema validation fails for any Claim Note missing required
                  Provenance fields (per SCH-003).
    AC-INV-004-2: Promotion refuses any Claim Note missing required Provenance,
                  returning ERR_PROVENANCE_MISSING.
"""

from __future__ import annotations

import pytest

from mycelium.invariants import (
    IngestionOutcome,
    SourceIdentity,
    WriteOperation,
    check_write_batch,
    resolve_source_identity,
    validate_canon_protection,
    validate_draft_first,
    validate_provenance_required,
)


# ─── AC-INV-002-1: No diffs under Canonical Scope without Promotion ─────────

class TestCanonProtection:
    """AC-INV-002-1 and AC-INV-002-2: Canonical notes are protected."""

    @pytest.mark.parametrize("canonical_dir", [
        "Sources", "Claims", "Concepts", "Questions", "Projects", "MOCs",
    ])
    def test_rejects_write_to_canonical_scope(self, canonical_dir: str):
        """AC-INV-002-2: Writes to Canonical Scope return ERR_CANON_WRITE_FORBIDDEN."""
        err = validate_canon_protection(f"{canonical_dir}/note.md", None)
        assert err is not None
        assert err.code == "ERR_CANON_WRITE_FORBIDDEN"
        assert err.retryable is False
        assert "INV-002" in err.message

    def test_rejects_modification_of_canon_note(self):
        """AC-INV-002-1: Cannot modify a note with status: canon."""
        err = validate_canon_protection("Inbox/Sources/note.md", "canon")
        assert err is not None
        assert err.code == "ERR_CANON_WRITE_FORBIDDEN"
        assert "canon" in err.message

    def test_allows_draft_note_modification(self):
        err = validate_canon_protection("Inbox/Sources/note.md", "draft")
        assert err is None

    def test_allows_reviewed_note_modification(self):
        err = validate_canon_protection("Inbox/Sources/note.md", "reviewed")
        assert err is None

    def test_allows_new_note_in_draft_scope(self):
        err = validate_canon_protection("Inbox/Sources/new.md", None)
        assert err is None

    def test_promotion_allows_canonical_write(self):
        err = validate_canon_protection("Sources/note.md", None, is_promotion=True)
        assert err is None

    def test_promotion_allows_canon_note_modification(self):
        err = validate_canon_protection("Inbox/Sources/note.md", "canon", is_promotion=True)
        assert err is None

    def test_error_details_for_canonical_scope(self):
        err = validate_canon_protection("Claims/c.md", None)
        assert err.details["path"] == "Claims/c.md"
        assert err.details["invariant"] == "INV-002"

    def test_error_details_for_canon_status(self):
        err = validate_canon_protection("Inbox/Sources/note.md", "canon")
        assert err.details["existing_status"] == "canon"
        assert err.details["invariant"] == "INV-002"


# ─── AC-INV-003-1: Draft status + Draft Scope ──────────────────────────────

class TestValidateDraftFirst:
    """AC-INV-003-1: Agent-generated notes must be status:draft in Draft Scope."""

    def test_valid_draft_in_inbox(self):
        err = validate_draft_first("Inbox/Sources/note.md", "draft")
        assert err is None

    def test_valid_draft_in_reports(self):
        err = validate_draft_first("Reports/Delta/run.yaml", "draft")
        assert err is None

    def test_valid_draft_in_quarantine(self):
        err = validate_draft_first("Quarantine/bad.md", "draft")
        assert err is None

    def test_rejects_canonical_scope_write(self):
        err = validate_draft_first("Sources/note.md", "draft")
        assert err is not None
        assert err.code == "ERR_CANON_WRITE_FORBIDDEN"
        assert err.retryable is False
        assert "INV-003" in err.message

    @pytest.mark.parametrize("canonical_dir", [
        "Sources", "Claims", "Concepts", "Questions", "Projects", "MOCs",
    ])
    def test_rejects_all_canonical_dirs(self, canonical_dir: str):
        err = validate_draft_first(f"{canonical_dir}/note.md", "draft")
        assert err is not None
        assert err.code == "ERR_CANON_WRITE_FORBIDDEN"

    def test_rejects_non_draft_status(self):
        err = validate_draft_first("Inbox/Sources/note.md", "canon")
        assert err is not None
        assert err.code == "ERR_STATUS_MUST_BE_DRAFT"
        assert err.retryable is False
        assert "canon" in err.message

    def test_rejects_reviewed_status(self):
        err = validate_draft_first("Inbox/Sources/note.md", "reviewed")
        assert err is not None
        assert err.code == "ERR_STATUS_MUST_BE_DRAFT"

    def test_promotion_bypasses_canonical_guard(self):
        err = validate_draft_first("Sources/note.md", "canon", is_promotion=True)
        assert err is None

    def test_promotion_bypasses_status_guard(self):
        err = validate_draft_first("Inbox/Sources/note.md", "canon", is_promotion=True)
        assert err is None

    def test_error_details_include_path(self):
        err = validate_draft_first("Claims/claim.md", "draft")
        assert err.details["path"] == "Claims/claim.md"
        assert err.details["invariant"] == "INV-003"

    def test_error_details_include_status(self):
        err = validate_draft_first("Inbox/Sources/note.md", "reviewed")
        assert err.details["status"] == "reviewed"
        assert err.details["expected"] == "draft"


# ─── AC-INV-003-2: Dry Run returns planned operations ──────────────────────

class TestDryRun:
    """AC-INV-003-2: Dry Run produces no filesystem writes and returns
    planned operations instead."""

    def test_dry_run_returns_planned_writes(self):
        writes = [
            WriteOperation(op="write", path="Inbox/Sources/note.md"),
            WriteOperation(op="mkdir", path="Inbox/Sources"),
        ]
        planned, errors = check_write_batch(
            writes, {}, dry_run=True
        )
        assert planned == writes
        assert errors == []

    def test_dry_run_returns_even_invalid_writes(self):
        """Dry run returns planned ops even for canonical paths."""
        writes = [
            WriteOperation(op="write", path="Sources/note.md"),
        ]
        planned, errors = check_write_batch(
            writes, {"Sources/note.md": "canon"}, dry_run=True
        )
        assert len(planned) == 1
        assert errors == []

    def test_real_run_rejects_canonical_writes(self):
        writes = [
            WriteOperation(op="write", path="Sources/note.md"),
        ]
        planned, errors = check_write_batch(
            writes, {"Sources/note.md": "draft"}, dry_run=False
        )
        assert planned == []
        assert len(errors) == 1
        assert errors[0].code == "ERR_CANON_WRITE_FORBIDDEN"

    def test_real_run_rejects_non_draft_status(self):
        writes = [
            WriteOperation(op="write", path="Inbox/Sources/note.md"),
        ]
        planned, errors = check_write_batch(
            writes, {"Inbox/Sources/note.md": "canon"}, dry_run=False
        )
        assert planned == []
        assert len(errors) == 1
        assert errors[0].code == "ERR_STATUS_MUST_BE_DRAFT"


# ─── Batch validation ──────────────────────────────────────────────────────

class TestCheckWriteBatch:

    def test_valid_batch(self):
        writes = [
            WriteOperation(op="write", path="Inbox/Sources/a.md"),
            WriteOperation(op="write", path="Inbox/Sources/b.md"),
            WriteOperation(op="mkdir", path="Reports/Delta"),
        ]
        statuses = {
            "Inbox/Sources/a.md": "draft",
            "Inbox/Sources/b.md": "draft",
        }
        planned, errors = check_write_batch(writes, statuses)
        assert errors == []

    def test_mixed_valid_and_invalid(self):
        writes = [
            WriteOperation(op="write", path="Inbox/Sources/ok.md"),
            WriteOperation(op="write", path="Claims/bad.md"),
        ]
        statuses = {
            "Inbox/Sources/ok.md": "draft",
            "Claims/bad.md": "draft",
        }
        planned, errors = check_write_batch(writes, statuses)
        assert len(errors) == 1
        assert errors[0].code == "ERR_CANON_WRITE_FORBIDDEN"

    def test_promotion_allows_canonical_batch(self):
        writes = [
            WriteOperation(op="write", path="Sources/note.md"),
            WriteOperation(op="write", path="Claims/claim.md"),
        ]
        statuses = {
            "Sources/note.md": "canon",
            "Claims/claim.md": "canon",
        }
        planned, errors = check_write_batch(writes, statuses, is_promotion=True)
        assert errors == []

    def test_delete_ops_not_checked(self):
        """Delete operations don't create notes, so INV-003 doesn't apply."""
        writes = [
            WriteOperation(op="delete", path="Sources/old.md"),
        ]
        planned, errors = check_write_batch(writes, {})
        assert errors == []

    def test_default_status_is_draft(self):
        """Paths not in statuses dict default to 'draft'."""
        writes = [
            WriteOperation(op="write", path="Inbox/Sources/note.md"),
        ]
        planned, errors = check_write_batch(writes, {})
        assert errors == []


# ─── WriteOperation ────────────────────────────────────────────────────────

class TestWriteOperation:

    def test_to_dict(self):
        w = WriteOperation(
            op="write",
            path="Inbox/Sources/note.md",
            reason="Ingested from URL",
        )
        d = w.to_dict()
        assert d["op"] == "write"
        assert d["path"] == "Inbox/Sources/note.md"
        assert d["from_path"] is None
        assert d["reason"] == "Ingested from URL"

    def test_move_operation(self):
        w = WriteOperation(
            op="move",
            path="Sources/note.md",
            from_path="Inbox/Sources/note.md",
            reason="Promotion",
        )
        d = w.to_dict()
        assert d["op"] == "move"
        assert d["from_path"] == "Inbox/Sources/note.md"


# ─── AC-INV-004: Provenance required for imported claims ───────────────────

def _valid_claim_fm(**overrides: Any) -> dict[str, Any]:
    """Build a valid claim frontmatter dict for testing."""
    base = {
        "type": "claim",
        "id": "c-001",
        "status": "draft",
        "created": "2026-03-01T00:00:00Z",
        "updated": "2026-03-01T00:00:00Z",
        "claim_text": "Test claim",
        "claim_type": "empirical",
        "polarity": "supports",
        "provenance": {
            "source_id": "s-001",
            "source_ref": "https://example.com",
            "locator": {"raw_locator": "page 1"},
        },
    }
    base.update(overrides)
    return base


class TestProvenanceRequired:
    """AC-INV-004-1 and AC-INV-004-2: Provenance required for claims."""

    def test_valid_claim_passes(self):
        fm = _valid_claim_fm()
        errors = validate_provenance_required(fm)
        assert errors == []

    def test_non_claim_type_skipped(self):
        """INV-004 only applies to claim notes."""
        fm = {"type": "source", "id": "s-001"}
        errors = validate_provenance_required(fm)
        assert errors == []

    def test_missing_provenance_object(self):
        """AC-INV-004-1: Missing provenance fails validation."""
        fm = _valid_claim_fm()
        del fm["provenance"]
        errors = validate_provenance_required(fm)
        assert len(errors) == 1
        assert errors[0].code == "ERR_SCHEMA_VALIDATION"
        assert "provenance" in errors[0].message

    def test_missing_provenance_at_promotion(self):
        """AC-INV-004-2: Missing provenance at promotion returns ERR_PROVENANCE_MISSING."""
        fm = _valid_claim_fm()
        del fm["provenance"]
        errors = validate_provenance_required(fm, is_promotion=True)
        assert len(errors) == 1
        assert errors[0].code == "ERR_PROVENANCE_MISSING"

    def test_missing_source_id_key(self):
        fm = _valid_claim_fm()
        del fm["provenance"]["source_id"]
        errors = validate_provenance_required(fm)
        assert len(errors) == 1
        assert "source_id" in errors[0].message

    def test_missing_source_ref_key(self):
        fm = _valid_claim_fm()
        del fm["provenance"]["source_ref"]
        errors = validate_provenance_required(fm)
        assert len(errors) == 1
        assert "source_ref" in errors[0].message

    def test_missing_locator_key(self):
        fm = _valid_claim_fm()
        del fm["provenance"]["locator"]
        errors = validate_provenance_required(fm)
        assert len(errors) == 1
        assert "locator" in errors[0].message

    def test_missing_multiple_keys_at_promotion(self):
        """AC-INV-004-2: Multiple missing keys still produce ERR_PROVENANCE_MISSING."""
        fm = _valid_claim_fm()
        fm["provenance"] = {}
        errors = validate_provenance_required(fm, is_promotion=True)
        assert len(errors) == 1
        assert errors[0].code == "ERR_PROVENANCE_MISSING"
        assert "source_id" in errors[0].message

    def test_non_dict_provenance(self):
        fm = _valid_claim_fm(provenance="not-a-dict")
        errors = validate_provenance_required(fm)
        assert len(errors) == 1
        assert "provenance" in errors[0].message

    def test_error_details_include_invariant(self):
        fm = _valid_claim_fm()
        del fm["provenance"]
        errors = validate_provenance_required(fm)
        assert errors[0].details["invariant"] == "INV-004"


# ─── AC-INV-005: Idempotent ingestion identity ─────────────────────────────

class TestIdempotentIngestion:
    """AC-INV-005-1 and AC-INV-005-2: Idempotent ingestion identity."""

    def _make_sources(self) -> list[SourceIdentity]:
        return [
            SourceIdentity(
                source_id="s-001",
                normalized_locator="https://example.com/article",
                fingerprint="sha256:" + "a" * 64,
            ),
            SourceIdentity(
                source_id="s-002",
                normalized_locator="https://example.com/other",
                fingerprint="sha256:" + "b" * 64,
            ),
        ]

    def test_same_content_reuses_source_id(self):
        """AC-INV-005-1: Same locator+fingerprint reuses source_id."""
        sources = self._make_sources()
        outcome, matched = resolve_source_identity(
            "https://example.com/article",
            "sha256:" + "a" * 64,
            sources,
        )
        assert outcome == IngestionOutcome.SAME_CONTENT
        assert matched is not None
        assert matched.source_id == "s-001"

    def test_revised_content_detected(self):
        """AC-INV-005-2: Same locator, different fingerprint → revision."""
        sources = self._make_sources()
        outcome, matched = resolve_source_identity(
            "https://example.com/article",
            "sha256:" + "c" * 64,  # different fingerprint
            sources,
        )
        assert outcome == IngestionOutcome.REVISED_CONTENT
        assert matched is not None
        assert matched.source_id == "s-001"
        assert matched.fingerprint == "sha256:" + "a" * 64  # prior fingerprint

    def test_new_source_detected(self):
        sources = self._make_sources()
        outcome, matched = resolve_source_identity(
            "https://example.com/brand-new",
            "sha256:" + "d" * 64,
            sources,
        )
        assert outcome == IngestionOutcome.NEW_SOURCE
        assert matched is None

    def test_empty_source_list(self):
        outcome, matched = resolve_source_identity(
            "https://example.com/anything",
            "sha256:" + "e" * 64,
            [],
        )
        assert outcome == IngestionOutcome.NEW_SOURCE
        assert matched is None

    def test_same_fingerprint_different_locator_is_new(self):
        """Different locator means new source even with same fingerprint."""
        sources = self._make_sources()
        outcome, matched = resolve_source_identity(
            "https://different-site.com/article",
            "sha256:" + "a" * 64,  # same fingerprint as s-001
            sources,
        )
        assert outcome == IngestionOutcome.NEW_SOURCE
        assert matched is None
