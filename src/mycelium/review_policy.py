"""
Review policy configuration (§8.1.1, §8.3.1).

Loads and validates Config/review_policy.yaml which governs:
- Hold TTL (hold_ttl_days): how many days a hold decision persists (default 14)
- Git Mode (git_mode.enabled): whether graduate --from_digest uses
  per-packet commit granularity (default false)

In Strict Mode, invalid config values produce ERR_SCHEMA_VALIDATION errors.
In non-Strict Mode, invalid values produce warnings and fall back to defaults.

Spec reference: mycelium_refactor_plan_apr_round5.md §8.1.1, §8.3.1
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml

from mycelium.models import ErrorObject, OutputEnvelope, WarningObject, make_envelope


CONFIG_RELATIVE_PATH = "Config/review_policy.yaml"

# Defaults per spec
DEFAULT_HOLD_TTL_DAYS = 14
DEFAULT_GIT_MODE_ENABLED = False


@dataclass
class ReviewPolicy:
    """Parsed review policy configuration."""

    hold_ttl_days: int = DEFAULT_HOLD_TTL_DAYS
    git_mode_enabled: bool = DEFAULT_GIT_MODE_ENABLED

    def hold_until(self, from_date: date | None = None) -> date:
        """Compute hold_until date from a starting date.

        Args:
            from_date: Starting date. Defaults to today.

        Returns:
            The date when the hold expires.
        """
        start = from_date or date.today()
        return start + timedelta(days=self.hold_ttl_days)

    def to_dict(self) -> dict[str, Any]:
        return {
            "hold_ttl_days": self.hold_ttl_days,
            "git_mode": {"enabled": self.git_mode_enabled},
        }


def _validate_config(raw: dict[str, Any]) -> list[str]:
    """Validate raw config dict, returning a list of error messages."""
    errors: list[str] = []

    if "hold_ttl_days" in raw:
        val = raw["hold_ttl_days"]
        if not isinstance(val, int) or isinstance(val, bool):
            errors.append(
                f"hold_ttl_days must be an integer, got {type(val).__name__}: {val!r}"
            )
        elif val < 1:
            errors.append(f"hold_ttl_days must be >= 1, got {val}")

    if "git_mode" in raw:
        gm = raw["git_mode"]
        if not isinstance(gm, dict):
            errors.append(
                f"git_mode must be a mapping, got {type(gm).__name__}: {gm!r}"
            )
        elif "enabled" in gm:
            val = gm["enabled"]
            if not isinstance(val, bool):
                errors.append(
                    f"git_mode.enabled must be a boolean, got {type(val).__name__}: {val!r}"
                )

    return errors


def load_review_policy(
    vault_root: Path,
    *,
    strict: bool = False,
) -> tuple[ReviewPolicy, OutputEnvelope]:
    """Load review policy from Config/review_policy.yaml.

    Args:
        vault_root: Absolute path to the vault root.
        strict: If True, validation errors produce ERR_SCHEMA_VALIDATION (ok=false).
                If False, validation errors produce warnings and defaults are used.

    Returns:
        Tuple of (ReviewPolicy, OutputEnvelope).
    """
    config_path = vault_root / CONFIG_RELATIVE_PATH

    # AC-1: absent config → defaults
    if not config_path.exists():
        policy = ReviewPolicy()
        return policy, make_envelope("load_review_policy", data=policy.to_dict())

    # Read and parse
    try:
        text = config_path.read_text(encoding="utf-8")
        raw = yaml.safe_load(text) or {}
    except (OSError, yaml.YAMLError) as e:
        if strict:
            return ReviewPolicy(), make_envelope(
                "load_review_policy",
                errors=[ErrorObject(
                    code="ERR_SCHEMA_VALIDATION",
                    message=f"Failed to read review_policy.yaml: {e}",
                    retryable=False,
                )],
            )
        return ReviewPolicy(), make_envelope(
            "load_review_policy",
            data=ReviewPolicy().to_dict(),
            warnings=[WarningObject(
                code="WARN_SCHEMA_VALIDATION",
                message=f"Failed to read review_policy.yaml: {e}",
            )],
        )

    if not isinstance(raw, dict):
        msg = f"review_policy.yaml must be a YAML mapping, got {type(raw).__name__}"
        if strict:
            return ReviewPolicy(), make_envelope(
                "load_review_policy",
                errors=[ErrorObject(
                    code="ERR_SCHEMA_VALIDATION",
                    message=msg,
                    retryable=False,
                )],
            )
        return ReviewPolicy(), make_envelope(
            "load_review_policy",
            data=ReviewPolicy().to_dict(),
            warnings=[WarningObject(code="WARN_SCHEMA_VALIDATION", message=msg)],
        )

    # Validate
    validation_errors = _validate_config(raw)
    if validation_errors:
        if strict:
            # AC-4: Strict Mode → ERR_SCHEMA_VALIDATION
            return ReviewPolicy(), make_envelope(
                "load_review_policy",
                errors=[
                    ErrorObject(
                        code="ERR_SCHEMA_VALIDATION",
                        message=msg,
                        retryable=False,
                    )
                    for msg in validation_errors
                ],
            )
        # AC-5: non-Strict → warnings, use defaults
        return ReviewPolicy(), make_envelope(
            "load_review_policy",
            data=ReviewPolicy().to_dict(),
            warnings=[
                WarningObject(code="WARN_SCHEMA_VALIDATION", message=msg)
                for msg in validation_errors
            ],
        )

    # Build policy from valid config
    hold_ttl = raw.get("hold_ttl_days", DEFAULT_HOLD_TTL_DAYS)
    git_mode = raw.get("git_mode", {})
    git_enabled = git_mode.get("enabled", DEFAULT_GIT_MODE_ENABLED) if isinstance(git_mode, dict) else DEFAULT_GIT_MODE_ENABLED

    policy = ReviewPolicy(
        hold_ttl_days=hold_ttl,
        git_mode_enabled=git_enabled,
    )

    return policy, make_envelope("load_review_policy", data=policy.to_dict())


def save_review_policy(vault_root: Path, policy: ReviewPolicy) -> None:
    """Write review policy to Config/review_policy.yaml.

    Args:
        vault_root: Absolute path to the vault root.
        policy: The policy to persist.
    """
    config_path = vault_root / CONFIG_RELATIVE_PATH
    config_path.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(
            policy.to_dict(),
            f,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )
