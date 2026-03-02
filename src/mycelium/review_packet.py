"""Review Packet schema validation and persistence (SCH-009).

Review Packets are persisted as YAML under ``Inbox/ReviewDigest/``,
one packet per Source included in a Review Digest.

Spec reference: §4.2.9 SCH-009
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

from mycelium.schema import SchemaValidationError, _parse_iso8601_utc

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

PACKET_ACTIONS = frozenset({
    "approve_all",
    "approve_selected",
    "hold",
    "reject",
})


# ---------------------------------------------------------------------------
# Required keys
# ---------------------------------------------------------------------------

REQUIRED_PACKET_KEYS = frozenset({
    "packet_id",
    "digest_date",
    "created_at",
    "source_id",
    "run_ids",
    "queue_ids",
    "decision",
})

REQUIRED_DECISION_KEYS = frozenset({
    "action",
    "actor",
    "decided_at",
    "reason",
})


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _validate_date_string(value: Any) -> str | None:
    """Return error string if value is not a valid YYYY-MM-DD date, else None."""
    if not isinstance(value, str):
        return f"expected string, got {type(value).__name__}"
    try:
        date.fromisoformat(value)
        return None
    except ValueError as exc:
        return f"invalid date format: {exc}"


def validate_review_packet(packet: dict[str, Any]) -> list[str]:
    """Validate a Review Packet dict against SCH-009.

    Returns a list of error strings (empty means valid).
    """
    errors: list[str] = []

    # Required keys
    missing = REQUIRED_PACKET_KEYS - set(packet.keys())
    if missing:
        errors.append(f"Missing required keys: {sorted(missing)}")

    # packet_id: non-empty string
    if "packet_id" in packet:
        pid = packet["packet_id"]
        if not isinstance(pid, str) or not pid.strip():
            errors.append("packet_id must be a non-empty string")

    # digest_date: YYYY-MM-DD
    if "digest_date" in packet:
        err = _validate_date_string(packet["digest_date"])
        if err:
            errors.append(f"Invalid digest_date: {err}")

    # created_at: ISO-8601 UTC
    if "created_at" in packet:
        try:
            _parse_iso8601_utc(packet["created_at"])
        except (ValueError, TypeError) as exc:
            errors.append(f"Invalid created_at datetime: {exc}")

    # source_id: non-empty string
    if "source_id" in packet:
        sid = packet["source_id"]
        if not isinstance(sid, str) or not sid.strip():
            errors.append("source_id must be a non-empty string")

    # run_ids: non-empty array of strings
    if "run_ids" in packet:
        rids = packet["run_ids"]
        if not isinstance(rids, list) or len(rids) == 0:
            errors.append("run_ids must be a non-empty array")
        elif not all(isinstance(r, str) and r.strip() for r in rids):
            errors.append("run_ids entries must be non-empty strings")

    # queue_ids: non-empty array of strings
    if "queue_ids" in packet:
        qids = packet["queue_ids"]
        if not isinstance(qids, list) or len(qids) == 0:
            errors.append("queue_ids must be a non-empty array")
        elif not all(isinstance(q, str) and q.strip() for q in qids):
            errors.append("queue_ids entries must be non-empty strings")

    # decision: null or valid decision object
    if "decision" in packet:
        decision = packet["decision"]
        if decision is not None:
            if not isinstance(decision, dict):
                errors.append("decision must be an object or null")
            else:
                errors.extend(_validate_decision(decision, packet))

    return errors


def _validate_decision(
    decision: dict[str, Any],
    packet: dict[str, Any],
) -> list[str]:
    """Validate the decision sub-object of a Review Packet."""
    errors: list[str] = []

    # Required decision keys
    missing = REQUIRED_DECISION_KEYS - set(decision.keys())
    if missing:
        errors.append(f"decision missing required keys: {sorted(missing)}")

    # action enum
    if "action" in decision:
        action = decision["action"]
        if action not in PACKET_ACTIONS:
            errors.append(
                f"Invalid decision.action: {action!r} "
                f"(expected one of {sorted(PACKET_ACTIONS)})"
            )

    # actor: non-empty string
    if "actor" in decision:
        actor = decision["actor"]
        if not isinstance(actor, str) or not actor.strip():
            errors.append("decision.actor must be a non-empty string")

    # decided_at: ISO-8601 UTC
    if "decided_at" in decision:
        try:
            _parse_iso8601_utc(decision["decided_at"])
        except (ValueError, TypeError) as exc:
            errors.append(f"Invalid decision.decided_at datetime: {exc}")

    # reason: string or null
    if "reason" in decision:
        reason = decision["reason"]
        if reason is not None and not isinstance(reason, str):
            errors.append("decision.reason must be a string or null")

    # AC-SCH-009-3: action-specific validation
    action = decision.get("action")

    if action == "approve_selected":
        if "approved_queue_ids" not in decision:
            errors.append(
                "approve_selected decisions must include approved_queue_ids"
            )
        else:
            aqids = decision["approved_queue_ids"]
            if not isinstance(aqids, list) or len(aqids) == 0:
                errors.append("approved_queue_ids must be a non-empty array")
            elif isinstance(aqids, list):
                # All approved_queue_ids must be in queue_ids
                queue_ids = set(packet.get("queue_ids", []))
                approved = set(aqids)
                invalid = approved - queue_ids
                if invalid:
                    errors.append(
                        f"approved_queue_ids contains ids not in queue_ids: "
                        f"{sorted(invalid)}"
                    )

    if action == "hold":
        if "hold_until" not in decision:
            errors.append("hold decisions must include hold_until (YYYY-MM-DD)")
        else:
            err = _validate_date_string(decision["hold_until"])
            if err:
                errors.append(f"Invalid decision.hold_until: {err}")

    return errors


def validate_review_packet_strict(packet: dict[str, Any]) -> None:
    """Validate and raise SchemaValidationError on failure."""
    errors = validate_review_packet(packet)
    if errors:
        raise SchemaValidationError(errors)


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

def build_review_packet(
    *,
    packet_id: str,
    digest_date: str,
    created_at: str,
    source_id: str,
    run_ids: list[str],
    queue_ids: list[str],
    decision: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a spec-conformant Review Packet dict.

    Args:
        packet_id: Unique packet ID.
        digest_date: Digest date (YYYY-MM-DD).
        created_at: ISO-8601 UTC timestamp.
        source_id: Source Note ID.
        run_ids: Non-empty list of ingestion run IDs.
        queue_ids: Non-empty list of queue item IDs.
        decision: Decision object or None (pending).

    Returns:
        A packet dict conforming to SCH-009.
    """
    return {
        "packet_id": packet_id,
        "digest_date": digest_date,
        "created_at": created_at,
        "source_id": source_id,
        "run_ids": run_ids,
        "queue_ids": queue_ids,
        "decision": decision,
    }


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_review_packet(vault_root: Path, packet: dict[str, Any]) -> Path:
    """Persist a Review Packet as YAML under ``Inbox/ReviewDigest/``.

    Args:
        vault_root: Absolute path to the vault root.
        packet: A validated packet dict.

    Returns:
        Path to the written YAML file.
    """
    validate_review_packet_strict(packet)

    digest_dir = vault_root / "Inbox" / "ReviewDigest"
    digest_dir.mkdir(parents=True, exist_ok=True)

    packet_id = packet["packet_id"]
    file_path = digest_dir / f"{packet_id}.yaml"

    with open(file_path, "w") as f:
        yaml.dump(
            packet, f,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )

    logger.info("Review packet written: %s", file_path)
    return file_path


def load_review_packet(file_path: Path) -> dict[str, Any]:
    """Load and validate a Review Packet from YAML.

    Args:
        file_path: Path to the packet YAML file.

    Returns:
        Parsed and validated packet dict.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        SchemaValidationError: If validation fails.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Review packet not found: {file_path}")

    with open(file_path) as f:
        packet = yaml.safe_load(f)

    validate_review_packet_strict(packet)
    return packet


def list_review_packets(vault_root: Path) -> list[Path]:
    """List all Review Packet YAML files under ``Inbox/ReviewDigest/``.

    Returns:
        Sorted list of packet file paths.
    """
    digest_dir = vault_root / "Inbox" / "ReviewDigest"
    if not digest_dir.exists():
        return []
    return sorted(digest_dir.glob("*.yaml"))
