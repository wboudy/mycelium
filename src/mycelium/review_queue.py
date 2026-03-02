"""
Review Queue Item schema validation and persistence (SCH-007).

Review Queue Items are persisted as YAML under ``Inbox/ReviewQueue/``.
They represent proposals that require human review before promotion
to Canonical Scope.

Key invariant: non-``pending_review`` items are immutable except via
explicit state transition operations (§8.2), enforced by returning
``ERR_QUEUE_IMMUTABLE`` on mutation attempts.

Spec reference: §4.2.7 SCH-007
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from mycelium.schema import SchemaValidationError, _parse_iso8601_utc

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

ITEM_TYPES = frozenset({
    "source_note",
    "claim_note",
    "concept_note",
    "question_note",
    "link_proposal",
    "merge_proposal",
})

PROPOSED_ACTIONS = frozenset({
    "create",
    "promote_to_canon",
    "merge",
    "link",
    "reject",
})

QUEUE_STATUSES = frozenset({
    "pending_review",
    "approved",
    "rejected",
})


# ---------------------------------------------------------------------------
# Error codes
# ---------------------------------------------------------------------------

ERR_QUEUE_IMMUTABLE = "ERR_QUEUE_IMMUTABLE"


# ---------------------------------------------------------------------------
# Required keys
# ---------------------------------------------------------------------------

REQUIRED_KEYS = frozenset({
    "queue_id",
    "run_id",
    "item_type",
    "target_path",
    "proposed_action",
    "status",
    "created_at",
    "checks",
})


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_queue_item(item: dict[str, Any]) -> list[str]:
    """Validate a Review Queue Item dict against SCH-007.

    Returns a list of error strings (empty means valid).
    """
    errors: list[str] = []

    # Required keys
    missing = REQUIRED_KEYS - set(item.keys())
    if missing:
        errors.append(f"Missing required keys: {sorted(missing)}")

    # item_type enum
    if "item_type" in item:
        it = item["item_type"]
        if it not in ITEM_TYPES:
            errors.append(
                f"Invalid item_type: {it!r} (expected one of {sorted(ITEM_TYPES)})"
            )

    # proposed_action enum
    if "proposed_action" in item:
        pa = item["proposed_action"]
        if pa not in PROPOSED_ACTIONS:
            errors.append(
                f"Invalid proposed_action: {pa!r} (expected one of {sorted(PROPOSED_ACTIONS)})"
            )

    # status enum
    if "status" in item:
        s = item["status"]
        if s not in QUEUE_STATUSES:
            errors.append(
                f"Invalid status: {s!r} (expected one of {sorted(QUEUE_STATUSES)})"
            )

    # created_at must be ISO-8601
    if "created_at" in item:
        try:
            _parse_iso8601_utc(item["created_at"])
        except (ValueError, TypeError) as exc:
            errors.append(f"Invalid created_at datetime: {exc}")

    # queue_id must be non-empty string
    if "queue_id" in item:
        qid = item["queue_id"]
        if not isinstance(qid, str) or not qid.strip():
            errors.append("queue_id must be a non-empty string")

    # target_path must be non-empty string
    if "target_path" in item:
        tp = item["target_path"]
        if not isinstance(tp, str) or not tp.strip():
            errors.append("target_path must be a non-empty string")

    # checks must be a dict
    if "checks" in item:
        if not isinstance(item["checks"], dict):
            errors.append("checks must be an object/dict")

    return errors


def validate_queue_item_strict(item: dict[str, Any]) -> None:
    """Validate and raise SchemaValidationError on failure."""
    errors = validate_queue_item(item)
    if errors:
        raise SchemaValidationError(errors)


# ---------------------------------------------------------------------------
# Immutability guard (AC-SCH-007-1)
# ---------------------------------------------------------------------------

def check_mutable(item: dict[str, Any]) -> None:
    """Check that a queue item can be mutated.

    Only ``pending_review`` items may be modified. Attempting to
    mutate a non-pending item raises SchemaValidationError with
    code ``ERR_QUEUE_IMMUTABLE``.

    Args:
        item: The current queue item dict.

    Raises:
        SchemaValidationError: If the item is not ``pending_review``.
    """
    status = item.get("status")
    if status != "pending_review":
        raise SchemaValidationError([
            f"{ERR_QUEUE_IMMUTABLE}: Cannot mutate queue item with status "
            f"{status!r}. Only 'pending_review' items can be modified."
        ])


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

def build_queue_item(
    *,
    queue_id: str,
    run_id: str,
    item_type: str,
    target_path: str,
    proposed_action: str,
    created_at: str,
    checks: dict[str, Any] | None = None,
    status: str = "pending_review",
) -> dict[str, Any]:
    """Build a spec-conformant Review Queue Item dict.

    Args:
        queue_id: Unique queue item ID.
        run_id: Ingestion run ID.
        item_type: One of ITEM_TYPES.
        target_path: Vault-relative path of the target.
        proposed_action: One of PROPOSED_ACTIONS.
        created_at: ISO-8601 UTC timestamp.
        checks: Validation results dict.
        status: Initial status (defaults to pending_review).

    Returns:
        A queue item dict conforming to SCH-007.
    """
    return {
        "queue_id": queue_id,
        "run_id": run_id,
        "item_type": item_type,
        "target_path": target_path,
        "proposed_action": proposed_action,
        "status": status,
        "created_at": created_at,
        "checks": checks or {},
    }


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_queue_item(vault_root: Path, item: dict[str, Any]) -> Path:
    """Persist a Review Queue Item as YAML under ``Inbox/ReviewQueue/``.

    Args:
        vault_root: Absolute path to the vault root.
        item: A validated queue item dict.

    Returns:
        Path to the written YAML file.
    """
    validate_queue_item_strict(item)

    queue_dir = vault_root / "Inbox" / "ReviewQueue"
    queue_dir.mkdir(parents=True, exist_ok=True)

    from mycelium.atomic_write import atomic_write_text

    from mycelium.vault_layout import sanitize_path_component

    queue_id = item["queue_id"]
    sanitize_path_component(queue_id)
    file_path = queue_dir / f"{queue_id}.yaml"

    yaml_content = yaml.dump(item, default_flow_style=False, allow_unicode=True, sort_keys=False)
    atomic_write_text(file_path, yaml_content, mkdir=False)

    logger.info(f"Queue item written: {file_path}")
    return file_path


def load_queue_item(file_path: Path) -> dict[str, Any]:
    """Load and validate a Review Queue Item from YAML.

    Args:
        file_path: Path to the queue item YAML file.

    Returns:
        Parsed and validated queue item dict.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        SchemaValidationError: If validation fails.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Queue item not found: {file_path}")

    with open(file_path) as f:
        item = yaml.safe_load(f)

    validate_queue_item_strict(item)
    return item


def update_queue_item(
    file_path: Path,
    updates: dict[str, Any],
    *,
    is_state_transition: bool = False,
) -> dict[str, Any]:
    """Update a queue item on disk, enforcing immutability.

    Args:
        file_path: Path to the queue item YAML file.
        updates: Fields to update.
        is_state_transition: If True, bypass the immutability guard
            (used by explicit state transition operations per §8.2).

    Returns:
        The updated queue item dict.

    Raises:
        SchemaValidationError: If the item is immutable and
            ``is_state_transition`` is False, or if the result
            fails validation.
    """
    item = load_queue_item(file_path)

    # AC-SCH-007-1: Only allow mutation of pending_review items,
    # unless this is an explicit state transition.
    if not is_state_transition:
        check_mutable(item)

    from mycelium.atomic_write import atomic_write_text

    item.update(updates)
    validate_queue_item_strict(item)

    yaml_content = yaml.dump(item, default_flow_style=False, allow_unicode=True, sort_keys=False)
    atomic_write_text(file_path, yaml_content, mkdir=False)

    return item
