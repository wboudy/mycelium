"""
Review Queue Item generation for ingestion results (REV-001).

Generates Review Queue Items (SCH-007) from Delta Report match groups.
All canonical-impacting proposals — new claims, new source notes,
contradicting claims, ambiguous-band claims, and EXACT provenance
attachments — produce queue items.

Spec reference: §8.1 REV-001, §6.1.1 Stage 7
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from mycelium.auto_approval import (
    AMBIGUOUS_SIMILARITY_HIGH,
    AMBIGUOUS_SIMILARITY_LOW,
)
from mycelium.review_queue import build_queue_item


def generate_queue_items(
    delta_report: dict[str, Any],
    *,
    source_note_path: str | None = None,
    created_at: str | None = None,
) -> list[dict[str, Any]]:
    """Generate Review Queue Items from a Delta Report.

    Produces queue items for all canonical-impacting proposals:
    - Each NEW claim → ``claim_note`` with ``promote_to_canon``
    - Each CONTRADICTING claim → ``claim_note`` with ``promote_to_canon``
      (will be routed to human-review, never auto-approved per REV-001B)
    - Each EXACT claim → ``claim_note`` with ``promote_to_canon``
      (auto-approvable provenance-attachment, AC-4)
    - Claims in [0.70..0.85) similarity → ``claim_note`` with
      merge/create recommendation (AC-3)
    - The source note itself (if any NEW claims exist) → ``source_note``
      with ``create``

    Each claim-related queue item includes ``checks.provenance_present``
    (AC-REV-001-2, AC-5).

    Args:
        delta_report: A validated Delta Report dict (SCH-006).
        source_note_path: Vault-relative path to the draft source note.
            If None, defaults to ``Inbox/Sources/<source_id>.md``.
        created_at: Override timestamp. Defaults to now UTC.

    Returns:
        List of queue item dicts conforming to SCH-007.
    """
    run_id = delta_report["run_id"]
    source_id = delta_report["source_id"]
    ts = created_at or datetime.now(timezone.utc).isoformat()
    items: list[dict[str, Any]] = []

    match_groups = delta_report.get("match_groups", {})
    new_claims = match_groups.get("NEW", [])
    contradicting_claims = match_groups.get("CONTRADICTING", [])
    exact_claims = match_groups.get("EXACT", [])
    near_dup_claims = match_groups.get("NEAR_DUPLICATE", [])
    supporting_claims = match_groups.get("SUPPORTING", [])

    # Generate queue items for NEW claims (AC-1)
    for claim in new_claims:
        claim_key = claim.get("extracted_claim_key", "unknown")
        draft_path = claim.get(
            "draft_claim_note_path",
            f"Inbox/Sources/{claim_key}.md",
        )
        items.append(build_queue_item(
            queue_id=_generate_queue_id(),
            run_id=run_id,
            item_type="claim_note",
            target_path=draft_path,
            proposed_action="promote_to_canon",
            created_at=ts,
            checks={
                "provenance_present": True,
                "match_class": "NEW",
                "extracted_claim_key": claim_key,
            },
        ))

    # Generate queue items for CONTRADICTING claims (AC-2)
    for claim in contradicting_claims:
        claim_key = claim.get("extracted_claim_key", "unknown")
        draft_path = claim.get(
            "draft_claim_note_path",
            f"Inbox/Sources/{claim_key}.md",
        )
        items.append(build_queue_item(
            queue_id=_generate_queue_id(),
            run_id=run_id,
            item_type="claim_note",
            target_path=draft_path,
            proposed_action="promote_to_canon",
            created_at=ts,
            checks={
                "provenance_present": True,
                "match_class": "CONTRADICTING",
                "extracted_claim_key": claim_key,
                "requires_human_review": True,
            },
        ))

    # Generate queue items for EXACT matches — auto-approvable provenance
    # attachment (AC-4)
    for claim in exact_claims:
        claim_key = claim.get("extracted_claim_key", "unknown")
        existing_id = claim.get("existing_claim_id")
        target_path = claim.get(
            "draft_claim_note_path",
            f"Inbox/Sources/{claim_key}.md",
        )
        items.append(build_queue_item(
            queue_id=_generate_queue_id(),
            run_id=run_id,
            item_type="claim_note",
            target_path=target_path,
            proposed_action="promote_to_canon",
            created_at=ts,
            checks={
                "provenance_present": True,
                "match_class": "EXACT",
                "extracted_claim_key": claim_key,
                "existing_claim_id": existing_id,
                "similarity": claim.get("similarity", 1.0),
            },
        ))

    # Generate queue items for claims in ambiguous similarity band
    # [0.70..0.85) — merge/create recommendation (AC-3)
    for claim in _ambiguous_band_claims(near_dup_claims, supporting_claims):
        claim_key = claim.get("extracted_claim_key", "unknown")
        existing_id = claim.get("existing_claim_id")
        similarity = claim.get("similarity", 0.0)
        target_path = claim.get(
            "draft_claim_note_path",
            f"Inbox/Sources/{claim_key}.md",
        )
        items.append(build_queue_item(
            queue_id=_generate_queue_id(),
            run_id=run_id,
            item_type="claim_note",
            target_path=target_path,
            proposed_action="merge",
            created_at=ts,
            checks={
                "provenance_present": True,
                "match_class": claim.get("match_class", "NEAR_DUPLICATE"),
                "extracted_claim_key": claim_key,
                "existing_claim_id": existing_id,
                "similarity": similarity,
                "requires_human_review": True,
                "review_recommendation": "merge_or_create",
            },
        ))

    # Generate source note queue item if there are any canonical-impacting claims
    if new_claims or contradicting_claims:
        src_path = source_note_path or f"Inbox/Sources/{source_id}.md"
        items.append(build_queue_item(
            queue_id=_generate_queue_id(),
            run_id=run_id,
            item_type="source_note",
            target_path=src_path,
            proposed_action="create",
            created_at=ts,
            checks={
                "new_claim_count": len(new_claims),
                "contradicting_claim_count": len(contradicting_claims),
            },
        ))

    return items


def _ambiguous_band_claims(
    near_dup: list[dict[str, Any]],
    supporting: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Filter claims that fall in the ambiguous similarity band [0.70..0.85)."""
    result: list[dict[str, Any]] = []
    for claim in near_dup + supporting:
        sim = claim.get("similarity", 0.0)
        if AMBIGUOUS_SIMILARITY_LOW <= sim < AMBIGUOUS_SIMILARITY_HIGH:
            result.append(claim)
    return result


def _generate_queue_id() -> str:
    """Generate a unique queue item ID."""
    return f"qi-{uuid.uuid4().hex[:12]}"
