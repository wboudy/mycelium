"""
Triage scoring with deterministic formula, buckets, and hysteresis.

Implements the MVP3 triage/skip policy using Option C (governed
deterministic lifecycle with hysteresis).

Spec reference: §12.4 TODO-Q-MVP3-1
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

# ─── Constants ────────────────────────────────────────────────────────────

W_CONFLICT = 0.45
W_SUPPORT_GAP = 0.25
W_NOVELTY = 0.20
W_STALENESS = 0.10

THRESHOLD_DENSE = 0.67
THRESHOLD_MIXED_LOW = 0.34

# Hysteresis thresholds
HYSTERESIS_DENSE_EXIT = 0.62
HYSTERESIS_WATERY_ENTRY = 0.42
HYSTERESIS_DENSE_CONSECUTIVE = 2


# ─── Types ────────────────────────────────────────────────────────────────

class TriageBucket(str, Enum):
    """Triage bucket classification."""
    DENSE = "dense"
    MIXED = "mixed"
    WATERY = "watery"


@dataclass
class TriageResult:
    """Result of a triage evaluation."""
    score: float
    bucket: TriageBucket

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "bucket": self.bucket.value,
        }


@dataclass
class TriageState:
    """Mutable triage state for hysteresis tracking."""
    current_bucket: TriageBucket
    consecutive_below_dense_exit: int = 0

    def to_dict(self) -> dict:
        return {
            "current_bucket": self.current_bucket.value,
            "consecutive_below_dense_exit": self.consecutive_below_dense_exit,
        }


# ─── Core functions ──────────────────────────────────────────────────────

def clamp01(value: float) -> float:
    """Clamp a value to [0.0, 1.0]."""
    return max(0.0, min(1.0, value))


def compute_triage_score(
    conflict_factor: float,
    support_gap: float,
    novelty: float,
    staleness: float,
) -> float:
    """Compute the triage score using the deterministic formula.

    Formula: clamp01(0.45*conflict_factor + 0.25*support_gap
                      + 0.20*novelty + 0.10*staleness)
    """
    raw = (
        W_CONFLICT * conflict_factor
        + W_SUPPORT_GAP * support_gap
        + W_NOVELTY * novelty
        + W_STALENESS * staleness
    )
    return clamp01(raw)


def classify_bucket(score: float) -> TriageBucket:
    """Classify a triage score into a bucket.

    - dense:  score >= 0.67
    - mixed:  0.34 <= score < 0.67
    - watery: score < 0.34
    """
    if score >= THRESHOLD_DENSE:
        return TriageBucket.DENSE
    elif score >= THRESHOLD_MIXED_LOW:
        return TriageBucket.MIXED
    else:
        return TriageBucket.WATERY


def evaluate_triage(
    conflict_factor: float,
    support_gap: float,
    novelty: float,
    staleness: float,
) -> TriageResult:
    """Evaluate triage: compute score and classify bucket."""
    score = compute_triage_score(conflict_factor, support_gap, novelty, staleness)
    bucket = classify_bucket(score)
    return TriageResult(score=score, bucket=bucket)


def apply_hysteresis(
    state: TriageState,
    new_score: float,
) -> TriageBucket:
    """Apply hysteresis rules to determine the effective bucket.

    Rules:
    - dense -> mixed: only after 2 consecutive evaluations with score < 0.62
    - watery -> mixed: on first evaluation with score >= 0.42

    Args:
        state: Current triage state (mutated in place).
        new_score: The newly computed triage score.

    Returns:
        The effective bucket after hysteresis.
    """
    raw_bucket = classify_bucket(new_score)

    if state.current_bucket == TriageBucket.DENSE:
        if new_score < HYSTERESIS_DENSE_EXIT:
            state.consecutive_below_dense_exit += 1
            if state.consecutive_below_dense_exit >= HYSTERESIS_DENSE_CONSECUTIVE:
                state.current_bucket = raw_bucket
                state.consecutive_below_dense_exit = 0
            # else: stay dense (hysteresis holds)
        else:
            # Score >= exit threshold: reset counter, stay DENSE.
            # Hysteresis rule: only exit DENSE after 2 consecutive below 0.62.
            state.consecutive_below_dense_exit = 0

    elif state.current_bucket == TriageBucket.WATERY:
        if new_score >= HYSTERESIS_WATERY_ENTRY:
            state.current_bucket = TriageBucket.MIXED
            state.consecutive_below_dense_exit = 0
        else:
            state.current_bucket = raw_bucket
            state.consecutive_below_dense_exit = 0

    else:
        # MIXED: no hysteresis, follow raw bucket
        state.current_bucket = raw_bucket
        state.consecutive_below_dense_exit = 0

    return state.current_bucket
