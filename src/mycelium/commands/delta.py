"""
Delta command contract (CMD-DEL-001).

Read-only command that surfaces delta report data including match groups
for all Match Classes with counts.

Spec reference: §5.2.2 CMD-DEL-001
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from mycelium.models import (
    ErrorObject,
    OutputEnvelope,
    make_envelope,
)


# ─── Error codes ──────────────────────────────────────────────────────────

ERR_SOURCE_NOT_FOUND = "ERR_SOURCE_NOT_FOUND"
ERR_DELTA_NOT_FOUND = "ERR_DELTA_NOT_FOUND"
ERR_SCHEMA_VALIDATION = "ERR_SCHEMA_VALIDATION"


# ─── Match Classes (§7) ──────────────────────────────────────────────────

class MatchClass(str, Enum):
    """Match classes per §7.1."""
    EXACT = "EXACT"
    NEAR_DUPLICATE = "NEAR_DUPLICATE"
    SUPPORTING = "SUPPORTING"
    CONTRADICTING = "CONTRADICTING"
    NEW = "NEW"


MATCH_CLASS_KEYS = [mc.value for mc in MatchClass]


# ─── Input model ─────────────────────────────────────────────────────────

@dataclass
class DeltaInput:
    """Validated input for the delta command."""
    source_id: str | None = None
    delta_report_path: str | None = None
    strict: bool = False


# ─── Validation ───────────────────────────────────────────────────────────

def validate_delta_input(raw: dict[str, Any]) -> DeltaInput | ErrorObject:
    """Validate raw input dict into DeltaInput."""
    source_id = raw.get("source_id")
    delta_report_path = raw.get("delta_report_path")

    modes = sum(1 for v in [source_id, delta_report_path] if v is not None)
    if modes == 0:
        return ErrorObject(
            code=ERR_SOURCE_NOT_FOUND,
            message="One of source_id or delta_report_path is required",
            retryable=False,
        )
    if modes > 1:
        return ErrorObject(
            code=ERR_SOURCE_NOT_FOUND,
            message="Provide exactly one of source_id or delta_report_path",
            retryable=False,
        )

    return DeltaInput(
        source_id=source_id,
        delta_report_path=delta_report_path,
        strict=bool(raw.get("strict", False)),
    )


def make_empty_match_groups() -> dict[str, list]:
    """Create match_groups with all required keys (AC-CMD-DEL-001-1)."""
    return {mc: [] for mc in MATCH_CLASS_KEYS}


def make_counts(match_groups: dict[str, list]) -> dict[str, int]:
    """Compute counts from match_groups.

    AC-CMD-DEL-001-2: total_extracted_claims equals sum of five class counts.
    """
    class_counts = {mc: len(items) for mc, items in match_groups.items()}
    total = sum(class_counts.values())
    return {
        **class_counts,
        "total_extracted_claims": total,
    }


def execute_delta(raw_input: dict[str, Any]) -> OutputEnvelope:
    """Execute the delta command contract.

    Read-only: loads and formats existing Delta Report data. Actual
    vault queries are wired in during integration.

    Args:
        raw_input: Raw command input dict.

    Returns:
        OutputEnvelope with delta results.
    """
    result = validate_delta_input(raw_input)
    if isinstance(result, ErrorObject):
        return make_envelope("delta", errors=[result])

    match_groups = make_empty_match_groups()
    counts = make_counts(match_groups)

    return make_envelope(
        "delta",
        data={
            "run_id": "",
            "source_id": result.source_id or "",
            "counts": counts,
            "match_groups": match_groups,
            "conflicts": [],
            "new_links": [],
            "follow_up_questions": [],
            "citations": [],
        },
    )
