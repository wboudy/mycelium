"""
Match class assignment comparator (DED-002).

Assigns exactly one Match Class to each extracted claim by comparing it
against existing canonical claims using similarity scores and fixed
threshold bands.

Spec reference: mycelium_refactor_plan_apr_round5.md §7.2
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any

from mycelium.canonicalize import canonicalize, extracted_claim_key


# ---------------------------------------------------------------------------
# Match classes
# ---------------------------------------------------------------------------

class MatchClass(enum.Enum):
    """One of five mutually exclusive match classes (DED-002)."""

    EXACT = "EXACT"
    NEAR_DUPLICATE = "NEAR_DUPLICATE"
    SUPPORTING = "SUPPORTING"
    CONTRADICTING = "CONTRADICTING"
    NEW = "NEW"


# ---------------------------------------------------------------------------
# Similarity thresholds (§7.3 decision record)
# ---------------------------------------------------------------------------

THRESHOLD_EXACT = 0.97
THRESHOLD_NEAR_DUPLICATE = 0.85
THRESHOLD_NEW = 0.70

# The band [0.70, 0.85) requires reviewer decision (DED-003 scope).
# For classification purposes, claims in that band are assigned
# SUPPORTING by default (the most conservative non-destructive class).


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class MatchRecord:
    """A single match result pairing an extracted claim with its classification.

    Spec: §7.2 DED-002
    - match_class: one of the five MatchClass values
    - similarity: float in [0..1]
    - extracted_claim_key: deterministic key for the new claim
    - existing_claim_id: ID of the best-matching existing claim (None if NEW)
    """

    match_class: MatchClass
    similarity: float
    extracted_claim_key: str
    existing_claim_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "match_class": self.match_class.value,
            "similarity": self.similarity,
            "extracted_claim_key": self.extracted_claim_key,
        }
        if self.existing_claim_id is not None:
            d["existing_claim_id"] = self.existing_claim_id
        return d


@dataclass
class CompareResult:
    """Result of comparing a batch of extracted claims against the canon.

    Groups match records by class for easy access. The total count across
    all groups must equal the input claim count (AC-DED-002-1).
    """

    match_groups: dict[str, list[MatchRecord]] = field(default_factory=lambda: {
        mc.value: [] for mc in MatchClass
    })

    @property
    def total(self) -> int:
        return sum(len(recs) for recs in self.match_groups.values())

    def add(self, record: MatchRecord) -> None:
        self.match_groups[record.match_class.value].append(record)

    def to_dict(self) -> dict[str, Any]:
        return {
            "match_groups": {
                k: [r.to_dict() for r in v]
                for k, v in self.match_groups.items()
            },
            "counts": {
                "total_extracted_claims": self.total,
                **{k: len(v) for k, v in self.match_groups.items()},
            },
        }


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def classify_similarity(similarity: float) -> MatchClass:
    """Assign a match class from a similarity score using fixed thresholds.

    Thresholds (§7.3):
        >= 0.97           → EXACT
        [0.85, 0.97)      → NEAR_DUPLICATE
        [0.70, 0.85)      → SUPPORTING (conservative default; reviewer may override)
        < 0.70            → NEW

    Note: CONTRADICTING is not assigned by threshold alone — it requires
    semantic analysis. Callers detecting contradiction should override
    the returned class.

    Args:
        similarity: Float in [0..1].

    Returns:
        The assigned MatchClass.

    Raises:
        ValueError: If similarity is outside [0, 1].
    """
    if not (0.0 <= similarity <= 1.0):
        raise ValueError(f"similarity must be in [0, 1], got {similarity}")

    if similarity >= THRESHOLD_EXACT:
        return MatchClass.EXACT
    if similarity >= THRESHOLD_NEAR_DUPLICATE:
        return MatchClass.NEAR_DUPLICATE
    if similarity >= THRESHOLD_NEW:
        return MatchClass.SUPPORTING
    return MatchClass.NEW


def compare_claim(
    claim_text: str,
    existing_claims: list[dict[str, str]],
    *,
    similarity_fn: _SimilarityFn | None = None,
) -> MatchRecord:
    """Compare a single extracted claim against existing canonical claims.

    Args:
        claim_text: The raw text of the extracted claim.
        existing_claims: List of dicts with at least ``"id"`` and ``"text"``
            keys representing existing canonical claims.
        similarity_fn: Optional custom similarity function. If None, uses
            the built-in canonical-form comparison. Signature:
            ``(canonical_new: str, canonical_existing: str) -> float``

    Returns:
        A MatchRecord with the assigned class, similarity, and key.
    """
    sim_fn = similarity_fn or _default_similarity
    key = extracted_claim_key(claim_text)
    canonical_new = canonicalize(claim_text)

    if not existing_claims:
        return MatchRecord(
            match_class=MatchClass.NEW,
            similarity=0.0,
            extracted_claim_key=key,
        )

    best_sim = 0.0
    best_id: str | None = None

    for existing in existing_claims:
        canonical_existing = canonicalize(existing["text"])
        sim = sim_fn(canonical_new, canonical_existing)
        # Guard against NaN / non-finite returns from custom similarity fns
        import math
        if not isinstance(sim, (int, float)) or math.isnan(sim) or math.isinf(sim):
            raise ValueError(
                f"similarity_fn returned {sim!r} for claim pair; "
                f"expected a finite float in [0, 1]"
            )
        if sim > best_sim:
            best_sim = sim
            best_id = existing["id"]

    match_class = classify_similarity(best_sim)

    return MatchRecord(
        match_class=match_class,
        similarity=best_sim,
        extracted_claim_key=key,
        existing_claim_id=best_id if match_class != MatchClass.NEW else None,
    )


def compare_claims(
    claims: list[str],
    existing_claims: list[dict[str, str]],
    *,
    similarity_fn: _SimilarityFn | None = None,
) -> CompareResult:
    """Compare a batch of extracted claims and produce grouped results.

    AC-DED-002-1: The total MatchRecords across all groups equals len(claims).

    Args:
        claims: Raw claim texts from extraction.
        existing_claims: Existing canonical claims (id + text).
        similarity_fn: Optional custom similarity function.

    Returns:
        CompareResult with records grouped by match class.
    """
    result = CompareResult()
    for claim_text in claims:
        record = compare_claim(claim_text, existing_claims, similarity_fn=similarity_fn)
        result.add(record)
    return result


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

from typing import Callable

_SimilarityFn = Callable[[str, str], float]


# ---------------------------------------------------------------------------
# Default similarity (character-level; production would use embeddings)
# ---------------------------------------------------------------------------

def _default_similarity(canonical_a: str, canonical_b: str) -> float:
    """Compute a simple character-level similarity ratio.

    Uses the Sørensen–Dice coefficient on character bigrams for a
    deterministic, embedding-free baseline. Production systems should
    replace this with a semantic similarity function.

    Returns:
        Float in [0..1].
    """
    if canonical_a == canonical_b:
        return 1.0
    if not canonical_a or not canonical_b:
        return 0.0

    bigrams_a = _char_bigrams(canonical_a)
    bigrams_b = _char_bigrams(canonical_b)

    if not bigrams_a or not bigrams_b:
        return 0.0

    # Intersection count: min of each shared bigram's count
    intersection_sum = sum(
        min(bigrams_a[bg], bigrams_b[bg])
        for bg in bigrams_a
        if bg in bigrams_b
    )
    return (2.0 * intersection_sum) / (
        sum(bigrams_a.values()) + sum(bigrams_b.values())
    )


def _char_bigrams(s: str) -> dict[str, int]:
    """Return a multiset of character bigrams."""
    counts: dict[str, int] = {}
    for i in range(len(s) - 1):
        bigram = s[i : i + 2]
        counts[bigram] = counts.get(bigram, 0) + 1
    return counts
