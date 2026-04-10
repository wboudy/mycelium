"""
Review command contract (CMD-REV-001).

Implements the authoritative state transition operation for queue decisions.
Supports direct mode (individual queue items) and digest mode (batch).

REV-002 enforcement: legal transitions are pending_review → approved and
pending_review → rejected. Any mutation of approved/rejected status without
explicit migration tooling returns ERR_QUEUE_IMMUTABLE. Hold is a review
decision artifact, not a queue status mutation.

Spec reference: §5.2.3 CMD-REV-001, §8.2 REV-002
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

from mycelium.models import (
    ErrorObject,
    OutputEnvelope,
    make_envelope,
)

# ─── Domain types ─────────────────────────────────────────────────────────


class ReviewDecision(str, Enum):
    """Decision options for direct review mode."""
    APPROVE = "approve"
    REJECT = "reject"
    HOLD = "hold"


class QueueStatus(str, Enum):
    """Queue item statuses per §8.2."""
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"


# Legal transitions per AC-CMD-REV-001-1
LEGAL_TRANSITIONS: dict[tuple[QueueStatus, ReviewDecision], QueueStatus | None] = {
    (QueueStatus.PENDING_REVIEW, ReviewDecision.APPROVE): QueueStatus.APPROVED,
    (QueueStatus.PENDING_REVIEW, ReviewDecision.REJECT): QueueStatus.REJECTED,
    # Hold does NOT transition status (AC-CMD-REV-001-2)
    (QueueStatus.PENDING_REVIEW, ReviewDecision.HOLD): None,
}


# ─── Error codes ──────────────────────────────────────────────────────────


ERR_QUEUE_ITEM_INVALID = "ERR_QUEUE_ITEM_INVALID"
ERR_QUEUE_IMMUTABLE = "ERR_QUEUE_IMMUTABLE"
ERR_REVIEW_DECISION_INVALID = "ERR_REVIEW_DECISION_INVALID"


# ─── Input / Output models ───────────────────────────────────────────────


@dataclass
class ReviewInput:
    """Validated input for the review command.

    One of queue_id, queue_item_paths, or digest_path must be provided.
    In direct mode, decision is required. In digest mode, decisions come
    from packet records.
    """
    queue_id: str | None = None
    queue_item_paths: list[str] | None = None
    digest_path: str | None = None
    decision: ReviewDecision | None = None
    reason: str | None = None
    actor: str | None = None

    def is_direct_mode(self) -> bool:
        return self.queue_id is not None or self.queue_item_paths is not None

    def is_digest_mode(self) -> bool:
        return self.digest_path is not None


@dataclass
class TransitionResult:
    """Result of a single queue item state transition."""
    queue_id: str
    old_status: str
    new_status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "queue_id": self.queue_id,
            "old_status": self.old_status,
            "new_status": self.new_status,
        }


@dataclass
class HoldResult:
    """Result of a hold decision on a queue item."""
    queue_id: str
    hold_until: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "queue_id": self.queue_id,
            "hold_until": self.hold_until,
        }


# ─── Validation ───────────────────────────────────────────────────────────


def validate_review_input(raw: dict[str, Any]) -> ReviewInput | ErrorObject:
    """Validate raw input dict into ReviewInput or return an error.

    Returns ReviewInput on success, ErrorObject on validation failure.
    """
    queue_id = raw.get("queue_id")
    queue_item_paths = raw.get("queue_item_paths")
    digest_path = raw.get("digest_path")

    # Must provide exactly one input mode
    modes = sum(1 for v in [queue_id, queue_item_paths, digest_path] if v is not None)
    if modes == 0:
        return ErrorObject(
            code=ERR_QUEUE_ITEM_INVALID,
            message="One of queue_id, queue_item_paths, or digest_path is required",
            retryable=False,
        )
    if modes > 1:
        return ErrorObject(
            code=ERR_QUEUE_ITEM_INVALID,
            message="Provide exactly one of queue_id, queue_item_paths, or digest_path",
            retryable=False,
        )

    # Parse decision for direct mode
    decision = None
    if queue_id is not None or queue_item_paths is not None:
        raw_decision = raw.get("decision")
        if raw_decision is None:
            return ErrorObject(
                code=ERR_REVIEW_DECISION_INVALID,
                message="decision is required in direct mode (approve|reject|hold)",
                retryable=False,
            )
        try:
            decision = ReviewDecision(raw_decision)
        except ValueError:
            return ErrorObject(
                code=ERR_REVIEW_DECISION_INVALID,
                message=f"Invalid decision: {raw_decision!r}. Must be approve, reject, or hold",
                retryable=False,
            )

    return ReviewInput(
        queue_id=queue_id,
        queue_item_paths=queue_item_paths,
        digest_path=digest_path,
        decision=decision,
        reason=raw.get("reason"),
        actor=raw.get("actor"),
    )


def apply_transition(
    current_status: QueueStatus,
    decision: ReviewDecision,
) -> QueueStatus | None | ErrorObject:
    """Apply a review decision to a queue item's current status.

    Returns:
        - New QueueStatus for approve/reject transitions
        - None for hold (no status change, AC-CMD-REV-001-2)
        - ErrorObject for illegal transitions (AC-CMD-REV-001-1)
    """
    key = (current_status, decision)
    if key in LEGAL_TRANSITIONS:
        return LEGAL_TRANSITIONS[key]

    # Illegal transition
    return ErrorObject(
        code=ERR_QUEUE_IMMUTABLE,
        message=(
            f"Cannot apply {decision.value} to item with status "
            f"{current_status.value}; only pending_review items can be transitioned"
        ),
        retryable=False,
    )


def _build_decision_record(
    *,
    mode: str,
    actor: str,
    reason: str | None,
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a Review Decision Record (SCH-010) dict.

    Args:
        mode: "direct" or "digest".
        actor: Who made the review decision.
        reason: Optional reason for the decision.
        results: List of transition result dicts.

    Returns:
        A dict conforming to SCH-010.
    """
    return {
        "decision_id": str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "actor": actor,
        "reason": reason,
        "results": results,
    }


