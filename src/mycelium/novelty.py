"""
Deterministic novelty scoring (DEL-002).

Computes novelty_score using only Delta Report counts.

Formula (§7.4):
    novelty_score = (new_count + contradicting_count) / max(1, total_extracted_claims)

Spec reference: mycelium_refactor_plan_apr_round5.md §7.4
"""

from __future__ import annotations


def compute_novelty_score(
    new_count: int,
    contradicting_count: int,
    total_extracted_claims: int,
) -> float:
    """Compute the deterministic novelty score from Delta Report counts.

    Args:
        new_count: Number of claims classified as NEW.
        contradicting_count: Number classified as CONTRADICTING.
        total_extracted_claims: Total extracted claims across all match groups.

    Returns:
        Float in [0..1]. Returns 0.0 when total_extracted_claims == 0.

    Raises:
        ValueError: If any count is negative.
    """
    if new_count < 0 or contradicting_count < 0 or total_extracted_claims < 0:
        raise ValueError("Counts must be non-negative")

    if total_extracted_claims == 0:
        return 0.0

    score = (new_count + contradicting_count) / max(1, total_extracted_claims)

    # Clamp to [0, 1] for safety (should not exceed 1 if counts are consistent)
    return min(1.0, score)
