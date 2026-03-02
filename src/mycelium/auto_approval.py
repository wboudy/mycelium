"""
Auto-Approval Lane policy for Review Queue Items (REV-001B).

Determines which queue items can be auto-approved versus which must
go to human review. Only low-risk, non-semantic updates qualify.

Spec reference: §8.1.2 REV-001B
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# ---------------------------------------------------------------------------
# Policy reason codes (AC-REV-001B-1)
# ---------------------------------------------------------------------------

REASON_EXACT_PROVENANCE = "EXACT_PROVENANCE_ATTACH"
REASON_METADATA_ONLY = "METADATA_ONLY_UPDATE"
REASON_FORMAT_NORMALIZATION = "FORMAT_NORMALIZATION"

REASON_DISALLOW_NEW = "DISALLOW_NEW_CLAIM"
REASON_DISALLOW_CONTRADICTING = "DISALLOW_CONTRADICTING"
REASON_DISALLOW_WEAK_PROVENANCE = "DISALLOW_WEAK_PROVENANCE"
REASON_DISALLOW_AMBIGUOUS_SIMILARITY = "DISALLOW_AMBIGUOUS_SIMILARITY"

# Similarity band that signals merge/create ambiguity (§7.3 DED-003)
AMBIGUOUS_SIMILARITY_LOW = 0.70
AMBIGUOUS_SIMILARITY_HIGH = 0.85


# ---------------------------------------------------------------------------
# Decision result
# ---------------------------------------------------------------------------

@dataclass
class ApprovalDecision:
    """Result of evaluating a queue item against the auto-approval policy.

    Attributes:
        auto_approve: Whether the item can be auto-approved.
        reason_code: Machine-readable reason code for the decision.
        reason_detail: Human-readable explanation.
    """

    auto_approve: bool
    reason_code: str
    reason_detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "auto_approve": self.auto_approve,
            "reason_code": self.reason_code,
            "reason_detail": self.reason_detail,
        }


# ---------------------------------------------------------------------------
# Policy evaluation
# ---------------------------------------------------------------------------

def evaluate_auto_approval(queue_item: dict[str, Any]) -> ApprovalDecision:
    """Evaluate whether a queue item qualifies for auto-approval.

    The auto-approval lane is constrained per REV-001B:

    **Allowed** (auto_approve=True):
    - EXACT matches that only attach provenance/support metadata.
    - Metadata-only updates with no claim meaning change.
    - Non-semantic formatting normalization.

    **Disallowed** (auto_approve=False):
    - Any NEW claim proposal.
    - Any CONTRADICTING proposal.
    - Any proposal with missing/weak provenance checks.
    - Any merge/create ambiguity in similarity band [0.70..0.85).

    Args:
        queue_item: A queue item dict (SCH-007) with checks populated.

    Returns:
        An ApprovalDecision with the auto-approval verdict and reason.
    """
    checks = queue_item.get("checks", {})
    match_class = checks.get("match_class")
    item_type = queue_item.get("item_type", "")
    proposed_action = queue_item.get("proposed_action", "")

    # --- Disallowed classes (check first) ---

    # NEW claims must always go to human review
    if match_class == "NEW":
        return ApprovalDecision(
            auto_approve=False,
            reason_code=REASON_DISALLOW_NEW,
            reason_detail="NEW claim proposals require human review.",
        )

    # CONTRADICTING claims must always go to human review
    if match_class == "CONTRADICTING":
        return ApprovalDecision(
            auto_approve=False,
            reason_code=REASON_DISALLOW_CONTRADICTING,
            reason_detail="CONTRADICTING proposals require human review.",
        )

    # Missing/weak provenance
    provenance_present = checks.get("provenance_present")
    if item_type == "claim_note" and not provenance_present:
        return ApprovalDecision(
            auto_approve=False,
            reason_code=REASON_DISALLOW_WEAK_PROVENANCE,
            reason_detail="Claim items with missing or weak provenance require human review.",
        )

    # Ambiguous similarity band [0.70..0.85)
    similarity = checks.get("similarity")
    if similarity is not None and AMBIGUOUS_SIMILARITY_LOW <= similarity < AMBIGUOUS_SIMILARITY_HIGH:
        return ApprovalDecision(
            auto_approve=False,
            reason_code=REASON_DISALLOW_AMBIGUOUS_SIMILARITY,
            reason_detail=(
                f"Similarity {similarity:.2f} is in the ambiguous band "
                f"[{AMBIGUOUS_SIMILARITY_LOW}..{AMBIGUOUS_SIMILARITY_HIGH}), "
                f"requiring human review."
            ),
        )

    # --- Allowed classes ---

    # EXACT match with provenance — auto-approve
    if match_class == "EXACT" and provenance_present:
        return ApprovalDecision(
            auto_approve=True,
            reason_code=REASON_EXACT_PROVENANCE,
            reason_detail="EXACT match with valid provenance; auto-approved.",
        )

    # Metadata-only updates (no claim_text change)
    if checks.get("metadata_only", False):
        return ApprovalDecision(
            auto_approve=True,
            reason_code=REASON_METADATA_ONLY,
            reason_detail="Metadata-only update with no claim meaning change; auto-approved.",
        )

    # Formatting normalization
    if checks.get("format_normalization_only", False):
        return ApprovalDecision(
            auto_approve=True,
            reason_code=REASON_FORMAT_NORMALIZATION,
            reason_detail="Non-semantic formatting normalization; auto-approved.",
        )

    # Default: route to human review (conservative policy)
    return ApprovalDecision(
        auto_approve=False,
        reason_code="REQUIRES_HUMAN_REVIEW",
        reason_detail="Item does not match any auto-approval criteria; routed to human review.",
    )
