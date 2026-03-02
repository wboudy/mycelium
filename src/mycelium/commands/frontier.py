"""
Frontier command scoring engine (CMD-FRN-001, CMD-FRN-002).

Surfaces conflicts, weak support, and open questions. Produces ranked
reading targets using a deterministic weighted scoring formula.

Spec reference: §5.2.7 CMD-FRN-001, CMD-FRN-002
Council decision: Option B (hardened deterministic factors)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from mycelium.models import (
    ErrorObject,
    OutputEnvelope,
    error_envelope,
    make_envelope,
)


# ─── Constants ────────────────────────────────────────────────────────────

# Scoring weights per CMD-FRN-002
W_CONFLICT = 0.35
W_SUPPORT_GAP = 0.25
W_GOAL_RELEVANCE = 0.20
W_NOVELTY = 0.10
W_STALENESS = 0.10

# Factor derivation parameters
SUPPORT_DENOMINATOR = 3.0        # support_gap: 1 - support/3
STALENESS_HORIZON_DAYS = 45.0    # staleness normalization window
NOVELTY_LOOKBACK_DAYS = 30       # novelty aggregation window
NEUTRAL_RELEVANCE = 0.5          # default when no project/tags

# Error codes
ERR_NO_FRONTIER_DATA = "ERR_NO_FRONTIER_DATA"


# ─── Utility ──────────────────────────────────────────────────────────────

def clamp01(x: float) -> float:
    """Clamp a value to [0, 1]."""
    return max(0.0, min(1.0, x))


def p75(values: list[float]) -> float:
    """Deterministic nearest-rank 75th percentile.

    Per spec: if values is empty, return 0.0.
    Uses nearest-rank method: index = ceil(0.75 * n) - 1.
    """
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    rank = math.ceil(0.75 * n) - 1
    return sorted_vals[max(0, rank)]


# ─── Factor derivations (Option B) ───────────────────────────────────────

@dataclass
class TargetData:
    """Input data for a single frontier target.

    This is the data contract that vault queries must populate.
    """
    target_id: str
    contradict_count: int = 0
    support_count: int = 0
    project: str | None = None
    tags: list[str] = field(default_factory=list)
    linked_delta_novelty_scores: list[float] = field(default_factory=list)
    last_reviewed_at: datetime | None = None
    updated: datetime | None = None

    def review_ts(self) -> datetime | None:
        """review_ts(T) = last_reviewed_at when present, else updated."""
        return self.last_reviewed_at or self.updated


@dataclass
class ScoringFactors:
    """The five scoring factors for a frontier target.

    AC-CMD-FRN-002-2: Each reading target includes factors with all five
    components, values in [0..1].
    """
    conflict_factor: float
    support_gap: float
    goal_relevance: float
    novelty: float
    staleness: float

    def to_dict(self) -> dict[str, float]:
        return {
            "conflict_factor": round(self.conflict_factor, 6),
            "support_gap": round(self.support_gap, 6),
            "goal_relevance": round(self.goal_relevance, 6),
            "novelty": round(self.novelty, 6),
            "staleness": round(self.staleness, 6),
        }


def compute_conflict_factor(target: TargetData) -> float:
    """conflict_factor(T) = clamp01(contradict / max(1, contradict + support))"""
    denom = max(1, target.contradict_count + target.support_count)
    return clamp01(target.contradict_count / denom)


def compute_support_gap(target: TargetData) -> float:
    """support_gap(T) = 1.0 - clamp01(support / 3.0)"""
    return 1.0 - clamp01(target.support_count / SUPPORT_DENOMINATOR)


def compute_goal_relevance(
    target: TargetData,
    input_project: str | None,
    input_tags: list[str] | None,
) -> float:
    """Goal relevance per spec derivations.

    If both project and tags inputs are omitted: 0.5.
    Otherwise: clamp01(0.6*project_match + 0.4*tag_overlap).
    """
    if input_project is None and (input_tags is None or len(input_tags) == 0):
        return NEUTRAL_RELEVANCE

    # project_match
    if input_project is None:
        project_match = 0.5
    elif target.project is None:
        project_match = 0.5
    elif target.project == input_project:
        project_match = 1.0
    else:
        project_match = 0.0

    # tag_overlap
    if input_tags is None or len(input_tags) == 0:
        tag_overlap = 0.5
    else:
        target_tags = set(target.tags)
        input_tag_set = set(input_tags)
        overlap = len(target_tags & input_tag_set)
        tag_overlap = overlap / max(1, len(input_tag_set))

    return clamp01(0.6 * project_match + 0.4 * tag_overlap)


def compute_novelty(target: TargetData) -> float:
    """novelty(T) = clamp01(p75(linked_delta_novelty_30d(T)))

    Note: The 30-day filtering is done at query time. The scores passed
    here should already be filtered to the lookback window.
    """
    return clamp01(p75(target.linked_delta_novelty_scores))


def compute_staleness(target: TargetData, ref_ts: datetime) -> float:
    """staleness(T) = clamp01(days_between(ref_ts, review_ts(T)) / 45.0)"""
    review = target.review_ts()
    if review is None:
        return 1.0  # Never reviewed = maximally stale
    delta = ref_ts - review
    days = max(0.0, delta.total_seconds() / 86400.0)
    return clamp01(days / STALENESS_HORIZON_DAYS)


def compute_factors(
    target: TargetData,
    ref_ts: datetime,
    input_project: str | None = None,
    input_tags: list[str] | None = None,
) -> ScoringFactors:
    """Compute all five scoring factors for a target."""
    return ScoringFactors(
        conflict_factor=compute_conflict_factor(target),
        support_gap=compute_support_gap(target),
        goal_relevance=compute_goal_relevance(target, input_project, input_tags),
        novelty=compute_novelty(target),
        staleness=compute_staleness(target, ref_ts),
    )


def compute_score(factors: ScoringFactors) -> float:
    """Compute frontier score from factors.

    score = 100 * (0.35*cf + 0.25*sg + 0.20*gr + 0.10*n + 0.10*s)
    Clamped to [0..100].
    """
    raw = (
        W_CONFLICT * factors.conflict_factor
        + W_SUPPORT_GAP * factors.support_gap
        + W_GOAL_RELEVANCE * factors.goal_relevance
        + W_NOVELTY * factors.novelty
        + W_STALENESS * factors.staleness
    )
    return max(0.0, min(100.0, round(100.0 * raw, 6)))


# ─── Reading target ──────────────────────────────────────────────────────

@dataclass
class ReadingTarget:
    """A ranked reading target in the frontier output."""
    target_id: str
    score: float
    factors: ScoringFactors
    rationale: str = ""
    citations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target_id,
            "score": round(self.score, 6),
            "rationale": self.rationale,
            "citations": self.citations,
            "factors": self.factors.to_dict(),
        }


# ─── Tie-breaking (AC-CMD-FRN-002-3) ─────────────────────────────────────

def sort_key(target: TargetData, rt: ReadingTarget) -> tuple:
    """Deterministic sort key: (-score, -conflict_factor, review_ts ASC, target_id ASC).

    Per spec: ties resolved by (higher conflict_factor, older last_reviewed_at,
    lexical target id).
    """
    review = target.review_ts()
    # For tie-breaking: older = smaller timestamp = sorts first ascending
    review_key = review.isoformat() if review else ""
    return (
        -rt.score,
        -rt.factors.conflict_factor,
        review_key,
        rt.target_id,
    )


def rank_targets(
    targets: list[TargetData],
    ref_ts: datetime,
    input_project: str | None = None,
    input_tags: list[str] | None = None,
    limit: int | None = None,
) -> list[ReadingTarget]:
    """Score, sort, and optionally limit frontier reading targets.

    AC-CMD-FRN-001-2: reading_targets sorted by numeric score.
    AC-CMD-FRN-002-1: Deterministic ordering for same inputs.
    AC-CMD-FRN-002-3: Tie-break per spec.
    """
    results: list[tuple[TargetData, ReadingTarget]] = []

    for td in targets:
        factors = compute_factors(td, ref_ts, input_project, input_tags)
        score = compute_score(factors)
        rt = ReadingTarget(
            target_id=td.target_id,
            score=score,
            factors=factors,
        )
        results.append((td, rt))

    # Deterministic sort
    results.sort(key=lambda pair: sort_key(pair[0], pair[1]))

    ranked = [rt for _, rt in results]
    if limit is not None:
        ranked = ranked[:limit]
    return ranked


# ─── Input validation ─────────────────────────────────────────────────────

@dataclass
class FrontierInput:
    """Validated input for the frontier command."""
    project: str | None = None
    tags: list[str] | None = None
    limit: int | None = None
    ref_ts: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def validate_frontier_input(raw: dict[str, Any]) -> FrontierInput | ErrorObject:
    """Validate raw input dict into FrontierInput."""
    limit = raw.get("limit")
    if limit is not None:
        if not isinstance(limit, int) or limit < 1:
            return ErrorObject(
                code=ERR_NO_FRONTIER_DATA,
                message="limit must be a positive integer",
                retryable=False,
            )

    tags = raw.get("tags")
    if tags is not None and not isinstance(tags, list):
        return ErrorObject(
            code=ERR_NO_FRONTIER_DATA,
            message="tags must be an array of strings",
            retryable=False,
        )

    return FrontierInput(
        project=raw.get("project"),
        tags=tags,
        limit=limit,
    )


def execute_frontier(raw_input: dict[str, Any]) -> OutputEnvelope:
    """Execute the frontier command contract.

    This implements the command contract and scoring engine. Actual vault
    queries to populate TargetData are wired in during integration.

    Args:
        raw_input: Raw command input dict.

    Returns:
        OutputEnvelope with frontier results.
    """
    result = validate_frontier_input(raw_input)
    if isinstance(result, ErrorObject):
        return make_envelope("frontier", errors=[result])

    return make_envelope(
        "frontier",
        data={
            "conflicts": [],
            "weak_support": [],
            "open_questions": [],
            "reading_targets": [],
            "explanations": {
                "formula": "score = 100 * (0.35*conflict_factor + 0.25*support_gap + 0.20*goal_relevance + 0.10*novelty + 0.10*staleness)",
                "weights": {
                    "conflict_factor": W_CONFLICT,
                    "support_gap": W_SUPPORT_GAP,
                    "goal_relevance": W_GOAL_RELEVANCE,
                    "novelty": W_NOVELTY,
                    "staleness": W_STALENESS,
                },
            },
        },
    )
