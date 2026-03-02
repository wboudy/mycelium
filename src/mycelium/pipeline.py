"""
Pipeline orchestrator — executes stages in order with stage-scoped error handling (PIPE-001).

Chains the 7 ingestion stages:
  capture → normalize → fingerprint → extract → compare → delta → propose_queue

On failure, no downstream semantic stage runs using outputs from a failed stage
(AC-PIPE-001-2). Failure-finalization steps (audit events, Delta Report with
failure status) still run after a stage failure (PIPE-002).

Spec reference: §6.1 PIPE-001, §6.1.2 PIPE-003, §6.3 PIPE-002
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mycelium.audit import EventType, emit_event
from mycelium.models import (
    ErrorObject,
    OutputEnvelope,
    WarningObject,
    make_envelope,
)
from mycelium.quarantine import quarantine_file
from mycelium.stages.capture import SourceInput, capture
from mycelium.stages.compare import ClaimIndex, compare
from mycelium.stages.delta import delta, delta_failure_finalization
from mycelium.stages.extract import extract
from mycelium.stages.fingerprint import fingerprint
from mycelium.stages.normalize import normalize
from mycelium.stages.propose_queue import propose_queue

# Canonical stage names (PIPE-003, AC-5)
STAGE_NAMES = (
    "capture",
    "normalize",
    "fingerprint",
    "extract",
    "compare",
    "delta",
    "propose_queue",
)

# Pipeline-level error codes
ERR_PIPELINE_FAILED = "ERR_PIPELINE_FAILED"


@dataclass
class PipelineResult:
    """Collected outputs from a pipeline run."""

    run_id: str
    source_id: str
    ok: bool = True
    failed_stage: str | None = None
    stage_envelopes: dict[str, OutputEnvelope] = field(default_factory=dict)
    # Stage outputs (None if stage didn't run or failed)
    delta_report: dict[str, Any] | None = None
    queue_items: list[dict[str, Any]] | None = None
    artifact_paths: list[str] = field(default_factory=list)
    quarantined_paths: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "run_id": self.run_id,
            "source_id": self.source_id,
            "ok": self.ok,
            "artifact_paths": self.artifact_paths,
        }
        if self.failed_stage is not None:
            d["failed_stage"] = self.failed_stage
        if self.delta_report is not None:
            d["pipeline_status"] = self.delta_report.get("pipeline_status")
            d["novelty_score"] = self.delta_report.get("novelty_score")
        if self.queue_items is not None:
            d["queue_items_count"] = len(self.queue_items)
        if self.quarantined_paths:
            d["quarantined_paths"] = self.quarantined_paths
        return d


def run_pipeline(
    source_input: SourceInput,
    *,
    vault_root: Path | None = None,
    run_id: str | None = None,
    source_id: str | None = None,
    claim_index: ClaimIndex | None = None,
) -> tuple[PipelineResult, OutputEnvelope]:
    """Execute the full ingestion pipeline.

    Runs stages in order: capture → normalize → fingerprint → extract →
    compare → delta → propose_queue.

    AC-1: Stages execute in order.
    AC-2: On failure, error includes the failing stage name.
    AC-3: No downstream semantic stage runs after a failure.
    AC-4: Failure-finalization (audit, Delta Report) still runs.
    AC-5: Audit events use canonical stage names.
    AC-6: Each stage receives typed input from the prior stage.

    Args:
        source_input: Source to ingest (url, pdf, or text_bundle).
        vault_root: If provided, stages write artifacts to disk.
        run_id: Ingestion run ID (auto-generated if omitted).
        source_id: Source identifier (derived from source_input if omitted).
        claim_index: Existing claims for deduplication. None means empty index.

    Returns:
        Tuple of (PipelineResult, OutputEnvelope).
    """
    rid = run_id or f"run-{uuid.uuid4().hex[:12]}"
    sid = source_id or source_input.source_id or f"src-{uuid.uuid4().hex[:8]}"

    result = PipelineResult(run_id=rid, source_id=sid)
    all_warnings: list[WarningObject] = []

    # Emit audit: ingest_started
    if vault_root is not None:
        emit_event(
            vault_root,
            EventType.INGEST_STARTED,
            actor="pipeline",
            run_id=rid,
            details={"source_id": sid},
        )

    # ── Stage 1: Capture ──────────────────────────────────────────────
    payload, env = capture(source_input)
    result.stage_envelopes["capture"] = env
    all_warnings.extend(env.warnings)
    if not env.ok or payload is None:
        return _fail(result, "capture", env, all_warnings, vault_root, rid, sid)

    # ── Stage 2: Normalize ────────────────────────────────────────────
    norm, env = normalize(payload)
    result.stage_envelopes["normalize"] = env
    all_warnings.extend(env.warnings)
    if not env.ok or norm is None:
        return _fail(result, "normalize", env, all_warnings, vault_root, rid, sid)

    # ── Stage 3: Fingerprint ──────────────────────────────────────────
    ident, env = fingerprint(norm)
    result.stage_envelopes["fingerprint"] = env
    all_warnings.extend(env.warnings)
    if not env.ok or ident is None:
        return _fail(result, "fingerprint", env, all_warnings, vault_root, rid, sid)

    # ── Stage 4: Extract ──────────────────────────────────────────────
    bundle, env = extract(
        norm,
        vault_root=vault_root,
        run_id=rid,
        source_id=sid,
    )
    result.stage_envelopes["extract"] = env
    all_warnings.extend(env.warnings)
    if env.data.get("artifact_path"):
        result.artifact_paths.append(env.data["artifact_path"])
    if not env.ok or bundle is None:
        return _fail(
            result, "extract", env, all_warnings, vault_root, rid, sid,
            normalized_locator=ident.normalized_locator,
            fp=ident.fingerprint,
        )

    # ── Stage 5: Compare ──────────────────────────────────────────────
    idx = claim_index if claim_index is not None else ClaimIndex(claims=[])
    compare_result, env = compare(
        bundle.get("claims", []),
        claim_index=idx,
    )
    result.stage_envelopes["compare"] = env
    all_warnings.extend(env.warnings)
    if not env.ok or compare_result is None:
        return _fail(
            result, "compare", env, all_warnings, vault_root, rid, sid,
            normalized_locator=ident.normalized_locator,
            fp=ident.fingerprint,
        )

    # ── Stage 6: Delta ────────────────────────────────────────────────
    delta_report, env = delta(
        run_id=rid,
        source_id=sid,
        normalized_locator=ident.normalized_locator,
        fingerprint=ident.fingerprint,
        compare_result=compare_result,
        vault_root=vault_root,
    )
    result.stage_envelopes["delta"] = env
    all_warnings.extend(env.warnings)
    if env.data.get("artifact_path"):
        result.artifact_paths.append(env.data["artifact_path"])
    if not env.ok or delta_report is None:
        return _fail(result, "delta", env, all_warnings, vault_root, rid, sid)

    result.delta_report = delta_report

    # ── Stage 7: Propose Queue ────────────────────────────────────────
    queue_items, env = propose_queue(
        delta_report,
        vault_root=vault_root,
    )
    result.stage_envelopes["propose_queue"] = env
    all_warnings.extend(env.warnings)
    if env.data.get("artifact_paths"):
        result.artifact_paths.extend(env.data["artifact_paths"])
    if not env.ok or queue_items is None:
        return _fail(result, "propose_queue", env, all_warnings, vault_root, rid, sid)

    result.queue_items = queue_items

    # ── Success ───────────────────────────────────────────────────────
    if vault_root is not None:
        emit_event(
            vault_root,
            EventType.INGEST_COMPLETED,
            actor="pipeline",
            run_id=rid,
            targets=result.artifact_paths,
            details={
                "source_id": sid,
                "pipeline_status": delta_report.get("pipeline_status"),
                "queue_items_count": len(queue_items),
            },
        )

    return result, make_envelope(
        "pipeline",
        data=result.to_dict(),
        warnings=all_warnings or None,
    )


def _quarantine_partial_artifacts(
    vault_root: Path,
    artifact_paths: list[str],
    *,
    error_code: str,
    error_message: str,
    stage: str,
    run_id: str,
    source_id: str,
) -> list:
    """Quarantine partial artifacts on pipeline failure (PIPE-002 AC-4).

    Moves any artifacts written by prior stages to Quarantine/ with
    diagnostic sidecars. This prevents partial artifacts from lingering
    in Draft Scope after a failed pipeline run.

    Args:
        vault_root: Vault root path.
        artifact_paths: Vault-relative paths of artifacts to quarantine.
        error_code: Error code from the failing stage.
        error_message: Error message from the failing stage.
        stage: The stage that failed.
        run_id: Pipeline run ID.
        source_id: Source identifier.

    Returns:
        List of QuarantineResult objects for successfully quarantined artifacts.
    """
    results = []
    for art_path in artifact_paths:
        full_path = vault_root / art_path
        if not full_path.exists():
            continue
        try:
            qr = quarantine_file(
                vault_root,
                art_path,
                error_code=error_code,
                error_message=f"Pipeline failed at stage '{stage}': {error_message}",
                stage=stage,
                details={
                    "run_id": run_id,
                    "source_id": source_id,
                    "partial_artifact": True,
                },
            )
            results.append(qr)
        except (FileNotFoundError, OSError):
            # Best-effort quarantine — don't let quarantine failure
            # mask the original pipeline failure
            pass
    return results


def _fail(
    result: PipelineResult,
    failed_stage: str,
    failed_env: OutputEnvelope,
    all_warnings: list[WarningObject],
    vault_root: Path | None,
    run_id: str,
    source_id: str,
    *,
    normalized_locator: str | None = None,
    fp: str | None = None,
) -> tuple[PipelineResult, OutputEnvelope]:
    """Handle a stage failure with proper finalization (PIPE-002).

    AC-2: Error includes the failing stage name.
    AC-3: No downstream semantic stage runs.
    AC-4: Failure-finalization (audit, Delta Report) still runs.
    """
    result.ok = False
    result.failed_stage = failed_stage

    # Extract error info from the failed envelope
    error_code = failed_env.errors[0].code if failed_env.errors else "UNKNOWN"
    error_message = failed_env.errors[0].message if failed_env.errors else "Unknown error"

    # PIPE-002 AC-4: Quarantine partial artifacts on failure
    if vault_root is not None and result.artifact_paths:
        quarantine_results = _quarantine_partial_artifacts(
            vault_root, result.artifact_paths,
            error_code=error_code,
            error_message=error_message,
            stage=failed_stage,
            run_id=run_id,
            source_id=source_id,
        )
        result.quarantined_paths = [qr.quarantined_path for qr in quarantine_results]

    # Failure-finalization: produce a Delta Report if we have enough context
    # (normalized_locator + fingerprint available means we got past fingerprint stage)
    if normalized_locator and fp and vault_root:
        failure_report, failure_env = delta_failure_finalization(
            run_id=run_id,
            source_id=source_id,
            normalized_locator=normalized_locator,
            fingerprint=fp,
            error_code=error_code,
            error_message=error_message,
            error_stage=failed_stage,
            vault_root=vault_root,
        )
        if failure_report is not None:
            result.delta_report = failure_report
            result.stage_envelopes["delta"] = failure_env
            if failure_env.data.get("artifact_path"):
                result.artifact_paths.append(failure_env.data["artifact_path"])

    # Emit audit: ingest_failed
    if vault_root is not None:
        emit_event(
            vault_root,
            EventType.INGEST_FAILED,
            actor="pipeline",
            run_id=run_id,
            targets=result.artifact_paths,
            details={
                "source_id": source_id,
                "failed_stage": failed_stage,
                "error_code": error_code,
                "error_message": error_message,
            },
        )

    # Build pipeline error
    pipeline_error = ErrorObject(
        code=ERR_PIPELINE_FAILED,
        message=f"Pipeline failed at stage '{failed_stage}': {error_message}",
        retryable=failed_env.errors[0].retryable if failed_env.errors else False,
        stage=failed_stage,
        details={
            "run_id": run_id,
            "source_id": source_id,
            "failed_stage": failed_stage,
            "original_error_code": error_code,
        },
    )

    return result, make_envelope(
        "pipeline",
        data=result.to_dict(),
        errors=[pipeline_error],
        warnings=all_warnings or None,
    )
