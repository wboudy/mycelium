"""
Delta Report schema validation and persistence (SCH-006).

Each Ingestion Job persists exactly one Delta Report per Run ID as YAML
under ``Reports/Delta/``. This module provides:

- Schema validation (``validate_delta_report``)
- Builder/factory (``build_delta_report``)
- Persistence (``save_delta_report``, ``load_delta_report``)

Spec reference: §4.2.6 SCH-006
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from mycelium.schema import SchemaValidationError, _parse_iso8601_utc

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums and constants
# ---------------------------------------------------------------------------

VALID_PIPELINE_STATUSES = frozenset({
    "completed",
    "failed_after_extraction",
    "failed_before_extraction",
})

MATCH_CLASS_KEYS = ("EXACT", "NEAR_DUPLICATE", "SUPPORTING", "CONTRADICTING", "NEW")

REQUIRED_TOP_KEYS = frozenset({
    "run_id", "source_id", "created_at", "source_revision",
    "pipeline_status", "counts", "novelty_score", "match_groups",
    "conflicts", "warnings", "failures", "new_links", "follow_up_questions",
})

REQUIRED_REVISION_KEYS = frozenset({
    "normalized_locator", "fingerprint", "prior_fingerprint",
})

REQUIRED_COUNTS_KEYS = frozenset({
    "total_extracted_claims", "exact_count", "near_duplicate_count",
    "supporting_count", "contradicting_count", "new_count",
})

REQUIRED_MATCH_RECORD_KEYS = frozenset({
    "extracted_claim_key", "match_class", "similarity", "existing_claim_id",
})

REQUIRED_CONFLICT_RECORD_KEYS = frozenset({
    "new_extracted_claim_key", "existing_claim_id", "evidence",
})


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_delta_report(report: dict[str, Any]) -> list[str]:
    """Validate a Delta Report dict against SCH-006.

    Returns a list of error strings (empty means valid).

    Checks:
    - AC-SCH-006-2: All required top-level keys present, empty arrays explicit.
    - AC-SCH-006-3: novelty_score in [0..1].
    - AC-SCH-006-4: Match Record required keys; match_class == group key.
    - AC-SCH-006-5: pipeline_status is valid enum.
    """
    errors: list[str] = []

    # AC-SCH-006-2: Required top-level keys
    missing_top = REQUIRED_TOP_KEYS - set(report.keys())
    if missing_top:
        errors.append(f"Missing required top-level keys: {sorted(missing_top)}")

    # pipeline_status enum (AC-SCH-006-5)
    if "pipeline_status" in report:
        ps = report["pipeline_status"]
        if ps not in VALID_PIPELINE_STATUSES:
            errors.append(
                f"Invalid pipeline_status: {ps!r} "
                f"(expected one of {sorted(VALID_PIPELINE_STATUSES)})"
            )

    # created_at must be ISO-8601
    if "created_at" in report:
        try:
            _parse_iso8601_utc(report["created_at"])
        except (ValueError, TypeError) as exc:
            errors.append(f"Invalid created_at datetime: {exc}")

    # AC-SCH-006-3: novelty_score in [0..1]
    if "novelty_score" in report:
        ns = report["novelty_score"]
        if not isinstance(ns, (int, float)):
            errors.append(f"novelty_score must be a number, got {type(ns).__name__}")
        elif not (0.0 <= ns <= 1.0):
            errors.append(f"novelty_score must be in [0..1], got {ns}")

    # source_revision required keys
    if "source_revision" in report:
        rev = report["source_revision"]
        if isinstance(rev, dict):
            missing_rev = REQUIRED_REVISION_KEYS - set(rev.keys())
            if missing_rev:
                errors.append(f"source_revision missing keys: {sorted(missing_rev)}")
        else:
            errors.append("source_revision must be a dict")

    # counts required keys
    if "counts" in report:
        counts = report["counts"]
        if isinstance(counts, dict):
            missing_counts = REQUIRED_COUNTS_KEYS - set(counts.keys())
            if missing_counts:
                errors.append(f"counts missing keys: {sorted(missing_counts)}")
        else:
            errors.append("counts must be a dict")

    # match_groups: all 5 class keys present, each an array
    if "match_groups" in report:
        mg = report["match_groups"]
        if isinstance(mg, dict):
            for cls in MATCH_CLASS_KEYS:
                if cls not in mg:
                    errors.append(f"match_groups missing key: {cls}")
                elif not isinstance(mg[cls], list):
                    errors.append(f"match_groups.{cls} must be an array")
                else:
                    # AC-SCH-006-4: Each record has required keys
                    for i, record in enumerate(mg[cls]):
                        if not isinstance(record, dict):
                            errors.append(f"match_groups.{cls}[{i}] must be a dict")
                            continue
                        missing_mr = REQUIRED_MATCH_RECORD_KEYS - set(record.keys())
                        if missing_mr:
                            errors.append(
                                f"match_groups.{cls}[{i}] missing keys: {sorted(missing_mr)}"
                            )
                        # match_class must equal group key
                        if "match_class" in record and record["match_class"] != cls:
                            errors.append(
                                f"match_groups.{cls}[{i}].match_class is "
                                f"{record['match_class']!r}, expected {cls!r}"
                            )
                        # similarity in [0..1]
                        if "similarity" in record:
                            sim = record["similarity"]
                            if isinstance(sim, (int, float)) and not (0.0 <= sim <= 1.0):
                                errors.append(
                                    f"match_groups.{cls}[{i}].similarity "
                                    f"must be in [0..1], got {sim}"
                                )
        else:
            errors.append("match_groups must be a dict")

    # Array fields must be lists (AC-SCH-006-2: explicit empty arrays)
    for array_key in ("conflicts", "warnings", "failures", "new_links", "follow_up_questions"):
        if array_key in report and not isinstance(report[array_key], list):
            errors.append(f"{array_key} must be an array")

    # Validate conflict records
    if "conflicts" in report and isinstance(report.get("conflicts"), list):
        for i, conflict in enumerate(report["conflicts"]):
            if not isinstance(conflict, dict):
                errors.append(f"conflicts[{i}] must be a dict")
                continue
            missing_cr = REQUIRED_CONFLICT_RECORD_KEYS - set(conflict.keys())
            if missing_cr:
                errors.append(f"conflicts[{i}] missing keys: {sorted(missing_cr)}")

    return errors


def validate_delta_report_strict(report: dict[str, Any]) -> None:
    """Validate and raise SchemaValidationError on failure."""
    errors = validate_delta_report(report)
    if errors:
        raise SchemaValidationError(errors)


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

def build_delta_report(
    *,
    run_id: str,
    source_id: str,
    normalized_locator: str,
    fingerprint: str,
    prior_fingerprint: str | None = None,
    pipeline_status: str = "completed",
    match_groups: dict[str, list[dict[str, Any]]] | None = None,
    conflicts: list[dict[str, Any]] | None = None,
    warnings: list[dict[str, Any]] | None = None,
    failures: list[dict[str, Any]] | None = None,
    new_links: list | None = None,
    follow_up_questions: list | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Build a spec-conformant Delta Report dict.

    Computes ``counts`` and ``novelty_score`` from the provided
    ``match_groups``. All array fields default to empty lists so
    keys are always explicitly present (AC-SCH-006-2).

    Args:
        run_id: Ingestion run ID.
        source_id: Source Note ID.
        normalized_locator: Source locator string.
        fingerprint: Current content fingerprint.
        prior_fingerprint: Previous fingerprint (None for first ingest).
        pipeline_status: Pipeline outcome status.
        match_groups: Dict of class → list[MatchRecord]. Defaults to all empty.
        conflicts: Conflict records.
        warnings: Warning records.
        failures: Failure records.
        new_links: New link proposals.
        follow_up_questions: Follow-up questions.
        created_at: Override timestamp (defaults to now UTC).

    Returns:
        A complete Delta Report dict conforming to SCH-006.
    """
    mg = match_groups or {cls: [] for cls in MATCH_CLASS_KEYS}
    # Ensure all class keys are present
    for cls in MATCH_CLASS_KEYS:
        mg.setdefault(cls, [])

    # Compute counts from match_groups
    exact_count = len(mg.get("EXACT", []))
    near_dup_count = len(mg.get("NEAR_DUPLICATE", []))
    supporting_count = len(mg.get("SUPPORTING", []))
    contradicting_count = len(mg.get("CONTRADICTING", []))
    new_count = len(mg.get("NEW", []))
    total = exact_count + near_dup_count + supporting_count + contradicting_count + new_count

    # Compute novelty_score per §7.4 DEL-002:
    # novelty_score = (new_count + contradicting_count) / max(1, total)
    novelty_score = (new_count + contradicting_count) / total if total > 0 else 0.0

    return {
        "run_id": run_id,
        "source_id": source_id,
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "source_revision": {
            "normalized_locator": normalized_locator,
            "fingerprint": fingerprint,
            "prior_fingerprint": prior_fingerprint,
        },
        "pipeline_status": pipeline_status,
        "counts": {
            "total_extracted_claims": total,
            "exact_count": exact_count,
            "near_duplicate_count": near_dup_count,
            "supporting_count": supporting_count,
            "contradicting_count": contradicting_count,
            "new_count": new_count,
        },
        "novelty_score": round(novelty_score, 4),
        "match_groups": mg,
        "conflicts": conflicts or [],
        "warnings": warnings or [],
        "failures": failures or [],
        "new_links": new_links or [],
        "follow_up_questions": follow_up_questions or [],
    }


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_delta_report(vault_root: Path, report: dict[str, Any]) -> Path:
    """Persist a Delta Report as YAML under ``Reports/Delta/``.

    The filename is ``delta-<run_id>.yaml``.

    Args:
        vault_root: Absolute path to the vault root.
        report: A validated Delta Report dict.

    Returns:
        Path to the written YAML file.

    Raises:
        SchemaValidationError: If the report fails validation.
    """
    validate_delta_report_strict(report)

    run_id = report["run_id"]
    delta_dir = vault_root / "Reports" / "Delta"
    delta_dir.mkdir(parents=True, exist_ok=True)

    from mycelium.atomic_write import atomic_write_text
    from mycelium.vault_layout import sanitize_path_component

    sanitize_path_component(run_id)
    file_path = delta_dir / f"delta-{run_id}.yaml"
    yaml_content = yaml.dump(report, default_flow_style=False, allow_unicode=True, sort_keys=False)
    atomic_write_text(file_path, yaml_content, mkdir=False)

    logger.info(f"Delta Report written: {file_path}")
    return file_path


def load_delta_report(file_path: Path) -> dict[str, Any]:
    """Load and validate a Delta Report from YAML.

    Args:
        file_path: Path to the Delta Report YAML file.

    Returns:
        Parsed and validated Delta Report dict.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        SchemaValidationError: If validation fails.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Delta Report not found: {file_path}")

    with open(file_path) as f:
        report = yaml.safe_load(f)

    validate_delta_report_strict(report)
    return report
