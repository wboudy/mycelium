"""
Tests for mycelium.auto_approval module (REV-001B).

Verifies:
- AC-REV-001B-1: Auto-approved items include policy reason codes.
- AC-REV-001B-2: Disallowed classes remain pending_review.
"""

from __future__ import annotations

import pytest

from mycelium.auto_approval import (
    AMBIGUOUS_SIMILARITY_HIGH,
    AMBIGUOUS_SIMILARITY_LOW,
    REASON_DISALLOW_AMBIGUOUS_SIMILARITY,
    REASON_DISALLOW_CONTRADICTING,
    REASON_DISALLOW_NEW,
    REASON_DISALLOW_WEAK_PROVENANCE,
    REASON_EXACT_PROVENANCE,
    REASON_FORMAT_NORMALIZATION,
    REASON_METADATA_ONLY,
    ApprovalDecision,
    evaluate_auto_approval,
)
from mycelium.review_queue import build_queue_item


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _item_with_checks(**checks):
    return build_queue_item(
        queue_id="qi-test",
        run_id="run-test",
        item_type=checks.pop("item_type", "claim_note"),
        target_path="Inbox/Sources/test.md",
        proposed_action=checks.pop("proposed_action", "promote_to_canon"),
        created_at="2026-03-01T00:00:00Z",
        checks=checks,
    )


# ---------------------------------------------------------------------------
# Disallowed classes (AC-REV-001B-2)
# ---------------------------------------------------------------------------

class TestDisallowedClasses:

    def test_new_claims_disallowed(self):
        """NEW claim proposals must NOT be auto-approved."""
        item = _item_with_checks(match_class="NEW", provenance_present=True)
        decision = evaluate_auto_approval(item)
        assert decision.auto_approve is False
        assert decision.reason_code == REASON_DISALLOW_NEW

    def test_contradicting_disallowed(self):
        """CONTRADICTING proposals must NOT be auto-approved."""
        item = _item_with_checks(match_class="CONTRADICTING", provenance_present=True)
        decision = evaluate_auto_approval(item)
        assert decision.auto_approve is False
        assert decision.reason_code == REASON_DISALLOW_CONTRADICTING

    def test_weak_provenance_disallowed(self):
        """Missing provenance must NOT be auto-approved."""
        item = _item_with_checks(match_class="EXACT", provenance_present=False)
        decision = evaluate_auto_approval(item)
        assert decision.auto_approve is False
        assert decision.reason_code == REASON_DISALLOW_WEAK_PROVENANCE

    def test_missing_provenance_disallowed(self):
        """No provenance_present key defaults to disallowed."""
        item = _item_with_checks(match_class="EXACT")
        decision = evaluate_auto_approval(item)
        assert decision.auto_approve is False
        assert decision.reason_code == REASON_DISALLOW_WEAK_PROVENANCE

    def test_ambiguous_similarity_disallowed(self):
        """Similarity in [0.70..0.85) must NOT be auto-approved."""
        item = _item_with_checks(
            match_class="NEAR_DUPLICATE",
            provenance_present=True,
            similarity=0.75,
        )
        decision = evaluate_auto_approval(item)
        assert decision.auto_approve is False
        assert decision.reason_code == REASON_DISALLOW_AMBIGUOUS_SIMILARITY

    def test_ambiguous_similarity_lower_bound(self):
        """Similarity exactly at 0.70 is disallowed."""
        item = _item_with_checks(
            match_class="NEAR_DUPLICATE",
            provenance_present=True,
            similarity=0.70,
        )
        decision = evaluate_auto_approval(item)
        assert decision.auto_approve is False

    def test_ambiguous_similarity_upper_bound_excluded(self):
        """Similarity exactly at 0.85 is NOT in the ambiguous band."""
        item = _item_with_checks(
            match_class="EXACT",
            provenance_present=True,
            similarity=0.85,
        )
        decision = evaluate_auto_approval(item)
        # Should pass through to EXACT check, not be blocked by ambiguity
        assert decision.auto_approve is True


