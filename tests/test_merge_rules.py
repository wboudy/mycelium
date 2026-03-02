"""
Tests for merge rules (DED-003).

Acceptance Criteria:
- AC-1: EXACT/NEAR_DUPLICATE do not create new canonical Claim Notes.
- AC-2: SUPPORTING attaches provenance as a proposal requiring review.
- AC-3 (AC-DED-003-2): CONTRADICTING emits Conflict Record with both IDs.
- AC-4 (AC-DED-003-3): NEW creates Draft Claim Notes in Draft Scope.
- AC-5 (AC-DED-003-1): Overlap-only re-ingestion → NEW.length==0.
- AC-6 (AC-DED-003-4): [0.70, 0.85) band → needs_review, no auto-approve.
- AC-7: NEAR_DUPLICATE creating new file requires review approval.
"""

from __future__ import annotations

import pytest

from mycelium.comparator import MatchClass, MatchRecord
from mycelium.merge_rules import (
    ConflictRecord,
    MergeAction,
    MergeDecision,
    MergeResult,
    apply_merge_rule,
    apply_merge_rules,
)


def _make_record(
    match_class: MatchClass,
    similarity: float = 0.99,
    key: str = "h-aabbccddeeff",
    existing_id: str | None = "c1",
) -> MatchRecord:
    return MatchRecord(
        match_class=match_class,
        similarity=similarity,
        extracted_claim_key=key,
        existing_claim_id=existing_id,
    )


# ---------------------------------------------------------------------------
# AC-1: EXACT and NEAR_DUPLICATE do not create new files
# ---------------------------------------------------------------------------

class TestExactAndNearDuplicate:
    """AC-1: no new canonical Claim Notes for EXACT/NEAR_DUPLICATE."""

    def test_exact_no_new_file(self):
        dec = apply_merge_rule(_make_record(MatchClass.EXACT, 1.0))
        assert dec.creates_new_file is False
        assert dec.action == MergeAction.UPDATE_PROVENANCE

    def test_exact_auto_approve(self):
        dec = apply_merge_rule(_make_record(MatchClass.EXACT, 0.99))
        assert dec.auto_approve is True

    def test_near_duplicate_no_new_file(self):
        dec = apply_merge_rule(_make_record(MatchClass.NEAR_DUPLICATE, 0.90))
        assert dec.creates_new_file is False
        assert dec.action == MergeAction.UPDATE_EXISTING

    def test_near_duplicate_auto_approve(self):
        dec = apply_merge_rule(_make_record(MatchClass.NEAR_DUPLICATE, 0.88))
        assert dec.auto_approve is True


# ---------------------------------------------------------------------------
# AC-2: SUPPORTING attaches provenance
# ---------------------------------------------------------------------------

class TestSupporting:
    """AC-2: SUPPORTING updates provenance, may require review."""

    def test_supporting_high_similarity_no_review(self):
        """Above the review band, SUPPORTING auto-approves."""
        dec = apply_merge_rule(_make_record(MatchClass.SUPPORTING, 0.86))
        assert dec.creates_new_file is False
        assert dec.action == MergeAction.UPDATE_PROVENANCE
        assert dec.requires_review is False


# ---------------------------------------------------------------------------
# AC-3: CONTRADICTING emits Conflict Record
# ---------------------------------------------------------------------------

class TestContradicting:
    """AC-DED-003-2: Conflict Record with existing_claim_id and new_extracted_claim_key."""

    def test_creates_conflict_record(self):
        rec = _make_record(MatchClass.CONTRADICTING, 0.80, existing_id="c42")
        dec = apply_merge_rule(rec)
        assert dec.conflict_record is not None
        assert dec.conflict_record.existing_claim_id == "c42"
        assert dec.conflict_record.new_extracted_claim_key == "h-aabbccddeeff"

    def test_creates_new_file(self):
        dec = apply_merge_rule(_make_record(MatchClass.CONTRADICTING, 0.75))
        assert dec.creates_new_file is True
        assert dec.action == MergeAction.CREATE_CONFLICT

    def test_not_auto_approve(self):
        dec = apply_merge_rule(_make_record(MatchClass.CONTRADICTING, 0.80))
        assert dec.auto_approve is False

    def test_conflict_record_to_dict(self):
        cr = ConflictRecord(
            existing_claim_id="c1",
            new_extracted_claim_key="h-112233445566",
            similarity=0.78,
        )
        d = cr.to_dict()
        assert d["existing_claim_id"] == "c1"
        assert d["new_extracted_claim_key"] == "h-112233445566"
        assert d["similarity"] == 0.78


