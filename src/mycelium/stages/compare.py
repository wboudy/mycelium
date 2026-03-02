"""
Compare (Dedupe) stage — stage 5/7 of the ingestion pipeline (§6.1.1).

Input:  Extracted claims (from ExtractionBundle) + claim index/snapshot
Output: CompareResult with MatchRecords grouped by match class (SCH-006)
Side effects: Reads claim index snapshot; no Canonical Scope writes.
Errors: ERR_INDEX_UNAVAILABLE, ERR_SCHEMA_VALIDATION

Spec reference: mycelium_refactor_plan_apr_round5.md §6.1.1, §7.2 DED-002
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from mycelium.comparator import (
    CompareResult,
    MatchClass,
    MatchRecord,
    compare_claim,
    compare_claims,
)
from mycelium.models import (
    ErrorObject,
    OutputEnvelope,
    WarningObject,
    make_envelope,
)

STAGE_NAME = "compare"

# Error codes (§10.1)
ERR_INDEX_UNAVAILABLE = "ERR_INDEX_UNAVAILABLE"
ERR_SCHEMA_VALIDATION = "ERR_SCHEMA_VALIDATION"

# Warning codes
WARN_NO_EXISTING_CLAIMS = "WARN_NO_EXISTING_CLAIMS"

# Type alias for similarity functions
SimilarityFn = Callable[[str, str], float]


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ClaimIndex:
    """Snapshot of existing canonical claims for comparison.

    Each entry is a dict with at least ``"id"`` and ``"text"`` keys.
    """

    claims: list[dict[str, str]] = field(default_factory=list)

    @property
    def available(self) -> bool:
        """Whether the index has been loaded (even if empty)."""
        return True

    def __len__(self) -> int:
        return len(self.claims)


# ---------------------------------------------------------------------------
# Match record normalization for SCH-006
# ---------------------------------------------------------------------------

def _match_record_to_scm006(record: MatchRecord) -> dict[str, Any]:
    """Convert a MatchRecord to SCH-006 compliant dict.

    Ensures existing_claim_id is always present (null for NEW).
    """
    return {
        "extracted_claim_key": record.extracted_claim_key,
        "match_class": record.match_class.value,
        "similarity": record.similarity,
        "existing_claim_id": record.existing_claim_id,
    }


# ---------------------------------------------------------------------------
# Main compare function
# ---------------------------------------------------------------------------

def compare(
    extracted_claims: list[dict[str, Any]],
    claim_index: ClaimIndex | None = None,
    *,
    similarity_fn: SimilarityFn | None = None,
) -> tuple[CompareResult | None, OutputEnvelope]:
    """Execute the compare (dedupe) stage.

    Compares each extracted claim against existing canonical claims
    to classify them into match groups.

    AC-1: Each claim gets exactly one MatchRecord with match_class and similarity.
    AC-2: Total MatchRecords equals total extracted claims.
    AC-4: No writes to Canonical Scope.

    Args:
        extracted_claims: List of claim dicts from ExtractionBundle.
            Each must have at least a ``"claim_text"`` key.
        claim_index: Snapshot of existing canonical claims. If None,
            returns ERR_INDEX_UNAVAILABLE.
        similarity_fn: Optional custom similarity function for testing.

    Returns:
        Tuple of (compare_result_or_none, envelope).
    """
    if claim_index is None:
        return None, make_envelope(
            STAGE_NAME,
            errors=[ErrorObject(
                code=ERR_INDEX_UNAVAILABLE,
                message="Claim index snapshot is not available",
                retryable=True,
                stage=STAGE_NAME,
            )],
        )

    # Extract claim texts
    claim_texts: list[str] = []
    for i, claim in enumerate(extracted_claims):
        text = claim.get("claim_text", "")
        if not text or not text.strip():
            return None, make_envelope(
                STAGE_NAME,
                errors=[ErrorObject(
                    code=ERR_SCHEMA_VALIDATION,
                    message=f"Extracted claim [{i}] has empty claim_text",
                    retryable=False,
                    stage=STAGE_NAME,
                    details={"claim_index": i},
                )],
            )
        claim_texts.append(text)

    # Run comparison
    result = compare_claims(
        claim_texts,
        claim_index.claims,
        similarity_fn=similarity_fn,
    )

    # Build envelope data
    envelope_data: dict[str, Any] = {
        "total_extracted_claims": result.total,
    }
    # Add per-class counts
    for mc in MatchClass:
        key = mc.value.lower() + "_count"
        envelope_data[key] = len(result.match_groups.get(mc.value, []))

    # Add warnings
    envelope_warnings: list[WarningObject] = []
    if not claim_index.claims:
        envelope_warnings.append(WarningObject(
            code=WARN_NO_EXISTING_CLAIMS,
            message="No existing claims in index; all claims classified as NEW",
        ))

    return result, make_envelope(
        STAGE_NAME,
        data=envelope_data,
        warnings=envelope_warnings or None,
    )


def compare_result_to_match_groups(result: CompareResult) -> dict[str, list[dict[str, Any]]]:
    """Convert CompareResult to SCH-006 match_groups dict.

    Ensures all five group keys are present and each record has
    existing_claim_id (even as null).
    """
    groups: dict[str, list[dict[str, Any]]] = {}
    for mc in MatchClass:
        records = result.match_groups.get(mc.value, [])
        groups[mc.value] = [_match_record_to_scm006(r) for r in records]
    return groups