def save_decision_record(
    vault_root: Path,
    record: dict[str, Any],
) -> Path:
    """Persist a Review Decision Record as YAML under Inbox/ReviewDigest/.

    Args:
        vault_root: Absolute path to the vault root.
        record: A validated decision record dict.

    Returns:
        Path to the written file.
    """
    digest_dir = vault_root / "Inbox" / "ReviewDigest"
    digest_dir.mkdir(parents=True, exist_ok=True)

    from mycelium.vault_layout import sanitize_path_component

    decision_id = record["decision_id"]
    sanitize_path_component(decision_id)
    file_path = digest_dir / f"{decision_id}.yaml"

    from mycelium.atomic_write import atomic_write_text

    yaml_content = yaml.safe_dump(
        record, default_flow_style=False, allow_unicode=True, sort_keys=False,
    )
    atomic_write_text(file_path, yaml_content, mkdir=False)

    return file_path


def review_transition(
    *,
    queue_id: str,
    current_status: str,
    decision: ReviewDecision,
    actor: str,
    reason: str | None = None,
    hold_until: str | None = None,
    vault_root: Path | None = None,
) -> tuple[dict[str, Any] | None, OutputEnvelope]:
    """Execute a single review state transition with decision record.

    Enforces REV-002: only pending_review items can be transitioned.
    Writes a Review Decision Record (SCH-010) with actor/reason metadata.

    Args:
        queue_id: The queue item ID.
        current_status: Current status of the queue item.
        decision: The review decision to apply.
        actor: Who is making this decision.
        reason: Optional reason for the decision.
        hold_until: Required for hold decisions (YYYY-MM-DD).
        vault_root: Vault root for persisting the decision record.

    Returns:
        Tuple of (decision_record_or_none, OutputEnvelope).
    """
    try:
        status = QueueStatus(current_status)
    except ValueError:
        return None, make_envelope(
            "review",
            errors=[ErrorObject(
                code=ERR_QUEUE_ITEM_INVALID,
                message=f"Invalid current status: {current_status!r}",
                retryable=False,
            )],
        )

    # AC-REV-002-1: enforce legal transitions
    result = apply_transition(status, decision)
    if isinstance(result, ErrorObject):
        return None, make_envelope("review", errors=[result])

    # Build the result entry for the decision record
    if result is None:
        # Hold: status doesn't change
        new_status = current_status
        result_entry: dict[str, Any] = {
            "queue_id": queue_id,
            "old_status": current_status,
            "new_status": new_status,
        }
        if hold_until:
            result_entry["hold_until"] = hold_until
    else:
        new_status = result.value
        result_entry = {
            "queue_id": queue_id,
            "old_status": current_status,
            "new_status": new_status,
        }

    # AC-REV-002-2: build decision record with actor/reason
    record = _build_decision_record(
        mode="direct",
        actor=actor,
        reason=reason,
        results=[result_entry],
    )

    # Persist if vault_root provided
    if vault_root is not None:
        path = save_decision_record(vault_root, record)
        record["decision_record_path"] = str(path)

    env_data = {
        "updated": [result_entry] if result is not None else [],
        "held": [result_entry] if result is None else [],
        "decision_record_path": record.get("decision_record_path", ""),
    }

    return record, make_envelope("review", data=env_data)