# ---------------------------------------------------------------------------
# AC-4: NEW creates Draft Claim Notes
# ---------------------------------------------------------------------------

class TestNew:
    """AC-DED-003-3: NEW creates Draft Claim Notes."""

    def test_creates_draft(self):
        rec = _make_record(MatchClass.NEW, 0.0, existing_id=None)
        dec = apply_merge_rule(rec)
        assert dec.creates_new_file is True
        assert dec.action == MergeAction.CREATE_DRAFT

    def test_not_auto_approve(self):
        rec = _make_record(MatchClass.NEW, 0.0, existing_id=None)
        dec = apply_merge_rule(rec)
        assert dec.auto_approve is False

    def test_no_conflict_record(self):
        rec = _make_record(MatchClass.NEW, 0.0, existing_id=None)
        dec = apply_merge_rule(rec)
        assert dec.conflict_record is None


# ---------------------------------------------------------------------------
# AC-5: Overlap-only fixture → NEW.length==0
# ---------------------------------------------------------------------------

class TestOverlapOnly:
    """AC-DED-003-1: re-ingesting overlap-only → no new claims."""

    def test_all_exact_no_new_drafts(self):
        records = [
            _make_record(MatchClass.EXACT, 1.0, key=f"h-{i:012d}")
            for i in range(5)
        ]
        result = apply_merge_rules(records)
        assert len(result.new_drafts) == 0

    def test_mixed_overlap_no_new(self):
        records = [
            _make_record(MatchClass.EXACT, 1.0),
            _make_record(MatchClass.NEAR_DUPLICATE, 0.92),
            _make_record(MatchClass.SUPPORTING, 0.88),
        ]
        result = apply_merge_rules(records)
        assert len(result.new_drafts) == 0


# ---------------------------------------------------------------------------
# AC-6: [0.70, 0.85) band → needs_review, no auto-approve
# ---------------------------------------------------------------------------

class TestReviewBand:
    """AC-DED-003-4: similarity [0.70, 0.85) → reviewer decision required."""

    @pytest.mark.parametrize("sim", [0.70, 0.75, 0.80, 0.849])
    def test_review_band_needs_review(self, sim: float):
        rec = _make_record(MatchClass.SUPPORTING, sim)
        dec = apply_merge_rule(rec)
        assert dec.requires_review is True
        assert dec.auto_approve is False
        assert dec.action == MergeAction.NEEDS_REVIEW

    def test_review_recommendation_present(self):
        rec = _make_record(MatchClass.SUPPORTING, 0.75)
        dec = apply_merge_rule(rec)
        assert dec.review_recommendation == "merge_or_create"

    def test_above_review_band_no_review(self):
        """SUPPORTING above 0.85 does not need review."""
        rec = _make_record(MatchClass.SUPPORTING, 0.86)
        dec = apply_merge_rule(rec)
        assert dec.requires_review is False


# ---------------------------------------------------------------------------
# AC-7: NEAR_DUPLICATE new file requires review
# ---------------------------------------------------------------------------

class TestNearDuplicateNewFile:
    """AC-7: NEAR_DUPLICATE default is update, not create."""

    def test_default_is_update(self):
        dec = apply_merge_rule(_make_record(MatchClass.NEAR_DUPLICATE, 0.90))
        assert dec.action == MergeAction.UPDATE_EXISTING
        assert dec.creates_new_file is False


# ---------------------------------------------------------------------------
# Batch processing
# ---------------------------------------------------------------------------

class TestBatch:

    def test_apply_merge_rules_total(self):
        records = [
            _make_record(MatchClass.EXACT, 1.0),
            _make_record(MatchClass.NEW, 0.0, existing_id=None),
            _make_record(MatchClass.CONTRADICTING, 0.78),
        ]
        result = apply_merge_rules(records)
        assert len(result.decisions) == 3

    def test_counts_in_to_dict(self):
        records = [
            _make_record(MatchClass.NEW, 0.0, existing_id=None),
            _make_record(MatchClass.NEW, 0.0, existing_id=None),
            _make_record(MatchClass.CONTRADICTING, 0.75),
        ]
        result = apply_merge_rules(records)
        d = result.to_dict()
        assert d["counts"]["total"] == 3
        assert d["counts"]["new_drafts"] == 2
        assert d["counts"]["conflicts"] == 1

    def test_merge_decision_to_dict(self):
        rec = _make_record(MatchClass.EXACT, 0.99)
        dec = apply_merge_rule(rec)
        d = dec.to_dict()
        assert d["match_class"] == "EXACT"
        assert d["action"] == "update_provenance"
        assert d["creates_new_file"] is False
