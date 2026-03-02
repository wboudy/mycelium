"""
Reading-first review digest workflow with packet semantics (REV-001A).

Implements the nightly review workflow that groups queue items by Source
into Review Packets, supports packet-level actions, and enforces
resurfacing of held items after configured hold TTL.

Spec reference: §8.1.1 REV-001A
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

from mycelium.review_policy import DEFAULT_HOLD_TTL_DAYS, ReviewPolicy


# ─── Constants ────────────────────────────────────────────────────────────

CONTRADICTING_CLASS = "CONTRADICTING"


# ─── Queue item model ────────────────────────────────────────────────────

@dataclass
class QueueItem:
    """A review queue item for workflow processing."""
    queue_id: str
    source_id: str
    run_id: str
    match_class: str | None = None
    status: str = "pending_review"
    hold_until: str | None = None
    claim_text: str | None = None
    proposed_action: str | None = None
    checks: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "queue_id": self.queue_id,
            "source_id": self.source_id,
            "run_id": self.run_id,
            "status": self.status,
        }
        if self.match_class is not None:
            d["match_class"] = self.match_class
        if self.hold_until is not None:
            d["hold_until"] = self.hold_until
        if self.claim_text is not None:
            d["claim_text"] = self.claim_text
        if self.proposed_action is not None:
            d["proposed_action"] = self.proposed_action
        if self.checks:
            d["checks"] = self.checks
        return d


# ─── Packet summary ─────────────────────────────────────────────────────

@dataclass
class PacketSummary:
    """Summary of a Source packet for the digest."""
    source_id: str
    queue_ids: list[str]
    run_ids: list[str]
    claim_count: int
    has_contradicting: bool
    canonical_impact: str
    citations: list[str] = field(default_factory=list)
    claim_cards: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "queue_ids": self.queue_ids,
            "run_ids": self.run_ids,
            "claim_count": self.claim_count,
            "has_contradicting": self.has_contradicting,
            "canonical_impact": self.canonical_impact,
            "citations": self.citations,
            "claim_cards": self.claim_cards,
        }


# ─── Grouping ────────────────────────────────────────────────────────────

def group_by_source(items: list[QueueItem]) -> dict[str, list[QueueItem]]:
    """Group queue items by source_id, preserving insertion order."""
    groups: dict[str, list[QueueItem]] = {}
    for item in items:
        groups.setdefault(item.source_id, []).append(item)
    return groups


# ─── Resurfacing ─────────────────────────────────────────────────────────

def should_resurface(item: QueueItem, digest_date: date) -> bool:
    """Determine if a held queue item should resurface.

    AC-REV-001A-3: Held items resurface when hold_until <= digest_date.
    """
    if item.status != "pending_review":
        return False
    if item.hold_until is None:
        return True  # not held, always included
    hold_date = date.fromisoformat(item.hold_until)
    return hold_date <= digest_date


def filter_for_digest(
    items: list[QueueItem],
    digest_date: date,
) -> list[QueueItem]:
    """Filter queue items for digest inclusion.

    Only pending_review items that should resurface are included.
    """
    return [
        item for item in items
        if item.status == "pending_review" and should_resurface(item, digest_date)
    ]


# ─── Packet generation ──────────────────────────────────────────────────

def build_packet_summary(
    source_id: str,
    items: list[QueueItem],
    include_claim_cards: bool = True,
) -> PacketSummary:
    """Build a PacketSummary for a group of queue items from one source.

    AC-REV-001A-1: Includes claim cards (when enabled), citations,
    and canonical-impact descriptions.
    """
    queue_ids = sorted(set(item.queue_id for item in items))
    run_ids = sorted(set(item.run_id for item in items))

    has_contradicting = any(
        item.match_class == CONTRADICTING_CLASS for item in items
    )

    claim_cards: list[dict[str, Any]] = []
    if include_claim_cards:
        for item in items:
            if item.claim_text is not None:
                claim_cards.append({
                    "queue_id": item.queue_id,
                    "claim_text": item.claim_text,
                    "match_class": item.match_class,
                })

    if has_contradicting:
        impact = "Contains contradicting claims requiring human review"
    elif len(items) > 3:
        impact = f"Batch of {len(items)} claims from this source"
    else:
        impact = "Standard review"

    return PacketSummary(
        source_id=source_id,
        queue_ids=queue_ids,
        run_ids=run_ids,
        claim_count=len(items),
        has_contradicting=has_contradicting,
        canonical_impact=impact,
        citations=[f"Sources/{source_id}.md"],
        claim_cards=claim_cards,
    )


# ─── Digest generation ──────────────────────────────────────────────────

@dataclass
class DigestResult:
    """Result of generating a review digest."""
    digest_date: str
    packets: list[PacketSummary]
    source_count: int
    pending_item_count: int
    held_item_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "digest_date": self.digest_date,
            "packets": [p.to_dict() for p in self.packets],
            "source_count": self.source_count,
            "pending_item_count": self.pending_item_count,
            "held_item_count": self.held_item_count,
        }


def generate_digest(
    items: list[QueueItem],
    digest_date: date,
    policy: ReviewPolicy | None = None,
    include_claim_cards: bool = True,
    limit_sources: int | None = None,
) -> DigestResult:
    """Generate a review digest from queue items.

    AC-REV-001A-1: Digest includes packet summaries with claim cards,
    citations, and canonical-impact descriptions.
    AC-REV-001A-3: Held items resurface when hold_until <= digest_date.
    """
    if policy is None:
        policy = ReviewPolicy()

    # Count held items before filtering
    held_count = sum(
        1 for item in items
        if item.status == "pending_review"
        and item.hold_until is not None
        and not should_resurface(item, digest_date)
    )

    # Filter items eligible for this digest
    eligible = filter_for_digest(items, digest_date)

    # Group by source
    groups = group_by_source(eligible)

    # Build packet summaries
    source_ids = sorted(groups.keys())
    if limit_sources is not None:
        source_ids = source_ids[:limit_sources]

    packets = [
        build_packet_summary(
            sid, groups[sid], include_claim_cards=include_claim_cards
        )
        for sid in source_ids
    ]

    return DigestResult(
        digest_date=digest_date.isoformat(),
        packets=packets,
        source_count=len(packets),
        pending_item_count=len(eligible),
        held_item_count=held_count,
    )


# ─── Hold application ───────────────────────────────────────────────────

def apply_hold(
    item: QueueItem,
    policy: ReviewPolicy,
    from_date: date | None = None,
) -> QueueItem:
    """Apply a hold to a queue item.

    Computes hold_until from policy and keeps status as pending_review.
    """
    hold_date = policy.hold_until(from_date)
    item.hold_until = hold_date.isoformat()
    item.status = "pending_review"
    return item


# ─── Packet action application ──────────────────────────────────────────

@dataclass
class ActionResult:
    """Result of applying a packet action."""
    approved: list[str] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)
    held: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "approved": self.approved,
            "rejected": self.rejected,
            "held": self.held,
            "skipped": self.skipped,
        }


def apply_packet_action(
    action: str,
    items: list[QueueItem],
    policy: ReviewPolicy | None = None,
    approved_queue_ids: list[str] | None = None,
    from_date: date | None = None,
) -> ActionResult:
    """Apply a packet action to a list of queue items.

    AC-REV-001A-2: Deterministic outcomes for deterministic fixtures.
    CONTRADICTING items are never auto-approved.

    Args:
        action: One of approve_all, approve_selected, hold, reject.
        items: Queue items in the packet.
        policy: Review policy for hold TTL.
        approved_queue_ids: For approve_selected, the IDs to approve.
        from_date: Date for hold_until computation.

    Returns:
        ActionResult with categorized queue IDs.
    """
    if policy is None:
        policy = ReviewPolicy()

    result = ActionResult()

    if action == "approve_all":
        for item in items:
            if item.match_class == CONTRADICTING_CLASS:
                result.skipped.append(item.queue_id)
            else:
                item.status = "approved"
                result.approved.append(item.queue_id)

    elif action == "approve_selected":
        selected = set(approved_queue_ids or [])
        for item in items:
            if item.queue_id in selected:
                if item.match_class == CONTRADICTING_CLASS:
                    result.skipped.append(item.queue_id)
                else:
                    item.status = "approved"
                    result.approved.append(item.queue_id)

    elif action == "hold":
        for item in items:
            apply_hold(item, policy, from_date)
            result.held.append(item.queue_id)

    elif action == "reject":
        for item in items:
            item.status = "rejected"
            result.rejected.append(item.queue_id)

    return result
