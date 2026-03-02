"""
Review Digest command contract (CMD-RDG-001).

Produces a reading-first artifact grouped by Source, with per-Source
Review Packets that support deterministic downstream decision application.

Spec reference: §5.2.4 CMD-RDG-001
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any

from mycelium.models import (
    ErrorObject,
    OutputEnvelope,
    error_envelope,
    make_envelope,
)


# ─── Error codes ──────────────────────────────────────────────────────────

ERR_REVIEW_DIGEST_EMPTY = "ERR_REVIEW_DIGEST_EMPTY"
ERR_SCHEMA_VALIDATION = "ERR_SCHEMA_VALIDATION"


# ─── Packet decision types (SCH-009) ─────────────────────────────────────

class PacketAction(str, Enum):
    """Review Packet actions per SCH-009 / AC-CMD-RDG-001-2."""
    APPROVE_ALL = "approve_all"
    APPROVE_SELECTED = "approve_selected"
    HOLD = "hold"
    REJECT = "reject"


# ─── Input / Output models ───────────────────────────────────────────────

@dataclass
class ReviewDigestInput:
    """Validated input for the review_digest command."""
    date: str  # YYYY-MM-DD
    run_ids: list[str] = field(default_factory=list)
    limit_sources: int | None = None
    include_claim_cards: bool = True
    actor: str | None = None


@dataclass
class ReviewPacket:
    """A per-Source Review Packet (SCH-009).

    AC-CMD-RDG-001-1: Each packet includes queue_ids and run_ids.
    AC-CMD-RDG-001-2: Packet actions are exactly approve_all,
    approve_selected, hold, reject.
    """
    source_id: str
    queue_ids: list[str]
    run_ids: list[str]
    packet_path: str
    allowed_actions: list[str] = field(default_factory=lambda: [
        a.value for a in PacketAction
    ])

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "queue_ids": self.queue_ids,
            "run_ids": self.run_ids,
            "packet_path": self.packet_path,
            "allowed_actions": self.allowed_actions,
        }


# ─── Validation ───────────────────────────────────────────────────────────

def validate_review_digest_input(raw: dict[str, Any]) -> ReviewDigestInput | ErrorObject:
    """Validate raw input dict into ReviewDigestInput.

    Returns ReviewDigestInput on success, ErrorObject on failure.
    """
    # Date: default to today, validate format
    raw_date = raw.get("date")
    if raw_date is None:
        digest_date = date.today().isoformat()
    else:
        try:
            date.fromisoformat(str(raw_date))
            digest_date = str(raw_date)
        except ValueError:
            return ErrorObject(
                code=ERR_SCHEMA_VALIDATION,
                message=f"Invalid date format: {raw_date!r}. Expected YYYY-MM-DD",
                retryable=False,
            )

    run_ids = raw.get("run_ids", [])
    if not isinstance(run_ids, list):
        return ErrorObject(
            code=ERR_SCHEMA_VALIDATION,
            message="run_ids must be an array of strings",
            retryable=False,
        )

    limit_sources = raw.get("limit_sources")
    if limit_sources is not None:
        if not isinstance(limit_sources, int) or limit_sources < 1:
            return ErrorObject(
                code=ERR_SCHEMA_VALIDATION,
                message="limit_sources must be a positive integer",
                retryable=False,
            )

    include_claim_cards = raw.get("include_claim_cards", True)

    return ReviewDigestInput(
        date=digest_date,
        run_ids=run_ids,
        limit_sources=limit_sources,
        include_claim_cards=bool(include_claim_cards),
        actor=raw.get("actor"),
    )


def execute_review_digest(raw_input: dict[str, Any]) -> OutputEnvelope:
    """Execute the review_digest command contract.

    This implements the command contract layer. Actual queue enumeration,
    packet generation, and filesystem writes are delegated to the review
    queue module (§8) during integration.

    Args:
        raw_input: Raw command input dict.

    Returns:
        OutputEnvelope with digest results.
    """
    result = validate_review_digest_input(raw_input)
    if isinstance(result, ErrorObject):
        return make_envelope("review_digest", errors=[result])

    digest_input = result

    # In full integration: enumerate pending queue items, group by source,
    # generate packets, write artifacts. For the contract layer, return
    # the spec-compliant output structure.
    return make_envelope(
        "review_digest",
        data={
            "digest_path": "",
            "packet_paths": [],
            "source_count": 0,
            "pending_item_count": 0,
        },
    )
