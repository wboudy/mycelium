"""
Tests for mycelium.delta_report module (SCH-006).

Verifies:
- AC-SCH-006-1: Delta Report exists after ingestion (tested via save/load).
- AC-SCH-006-2: Required top-level keys always present, empty arrays explicit.
- AC-SCH-006-3: Rejects novelty_score outside [0..1].
- AC-SCH-006-4: Match Record keys; match_class == group key.
- AC-SCH-006-5: pipeline_status valid enum.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from mycelium.delta_report import (
    MATCH_CLASS_KEYS,
    REQUIRED_TOP_KEYS,
    VALID_PIPELINE_STATUSES,
    build_delta_report,
    load_delta_report,
    save_delta_report,
    validate_delta_report,
    validate_delta_report_strict,
)
from mycelium.schema import SchemaValidationError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_report(**overrides: Any) -> dict[str, Any]:
    """Build a minimal valid Delta Report for testing."""
    report = build_delta_report(
        run_id="run-001",
        source_id="source-001",
        normalized_locator="example.com/test",
        fingerprint="sha256:" + "a" * 64,
        created_at="2026-03-01T00:00:00Z",
    )
    report.update(overrides)
    return report


def _report_with_matches() -> dict[str, Any]:
    """Build a Delta Report with match records."""
    return build_delta_report(
        run_id="run-002",
        source_id="source-002",
        normalized_locator="example.com/test2",
        fingerprint="sha256:" + "b" * 64,
        created_at="2026-03-01T00:00:00Z",
        match_groups={
            "EXACT": [{
                "extracted_claim_key": "h-aabbccddee11",
                "match_class": "EXACT",
                "similarity": 1.0,
                "existing_claim_id": "claim-1",
            }],
            "NEAR_DUPLICATE": [],
            "SUPPORTING": [],
            "CONTRADICTING": [{
                "extracted_claim_key": "h-112233445566",
                "match_class": "CONTRADICTING",
                "similarity": 0.45,
                "existing_claim_id": "claim-2",
            }],
            "NEW": [{
                "extracted_claim_key": "h-ffeeddccbbaa",
                "match_class": "NEW",
                "similarity": 0.0,
                "existing_claim_id": None,
            }],
        },
        conflicts=[{
            "new_extracted_claim_key": "h-112233445566",
            "existing_claim_id": "claim-2",
            "evidence": {"reason": "test conflict"},
        }],
    )


# ---------------------------------------------------------------------------
# validate_delta_report
# ---------------------------------------------------------------------------

class TestValidateDeltaReport:
    """Validation tests for SCH-006."""

    def test_valid_minimal_report(self):
        report = _minimal_report()
        errors = validate_delta_report(report)
        assert errors == []

    def test_valid_report_with_matches(self):
        report = _report_with_matches()
        errors = validate_delta_report(report)
        assert errors == []

    # AC-SCH-006-2: Required top-level keys
    def test_missing_top_level_keys(self):
        errors = validate_delta_report({})
        assert any("Missing required top-level keys" in e for e in errors)

    def test_each_required_key_individually(self):
        """Removing any single required key produces an error."""
        for key in REQUIRED_TOP_KEYS:
            report = _minimal_report()
            del report[key]
            errors = validate_delta_report(report)
            assert len(errors) > 0, f"Removing {key} should produce error"

    # AC-SCH-006-3: novelty_score range
    def test_novelty_score_below_zero(self):
        report = _minimal_report(novelty_score=-0.1)
        errors = validate_delta_report(report)
        assert any("novelty_score" in e for e in errors)

    def test_novelty_score_above_one(self):
        report = _minimal_report(novelty_score=1.5)
        errors = validate_delta_report(report)
        assert any("novelty_score" in e for e in errors)

    def test_novelty_score_zero_valid(self):
        report = _minimal_report(novelty_score=0.0)
        errors = validate_delta_report(report)
        assert errors == []

    def test_novelty_score_one_valid(self):
        report = _minimal_report(novelty_score=1.0)
        errors = validate_delta_report(report)
        assert errors == []

    def test_novelty_score_non_numeric(self):
        report = _minimal_report(novelty_score="high")
        errors = validate_delta_report(report)
        assert any("novelty_score" in e for e in errors)

    # AC-SCH-006-4: Match Record validation
    def test_match_class_mismatch(self):
        """match_class must equal containing group key."""
        report = _minimal_report()
        report["match_groups"]["EXACT"] = [{
            "extracted_claim_key": "h-aabbccddee11",
            "match_class": "NEW",  # Wrong!
            "similarity": 1.0,
            "existing_claim_id": "claim-1",
        }]
        errors = validate_delta_report(report)
        assert any("match_class" in e and "EXACT" in e for e in errors)

    def test_match_record_missing_keys(self):
        report = _minimal_report()
        report["match_groups"]["NEW"] = [{"match_class": "NEW"}]  # missing keys
        errors = validate_delta_report(report)
        assert any("missing keys" in e for e in errors)

    def test_similarity_out_of_range(self):
        report = _minimal_report()
        report["match_groups"]["EXACT"] = [{
            "extracted_claim_key": "h-aabbccddee11",
            "match_class": "EXACT",
            "similarity": 1.5,
            "existing_claim_id": "claim-1",
        }]
        errors = validate_delta_report(report)
        assert any("similarity" in e for e in errors)

    def test_missing_match_group_key(self):
        """All 5 class keys must be present in match_groups."""
        report = _minimal_report()
        del report["match_groups"]["SUPPORTING"]
        errors = validate_delta_report(report)
        assert any("SUPPORTING" in e for e in errors)

    # AC-SCH-006-5: pipeline_status enum
    def test_valid_pipeline_statuses(self):
        for status in VALID_PIPELINE_STATUSES:
            report = _minimal_report(pipeline_status=status)
            errors = validate_delta_report(report)
            assert errors == [], f"Status {status} should be valid"

    def test_invalid_pipeline_status(self):
        report = _minimal_report(pipeline_status="partially_done")
        errors = validate_delta_report(report)
        assert any("pipeline_status" in e for e in errors)

    # source_revision validation
    def test_source_revision_missing_keys(self):
        report = _minimal_report()
        report["source_revision"] = {"normalized_locator": "x"}
        errors = validate_delta_report(report)
        assert any("source_revision" in e for e in errors)

    # counts validation
    def test_counts_missing_keys(self):
        report = _minimal_report()
        report["counts"] = {"total_extracted_claims": 0}
        errors = validate_delta_report(report)
        assert any("counts" in e for e in errors)

    # Conflict record validation
    def test_conflict_record_missing_keys(self):
        report = _minimal_report()
        report["conflicts"] = [{"new_extracted_claim_key": "h-abc"}]
        errors = validate_delta_report(report)
        assert any("conflicts" in e for e in errors)

    # created_at validation
    def test_invalid_created_at(self):
        report = _minimal_report(created_at="not-a-date")
        errors = validate_delta_report(report)
        assert any("created_at" in e for e in errors)

    # Array type validation
    def test_array_fields_must_be_lists(self):
        for key in ("conflicts", "warnings", "failures", "new_links", "follow_up_questions"):
            report = _minimal_report()
            report[key] = "not-a-list"
            errors = validate_delta_report(report)
            assert any(key in e for e in errors), f"{key} should require list type"

    # strict wrapper
    def test_strict_raises(self):
        with pytest.raises(SchemaValidationError):
            validate_delta_report_strict({})

    def test_strict_passes_valid(self):
        validate_delta_report_strict(_minimal_report())


# ---------------------------------------------------------------------------
# build_delta_report
# ---------------------------------------------------------------------------

class TestBuildDeltaReport:
    """Verify builder produces valid reports."""

    def test_minimal_build_is_valid(self):
        report = build_delta_report(
            run_id="r1",
            source_id="s1",
            normalized_locator="test.com/a",
            fingerprint="sha256:" + "f" * 64,
        )
        errors = validate_delta_report(report)
        assert errors == []

    def test_all_match_group_keys_present(self):
        """AC-SCH-006-2: Empty arrays explicitly present."""
        report = build_delta_report(
            run_id="r1",
            source_id="s1",
            normalized_locator="test.com/a",
            fingerprint="sha256:" + "f" * 64,
        )
        for cls in MATCH_CLASS_KEYS:
            assert cls in report["match_groups"]
            assert isinstance(report["match_groups"][cls], list)

    def test_all_array_fields_present(self):
        """AC-SCH-006-2: All array fields exist even when empty."""
        report = build_delta_report(
            run_id="r1",
            source_id="s1",
            normalized_locator="test.com/a",
            fingerprint="sha256:" + "f" * 64,
        )
        for key in ("conflicts", "warnings", "failures", "new_links", "follow_up_questions"):
            assert key in report
            assert isinstance(report[key], list)

    def test_counts_computed_from_match_groups(self):
        report = build_delta_report(
            run_id="r1",
            source_id="s1",
            normalized_locator="test.com/a",
            fingerprint="sha256:" + "f" * 64,
            match_groups={
                "EXACT": [{"extracted_claim_key": "h-1", "match_class": "EXACT", "similarity": 1.0, "existing_claim_id": "c1"}],
                "NEAR_DUPLICATE": [],
                "SUPPORTING": [],
                "CONTRADICTING": [],
                "NEW": [
                    {"extracted_claim_key": "h-2", "match_class": "NEW", "similarity": 0.0, "existing_claim_id": None},
                    {"extracted_claim_key": "h-3", "match_class": "NEW", "similarity": 0.0, "existing_claim_id": None},
                ],
            },
        )
        counts = report["counts"]
        assert counts["total_extracted_claims"] == 3
        assert counts["exact_count"] == 1
        assert counts["new_count"] == 2
        assert counts["near_duplicate_count"] == 0

    def test_novelty_score_computed(self):
        report = build_delta_report(
            run_id="r1",
            source_id="s1",
            normalized_locator="test.com/a",
            fingerprint="sha256:" + "f" * 64,
            match_groups={
                "EXACT": [{"extracted_claim_key": "h-1", "match_class": "EXACT", "similarity": 1.0, "existing_claim_id": "c1"}],
                "NEAR_DUPLICATE": [],
                "SUPPORTING": [],
                "CONTRADICTING": [],
                "NEW": [{"extracted_claim_key": "h-2", "match_class": "NEW", "similarity": 0.0, "existing_claim_id": None}],
            },
        )
        assert report["novelty_score"] == 0.5  # 1 NEW out of 2 total

    def test_novelty_score_zero_when_no_claims(self):
        report = build_delta_report(
            run_id="r1",
            source_id="s1",
            normalized_locator="test.com/a",
            fingerprint="sha256:" + "f" * 64,
        )
        assert report["novelty_score"] == 0.0

    def test_prior_fingerprint(self):
        report = build_delta_report(
            run_id="r1",
            source_id="s1",
            normalized_locator="test.com/a",
            fingerprint="sha256:" + "a" * 64,
            prior_fingerprint="sha256:" + "b" * 64,
        )
        assert report["source_revision"]["prior_fingerprint"] == "sha256:" + "b" * 64


# ---------------------------------------------------------------------------
# Persistence (save/load)
# ---------------------------------------------------------------------------

class TestPersistence:
    """Verify YAML save/load roundtrip."""

    def test_save_creates_file(self, tmp_path: Path):
        report = _minimal_report()
        path = save_delta_report(tmp_path, report)
        assert path.exists()
        assert path.suffix == ".yaml"

    def test_save_under_reports_delta(self, tmp_path: Path):
        report = _minimal_report()
        path = save_delta_report(tmp_path, report)
        assert "Reports" in path.parts
        assert "Delta" in path.parts

    def test_filename_contains_run_id(self, tmp_path: Path):
        report = _minimal_report()
        path = save_delta_report(tmp_path, report)
        assert "run-001" in path.name

    def test_roundtrip(self, tmp_path: Path):
        original = _report_with_matches()
        path = save_delta_report(tmp_path, original)
        loaded = load_delta_report(path)

        assert loaded["run_id"] == original["run_id"]
        assert loaded["source_id"] == original["source_id"]
        assert loaded["pipeline_status"] == original["pipeline_status"]
        assert loaded["novelty_score"] == original["novelty_score"]
        assert len(loaded["match_groups"]["EXACT"]) == 1
        assert len(loaded["match_groups"]["CONTRADICTING"]) == 1
        assert len(loaded["match_groups"]["NEW"]) == 1
        assert len(loaded["conflicts"]) == 1

    def test_save_validates(self, tmp_path: Path):
        """save_delta_report rejects invalid reports."""
        with pytest.raises(SchemaValidationError):
            save_delta_report(tmp_path, {"invalid": True})

    def test_load_validates(self, tmp_path: Path):
        """load_delta_report rejects invalid YAML."""
        bad_path = tmp_path / "Reports" / "Delta" / "bad.yaml"
        bad_path.parent.mkdir(parents=True)
        bad_path.write_text("invalid: true\n")
        with pytest.raises(SchemaValidationError):
            load_delta_report(bad_path)

    def test_load_file_not_found(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            load_delta_report(tmp_path / "nonexistent.yaml")

    def test_yaml_content_is_readable(self, tmp_path: Path):
        """The saved YAML is human-readable (not flow style)."""
        report = _minimal_report()
        path = save_delta_report(tmp_path, report)
        content = path.read_text()
        # Should not have flow-style indicators like {, }
        assert "run_id: run-001" in content
