"""
Append-only audit logging for Mycelium (AUD-001).

Writes structured audit events as newline-delimited JSON (JSONL) under
``Logs/Audit/`` in the vault. Each event is a single JSON line containing
the minimum fields specified in §9.1 of the spec.

Events are append-only: ``emit_event`` opens the file in append mode and
writes a single line, never overwriting prior content (AC-AUD-001-2).

Spec reference: §9.1 AUD-001, §9.1 AUD-002
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Event types (§9.1)
# ---------------------------------------------------------------------------

class EventType(str, Enum):
    """Audit event types per AUD-001."""

    INGEST_STARTED = "ingest_started"
    INGEST_COMPLETED = "ingest_completed"
    INGEST_FAILED = "ingest_failed"
    PROMOTION_APPLIED = "promotion_applied"
    EGRESS_ATTEMPTED = "egress_attempted"
    EGRESS_BLOCKED = "egress_blocked"
    EGRESS_COMPLETED = "egress_completed"
    EGRESS_MODE_TRANSITION = "egress_mode_transition"


#: Terminal ingest event types — exactly one must follow ingest_started.
TERMINAL_INGEST_EVENTS = frozenset({
    EventType.INGEST_COMPLETED,
    EventType.INGEST_FAILED,
})


# ---------------------------------------------------------------------------
# AuditEvent data model
# ---------------------------------------------------------------------------

@dataclass
class AuditEvent:
    """A single audit event conforming to AUD-001 minimum fields.

    Attributes:
        event_id: Unique identifier for this event.
        timestamp: ISO-8601 UTC timestamp string.
        actor: Who/what triggered the event (``"unknown"`` if not determinable).
        event_type: One of the ``EventType`` enum values.
        run_id: Ingestion run ID, or ``None`` for non-run events.
        targets: Affected vault-relative file paths.
        details: Arbitrary additional context.
    """

    event_id: str
    timestamp: str
    actor: str
    event_type: str
    run_id: str | None = None
    targets: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def to_json_line(self) -> str:
        """Serialize to a single JSON line (no trailing newline)."""
        return json.dumps(asdict(self), separators=(",", ":"), sort_keys=True)


# ---------------------------------------------------------------------------
# Audit log writer
# ---------------------------------------------------------------------------

def _audit_log_path(vault_root: Path, log_date: datetime | None = None) -> Path:
    """Compute the JSONL audit log file path for a given date.

    Files are partitioned by date under ``Logs/Audit/``:
    ``Logs/Audit/audit-YYYY-MM-DD.jsonl``

    Args:
        vault_root: Absolute path to the vault root.
        log_date: Date for the log file. Defaults to now (UTC).

    Returns:
        Absolute path to the audit log file.
    """
    if log_date is None:
        log_date = datetime.now(timezone.utc)
    date_str = log_date.strftime("%Y-%m-%d")
    return vault_root / "Logs" / "Audit" / f"audit-{date_str}.jsonl"


def emit_event(
    vault_root: Path,
    event_type: EventType | str,
    *,
    actor: str = "unknown",
    run_id: str | None = None,
    targets: list[str] | None = None,
    details: dict[str, Any] | None = None,
    event_id: str | None = None,
    timestamp: str | None = None,
) -> AuditEvent:
    """Append a single audit event to the JSONL log file.

    This function is append-only: it opens the log file in ``"a"`` mode
    and writes exactly one JSON line, preserving all prior content
    (AC-AUD-001-2, AC-AUD-002-2).

    Args:
        vault_root: Absolute path to the vault root directory.
        event_type: Event type enum value or string.
        actor: Who triggered the event.
        run_id: Ingestion run ID (nullable).
        targets: Affected file paths (vault-relative).
        details: Additional context dict.
        event_id: Override event ID (defaults to new UUID).
        timestamp: Override timestamp (defaults to now UTC).

    Returns:
        The ``AuditEvent`` that was written.
    """
    # Normalize event_type to string
    if isinstance(event_type, EventType):
        event_type_str = event_type.value
    else:
        event_type_str = str(event_type)

    event = AuditEvent(
        event_id=event_id or str(uuid.uuid4()),
        timestamp=timestamp or datetime.now(timezone.utc).isoformat(),
        actor=actor,
        event_type=event_type_str,
        run_id=run_id,
        targets=targets or [],
        details=details or {},
    )

    log_path = _audit_log_path(vault_root)

    # Ensure directory exists
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Append-only write (AC-AUD-001-2)
    with open(log_path, "a") as f:
        f.write(event.to_json_line() + "\n")

    logger.info(f"Audit event: {event_type_str} (run_id={run_id})")
    return event


def read_audit_log(log_path: Path) -> list[AuditEvent]:
    """Read and parse a JSONL audit log file.

    Each line is parsed as a JSON object and validated against the
    AuditEvent minimum fields (AUD-001).

    Args:
        log_path: Path to the ``.jsonl`` file.

    Returns:
        List of parsed ``AuditEvent`` objects.

    Raises:
        FileNotFoundError: If the log file doesn't exist.
    """
    events: list[AuditEvent] = []
    with open(log_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            events.append(AuditEvent(
                event_id=data["event_id"],
                timestamp=data["timestamp"],
                actor=data["actor"],
                event_type=data["event_type"],
                run_id=data.get("run_id"),
                targets=data.get("targets", []),
                details=data.get("details", {}),
            ))
    return events
