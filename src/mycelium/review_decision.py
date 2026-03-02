"""
Review Decision Record schema validation (SCH-010).

Each invocation of ``review`` persists exactly one Review Decision Record
in YAML under ``Inbox/ReviewDigest/``.

Spec reference: §4.2.10
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from mycelium.schema import SchemaValidationError, _parse_iso8601_utc


# ─── Constants ────────────────────────────────────────────────────────────

DECISION_MODES = frozenset({"direct", "digest"})
QUEUE_STATUSES = frozenset({"pending_review", "approved", "rejected"})

REQUIRED_KEYS = (
    "decision_id", "created_at", "mode", "actor", "reason", "results",
)

RESULT_REQUIRED_KEYS = ("queue_id", "old_status", "new_status")

_DATE_RE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"
import re
_DATE_RE = re.compile(_DATE_RE_PATTERN)


# ─── Validation ───────────────────────────────────────────────────────────

def validate_review_decision(record: dict[str, Any]) -> list[str]:
    """Validate a Review Decision Record per SCH-010.

    Returns a list of validation error strings (empty means valid).
    Unknown keys are silently ignored (forward compatibility).

    Checks:
      - Required top-level keys present.
      - created_at is valid ISO-8601 UTC.
      - mode is one of direct|digest.
      - results is an array; each entry has required keys with valid enums.
      - AC-SCH-010-2: For hold decisions (new_status=pending_review and
        old_status=pending_review), hold_until must be present.
    """
    errors: list[str] = []

    # Check required top-level keys
    for key in REQUIRED_KEYS:
        if key not in record:
            errors.append(f"Missing required key: {key}")

    # Validate decision_id is non-empty string
    if "decision_id" in record:
        did = record["decision_id"]
        if not isinstance(did, str) or not did.strip():
            errors.append("decision_id must be a non-empty string")

    # Validate created_at as ISO-8601 UTC
    if "created_at" in record:
        try:
            _parse_iso8601_utc(record["created_at"])
        except (ValueError, TypeError) as exc:
            errors.append(f"Invalid created_at datetime: {exc}")

    # Validate mode enum
    if "mode" in record:
        mode = record["mode"]
        if mode not in DECISION_MODES:
            errors.append(
                f"Invalid mode: {mode!r} (expected one of {sorted(DECISION_MODES)})"
            )

    # Validate actor is non-empty string
    if "actor" in record:
        actor = record["actor"]
        if not isinstance(actor, str) or not actor.strip():
            errors.append("actor must be a non-empty string")

    # reason is nullable — just check type if present and non-null
    if "reason" in record:
        reason = record["reason"]
        if reason is not None and not isinstance(reason, str):
            errors.append("reason must be a string or null")

    # Validate results array
    if "results" in record:
        results = record["results"]
        if not isinstance(results, list):
            errors.append("results must be an array")
        else:
            for i, entry in enumerate(results):
                if not isinstance(entry, dict):
                    errors.append(f"results[{i}] must be an object")
                    continue
                _validate_result_entry(entry, i, errors)

    return errors


def _validate_result_entry(
    entry: dict[str, Any], index: int, errors: list[str]
) -> None:
    """Validate a single results entry."""
    # Check required keys
    for key in RESULT_REQUIRED_KEYS:
        if key not in entry:
            errors.append(f"results[{index}] missing required key: {key}")

    # Validate queue_id
    if "queue_id" in entry:
        qid = entry["queue_id"]
        if not isinstance(qid, str) or not qid.strip():
            errors.append(f"results[{index}].queue_id must be a non-empty string")

    # Validate old_status enum
    if "old_status" in entry:
        old = entry["old_status"]
        if old not in QUEUE_STATUSES:
            errors.append(
                f"results[{index}].old_status invalid: {old!r} "
                f"(expected one of {sorted(QUEUE_STATUSES)})"
            )

    # Validate new_status enum
    if "new_status" in entry:
        new = entry["new_status"]
        if new not in QUEUE_STATUSES:
            errors.append(
                f"results[{index}].new_status invalid: {new!r} "
                f"(expected one of {sorted(QUEUE_STATUSES)})"
            )

    # AC-SCH-010-2: Hold decisions require hold_until
    old_status = entry.get("old_status")
    new_status = entry.get("new_status")
    if old_status == "pending_review" and new_status == "pending_review":
        if "hold_until" not in entry or entry["hold_until"] is None:
            errors.append(
                f"results[{index}]: hold decisions (pending_review -> pending_review) "
                f"require hold_until"
            )

    # Validate hold_until format if present
    if "hold_until" in entry and entry["hold_until"] is not None:
        hu = entry["hold_until"]
        if not isinstance(hu, str) or not _DATE_RE.match(hu):
            errors.append(
                f"results[{index}].hold_until must be YYYY-MM-DD format, got {hu!r}"
            )


def validate_review_decision_strict(record: dict[str, Any]) -> None:
    """Validate and raise SchemaValidationError on failure."""
    errors = validate_review_decision(record)
    if errors:
        raise SchemaValidationError(errors)