# ---------------------------------------------------------------------------
# Allowed classes (AC-REV-001B-1)
# ---------------------------------------------------------------------------

class TestAllowedClasses:

    def test_exact_with_provenance_approved(self):
        """EXACT match with provenance is auto-approved."""
        item = _item_with_checks(match_class="EXACT", provenance_present=True)
        decision = evaluate_auto_approval(item)
        assert decision.auto_approve is True
        assert decision.reason_code == REASON_EXACT_PROVENANCE

    def test_metadata_only_approved(self):
        """Metadata-only updates are auto-approved."""
        item = _item_with_checks(
            match_class="SUPPORTING",
            provenance_present=True,
            metadata_only=True,
        )
        decision = evaluate_auto_approval(item)
        assert decision.auto_approve is True
        assert decision.reason_code == REASON_METADATA_ONLY

    def test_format_normalization_approved(self):
        """Format normalization is auto-approved."""
        item = _item_with_checks(
            provenance_present=True,
            format_normalization_only=True,
        )
        decision = evaluate_auto_approval(item)
        assert decision.auto_approve is True
        assert decision.reason_code == REASON_FORMAT_NORMALIZATION


# ---------------------------------------------------------------------------
# AC-REV-001B-1: Reason codes in audit details
# ---------------------------------------------------------------------------

class TestReasonCodes:

    def test_decision_has_reason_code(self):
        """Every decision includes a reason code."""
        item = _item_with_checks(match_class="NEW", provenance_present=True)
        decision = evaluate_auto_approval(item)
        assert decision.reason_code
        assert isinstance(decision.reason_code, str)

    def test_decision_has_reason_detail(self):
        """Every decision includes a human-readable detail."""
        item = _item_with_checks(match_class="EXACT", provenance_present=True)
        decision = evaluate_auto_approval(item)
        assert decision.reason_detail
        assert isinstance(decision.reason_detail, str)

    def test_to_dict(self):
        """Decision serializes to dict for audit logging."""
        item = _item_with_checks(match_class="EXACT", provenance_present=True)
        decision = evaluate_auto_approval(item)
        d = decision.to_dict()
        assert "auto_approve" in d
        assert "reason_code" in d
        assert "reason_detail" in d

    def test_all_reason_codes_are_uppercase(self):
        """Reason codes follow UPPER_SNAKE convention."""
        codes = [
            REASON_EXACT_PROVENANCE,
            REASON_METADATA_ONLY,
            REASON_FORMAT_NORMALIZATION,
            REASON_DISALLOW_NEW,
            REASON_DISALLOW_CONTRADICTING,
            REASON_DISALLOW_WEAK_PROVENANCE,
            REASON_DISALLOW_AMBIGUOUS_SIMILARITY,
        ]
        for code in codes:
            assert code == code.upper(), f"Reason code {code!r} should be UPPER_SNAKE"


# ---------------------------------------------------------------------------
# Default behavior
# ---------------------------------------------------------------------------

class TestDefaultBehavior:

    def test_unknown_class_routes_to_human(self):
        """Unrecognized items default to human review (conservative)."""
        item = _item_with_checks(
            item_type="source_note",
            proposed_action="create",
            match_class="SUPPORTING",
            provenance_present=True,
        )
        decision = evaluate_auto_approval(item)
        # SUPPORTING without metadata_only or format_normalization → human review
        assert decision.auto_approve is False

    def test_empty_checks_routes_to_human(self):
        """Items with no checks route to human review."""
        item = build_queue_item(
            queue_id="qi-empty",
            run_id="r",
            item_type="source_note",
            target_path="Inbox/Sources/x.md",
            proposed_action="create",
            created_at="2026-01-01T00:00:00Z",
        )
        decision = evaluate_auto_approval(item)
        assert decision.auto_approve is False
