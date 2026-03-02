"""
Source reliability configuration for MVP2 (CONF-001 resolution).

Loads Config/source_reliability.yaml which maps domain/publisher keys
to numeric reliability values in [0..1]. Used by the confidence rubric
to replace the hardcoded 0.5 constant from MVP1.

Spec reference: §7.5 TODO-Q-CONF-1 resolution
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from mycelium.models import ErrorObject, OutputEnvelope, WarningObject, make_envelope


CONFIG_RELATIVE_PATH = "Config/source_reliability.yaml"
DEFAULT_RELIABILITY = 0.5


# ─── Validation ───────────────────────────────────────────────────────────

def _validate_config(raw: dict[str, Any]) -> tuple[dict[str, float], list[str]]:
    """Validate raw config, returning (valid_entries, errors).

    Schema: map of domain/publisher key -> numeric reliability in [0..1],
    plus optional "default" key.
    """
    entries: dict[str, float] = {}
    errors: list[str] = []

    for key, val in raw.items():
        if not isinstance(key, str):
            errors.append(f"Key must be a string, got {type(key).__name__}: {key!r}")
            continue

        if not isinstance(val, (int, float)) or isinstance(val, bool):
            errors.append(
                f"Value for {key!r} must be a number, "
                f"got {type(val).__name__}: {val!r}"
            )
            continue

        if val < 0.0 or val > 1.0:
            errors.append(
                f"Value for {key!r} must be in [0..1], got {val}"
            )
            continue

        entries[key] = float(val)

    return entries, errors


def _clamp01(val: float) -> float:
    return max(0.0, min(1.0, val))


# ─── Lookup ──────────────────────────────────────────────────────────────

def _parent_domain(domain: str) -> str | None:
    """Extract parent domain from a subdomain.

    e.g. "blog.example.com" -> "example.com"
         "example.com" -> None
    """
    parts = domain.split(".")
    if len(parts) <= 2:
        return None
    return ".".join(parts[1:])


def lookup_reliability(
    entries: dict[str, float],
    key: str,
) -> float:
    """Look up reliability for a domain/publisher key.

    Lookup order:
    1. Exact key match
    2. Parent-domain fallback (iterative)
    3. "default" key
    4. DEFAULT_RELIABILITY constant (0.5)
    """
    # Exact match
    if key in entries:
        return entries[key]

    # Parent-domain fallback
    current = key
    while True:
        parent = _parent_domain(current)
        if parent is None:
            break
        if parent in entries:
            return entries[parent]
        current = parent

    # Default key
    if "default" in entries:
        return entries["default"]

    return DEFAULT_RELIABILITY


# ─── Loading ─────────────────────────────────────────────────────────────

def load_source_reliability(
    vault_root: Path,
    *,
    strict: bool = False,
) -> tuple[dict[str, float], OutputEnvelope]:
    """Load source reliability config from Config/source_reliability.yaml.

    Args:
        vault_root: Absolute path to the vault root.
        strict: If True, validation errors produce ERR_SCHEMA_VALIDATION.
                If False, validation errors produce warnings and invalid
                entries are skipped.

    Returns:
        Tuple of (entries dict, OutputEnvelope).
    """
    config_path = vault_root / CONFIG_RELATIVE_PATH

    # AC-4: absent config → default 0.5
    if not config_path.exists():
        return {}, make_envelope(
            "load_source_reliability",
            data={"entries": {}, "default": DEFAULT_RELIABILITY},
        )

    # Read and parse
    try:
        text = config_path.read_text(encoding="utf-8")
        raw = yaml.safe_load(text) or {}
    except (OSError, yaml.YAMLError) as e:
        msg = f"Failed to read source_reliability.yaml: {e}"
        if strict:
            return {}, make_envelope(
                "load_source_reliability",
                errors=[ErrorObject(
                    code="ERR_SCHEMA_VALIDATION",
                    message=msg,
                    retryable=False,
                )],
            )
        return {}, make_envelope(
            "load_source_reliability",
            data={"entries": {}, "default": DEFAULT_RELIABILITY},
            warnings=[WarningObject(code="WARN_SCHEMA_VALIDATION", message=msg)],
        )

    if not isinstance(raw, dict):
        msg = f"source_reliability.yaml must be a YAML mapping, got {type(raw).__name__}"
        if strict:
            return {}, make_envelope(
                "load_source_reliability",
                errors=[ErrorObject(
                    code="ERR_SCHEMA_VALIDATION",
                    message=msg,
                    retryable=False,
                )],
            )
        return {}, make_envelope(
            "load_source_reliability",
            data={"entries": {}, "default": DEFAULT_RELIABILITY},
            warnings=[WarningObject(code="WARN_SCHEMA_VALIDATION", message=msg)],
        )

    # Validate
    entries, validation_errors = _validate_config(raw)

    if validation_errors:
        if strict:
            # AC-5: Strict Mode → ERR_SCHEMA_VALIDATION
            return {}, make_envelope(
                "load_source_reliability",
                errors=[
                    ErrorObject(
                        code="ERR_SCHEMA_VALIDATION",
                        message=msg,
                        retryable=False,
                    )
                    for msg in validation_errors
                ],
            )
        # AC-6: non-Strict → warnings, skip invalid entries
        return entries, make_envelope(
            "load_source_reliability",
            data={"entries": entries, "default": entries.get("default", DEFAULT_RELIABILITY)},
            warnings=[
                WarningObject(code="WARN_SCHEMA_VALIDATION", message=msg)
                for msg in validation_errors
            ],
        )

    return entries, make_envelope(
        "load_source_reliability",
        data={"entries": entries, "default": entries.get("default", DEFAULT_RELIABILITY)},
    )
