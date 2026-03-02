"""Tests for the Delta stage (stage 6/7) of the ingestion pipeline.

Validates acceptance criteria from §6.5 DEL-001 and §4.2.6 SCH-006:
  AC-1: Produces a Delta Report conforming to SCH-006.
  AC-2: match_groups includes all 5 required keys.
  AC-3: counts.total_extracted_claims == sum(len(match_groups[*])).
  AC-4: Non-empty match_groups for novel/overlap claims.
  AC-5: pipeline_status reflects success/failure.
  AC-6: Delta Report written to Reports/Delta/.
  AC-7: Failure-finalization still produces a Delta Report.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from mycelium.comparator import CompareResult, MatchClass, MatchRecord
from mycelium.delta_report import MATCH_CLASS_KEYS, validate_delta_report
from mycelium.stages.delta import (
    STAGE_NAME,
    ERR_SCHEMA_VALIDATION,
    STATUS_COMPLETED,
    STATUS_FAILED_AFTER_EXTRACTION,
    STATUS_FAILED_BEFORE_EXTRACTION,
    delta,
    delta_failure_finalization,
)


# ─── Helpers ──────────────────────────────────────────────────────────────

FP = "sha256:" + "a" * 64


def _compare_result(*records: tuple[str, float, str | None]) -> CompareResult:
    """Build a CompareResult from (match_class, similarity, existing_id) tuples."""
    result = CompareResult()
    for i, (mc_val, sim, eid) in enumerate(records):
        mc = MatchClass(mc_val)
        result.add(MatchRecord(
            match_class=mc,
            similarity=sim,
            extracted_claim_key=f"h-{i:012d}",
            existing_claim_id=eid,
        ))
    return result


def _new_claims_result(n: int) -> CompareResult:
    """CompareResult with n NEW claims."""
    result = CompareResult()
    for i in range(n):
        result.add(MatchRecord(
            match_class=MatchClass.NEW,
            similarity=0.0,
            extracted_claim_key=f"h-{i:012d}",
        ))
    return result


def _mixed_result() -> CompareResult:
    """CompareResult with one of each class (except CONTRADICTING)."""
    return _compare_result(
        ("EXACT", 1.0, "c1"),
        ("NEAR_DUPLICATE", 0.90, "c2"),
        ("SUPPORTING", 0.75, "c3"),
        ("NEW", 0.1, None),
    )


# ─── AC-1: SCH-006 compliant Delta Report ─────────────────────────────────

class TestSCH006Compliance:
    """AC-1: Produces a Delta Report conforming to SCH-006."""

    def test_validates_schema(self):
        result = _new_claims_result(3)
        report, env = delta(
            run_id="run-1", source_id="src-1",
            normalized_locator="https://example.com",
            fingerprint=FP, compare_result=result,
        )
        assert report is not None
        assert env.ok is True
        errors = validate_delta_report(report)
        assert errors == [], f"Schema errors: {errors}"

    def test_has_required_top_keys(self):
        result = _new_claims_result(1)
        report, _ = delta(
            run_id="run-1", source_id="src-1",
            normalized_locator="loc", fingerprint=FP,
            compare_result=result,
        )
        assert report is not None
        for key in ("run_id", "source_id", "created_at", "source_revision",
                     "pipeline_status", "counts", "novelty_score",
                     "match_groups", "conflicts", "warnings", "failures",
                     "new_links", "follow_up_questions"):
            assert key in report, f"Missing key: {key}"

    def test_source_revision_keys(self):
        result = _new_claims_result(1)
        report, _ = delta(
            run_id="run-1", source_id="src-1",
            normalized_locator="loc", fingerprint=FP,
            compare_result=result, prior_fingerprint="sha256:" + "b" * 64,
        )
        assert report is not None
        rev = report["source_revision"]
        assert rev["normalized_locator"] == "loc"
        assert rev["fingerprint"] == FP
        assert rev["prior_fingerprint"] == "sha256:" + "b" * 64


# ─── AC-2: All 5 match group keys ─────────────────────────────────────────

class TestMatchGroupKeys:
    """AC-2: match_groups includes all 5 required keys."""

    def test_all_keys_present(self):
        result = _new_claims_result(1)
        report, _ = delta(
            run_id="run-1", source_id="src-1",
            normalized_locator="loc", fingerprint=FP,
            compare_result=result,
        )
        assert report is not None
        for key in MATCH_CLASS_KEYS:
            assert key in report["match_groups"]
            assert isinstance(report["match_groups"][key], list)

    def test_empty_groups_present(self):
        result = _new_claims_result(1)
        report, _ = delta(
            run_id="run-1", source_id="src-1",
            normalized_locator="loc", fingerprint=FP,
            compare_result=result,
        )
        assert report is not None
        # Only NEW should be non-empty
        assert len(report["match_groups"]["NEW"]) == 1
        assert len(report["match_groups"]["EXACT"]) == 0
        assert len(report["match_groups"]["NEAR_DUPLICATE"]) == 0
        assert len(report["match_groups"]["SUPPORTING"]) == 0
        assert len(report["match_groups"]["CONTRADICTING"]) == 0

    def test_no_compare_result_all_empty(self):
        report, _ = delta(
            run_id="run-1", source_id="src-1",
            normalized_locator="loc", fingerprint=FP,
            pipeline_status=STATUS_FAILED_BEFORE_EXTRACTION,
        )
        assert report is not None
        for key in MATCH_CLASS_KEYS:
            assert key in report["match_groups"]
            assert report["match_groups"][key] == []


# ─── AC-3: Counts consistency ─────────────────────────────────────────────

class TestCountsConsistency:
    """AC-3: total_extracted_claims == sum of match group sizes."""

    def test_counts_match_total(self):
        result = _mixed_result()
        report, _ = delta(
            run_id="run-1", source_id="src-1",
            normalized_locator="loc", fingerprint=FP,
            compare_result=result,
        )
        assert report is not None
        counts = report["counts"]
        total = counts["total_extracted_claims"]
        parts = (
            counts["exact_count"]
            + counts["near_duplicate_count"]
            + counts["supporting_count"]
            + counts["contradicting_count"]
            + counts["new_count"]
        )
        assert total == parts

    def test_counts_match_groups_lengths(self):
        result = _mixed_result()
        report, _ = delta(
            run_id="run-1", source_id="src-1",
            normalized_locator="loc", fingerprint=FP,
            compare_result=result,
        )
        assert report is not None
        mg = report["match_groups"]
        counts = report["counts"]
        assert counts["exact_count"] == len(mg["EXACT"])
        assert counts["near_duplicate_count"] == len(mg["NEAR_DUPLICATE"])
        assert counts["supporting_count"] == len(mg["SUPPORTING"])
        assert counts["contradicting_count"] == len(mg["CONTRADICTING"])
        assert counts["new_count"] == len(mg["NEW"])

    def test_zero_claims(self):
        result = CompareResult()  # empty
        report, _ = delta(
            run_id="run-1", source_id="src-1",
            normalized_locator="loc", fingerprint=FP,
            compare_result=result,
        )
        assert report is not None
        assert report["counts"]["total_extracted_claims"] == 0


# ─── AC-4: Non-empty groups for novel/overlap ─────────────────────────────

class TestNonEmptyGroups:
    """AC-4: Delta Report has non-empty groups for novel and overlap claims."""

    def test_novel_claims_in_new(self):
        result = _new_claims_result(3)
        report, _ = delta(
            run_id="run-1", source_id="src-1",
            normalized_locator="loc", fingerprint=FP,
            compare_result=result,
        )
        assert report is not None
        assert len(report["match_groups"]["NEW"]) == 3

    def test_overlap_in_exact(self):
        result = _compare_result(("EXACT", 1.0, "c1"))
        report, _ = delta(
            run_id="run-1", source_id="src-1",
            normalized_locator="loc", fingerprint=FP,
            compare_result=result,
        )
        assert report is not None
        assert len(report["match_groups"]["EXACT"]) == 1


# ─── AC-5: Pipeline status ────────────────────────────────────────────────

class TestPipelineStatus:
    """AC-5: pipeline_status reflects success/failure."""

    def test_completed_on_success(self):
        result = _new_claims_result(1)
        report, _ = delta(
            run_id="run-1", source_id="src-1",
            normalized_locator="loc", fingerprint=FP,
            compare_result=result,
        )
        assert report is not None
        assert report["pipeline_status"] == STATUS_COMPLETED

    def test_failed_after_extraction(self):
        report, _ = delta(
            run_id="run-1", source_id="src-1",
            normalized_locator="loc", fingerprint=FP,
            failures=[{"stage": "compare", "error": "index unavailable"}],
        )
        assert report is not None
        assert report["pipeline_status"] == STATUS_FAILED_AFTER_EXTRACTION

    def test_failed_before_extraction(self):
        report, _ = delta(
            run_id="run-1", source_id="src-1",
            normalized_locator="loc", fingerprint=FP,
            pipeline_status=STATUS_FAILED_BEFORE_EXTRACTION,
        )
        assert report is not None
        assert report["pipeline_status"] == STATUS_FAILED_BEFORE_EXTRACTION

    def test_override_status(self):
        result = _new_claims_result(1)
        report, _ = delta(
            run_id="run-1", source_id="src-1",
            normalized_locator="loc", fingerprint=FP,
            compare_result=result,
            pipeline_status=STATUS_FAILED_AFTER_EXTRACTION,
        )
        assert report is not None
        assert report["pipeline_status"] == STATUS_FAILED_AFTER_EXTRACTION

    def test_envelope_has_status(self):
        result = _new_claims_result(1)
        _, env = delta(
            run_id="run-1", source_id="src-1",
            normalized_locator="loc", fingerprint=FP,
            compare_result=result,
        )
        assert env.data["pipeline_status"] == STATUS_COMPLETED


# ─── AC-6: Written to Reports/Delta/ ──────────────────────────────────────

class TestWriteToDisk:
    """AC-6: Delta Report written to Reports/Delta/."""

    def test_writes_yaml_file(self, tmp_path: Path):
        result = _new_claims_result(2)
        report, env = delta(
            run_id="run-1", source_id="src-1",
            normalized_locator="loc", fingerprint=FP,
            compare_result=result, vault_root=tmp_path,
        )
        assert report is not None
        assert env.ok is True
        assert "artifact_path" in env.data
        artifact = tmp_path / env.data["artifact_path"]
        assert artifact.exists()

    def test_yaml_parses_back(self, tmp_path: Path):
        result = _new_claims_result(1)
        report, env = delta(
            run_id="run-1", source_id="src-1",
            normalized_locator="loc", fingerprint=FP,
            compare_result=result, vault_root=tmp_path,
        )
        assert report is not None
        artifact = tmp_path / env.data["artifact_path"]
        loaded = yaml.safe_load(artifact.read_text())
        assert loaded["run_id"] == "run-1"
        assert loaded["source_id"] == "src-1"

    def test_written_report_validates(self, tmp_path: Path):
        result = _mixed_result()
        report, env = delta(
            run_id="run-1", source_id="src-1",
            normalized_locator="loc", fingerprint=FP,
            compare_result=result, vault_root=tmp_path,
        )
        assert report is not None
        artifact = tmp_path / env.data["artifact_path"]
        loaded = yaml.safe_load(artifact.read_text())
        errors = validate_delta_report(loaded)
        assert errors == [], f"Loaded report errors: {errors}"

    def test_artifact_path_vault_relative(self, tmp_path: Path):
        result = _new_claims_result(1)
        _, env = delta(
            run_id="run-1", source_id="src-1",
            normalized_locator="loc", fingerprint=FP,
            compare_result=result, vault_root=tmp_path,
        )
        assert env.data["artifact_path"].startswith("Reports/Delta/")

    def test_reports_delta_dir_created(self, tmp_path: Path):
        result = _new_claims_result(1)
        delta(
            run_id="run-1", source_id="src-1",
            normalized_locator="loc", fingerprint=FP,
            compare_result=result, vault_root=tmp_path,
        )
        assert (tmp_path / "Reports" / "Delta").is_dir()


# ─── AC-7: Failure finalization ────────────────────────────────────────────

class TestFailureFinalization:
    """AC-7: Failure-finalization still produces a Delta Report."""

    def test_failure_finalization_produces_report(self):
        report, env = delta_failure_finalization(
            run_id="run-1", source_id="src-1",
            normalized_locator="loc", fingerprint=FP,
            error_code="ERR_CAPTURE_FAILED",
            error_message="Network timeout",
            error_stage="capture",
        )
        assert report is not None
        assert env.ok is True

    def test_failure_report_validates(self):
        report, _ = delta_failure_finalization(
            run_id="run-1", source_id="src-1",
            normalized_locator="loc", fingerprint=FP,
            error_code="ERR_CAPTURE_FAILED",
            error_message="Network timeout",
            error_stage="capture",
        )
        assert report is not None
        errors = validate_delta_report(report)
        assert errors == []

    def test_failure_before_extraction(self):
        report, _ = delta_failure_finalization(
            run_id="run-1", source_id="src-1",
            normalized_locator="loc", fingerprint=FP,
            error_code="ERR_CAPTURE_FAILED",
            error_message="timeout",
            error_stage="capture",
        )
        assert report is not None
        assert report["pipeline_status"] == STATUS_FAILED_BEFORE_EXTRACTION

    def test_failure_after_extraction(self):
        report, _ = delta_failure_finalization(
            run_id="run-1", source_id="src-1",
            normalized_locator="loc", fingerprint=FP,
            error_code="ERR_INDEX_UNAVAILABLE",
            error_message="index not found",
            error_stage="compare",
        )
        assert report is not None
        assert report["pipeline_status"] == STATUS_FAILED_AFTER_EXTRACTION

    def test_failure_record_included(self):
        report, _ = delta_failure_finalization(
            run_id="run-1", source_id="src-1",
            normalized_locator="loc", fingerprint=FP,
            error_code="ERR_EXTRACTION_FAILED",
            error_message="parse error",
            error_stage="extract",
        )
        assert report is not None
        assert len(report["failures"]) == 1
        assert report["failures"][0]["error_code"] == "ERR_EXTRACTION_FAILED"

    def test_failure_writes_to_disk(self, tmp_path: Path):
        report, env = delta_failure_finalization(
            run_id="run-1", source_id="src-1",
            normalized_locator="loc", fingerprint=FP,
            error_code="ERR_CAPTURE_FAILED",
            error_message="timeout",
            error_stage="capture",
            vault_root=tmp_path,
        )
        assert report is not None
        assert "artifact_path" in env.data
        assert (tmp_path / env.data["artifact_path"]).exists()

    def test_failure_empty_match_groups(self):
        report, _ = delta_failure_finalization(
            run_id="run-1", source_id="src-1",
            normalized_locator="loc", fingerprint=FP,
            error_code="ERR_CAPTURE_FAILED",
            error_message="timeout",
            error_stage="capture",
        )
        assert report is not None
        for key in MATCH_CLASS_KEYS:
            assert report["match_groups"][key] == []
        assert report["counts"]["total_extracted_claims"] == 0


# ─── Novelty score ────────────────────────────────────────────────────────

class TestNoveltyScore:

    def test_all_new_score_1(self):
        result = _new_claims_result(5)
        report, _ = delta(
            run_id="run-1", source_id="src-1",
            normalized_locator="loc", fingerprint=FP,
            compare_result=result,
        )
        assert report is not None
        assert report["novelty_score"] == 1.0

    def test_no_claims_score_0(self):
        result = CompareResult()
        report, _ = delta(
            run_id="run-1", source_id="src-1",
            normalized_locator="loc", fingerprint=FP,
            compare_result=result,
        )
        assert report is not None
        assert report["novelty_score"] == 0.0

    def test_mixed_score(self):
        result = _compare_result(
            ("EXACT", 1.0, "c1"),
            ("NEW", 0.1, None),
        )
        report, _ = delta(
            run_id="run-1", source_id="src-1",
            normalized_locator="loc", fingerprint=FP,
            compare_result=result,
        )
        assert report is not None
        assert 0.0 < report["novelty_score"] < 1.0

    def test_score_in_envelope(self):
        result = _new_claims_result(1)
        _, env = delta(
            run_id="run-1", source_id="src-1",
            normalized_locator="loc", fingerprint=FP,
            compare_result=result,
        )
        assert env.data["novelty_score"] == 1.0


# ─── Envelope structure ───────────────────────────────────────────────────

class TestEnvelopeStructure:

    def test_command_is_stage_name(self):
        result = _new_claims_result(1)
        _, env = delta(
            run_id="run-1", source_id="src-1",
            normalized_locator="loc", fingerprint=FP,
            compare_result=result,
        )
        assert env.command == STAGE_NAME

    def test_envelope_data_keys(self):
        result = _new_claims_result(1)
        _, env = delta(
            run_id="run-1", source_id="src-1",
            normalized_locator="loc", fingerprint=FP,
            compare_result=result,
        )
        assert "run_id" in env.data
        assert "source_id" in env.data
        assert "pipeline_status" in env.data
        assert "novelty_score" in env.data
        assert "total_extracted_claims" in env.data

    def test_incomplete_pipeline_warning(self):
        report, env = delta(
            run_id="run-1", source_id="src-1",
            normalized_locator="loc", fingerprint=FP,
            pipeline_status=STATUS_FAILED_BEFORE_EXTRACTION,
        )
        warning_codes = [w.code for w in env.warnings]
        assert "WARN_PIPELINE_INCOMPLETE" in warning_codes

    def test_no_warning_on_completed(self):
        result = _new_claims_result(1)
        _, env = delta(
            run_id="run-1", source_id="src-1",
            normalized_locator="loc", fingerprint=FP,
            compare_result=result,
        )
        warning_codes = [w.code for w in env.warnings]
        assert "WARN_PIPELINE_INCOMPLETE" not in warning_codes


# ─── In-memory only ───────────────────────────────────────────────────────

class TestInMemoryOnly:

    def test_no_artifact_path_without_vault(self):
        result = _new_claims_result(1)
        _, env = delta(
            run_id="run-1", source_id="src-1",
            normalized_locator="loc", fingerprint=FP,
            compare_result=result,
        )
        assert "artifact_path" not in env.data

    def test_returns_report(self):
        result = _new_claims_result(1)
        report, env = delta(
            run_id="run-1", source_id="src-1",
            normalized_locator="loc", fingerprint=FP,
            compare_result=result,
        )
        assert report is not None
        assert env.ok is True
