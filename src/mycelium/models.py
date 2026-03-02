"""
Output Envelope and supporting data models for Mycelium commands.

Implements IF-001 and IF-002 from the refactor spec (§5.1).
- IF-001: Every command response MUST return the Output Envelope.
- IF-002: Commands that write files MUST support Dry Run mode.

Spec reference: mycelium_refactor_plan_apr_round5.md §5.1, lines 443-483
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


@dataclass
class ErrorObject:
    """Structured error within an Output Envelope.

    Spec: §5.1 ErrorObject
    - code: string (machine-readable error code)
    - message: string (human-readable description)
    - retryable: boolean (whether the caller can retry)
    - details: object (optional, additional context)
    - stage: string|null (optional, pipeline stage name per §6.1.2)
    """

    code: str
    message: str
    retryable: bool
    details: dict[str, Any] | None = None
    stage: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
        }
        if self.details is not None:
            d["details"] = self.details
        if self.stage is not None:
            d["stage"] = self.stage
        return d


@dataclass
class WarningObject:
    """Structured warning within an Output Envelope.

    Spec: §5.1 WarningObject
    - code: string (machine-readable warning code)
    - message: string (human-readable description)
    - details: object (optional, additional context)
    """

    code: str
    message: str
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
        }
        if self.details is not None:
            d["details"] = self.details
        return d


@dataclass
class OutputEnvelope:
    """Universal response schema for all Mycelium commands (IF-001).

    Spec: §5.1 Output Envelope
    - ok: boolean
    - command: string (the invoked command name)
    - timestamp: string (ISO-8601 UTC)
    - data: object (command-specific; MAY include partial results on failure)
    - errors: array[ErrorObject] (empty if ok=true)
    - warnings: array[WarningObject] (empty allowed)
    - trace: object|null (optional, for debug/diagnostics)

    Acceptance criteria:
    - AC-IF-001-1: All commands return envelope keys exactly as specified.
    - AC-IF-001-2: If a command fails, ok=false and errors.length>=1.
    - AC-IF-001-3: Error objects always include code, message, and retryable.
    - AC-IF-001-4: timestamp parses as ISO-8601 UTC and command equals the
      invoked command name.
    """

    ok: bool
    command: str
    timestamp: str
    data: dict[str, Any] = field(default_factory=dict)
    errors: list[ErrorObject] = field(default_factory=list)
    warnings: list[WarningObject] = field(default_factory=list)
    trace: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "ok": self.ok,
            "command": self.command,
            "timestamp": self.timestamp,
            "data": self.data,
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [w.to_dict() for w in self.warnings],
            "trace": self.trace,
        }
        return d


def make_envelope(
    command: str,
    *,
    ok: bool = True,
    data: dict[str, Any] | None = None,
    errors: list[ErrorObject] | None = None,
    warnings: list[WarningObject] | None = None,
    trace: dict[str, Any] | None = None,
) -> OutputEnvelope:
    """Build an OutputEnvelope with automatic timestamp and consistency checks.

    If errors are provided and ok is not explicitly set to False, ok will be
    forced to False (AC-IF-001-2). Conversely, if ok=False, at least one error
    must be present.

    Args:
        command: The invoked command name.
        ok: Whether the command succeeded.
        data: Command-specific result data.
        errors: List of ErrorObject instances.
        warnings: List of WarningObject instances.
        trace: Optional debug/diagnostics object.

    Returns:
        A fully-populated OutputEnvelope.

    Raises:
        ValueError: If ok=False but no errors are provided (AC-IF-001-2).
    """
    errors = errors or []
    warnings = warnings or []

    # AC-IF-001-2: errors present implies ok=False
    if errors:
        ok = False

    # AC-IF-001-2: ok=False requires at least one error
    if not ok and not errors:
        raise ValueError(
            "AC-IF-001-2 violation: ok=False requires at least one error"
        )

    return OutputEnvelope(
        ok=ok,
        command=command,
        timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        data=data or {},
        errors=errors,
        warnings=warnings,
        trace=trace,
    )


def error_envelope(
    command: str,
    code: str,
    message: str,
    *,
    retryable: bool = False,
    stage: str | None = None,
    details: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    trace: dict[str, Any] | None = None,
) -> OutputEnvelope:
    """Convenience: build a single-error failure envelope.

    Args:
        command: The invoked command name.
        code: Machine-readable error code.
        message: Human-readable error description.
        retryable: Whether the caller can retry.
        stage: Optional pipeline stage name.
        details: Optional error details.
        data: Optional partial results.
        trace: Optional debug/diagnostics object.

    Returns:
        An OutputEnvelope with ok=False and one ErrorObject.
    """
    return make_envelope(
        command,
        ok=False,
        data=data,
        errors=[
            ErrorObject(
                code=code,
                message=message,
                retryable=retryable,
                details=details,
                stage=stage,
            )
        ],
        trace=trace,
    )


# ─── IF-002: Dry Run ──────────────────────────────────────────────────────


class FileOp(str, Enum):
    """File operation types for Dry Run planned writes (§5.1.1)."""

    WRITE = "write"
    MOVE = "move"
    COPY = "copy"
    MKDIR = "mkdir"
    DELETE = "delete"


@dataclass
class PlannedOperation:
    """A single planned file operation returned by Dry Run mode (IF-002).

    Spec: §5.1.1
    - op: enum (write|move|copy|mkdir|delete)
    - path: string (vault-relative target path)
    - from_path: string|null (required when op is move|copy|delete)
    - reason: string|null (human-readable rationale)
    """

    op: FileOp
    path: str
    from_path: str | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.op, str):
            self.op = FileOp(self.op)
        if self.op in (FileOp.MOVE, FileOp.COPY, FileOp.DELETE) and self.from_path is None:
            raise ValueError(
                f"from_path is required when op is {self.op.value}"
            )

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "op": self.op.value,
            "path": self.path,
            "from_path": self.from_path,
            "reason": self.reason,
        }
        return d


def dry_run_envelope(
    command: str,
    planned_writes: list[PlannedOperation],
    *,
    warnings: list[WarningObject] | None = None,
    trace: dict[str, Any] | None = None,
) -> OutputEnvelope:
    """Build a Dry Run success envelope with planned_writes in data.

    AC-IF-002-1: Returns planned file operations in data.planned_writes.
    AC-IF-002-2: Schema validation errors should be added as warnings
    or errors by the caller before invoking this helper.

    Args:
        command: The invoked command name.
        planned_writes: List of PlannedOperation instances.
        warnings: Optional schema validation warnings.
        trace: Optional debug/diagnostics object.

    Returns:
        An OutputEnvelope with ok=True and data.planned_writes populated.
    """
    return make_envelope(
        command,
        data={"planned_writes": [pw.to_dict() for pw in planned_writes]},
        warnings=warnings,
        trace=trace,
    )
