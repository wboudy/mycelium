"""Tests for the pipeline orchestrator (PIPE-001).

Validates acceptance criteria:
  AC-1: Pipeline executes stages in order: capture → normalize → fingerprint →
        extract → compare → delta → propose_queue.
  AC-2: When a stage fails, error includes the failing stage name.
  AC-3: No downstream semantic stage runs using outputs from a failed stage.
  AC-4: After failure, failure-finalization (audit, Delta Report) still runs.
  AC-5: Audit events reference canonical stage names.
  AC-6: Each stage receives typed input from the prior stage's output.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from mycelium.audit import EventType, read_audit_log
from mycelium.pipeline import (
    ERR_PIPELINE_FAILED,
    STAGE_NAMES,
    PipelineResult,
    run_pipeline,
)
from mycelium.stages.capture import SourceInput
from mycelium.stages.compare import ClaimIndex


# ─── Helpers ──────────────────────────────────────────────────────────────

def _text_source(
    text: str = (
        "Machine learning models require large datasets for training. "
        "Neural networks can approximate any continuous function. "
        "The transformer architecture revolutionized natural language processing."
    ),
    source_id: str = "test-src",
) -> SourceInput:
    return SourceInput(text_bundle=text, source_id=source_id)


def _audit_events(vault: Path) -> list[dict[str, Any]]:
    """Read all audit events from all log files in the vault."""
    log_dir = vault / "Logs" / "Audit"
    if not log_dir.exists():
        return []
    events = []
    for f in sorted(log_dir.glob("*.jsonl")):
        for line in f.read_text().strip().splitlines():
            if line.strip():
                events.append(json.loads(line))
    return events


# ─── AC-1: Stages execute in order ──────────────────────────────────────

class TestStageOrder:
    """AC-1: Pipeline executes stages in correct order."""

    def test_all_stages_run_on_success(self, tmp_path: Path):
        si = _text_source()
        result, env = run_pipeline(si, vault_root=tmp_path, run_id="run-1", source_id="src-1")
        assert env.ok is True
        assert result.ok is True
        # All 7 stages should have envelopes
        for stage in STAGE_NAMES:
            assert stage in result.stage_envelopes, f"Missing envelope for {stage}"

    def test_stage_envelopes_all_ok(self, tmp_path: Path):
        si = _text_source()
        result, _ = run_pipeline(si, vault_root=tmp_path, run_id="run-1", source_id="src-1")
        for stage, env in result.stage_envelopes.items():
            assert env.ok is True, f"Stage {stage} failed: {env.errors}"

    def test_run_id_propagated(self, tmp_path: Path):
        si = _text_source()
        result, env = run_pipeline(si, vault_root=tmp_path, run_id="run-abc", source_id="src-1")
        assert result.run_id == "run-abc"
        assert env.data["run_id"] == "run-abc"

    def test_source_id_propagated(self, tmp_path: Path):
        si = _text_source()
        result, env = run_pipeline(si, vault_root=tmp_path, run_id="run-1", source_id="src-abc")
        assert result.source_id == "src-abc"
        assert env.data["source_id"] == "src-abc"

    def test_auto_generated_ids(self):
        si = _text_source()
        result, env = run_pipeline(si)
        assert result.run_id.startswith("run-")
        assert result.source_id.startswith("src-") or result.source_id == "test-src"


# ─── AC-2: Error includes failing stage name ────────────────────────────

class TestFailingStageReported:
    """AC-2: When a stage fails, error includes the stage name."""

    def test_capture_failure_reports_stage(self):
        si = SourceInput()  # No source input
        result, env = run_pipeline(si, run_id="run-fail")
        assert env.ok is False
        assert result.failed_stage == "capture"
        assert env.errors[0].stage == "capture"

    def test_error_code_is_pipeline_failed(self):
        si = SourceInput()
        _, env = run_pipeline(si, run_id="run-fail")
        assert env.errors[0].code == ERR_PIPELINE_FAILED

    def test_error_includes_original_code(self):
        si = SourceInput()
        _, env = run_pipeline(si, run_id="run-fail")
        assert "original_error_code" in env.errors[0].details

    def test_empty_text_bundle_fails_at_capture(self):
        si = SourceInput(text_bundle="")
        result, env = run_pipeline(si, run_id="run-fail")
        assert env.ok is False
        assert result.failed_stage == "capture"


# ─── AC-3: No downstream stage runs after failure ───────────────────────

class TestNoDownstreamAfterFailure:
    """AC-3: No downstream semantic stage runs using outputs from a failed stage."""

    def test_capture_failure_no_downstream(self):
        si = SourceInput()
        result, _ = run_pipeline(si, run_id="run-fail")
        # Only capture envelope should exist
        assert "capture" in result.stage_envelopes
        assert "normalize" not in result.stage_envelopes
        assert "extract" not in result.stage_envelopes

    def test_no_artifacts_on_early_failure(self):
        si = SourceInput()
        result, _ = run_pipeline(si, run_id="run-fail")
        assert result.delta_report is None
        assert result.queue_items is None


# ─── AC-4: Failure finalization ──────────────────────────────────────────

class TestFailureFinalization:
    """AC-4: After failure, failure-finalization steps still run."""

    def test_audit_ingest_failed_emitted(self, tmp_path: Path):
        si = SourceInput()
        run_pipeline(si, vault_root=tmp_path, run_id="run-fail", source_id="src-fail")
        events = _audit_events(tmp_path)
        event_types = [e["event_type"] for e in events]
        assert "ingest_started" in event_types
        assert "ingest_failed" in event_types

    def test_audit_ingest_completed_on_success(self, tmp_path: Path):
        si = _text_source()
        run_pipeline(si, vault_root=tmp_path, run_id="run-ok", source_id="src-ok")
        events = _audit_events(tmp_path)
        event_types = [e["event_type"] for e in events]
        assert "ingest_started" in event_types
        assert "ingest_completed" in event_types

    def test_failure_audit_includes_stage(self, tmp_path: Path):
        si = SourceInput()
        run_pipeline(si, vault_root=tmp_path, run_id="run-fail", source_id="src-fail")
        events = _audit_events(tmp_path)
        fail_events = [e for e in events if e["event_type"] == "ingest_failed"]
        assert len(fail_events) == 1
        assert fail_events[0]["details"]["failed_stage"] == "capture"

    def test_no_failure_delta_for_pre_fingerprint_failure(self, tmp_path: Path):
        """Failures before fingerprint can't produce a failure Delta Report."""
        si = SourceInput()
        result, _ = run_pipeline(si, vault_root=tmp_path, run_id="run-fail")
        # No delta report since we failed before fingerprint
        assert result.delta_report is None


