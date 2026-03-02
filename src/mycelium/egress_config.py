"""
Egress policy configuration (§9.2 TODO-Q-SEC-1 resolution, SEC-003).

Manages ``Config/egress_policy.yaml`` which tracks the egress mode
(``report_only`` or ``enforce``), burn-in timing, and transition metadata.

Key behaviours:
  - Missing config file defaults to ``report_only`` mode.
  - Burn-in elapsed days computed at evaluation time (no scheduler).
  - Mode transitions are explicit only; 14-day burn-in does NOT auto-flip.
  - Transitions emit an audit event per SEC-003 (AC-SEC-003-3).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from mycelium.audit import EventType, emit_event


# ── Constants ─────────────────────────────────────────────────────────

EGRESS_MODES = frozenset({"report_only", "enforce"})
DEFAULT_MODE = "report_only"
CONFIG_RELATIVE_PATH = "Config/egress_policy.yaml"


# ── Data model ────────────────────────────────────────────────────────

@dataclass
class EgressPolicyConfig:
    """Egress policy state persisted in Config/egress_policy.yaml.

    Attributes:
        mode: Current egress mode (``report_only`` or ``enforce``).
        burn_in_started_at: ISO-8601 UTC timestamp when burn-in began.
        last_transition_at: ISO-8601 UTC timestamp of the last mode transition,
            or ``None`` if no transition has occurred.
        transitioned_by: Actor who performed the last transition, or ``None``.
        transition_reason: Human-readable reason for the last transition,
            or ``None``.
    """

    mode: str = DEFAULT_MODE
    burn_in_started_at: str = ""
    last_transition_at: str | None = None
    transitioned_by: str | None = None
    transition_reason: str | None = None

    def __post_init__(self) -> None:
        if not self.burn_in_started_at:
            self.burn_in_started_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict suitable for YAML output."""
        return {
            "mode": self.mode,
            "burn_in_started_at": self.burn_in_started_at,
            "last_transition_at": self.last_transition_at,
            "transitioned_by": self.transitioned_by,
            "transition_reason": self.transition_reason,
        }

    def burn_in_elapsed_days(self, now: datetime | None = None) -> float:
        """Compute elapsed burn-in days from burn_in_started_at.

        Args:
            now: Reference time (defaults to ``datetime.now(UTC)``).

        Returns:
            Elapsed days as a float.
        """
        if now is None:
            now = datetime.now(timezone.utc)
        started = datetime.fromisoformat(
            self.burn_in_started_at.replace("Z", "+00:00")
        )
        return (now - started).total_seconds() / 86400.0


# ── Validation ────────────────────────────────────────────────────────

def validate_egress_policy_config(data: dict[str, Any]) -> list[str]:
    """Validate raw config dict against the egress policy schema.

    Returns a list of error strings (empty means valid).
    """
    errors: list[str] = []

    if "mode" not in data:
        errors.append("Missing required key: mode")
    elif data["mode"] not in EGRESS_MODES:
        errors.append(
            f"Invalid mode: {data['mode']!r} "
            f"(expected one of {sorted(EGRESS_MODES)})"
        )

    if "burn_in_started_at" not in data:
        errors.append("Missing required key: burn_in_started_at")
    else:
        try:
            _parse_iso(data["burn_in_started_at"])
        except (ValueError, TypeError) as exc:
            errors.append(f"Invalid burn_in_started_at: {exc}")

    # Optional datetime fields
    for key in ("last_transition_at",):
        if key in data and data[key] is not None:
            try:
                _parse_iso(data[key])
            except (ValueError, TypeError) as exc:
                errors.append(f"Invalid {key}: {exc}")

    return errors


def _parse_iso(value: Any) -> datetime:
    """Parse an ISO-8601 string, handling Z suffix."""
    if not isinstance(value, str):
        raise ValueError(f"Expected string, got {type(value).__name__}")
    normalized = value.replace("Z", "+00:00") if value.endswith("Z") else value
    return datetime.fromisoformat(normalized)


# ── I/O ───────────────────────────────────────────────────────────────

def _config_path(vault_root: Path) -> Path:
    """Return the absolute path to Config/egress_policy.yaml."""
    return vault_root / CONFIG_RELATIVE_PATH


def load_egress_policy(vault_root: Path) -> EgressPolicyConfig:
    """Load egress policy config, defaulting to report_only if missing.

    AC-1: Missing Config/egress_policy.yaml defaults to report_only mode.
    AC-2: Config with mode=enforce is loaded and respected.

    Returns:
        An EgressPolicyConfig instance.
    """
    path = _config_path(vault_root)
    if not path.exists():
        return EgressPolicyConfig()

    with open(path) as f:
        data = yaml.safe_load(f) or {}

    return EgressPolicyConfig(
        mode=data.get("mode", DEFAULT_MODE),
        burn_in_started_at=data.get("burn_in_started_at", ""),
        last_transition_at=data.get("last_transition_at"),
        transitioned_by=data.get("transitioned_by"),
        transition_reason=data.get("transition_reason"),
    )


def save_egress_policy(vault_root: Path, config: EgressPolicyConfig) -> Path:
    """Write egress policy config to Config/egress_policy.yaml.

    AC-5: Config round-trips (writing then reading produces identical values).

    Returns:
        The absolute path to the written file.
    """
    path = _config_path(vault_root)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w") as f:
        yaml.dump(
            config.to_dict(),
            f,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )

    return path


# ── Mode transitions (SEC-003) ────────────────────────────────────────

class EgressTransitionError(Exception):
    """Raised when an egress mode transition is invalid."""

    def __init__(self, message: str) -> None:
        self.code = "ERR_EGRESS_TRANSITION"
        super().__init__(message)


def transition_egress_mode(
    vault_root: Path,
    new_mode: str,
    *,
    actor: str,
    reason: str | None = None,
) -> EgressPolicyConfig:
    """Explicitly transition egress mode and emit audit event.

    AC-SEC-003-3: Mode transitions append an audit event including actor,
    timestamp, and reason.

    Args:
        vault_root: Absolute path to the vault root.
        new_mode: Target mode (``report_only`` or ``enforce``).
        actor: Who is performing the transition.
        reason: Why the transition is being made.

    Returns:
        The updated EgressPolicyConfig.

    Raises:
        EgressTransitionError: If new_mode is invalid or same as current.
    """
    if new_mode not in EGRESS_MODES:
        raise EgressTransitionError(
            f"Invalid target mode: {new_mode!r} "
            f"(expected one of {sorted(EGRESS_MODES)})"
        )

    config = load_egress_policy(vault_root)

    if config.mode == new_mode:
        raise EgressTransitionError(
            f"Already in mode {new_mode!r}; no transition needed"
        )

    old_mode = config.mode
    now = datetime.now(timezone.utc).isoformat()

    config.mode = new_mode
    config.last_transition_at = now
    config.transitioned_by = actor
    config.transition_reason = reason

    save_egress_policy(vault_root, config)

    # AC-SEC-003-3: emit audit event for the transition
    emit_event(
        vault_root,
        EventType.EGRESS_MODE_TRANSITION,
        actor=actor,
        details={
            "old_mode": old_mode,
            "new_mode": new_mode,
            "reason": reason,
        },
    )

    return config
