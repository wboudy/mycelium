"""Strict Mode semantics for Mycelium commands (IF-003).

Implements the cross-cutting Strict Mode flag from §5.1.2:
- strict=true: schema validation errors produce ok=false (errors in envelope).
- strict=false: schema validation errors are downgraded to warnings for
  read-only commands. Write commands still produce errors for validation
  failures even when strict=false.

For ingestion-associated operations, downgraded warnings are also collected
so they can be recorded in the Delta Report warnings array (AC-IF-003-2).

Spec reference: mycelium_refactor_plan_apr_round5.md §5.1.2, lines 485-492
"""

from __future__ import annotations

from typing import Any

from mycelium.models import ErrorObject, OutputEnvelope, WarningObject, make_envelope


def apply_strict_mode(
    command: str,
    *,
    strict: bool,
    validation_errors: list[str],
    data: dict[str, Any] | None = None,
    read_only: bool = False,
    trace: dict[str, Any] | None = None,
) -> OutputEnvelope:
    """Build an OutputEnvelope applying Strict Mode semantics to validation errors.

    Args:
        command: The invoked command name.
        strict: If True, validation errors become envelope errors (ok=false).
                If False and read_only, validation errors become warnings (ok=true).
        validation_errors: List of validation error strings (e.g., from
                          validate_shared_frontmatter).
        data: Command-specific result data.
        read_only: If True, the command does not write files. Non-strict mode
                   can downgrade errors to warnings for read-only commands.
        trace: Optional debug/diagnostics object.

    Returns:
        An OutputEnvelope. When strict=true and there are validation errors,
        ok=false. When strict=false and read_only, validation issues are
        reported as warnings with ok=true.
    """
    if not validation_errors:
        return make_envelope(command, data=data, trace=trace)

    if strict:
        # AC-IF-003-1 (strict=true path): validation errors → envelope errors
        errors = [
            ErrorObject(
                code="ERR_SCHEMA_VALIDATION",
                message=msg,
                retryable=False,
            )
            for msg in validation_errors
        ]
        return make_envelope(
            command,
            ok=False,
            data=data,
            errors=errors,
            trace=trace,
        )

    if read_only:
        # AC-IF-003-1 (strict=false, read-only path): downgrade to warnings
        warnings = [
            WarningObject(
                code="WARN_SCHEMA_VALIDATION",
                message=msg,
            )
            for msg in validation_errors
        ]
        return make_envelope(
            command,
            data=data,
            warnings=warnings,
            trace=trace,
        )

    # strict=false but write command: validation errors still produce errors
    errors = [
        ErrorObject(
            code="ERR_SCHEMA_VALIDATION",
            message=msg,
            retryable=False,
        )
        for msg in validation_errors
    ]
    return make_envelope(
        command,
        ok=False,
        data=data,
        errors=errors,
        trace=trace,
    )


def collect_strict_warnings(
    validation_errors: list[str],
    *,
    strict: bool,
    read_only: bool = False,
) -> list[dict[str, Any]]:
    """Collect warnings in Delta Report format for non-strict validation errors.

    When strict=false and the command is read-only, validation errors are
    downgraded to warnings. This function returns those warnings in the
    format expected by the Delta Report warnings array (AC-IF-003-2):
      {code: string, message: string}

    Args:
        validation_errors: Validation error strings.
        strict: The strict flag value.
        read_only: Whether the command is read-only.

    Returns:
        List of warning dicts suitable for the Delta Report warnings array.
        Empty if strict=true or no validation errors.
    """
    if strict or not validation_errors:
        return []

    if not read_only:
        return []

    return [
        {"code": "WARN_SCHEMA_VALIDATION", "message": msg}
        for msg in validation_errors
    ]
