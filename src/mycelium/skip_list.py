"""
Skip-list lifecycle with entry criteria, safety cap, and auto-resurface.

Implements the MVP3 skip-list governed lifecycle (TODO-Q-MVP3-1).

Spec reference: §12.4
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any


# ─── Constants ────────────────────────────────────────────────────────────

CONSECUTIVE_WATERY_REQUIRED = 3
MIN_TARGET_AGE_DAYS = 14
DEFAULT_SKIP_DURATION_DAYS = 30
SAFETY_CAP_RATIO = 0.20


# ─── Models ──────────────────────────────────────────────────────────────

@dataclass
class TargetState:
    """State of a target for skip-list evaluation."""
    target_id: str
    consecutive_watery: int = 0
    conflict_factor: float = 0.0
    open_question_count: int = 0
    manually_pinned: bool = False
    target_age_days: int = 0
    skipped: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "consecutive_watery": self.consecutive_watery,
            "conflict_factor": self.conflict_factor,
            "open_question_count": self.open_question_count,
            "manually_pinned": self.manually_pinned,
            "target_age_days": self.target_age_days,
            "skipped": self.skipped,
        }


@dataclass
class SkipEntry:
    """Metadata for a skipped target."""
    target_id: str
    skip_since: str  # ISO date
    skip_reason: str
    next_review_at: str  # ISO date

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "skip_since": self.skip_since,
            "skip_reason": self.skip_reason,
            "next_review_at": self.next_review_at,
        }


# ─── Entry criteria ─────────────────────────────────────────────────────

@dataclass
class EntryCheck:
    """Result of checking skip-list entry criteria."""
    eligible: bool
    violations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "eligible": self.eligible,
            "violations": self.violations,
        }


def check_entry_criteria(target: TargetState) -> EntryCheck:
    """Check if a target meets all skip-list entry criteria.

    All 5 conditions must hold simultaneously:
    1. 3 consecutive watery evaluations
    2. conflict_factor == 0
    3. zero open-question references
    4. target not manually pinned
    5. target age >= 14 days
    """
    violations: list[str] = []

    if target.consecutive_watery < CONSECUTIVE_WATERY_REQUIRED:
        violations.append(
            f"consecutive_watery={target.consecutive_watery} "
            f"(need >= {CONSECUTIVE_WATERY_REQUIRED})"
        )

    if target.conflict_factor != 0.0:
        violations.append(
            f"conflict_factor={target.conflict_factor} (need == 0)"
        )

    if target.open_question_count > 0:
        violations.append(
            f"open_question_count={target.open_question_count} (need == 0)"
        )

    if target.manually_pinned:
        violations.append("target is manually pinned")

    if target.target_age_days < MIN_TARGET_AGE_DAYS:
        violations.append(
            f"target_age_days={target.target_age_days} "
            f"(need >= {MIN_TARGET_AGE_DAYS})"
        )

    return EntryCheck(
        eligible=len(violations) == 0,
        violations=violations,
    )


# ─── Skip-list management ───────────────────────────────────────────────

@dataclass
class SkipList:
    """Managed skip-list with safety cap enforcement."""
    entries: dict[str, SkipEntry] = field(default_factory=dict)

    def add(
        self,
        target: TargetState,
        skip_date: date,
        total_active_targets: int,
        reason: str = "auto",
    ) -> SkipEntry | str:
        """Add a target to the skip-list.

        Returns SkipEntry on success, error string on failure.
        """
        # Check entry criteria
        check = check_entry_criteria(target)
        if not check.eligible:
            return f"Entry criteria not met: {'; '.join(check.violations)}"

        # Safety cap check
        max_allowed = max(1, int(total_active_targets * SAFETY_CAP_RATIO))
        if len(self.entries) >= max_allowed:
            return (
                f"Safety cap exceeded: {len(self.entries)}/{max_allowed} "
                f"(20% of {total_active_targets} active targets)"
            )

        next_review = skip_date + timedelta(days=DEFAULT_SKIP_DURATION_DAYS)
        entry = SkipEntry(
            target_id=target.target_id,
            skip_since=skip_date.isoformat(),
            skip_reason=reason,
            next_review_at=next_review.isoformat(),
        )
        self.entries[target.target_id] = entry
        target.skipped = True
        return entry

    def remove(self, target_id: str, reason: str = "manual") -> bool:
        """Remove a target from the skip-list.

        Returns True if removed, False if not found.
        """
        if target_id in self.entries:
            del self.entries[target_id]
            return True
        return False

    def contains(self, target_id: str) -> bool:
        return target_id in self.entries

    def get(self, target_id: str) -> SkipEntry | None:
        return self.entries.get(target_id)

    def size(self) -> int:
        return len(self.entries)

    def to_list(self) -> list[dict[str, Any]]:
        return [e.to_dict() for e in self.entries.values()]


# ─── Removal triggers ───────────────────────────────────────────────────

def check_removal_triggers(
    skip_list: SkipList,
    target_id: str,
    *,
    has_new_conflict: bool = False,
    has_new_question: bool = False,
    manual_unskip: bool = False,
    current_date: date | None = None,
) -> str | None:
    """Check if a skipped target should be removed from the skip-list.

    Returns the removal reason if triggered, None if no removal needed.
    """
    entry = skip_list.get(target_id)
    if entry is None:
        return None

    if has_new_conflict:
        return "new_conflict_reference"

    if has_new_question:
        return "new_open_question_reference"

    if manual_unskip:
        return "manual_unskip"

    if current_date is not None:
        next_review = date.fromisoformat(entry.next_review_at)
        if current_date >= next_review:
            return "next_review_at_reached"

    return None


def process_removals(
    skip_list: SkipList,
    target_id: str,
    **kwargs: Any,
) -> str | None:
    """Check removal triggers and remove if needed.

    Returns the removal reason if removed, None otherwise.
    """
    reason = check_removal_triggers(skip_list, target_id, **kwargs)
    if reason is not None:
        skip_list.remove(target_id, reason=reason)
    return reason


# ─── Filtering ───────────────────────────────────────────────────────────

def filter_targets(
    targets: list[TargetState],
    skip_list: SkipList,
    include_skip: bool = False,
) -> list[TargetState]:
    """Filter targets based on skip-list membership.

    By default, skipped targets are excluded.
    With include_skip=True, all targets are returned.
    """
    if include_skip:
        return targets
    return [t for t in targets if not skip_list.contains(t.target_id)]
