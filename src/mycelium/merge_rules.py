"""
Merge rules for each match class (DED-003).

Determines how each match classification affects canonical state:
what to update, what to create, and what requires review.

Spec reference: mycelium_refactor_plan_apr_round5.md §7.3
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any

from mycelium.comparator import MatchClass, MatchRecord


# ---------------------------------------------------------------------------
# Merge actions
# ---------------------------------------------------------------------------

class MergeAction(enum.Enum):
    """The action a merge rule prescribes for a matched claim."""

    UPDATE_PROVENANCE = "update_provenance"
    """Update existing claim's provenance/support only (no new file)."""

    UPDATE_EXISTING = "update_existing"
    """Update existing claim (default for NEAR_DUPLICATE)."""

    CREATE_DRAFT = "create_draft"
    """Create a new Draft Claim Note in Draft Scope."""

    CREATE_CONFLICT = "create_conflict"
    """Create a draft claim + emit a Conflict Record."""

    NEEDS_REVIEW = "needs_review"
    """Requires reviewer decision (similarity in [0.70, 0.85) band)."""


# ---------------------------------------------------------------------------
# Conflict Record
# ---------------------------------------------------------------------------

@dataclass
class ConflictRecord:
    """An explicit conflict between an existing and new claim (DED-003).

    Emitted when match_class == CONTRADICTING. The Delta Report must include
    this record with both existing_claim_id and new_extracted_claim_key present
    (AC-DED-003-2).
    """

    existing_claim_id: str
    new_extracted_claim_key: str
    similarity: float
    reason: str = "contradicting_match"

    def to_dict(self) -> dict[str, Any]:
        return {
            "existing_claim_id": self.existing_claim_id,
            "new_extracted_claim_key": self.new_extracted_claim_key,
            "similarity": self.similarity,
            "reason": self.reason,
        }


# ---------------------------------------------------------------------------
# Merge decision
# ---------------------------------------------------------------------------

@dataclass
class MergeDecision:
    """The result of applying merge rules to a single MatchRecord."""

    match_record: MatchRecord
    action: MergeAction
    creates_new_file: bool
    requires_review: bool
    auto_approve: bool
    conflict_record: ConflictRecord | None = None
    review_recommendation: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "extracted_claim_key": self.match_record.extracted_claim_key,
            "match_class": self.match_record.match_class.value,
            "similarity": self.match_record.similarity,
            "action": self.action.value,
            "creates_new_file": self.creates_new_file,
            "requires_review": self.requires_review,
            "auto_approve": self.auto_approve,
        }
        if self.match_record.existing_claim_id is not None:
            d["existing_claim_id"] = self.match_record.existing_claim_id
        if self.conflict_record is not None:
            d["conflict_record"] = self.conflict_record.to_dict()
        if self.review_recommendation is not None:
            d["review_recommendation"] = self.review_recommendation
        return d


# ---------------------------------------------------------------------------
# Merge result (batch)
# ---------------------------------------------------------------------------

@dataclass
class MergeResult:
    """Aggregated merge decisions for a batch of claims."""

    decisions: list[MergeDecision] = field(default_factory=list)

    @property
    def new_drafts(self) -> list[MergeDecision]:
        return [d for d in self.decisions if d.action == MergeAction.CREATE_DRAFT]

    @property
    def conflicts(self) -> list[ConflictRecord]:
        return [d.conflict_record for d in self.decisions if d.conflict_record is not None]

    @property
    def needs_review(self) -> list[MergeDecision]:
        return [d for d in self.decisions if d.requires_review]

    def to_dict(self) -> dict[str, Any]:
        return {
            "decisions": [d.to_dict() for d in self.decisions],
            "counts": {
                "total": len(self.decisions),
                "new_drafts": len(self.new_drafts),
                "conflicts": len(self.conflicts),
                "needs_review": len(self.needs_review),
            },
        }


# ---------------------------------------------------------------------------
# Core merge logic
# ---------------------------------------------------------------------------

# The similarity band that requires reviewer decision (§7.3).
_REVIEW_BAND_LOW = 0.70
_REVIEW_BAND_HIGH = 0.85


def apply_merge_rule(record: MatchRecord) -> MergeDecision:
    """Apply the merge rule for a single MatchRecord.

    Rules (§7.3):
        EXACT          → update provenance only, no new file
        NEAR_DUPLICATE → update existing claim (new file needs review approval)
        SUPPORTING     → update support/provenance, no new file
        CONTRADICTING  → create draft + conflict record, no overwrite
        NEW            → create draft, queue for promotion

    Claims in [0.70, 0.85) similarity need reviewer decision (AC-DED-003-4).

    Args:
        record: A classified MatchRecord from the comparator.

    Returns:
        A MergeDecision describing the prescribed action.
    """
    mc = record.match_class

    if mc == MatchClass.EXACT:
        return MergeDecision(
            match_record=record,
            action=MergeAction.UPDATE_PROVENANCE,
            creates_new_file=False,
            requires_review=False,
            auto_approve=True,
        )

    if mc == MatchClass.NEAR_DUPLICATE:
        return MergeDecision(
            match_record=record,
            action=MergeAction.UPDATE_EXISTING,
            creates_new_file=False,
            requires_review=False,
            auto_approve=True,
        )

    if mc == MatchClass.SUPPORTING:
        # Check if in the review band [0.70, 0.85)
        in_review_band = _REVIEW_BAND_LOW <= record.similarity < _REVIEW_BAND_HIGH
        if in_review_band:
            return MergeDecision(
                match_record=record,
                action=MergeAction.NEEDS_REVIEW,
                creates_new_file=False,
                requires_review=True,
                auto_approve=False,
                review_recommendation="merge_or_create",
            )
        return MergeDecision(
            match_record=record,
            action=MergeAction.UPDATE_PROVENANCE,
            creates_new_file=False,
            requires_review=False,
            auto_approve=True,
        )

    if mc == MatchClass.CONTRADICTING:
        if not record.existing_claim_id:
            raise ValueError(
                f"CONTRADICTING match for {record.extracted_claim_key!r} "
                f"requires existing_claim_id (AC-DED-003-2)"
            )
        conflict = ConflictRecord(
            existing_claim_id=record.existing_claim_id,
            new_extracted_claim_key=record.extracted_claim_key,
            similarity=record.similarity,
        )
        return MergeDecision(
            match_record=record,
            action=MergeAction.CREATE_CONFLICT,
            creates_new_file=True,
            requires_review=False,
            auto_approve=False,
            conflict_record=conflict,
        )

    # MatchClass.NEW
    return MergeDecision(
        match_record=record,
        action=MergeAction.CREATE_DRAFT,
        creates_new_file=True,
        requires_review=False,
        auto_approve=False,
    )


def apply_merge_rules(records: list[MatchRecord]) -> MergeResult:
    """Apply merge rules to a batch of MatchRecords.

    Args:
        records: List of classified MatchRecords.

    Returns:
        MergeResult with all decisions.
    """
    result = MergeResult()
    for record in records:
        result.decisions.append(apply_merge_rule(record))
    return result
