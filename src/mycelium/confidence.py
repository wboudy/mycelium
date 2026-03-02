"""
Deterministic advisory confidence rubric (CONF-001).

Computes an advisory confidence score for extracted claims using a
weighted formula over four factors. The score guides review ordering
but is NOT a promotion decision.

Formula:
  confidence = clamp(0, 1,
    0.40*provenance_quality + 0.30*extract_consistency
    + 0.20*dedupe_support + 0.10*source_reliability)

MVP1 simplifications:
  - source_reliability is hardcoded to 0.5
  - provenance_quality and extract_consistency are binary (0.0 or 1.0)

Spec reference: §7.5 CONF-001
"""

from __future__ import annotations

from typing import Any


# ─── Weights ──────────────────────────────────────────────────────────────

W_PROVENANCE = 0.40
W_EXTRACT = 0.30
W_DEDUPE = 0.20
W_SOURCE = 0.10

# MVP1 constant
DEFAULT_SOURCE_RELIABILITY = 0.5

# Match class -> dedupe_support mapping
DEDUPE_SUPPORT_MAP: dict[str, float] = {
    "EXACT": 1.0,
    "NEAR_DUPLICATE": 0.8,
    "SUPPORTING": 0.6,
    "NEW": 0.4,
    "CONTRADICTING": 0.2,
}

# Threshold below which claims are routed to human review
HUMAN_REVIEW_THRESHOLD = 0.4


# ─── Factor computation ─────────────────────────────────────────────────

def clamp01(value: float) -> float:
    """Clamp a value to [0.0, 1.0]."""
    return max(0.0, min(1.0, value))


def compute_provenance_quality(provenance: dict[str, Any] | None) -> float:
    """Compute provenance_quality factor.

    1.0 if provenance meets structured minima (SCH-003):
      - source_id, source_ref, locator all present and non-empty
    0.0 otherwise.
    """
    if provenance is None:
        return 0.0
    if not isinstance(provenance, dict):
        return 0.0

    for key in ("source_id", "source_ref", "locator"):
        val = provenance.get(key)
        if val is None:
            return 0.0
        if isinstance(val, str) and not val.strip():
            return 0.0

    return 1.0


def compute_extract_consistency(extraction_valid: bool) -> float:
    """Compute extract_consistency factor.

    1.0 if extraction passes SCH-008 validation, 0.0 otherwise.
    """
    return 1.0 if extraction_valid else 0.0


def compute_dedupe_support(match_class: str | None) -> float:
    """Compute dedupe_support factor from match class.

    Returns the mapped value for known classes, 0.0 for unknown/None.
    """
    if match_class is None:
        return 0.0
    return DEDUPE_SUPPORT_MAP.get(match_class, 0.0)


def compute_source_reliability() -> float:
    """Compute source_reliability factor.

    MVP1: hardcoded to 0.5. MVP2 will make this configurable.
    """
    return DEFAULT_SOURCE_RELIABILITY


# ─── Main computation ───────────────────────────────────────────────────

def compute_confidence(
    provenance: dict[str, Any] | None,
    extraction_valid: bool,
    match_class: str | None,
    source_reliability: float | None = None,
) -> float:
    """Compute the advisory confidence score for a claim.

    AC-CONF-001-1: Deterministic — same inputs yield identical outputs.

    Args:
        provenance: The claim's provenance dict (SCH-003 structure).
        extraction_valid: Whether extraction passed SCH-008 validation.
        match_class: The claim's match class (EXACT, NEAR_DUPLICATE, etc).
        source_reliability: Override for source reliability. Defaults to 0.5.

    Returns:
        Confidence score in [0.0, 1.0].
    """
    pq = compute_provenance_quality(provenance)
    ec = compute_extract_consistency(extraction_valid)
    ds = compute_dedupe_support(match_class)
    sr = source_reliability if source_reliability is not None else compute_source_reliability()

    raw = (
        W_PROVENANCE * pq
        + W_EXTRACT * ec
        + W_DEDUPE * ds
        + W_SOURCE * sr
    )
    return clamp01(raw)


def needs_human_review(confidence: float) -> bool:
    """Determine if a claim needs human review based on confidence.

    AC-CONF-001-2: Claims with confidence <= 0.4 are routed to human review.
    """
    return confidence <= HUMAN_REVIEW_THRESHOLD