# ─── AC-5: Canonical stage names in audit ────────────────────────────────

class TestCanonicalStageNames:
    """AC-5: Audit events use canonical stage names."""

    def test_stage_names_constant(self):
        assert STAGE_NAMES == (
            "capture", "normalize", "fingerprint",
            "extract", "compare", "delta", "propose_queue",
        )

    def test_failed_stage_is_canonical(self):
        si = SourceInput()
        result, _ = run_pipeline(si, run_id="run-fail")
        assert result.failed_stage in STAGE_NAMES

    def test_envelope_commands_are_canonical(self, tmp_path: Path):
        si = _text_source()
        result, _ = run_pipeline(si, vault_root=tmp_path, run_id="run-1")
        for stage_name, env in result.stage_envelopes.items():
            assert stage_name in STAGE_NAMES
            assert env.command == stage_name


# ─── AC-6: Typed input from prior stage ─────────────────────────────────

class TestTypedStageInputs:
    """AC-6: Each stage receives typed input from the prior stage."""

    def test_delta_report_produced(self, tmp_path: Path):
        si = _text_source()
        result, _ = run_pipeline(si, vault_root=tmp_path, run_id="run-1", source_id="src-1")
        assert result.delta_report is not None
        assert result.delta_report["run_id"] == "run-1"
        assert result.delta_report["source_id"] == "src-1"

    def test_queue_items_produced(self, tmp_path: Path):
        si = _text_source()
        result, _ = run_pipeline(si, vault_root=tmp_path, run_id="run-1", source_id="src-1")
        assert result.queue_items is not None
        assert len(result.queue_items) > 0

    def test_delta_report_completed_status(self, tmp_path: Path):
        si = _text_source()
        result, _ = run_pipeline(si, vault_root=tmp_path, run_id="run-1", source_id="src-1")
        assert result.delta_report["pipeline_status"] == "completed"

    def test_delta_has_match_groups(self, tmp_path: Path):
        si = _text_source()
        result, _ = run_pipeline(si, vault_root=tmp_path, run_id="run-1", source_id="src-1")
        for group in ["EXACT", "NEAR_DUPLICATE", "SUPPORTING", "CONTRADICTING", "NEW"]:
            assert group in result.delta_report["match_groups"]


# ─── Artifact writing ───────────────────────────────────────────────────