def execute_review(raw_input: dict[str, Any]) -> OutputEnvelope:
    """Execute the review command contract.

    This implements the command contract layer. Actual queue persistence
    and filesystem operations are delegated to the review queue module
    (§8) which is wired in during integration.

    Args:
        raw_input: Raw command input dict.

    Returns:
        OutputEnvelope with review results.
    """
    # Validate input
    result = validate_review_input(raw_input)
    if isinstance(result, ErrorObject):
        return make_envelope("review", errors=[result])

    review_input = result

    if review_input.is_digest_mode():
        # Digest mode: delegate to digest processing
        # Actual implementation will load packet records and apply decisions
        # For now, return the contract-compliant envelope structure
        return make_envelope(
            "review",
            data={
                "updated": [],
                "held": [],
                "decision_record_path": "",
            },
        )

    # Direct mode: load queue item from vault and apply transition
    import os
    from pathlib import Path

    vault_root_str = os.environ.get("MYCELIUM_VAULT_ROOT", "vault")
    vault_root = Path(vault_root_str).resolve()
    queue_dir = vault_root / "Inbox" / "ReviewQueue"

    if not queue_dir.exists():
        return make_envelope("review", errors=[ErrorObject(
            code=ERR_QUEUE_ITEM_INVALID,
            message="Review queue directory not found",
            retryable=False,
        )])

    # Find the queue item
    queue_id = review_input.queue_id
    if not queue_id:
        return make_envelope("review", errors=[ErrorObject(
            code=ERR_QUEUE_ITEM_INVALID,
            message="queue_id is required for direct mode",
            retryable=False,
        )])

    queue_file = queue_dir / f"{queue_id}.yaml"
    if not queue_file.exists():
        return make_envelope("review", errors=[ErrorObject(
            code=ERR_QUEUE_ITEM_INVALID,
            message=f"Queue item not found: {queue_id}",
            retryable=False,
        )])

    # Load queue item
    import yaml
    with open(queue_file) as f:
        queue_item = yaml.safe_load(f) or {}

    current_status = queue_item.get("status", "pending_review")

    # Apply transition
    decision = review_input.decision
    if decision is None:
        return make_envelope("review", errors=[ErrorObject(
            code=ERR_QUEUE_ITEM_INVALID,
            message="decision is required for direct mode",
            retryable=False,
        )])

    result = apply_transition(current_status, decision)
    if isinstance(result, ErrorObject):
        return make_envelope("review", errors=[result])

    # Update queue item on disk
    if result is not None:
        queue_item["status"] = result.value
    with open(queue_file, "w") as f:
        yaml.safe_dump(queue_item, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    new_status = result.value if result is not None else current_status
    result_entry = {
        "queue_id": queue_id,
        "old_status": current_status,
        "new_status": new_status,
    }

    # Build and save decision record
    record = _build_decision_record(
        mode="direct",
        actor=review_input.actor or "human",
        reason=review_input.reason or "",
        results=[result_entry],
    )
    record_path = save_decision_record(vault_root, record)

    return make_envelope(
        "review",
        data={
            "updated": [result_entry] if result is not None else [],
            "held": [result_entry] if result is None else [],
            "decision_record_path": str(record_path),
        },
    )
