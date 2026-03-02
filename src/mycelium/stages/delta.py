"""
Delta stage — stage 6/7 of the ingestion pipeline (§6.1.1).

Input:  MatchResults (CompareResult) + source metadata (or failure context)
Output: Delta Report (SCH-006 compliant)
Side effects: Writes one Delta Report under Reports/Delta/; appends audit metadata.
Errors: ERR_SCHEMA_VALIDATION

Spec reference: mycelium_refactor_plan_apr_round5.md §6.1.1, §6.5 DEL-001, §4.2.6 SCH-006
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mycelium.comparator import CompareResult, MatchClass
from mycelium.delta_report import (
    build_delta_report,
    save_delta_report,
    validate_delta_report,
)
from mycelium.models import (
    ErrorObject,
    OutputEnvelope,
    WarningObject,
    make_envelope,
)
from mycelium.stages.compare import compare_result_to_match_groups

STAGE_NAME = "delta"

# Error codes
ERR_SCHEMA_VALIDATION = "ERR_SCHEMA_VALIDATION"
ERR_DELTA_WRITE_FAILED = "ERR_DELTA_WRITE_FAILED"

# Pipeline status values (SCH-006)
STATUS_COMPLETED = "completed"
STATUS_FAILED_AFTER_EXTRACTION = "failed_after_extraction"
STATUS_FAILED_BEFORE_EXTRACTION = "failed_before_extraction"


# ---------------------------------------------------------------------------
# Main delta function
# ---------------------------------------------------------------------------

def delta(
    *,
    run_id: str,
    source_id: str,
    normalized_locator: str,
    fingerprint: str,
    compare_result: CompareResult | None = None,
    prior_fingerprint: str | None = None,
    pipeline_status: str | None = None,
    failures: list[dict[str, Any]] | None = None,
    vault_root: Path | None = None,
) -> tuple[dict[str, Any] | None, OutputEnvelope]:
    """Execute the delta stage — produce and persist a Delta Report.

    AC-1: Produces a SCH-006 compliant Delta Report.
    AC-2: All 5 match group keys present.
    AC-3: counts.total_extracted_claims == sum of match group sizes.
    AC-5: pipeline_status reflects success/failure.
    AC-6: Report written to Reports/Delta/.
    AC-7: On failure-finalization, still produces a Delta Report.

    Args:
        run_id: Ingestion run ID.
        source_id: Source identifier.
        normalized_locator: Normalized source locator string.
        fingerprint: Current content fingerprint (sha256:...).
        compare_result: CompareResult from the compare stage. None if
            pipeline failed before comparison.
        prior_fingerprint: Previous fingerprint (None for first ingest).
        pipeline_status: Override pipeline status. Auto-determined if None.
        failures: Failure records to include in the report.
        vault_root: If provided, writes the report to Reports/Delta/.

    Returns:
        Tuple of (delta_report_dict_or_none, envelope).
    """
    # Determine pipeline status
    if pipeline_status is not None:
        status = pipeline_status
    elif compare_result is not None:
        status = STATUS_COMPLETED
    elif failures:
        # Failed, but we can check if it was before or after extraction
        status = STATUS_FAILED_AFTER_EXTRACTION
    else:
        status = STATUS_FAILED_BEFORE_EXTRACTION

    # Build match_groups from CompareResult
    match_groups: dict[str, list[dict[str, Any]]] | None = None
    if compare_result is not None:
        match_groups = compare_result_to_match_groups(compare_result)

    # Build the Delta Report
    report = build_delta_report(
        run_id=run_id,
        source_id=source_id,
        normalized_locator=normalized_locator,
        fingerprint=fingerprint,
        prior_fingerprint=prior_fingerprint,
        pipeline_status=status,
        match_groups=match_groups,
        failures=failures,
    )

    # Validate
    schema_errors = validate_delta_report(report)
    if schema_errors:
        return None, make_envelope(
            STAGE_NAME,
            errors=[ErrorObject(
                code=ERR_SCHEMA_VALIDATION,
                message=f"Delta Report failed schema validation: {'; '.join(schema_errors)}",
                retryable=False,
                stage=STAGE_NAME,
                details={"schema_errors": schema_errors},
            )],
        )

    # Write to disk if vault_root provided
    artifact_path: str | None = None
    if vault_root is not None:
        try:
            written_path = save_delta_report(vault_root, report)
            artifact_path = str(written_path.relative_to(vault_root))
        except Exception as e:
            return None, make_envelope(
                STAGE_NAME,
                errors=[ErrorObject(
                    code=ERR_DELTA_WRITE_FAILED,
                    message=f"Failed to write Delta Report: {e}",
                    retryable=True,
                    stage=STAGE_NAME,
                    details={"vault_root": str(vault_root)},
                )],
            )

    # Build envelope data
    counts = report.get("counts", {})
    envelope_data: dict[str, Any] = {
        "run_id": run_id,
        "source_id": source_id,
        "pipeline_status": status,
        "novelty_score": report.get("novelty_score", 0.0),
        "total_extracted_claims": counts.get("total_extracted_claims", 0),
        "new_count": counts.get("new_count", 0),
        "exact_count": counts.get("exact_count", 0),
    }
    if artifact_path:
        envelope_data["artifact_path"] = artifact_path

    # Build warnings
    envelope_warnings: list[WarningObject] = []
    if status != STATUS_COMPLETED:
        envelope_warnings.append(WarningObject(
            code="WARN_PIPELINE_INCOMPLETE",
            message=f"Pipeline status: {status}",
        ))

    return report, make_envelope(
        STAGE_NAME,
        data=envelope_data,
        warnings=envelope_warnings or None,
    )


def delta_failure_finalization(
    *,
    run_id: str,
    source_id: str,
    normalized_locator: str,
    fingerprint: str,
    error_code: str,
    error_message: str,
    error_stage: str,
    prior_fingerprint: str | None = None,
    vault_root: Path | None = None,
) -> tuple[dict[str, Any] | None, OutputEnvelope]:
    """Generate a failure-finalization Delta Report (PIPE-002).

    AC-7: Even on pipeline failure, a Delta Report is produced recording
    the failure context.

    Args:
        run_id: Ingestion run ID.
        source_id: Source identifier.
        normalized_locator: Normalized source locator.
        fingerprint: Content fingerprint.
        error_code: Error code from the failed stage.
        error_message: Error message from the failed stage.
        error_stage: Name of the stage that failed.
        prior_fingerprint: Previous fingerprint if available.
        vault_root: If provided, writes to Reports/Delta/.

    Returns:
        Tuple of (delta_report_dict_or_none, envelope).
    """
    failure_record = {
        "stage": error_stage,
        "error_code": error_code,
        "error_message": error_message,
    }

    # Determine if failure was before or after extraction
    pre_extraction_stages = {"capture", "normalize", "fingerprint"}
    if error_stage in pre_extraction_stages:
        pipeline_status = STATUS_FAILED_BEFORE_EXTRACTION
    else:
        pipeline_status = STATUS_FAILED_AFTER_EXTRACTION

    return delta(
        run_id=run_id,
        source_id=source_id,
        normalized_locator=normalized_locator,
        fingerprint=fingerprint,
        prior_fingerprint=prior_fingerprint,
        pipeline_status=pipeline_status,
        failures=[failure_record],
        vault_root=vault_root,
    )