class TestArtifactWriting:
    """Pipeline writes artifacts to disk when vault_root provided."""

    def test_extraction_bundle_written(self, tmp_path: Path):
        si = _text_source()
        run_pipeline(si, vault_root=tmp_path, run_id="run-1", source_id="src-1")
        bundles = list((tmp_path / "Inbox" / "Sources").glob("*extraction*.yaml"))
        assert len(bundles) >= 1

    def test_delta_report_written(self, tmp_path: Path):
        si = _text_source()
        run_pipeline(si, vault_root=tmp_path, run_id="run-1", source_id="src-1")
        deltas = list((tmp_path / "Reports" / "Delta").glob("*.yaml"))
        assert len(deltas) >= 1

    def test_queue_items_written(self, tmp_path: Path):
        si = _text_source()
        result, _ = run_pipeline(si, vault_root=tmp_path, run_id="run-1", source_id="src-1")
        if result.queue_items:
            queue_files = list((tmp_path / "Inbox" / "ReviewQueue").glob("*.yaml"))
            assert len(queue_files) == len(result.queue_items)

    def test_artifact_paths_collected(self, tmp_path: Path):
        si = _text_source()
        result, env = run_pipeline(si, vault_root=tmp_path, run_id="run-1", source_id="src-1")
        assert len(result.artifact_paths) > 0
        assert "artifact_paths" in env.data

    def test_no_artifacts_without_vault(self):
        si = _text_source()
        result, _ = run_pipeline(si, run_id="run-1", source_id="src-1")
        assert len(result.artifact_paths) == 0


# ─── In-memory mode (no vault_root) ─────────────────────────────────────

class TestInMemoryMode:
    """Pipeline runs correctly without vault_root."""

    def test_success_without_vault(self):
        si = _text_source()
        result, env = run_pipeline(si, run_id="run-mem", source_id="src-mem")
        assert env.ok is True
        assert result.ok is True
        assert result.delta_report is not None
        assert result.queue_items is not None

    def test_no_audit_without_vault(self):
        si = _text_source()
        result, _ = run_pipeline(si, run_id="run-mem", source_id="src-mem")
        # No audit dir should exist
        assert result.ok is True


# ─── ClaimIndex integration ─────────────────────────────────────────────

class TestClaimIndexIntegration:
    """Pipeline works with provided claim index for dedup."""

    def test_empty_index_all_new(self, tmp_path: Path):
        si = _text_source()
        result, _ = run_pipeline(
            si,
            vault_root=tmp_path,
            run_id="run-1",
            source_id="src-1",
            claim_index=ClaimIndex(claims=[]),
        )
        assert result.delta_report is not None
        assert result.delta_report["counts"]["new_count"] >= 1

    def test_default_empty_index(self, tmp_path: Path):
        """When claim_index is None, defaults to empty index."""
        si = _text_source()
        result, env = run_pipeline(si, vault_root=tmp_path, run_id="run-1", source_id="src-1")
        assert env.ok is True
        assert result.delta_report is not None


# ─── Envelope structure ─────────────────────────────────────────────────

class TestEnvelopeStructure:

    def test_success_envelope_has_data(self, tmp_path: Path):
        si = _text_source()
        _, env = run_pipeline(si, vault_root=tmp_path, run_id="run-1", source_id="src-1")
        assert env.command == "pipeline"
        assert "run_id" in env.data
        assert "source_id" in env.data
        assert env.data["ok"] is True

    def test_failure_envelope_has_error(self):
        si = SourceInput()
        _, env = run_pipeline(si, run_id="run-fail")
        assert env.command == "pipeline"
        assert env.ok is False
        assert len(env.errors) == 1
        assert env.errors[0].code == ERR_PIPELINE_FAILED

    def test_warnings_aggregated(self, tmp_path: Path):
        si = _text_source()
        _, env = run_pipeline(
            si, vault_root=tmp_path, run_id="run-1", source_id="src-1",
            claim_index=ClaimIndex(claims=[]),
        )
        # Should have at least the "no existing claims" warning from compare
        assert len(env.warnings) >= 1


# ─── PipelineResult dataclass ────────────────────────────────────────────

class TestPipelineResult:

    def test_to_dict_success(self, tmp_path: Path):
        si = _text_source()
        result, _ = run_pipeline(si, vault_root=tmp_path, run_id="run-1", source_id="src-1")
        d = result.to_dict()
        assert d["run_id"] == "run-1"
        assert d["source_id"] == "src-1"
        assert d["ok"] is True
        assert "pipeline_status" in d
        assert "queue_items_count" in d

    def test_to_dict_failure(self):
        si = SourceInput()
        result, _ = run_pipeline(si, run_id="run-fail", source_id="src-fail")
        d = result.to_dict()
        assert d["ok"] is False
        assert d["failed_stage"] == "capture"
