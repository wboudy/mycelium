"""
Propose+Queue stage — stage 7/7 of the ingestion pipeline (§6.1.1).

Input:  Delta Report (SCH-006) + vault snapshot
Output: Review Queue Items (SCH-007 compliant)
Side effects: Writes queue items under Inbox/ReviewQueue/.
Errors: ERR_SCHEMA_VALIDATION

Spec reference: mycelium_refactor_plan_apr_round5.md §6.1.1, §4.2.7 SCH-007, §8.1 REV-001
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mycelium.auto_approval import evaluate_auto_approval
from mycelium.models import (
    ErrorObject,
    OutputEnvelope,
    WarningObject,
    make_envelope,
)
from mycelium.review_generation import generate_queue_items
from mycelium.review_queue import (
    save_queue_item,
    validate_queue_item,
)

STAGE_NAME = "propose_queue"

# Error codes
ERR_SCHEMA_VALIDATION = "ERR_SCHEMA_VALIDATION"
ERR_QUEUE_WRITE_FAILED = "ERR_QUEUE_WRITE_FAILED"

# Warning codes
WARN_NO_QUEUE_ITEMS = "WARN_NO_QUEUE_ITEMS"
WARN_CONTRADICTING_REQUIRES_REVIEW = "WARN_CONTRADICTING_REQUIRES_REVIEW"
WARN_AMBIGUOUS_REQUIRES_REVIEW = "WARN_AMBIGUOUS_REQUIRES_REVIEW"


# ---------------------------------------------------------------------------
# Main propose_queue function
# ---------------------------------------------------------------------------

def propose_queue(
    delta_report: dict[str, Any],
    *,
    vault_root: Path | None = None,
    source_note_path: str | None = None,
) -> tuple[list[dict[str, Any]] | None, OutputEnvelope]:
    """Execute the propose+queue stage.

    Generates Review Queue Items from a Delta Report's match groups,
    evaluates auto-approval policy, and writes them to Inbox/ReviewQueue/.

    AC-1: NEW claims → claim_note with promote_to_canon.
    AC-2: CONTRADICTING → human-review only, never auto-approved.
    AC-3: Ambiguous similarity [0.70..0.85) → merge/create recommendation.
    AC-4: EXACT matches → auto-approvable provenance-attachment items.
    AC-5: Queue items include checks with provenance_present.
    AC-6: Written to Inbox/ReviewQueue/.
    AC-7: Items conform to SCH-007.

    Args:
        delta_report: A validated Delta Report dict (SCH-006).
        vault_root: If provided, writes queue items to Inbox/ReviewQueue/.
        source_note_path: Optional vault-relative path for source note.

    Returns:
        Tuple of (queue_items_or_none, envelope).
    """
    run_id = delta_report.get("run_id", "unknown")

    # Generate queue items from delta report
    try:
        items = generate_queue_items(
            delta_report,
            source_note_path=source_note_path,
        )
    except Exception as e:
        return None, make_envelope(
            STAGE_NAME,
            errors=[ErrorObject(
                code=ERR_SCHEMA_VALIDATION,
                message=f"Failed to generate queue items: {e}",
                retryable=False,
                stage=STAGE_NAME,
                details={"run_id": run_id},
            )],
        )

    # Evaluate auto-approval policy for each item and annotate
    for item in items:
        decision = evaluate_auto_approval(item)
        item["checks"]["auto_approval"] = decision.to_dict()

    # Validate all items
    for i, item in enumerate(items):
        schema_errors = validate_queue_item(item)
        if schema_errors:
            return None, make_envelope(
                STAGE_NAME,
                errors=[ErrorObject(
                    code=ERR_SCHEMA_VALIDATION,
                    message=f"Queue item [{i}] failed validation: {'; '.join(schema_errors)}",
                    retryable=False,
                    stage=STAGE_NAME,
                    details={"queue_item_index": i, "schema_errors": schema_errors},
                )],
            )

    # Write to disk if vault_root provided
    artifact_paths: list[str] = []
    if vault_root is not None and items:
        try:
            for item in items:
                written_path = save_queue_item(vault_root, item)
                artifact_paths.append(str(written_path.relative_to(vault_root)))
        except Exception as e:
            return None, make_envelope(
                STAGE_NAME,
                errors=[ErrorObject(
                    code=ERR_QUEUE_WRITE_FAILED,
                    message=f"Failed to write queue items: {e}",
                    retryable=True,
                    stage=STAGE_NAME,
                    details={"vault_root": str(vault_root)},
                )],
            )

    # Build envelope data
    match_groups = delta_report.get("match_groups", {})
    new_count = len(match_groups.get("NEW", []))
    contradicting_count = len(match_groups.get("CONTRADICTING", []))
    exact_count = len(match_groups.get("EXACT", []))

    claim_items = [i for i in items if i["item_type"] == "claim_note"]
    source_items = [i for i in items if i["item_type"] == "source_note"]
    auto_approved = [
        i for i in items
        if i.get("checks", {}).get("auto_approval", {}).get("auto_approve") is True
    ]
    ambiguous_items = [
        i for i in items
        if i.get("checks", {}).get("review_recommendation") == "merge_or_create"
    ]

    envelope_data: dict[str, Any] = {
        "run_id": run_id,
        "queue_items_count": len(items),
        "claim_items_count": len(claim_items),
        "source_items_count": len(source_items),
        "new_claim_items": new_count,
        "contradicting_claim_items": contradicting_count,
        "exact_claim_items": exact_count,
        "auto_approved_count": len(auto_approved),
        "ambiguous_count": len(ambiguous_items),
    }
    if artifact_paths:
        envelope_data["artifact_paths"] = artifact_paths

    # Build warnings
    envelope_warnings: list[WarningObject] = []
    if not items:
        envelope_warnings.append(WarningObject(
            code=WARN_NO_QUEUE_ITEMS,
            message="No queue items generated (no canonical-impacting claims)",
        ))
    if contradicting_count > 0:
        envelope_warnings.append(WarningObject(
            code=WARN_CONTRADICTING_REQUIRES_REVIEW,
            message=f"{contradicting_count} contradicting claim(s) require human review",
        ))
    if ambiguous_items:
        envelope_warnings.append(WarningObject(
            code=WARN_AMBIGUOUS_REQUIRES_REVIEW,
            message=(
                f"{len(ambiguous_items)} claim(s) in ambiguous similarity band "
                f"[0.70..0.85) require reviewer merge/create decision"
            ),
        ))

    return items, make_envelope(
        STAGE_NAME,
        data=envelope_data,
        warnings=envelope_warnings or None,
    )
