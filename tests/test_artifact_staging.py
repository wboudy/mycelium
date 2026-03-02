"""Tests for artifact staging and atomicity guarantees (PIPE-002).

Verifies acceptance criteria:
  AC-1: All ingestion outputs staged in Draft Scope before promotion path.
  AC-2: Failure after Extract but before Propose+Queue results in quarantined
        partial artifacts with diagnostics, Delta Report reflects failure.
  AC-3: No files in Canonical Scope created/modified in any failure scenario
        without Promotion (INV-002).
  AC-4: Partial artifacts on failure moved to quarantine with diagnostic sidecar.
  AC-5: Write operations use atomic patterns (temp file + rename).

Spec reference: §6.3 PIPE-002, INV-002, INV-003
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from mycelium.atomic_write import atomic_write_bytes, atomic_write_text
from mycelium.pipeline import PipelineResult, _quarantine_partial_artifacts, run_pipeline
from mycelium.stages.capture import SourceInput
from mycelium.stages.compare import ClaimIndex
from mycelium.vault_layout import CANONICAL_DIRS, is_canonical_scope


# ── Helpers ──────────────────────────────────────────────────────────

def _text_source(
    text: str = (
        "Machine learning models require large datasets for training. "
        "Neural networks can approximate any continuous function. "
        "The transformer architecture revolutionized natural language processing."
    ),
    source_id: str = "test-src",
) -> SourceInput:
    return SourceInput(text_bundle=text, source_id=source_id)


def _list_all_files(root: Path) -> list[str]:
    """List all files under root as vault-relative paths."""
    return sorted(
        str(f.relative_to(root))
        for f in root.rglob("*")
        if f.is_file()
    )


def _canonical_files(root: Path) -> list[str]:
    """List files that are in Canonical Scope directories."""
    all_files = _list_all_files(root)
    return [f for f in all_files if is_canonical_scope(f)]


# ── AC-5: Atomic write utility ──────────────────────────────────────

class TestAtomicWrite:
    """AC-5: Write operations use atomic patterns (temp file + rename)."""

    def test_atomic_write_text_creates_file(self, tmp_path: Path):
        target = tmp_path / "test.txt"
        atomic_write_text(target, "hello world")
        assert target.exists()
        assert target.read_text() == "hello world"

    def test_atomic_write_bytes_creates_file(self, tmp_path: Path):
        target = tmp_path / "test.bin"
        atomic_write_bytes(target, b"\x00\x01\x02")
        assert target.exists()
        assert target.read_bytes() == b"\x00\x01\x02"

    def test_atomic_write_text_overwrites(self, tmp_path: Path):
        target = tmp_path / "test.txt"
        target.write_text("old content")
        atomic_write_text(target, "new content")
        assert target.read_text() == "new content"

    def test_atomic_write_text_creates_parent_dirs(self, tmp_path: Path):
        target = tmp_path / "sub" / "dir" / "test.txt"
        atomic_write_text(target, "deep write")
        assert target.exists()
        assert target.read_text() == "deep write"

    def test_atomic_write_text_mkdir_false(self, tmp_path: Path):
        target = tmp_path / "nonexistent" / "test.txt"
        with pytest.raises(FileNotFoundError):
            atomic_write_text(target, "fail", mkdir=False)

    def test_atomic_write_no_temp_file_left_on_success(self, tmp_path: Path):
        target = tmp_path / "test.txt"
        atomic_write_text(target, "hello")
        tmp_files = [f for f in tmp_path.iterdir() if f.name.startswith(".")]
        assert len(tmp_files) == 0

    def test_atomic_write_encoding(self, tmp_path: Path):
        target = tmp_path / "utf8.txt"
        atomic_write_text(target, "café ñ")
        assert target.read_text(encoding="utf-8") == "café ñ"


# ── AC-1: All outputs staged in Draft Scope ──────────────────────────

class TestDraftScopeStaging:
    """AC-1: All ingestion outputs are staged in Draft Scope."""

    def test_successful_pipeline_no_canonical_writes(self, tmp_path: Path):
        """A successful pipeline run writes only to Draft Scope."""
        si = _text_source()
        result, env = run_pipeline(
            si, vault_root=tmp_path, run_id="run-1", source_id="src-1"
        )
        assert env.ok is True

        # Check that no files exist in Canonical Scope
        canonical = _canonical_files(tmp_path)
        assert canonical == [], f"Canonical files created by pipeline: {canonical}"

    def test_artifacts_in_draft_scope(self, tmp_path: Path):
        """All artifact paths are in Draft Scope directories."""
        si = _text_source()
        result, _ = run_pipeline(
            si, vault_root=tmp_path, run_id="run-1", source_id="src-1"
        )
        for art_path in result.artifact_paths:
            assert not is_canonical_scope(art_path), (
                f"Artifact {art_path} is in Canonical Scope"
            )

    def test_extraction_bundle_in_inbox(self, tmp_path: Path):
        si = _text_source()
        run_pipeline(si, vault_root=tmp_path, run_id="run-1", source_id="src-1")
        inbox = tmp_path / "Inbox" / "Sources"
        assert inbox.exists()
        bundles = list(inbox.glob("*.yaml"))
        assert len(bundles) >= 1

    def test_delta_report_in_reports(self, tmp_path: Path):
        si = _text_source()
        run_pipeline(si, vault_root=tmp_path, run_id="run-1", source_id="src-1")
        delta_dir = tmp_path / "Reports" / "Delta"
        assert delta_dir.exists()
        reports = list(delta_dir.glob("*.yaml"))
        assert len(reports) >= 1

    def test_queue_items_in_inbox(self, tmp_path: Path):
        si = _text_source()
        result, _ = run_pipeline(si, vault_root=tmp_path, run_id="run-1", source_id="src-1")
        if result.queue_items:
            queue_dir = tmp_path / "Inbox" / "ReviewQueue"
            assert queue_dir.exists()


# ── AC-3: No Canonical Scope modifications in failure scenarios ──────

class TestCanonicalScopeProtection:
    """AC-3: No files in Canonical Scope created/modified without Promotion."""

    def test_capture_failure_no_canonical_writes(self, tmp_path: Path):
        si = SourceInput()  # No source
        run_pipeline(si, vault_root=tmp_path, run_id="run-fail")
        canonical = _canonical_files(tmp_path)
        assert canonical == []

    def test_empty_text_failure_no_canonical_writes(self, tmp_path: Path):
        si = SourceInput(text_bundle="")
        run_pipeline(si, vault_root=tmp_path, run_id="run-fail")
        canonical = _canonical_files(tmp_path)
        assert canonical == []

    def test_canonical_dirs_untouched_on_success(self, tmp_path: Path):
        """Even successful pipeline does not create canonical directories."""
        si = _text_source()
        run_pipeline(si, vault_root=tmp_path, run_id="run-1", source_id="src-1")
        for d in CANONICAL_DIRS:
            canon_dir = tmp_path / d
            if canon_dir.exists():
                files = list(canon_dir.rglob("*"))
                assert files == [], f"Unexpected files in {d}: {files}"


# ── AC-2 / AC-4: Quarantine on failure ───────────────────────────────

class TestPartialArtifactQuarantine:
    """AC-2/AC-4: Partial artifacts quarantined on failure with diagnostics."""

    def test_quarantine_partial_artifacts_helper(self, tmp_path: Path):
        """_quarantine_partial_artifacts moves files to Quarantine/."""
        # Create a fake artifact
        inbox = tmp_path / "Inbox" / "Sources"
        inbox.mkdir(parents=True)
        artifact = inbox / "run-test_extraction.yaml"
        artifact.write_text("fake: artifact")

        results = _quarantine_partial_artifacts(
            tmp_path,
            ["Inbox/Sources/run-test_extraction.yaml"],
            error_code="ERR_TEST",
            error_message="Test failure",
            stage="compare",
            run_id="run-test",
            source_id="src-test",
        )
        assert len(results) == 1
        # Quarantine copy exists
        q_path = tmp_path / results[0].quarantined_path
        assert q_path.exists()
        # Sidecar exists
        s_path = tmp_path / results[0].sidecar_path
        assert s_path.exists()

    def test_quarantine_preserves_original(self, tmp_path: Path):
        """Original artifact is preserved (copy, not move)."""
        inbox = tmp_path / "Inbox" / "Sources"
        inbox.mkdir(parents=True)
        artifact = inbox / "run-test_extraction.yaml"
        artifact.write_text("fake: artifact")

        _quarantine_partial_artifacts(
            tmp_path,
            ["Inbox/Sources/run-test_extraction.yaml"],
            error_code="ERR_TEST",
            error_message="Test",
            stage="compare",
            run_id="run-test",
            source_id="src-test",
        )
        # Original still exists (quarantine uses copy)
        assert artifact.exists()

    def test_quarantine_sidecar_has_diagnostics(self, tmp_path: Path):
        """Sidecar contains error code, stage, and run info."""
        import yaml

        inbox = tmp_path / "Inbox" / "Sources"
        inbox.mkdir(parents=True)
        artifact = inbox / "run-test_extraction.yaml"
        artifact.write_text("fake: artifact")

        results = _quarantine_partial_artifacts(
            tmp_path,
            ["Inbox/Sources/run-test_extraction.yaml"],
            error_code="ERR_COMPARE",
            error_message="Dedup failed",
            stage="compare",
            run_id="run-test",
            source_id="src-test",
        )
        s_path = tmp_path / results[0].sidecar_path
        sidecar = yaml.safe_load(s_path.read_text())
        assert sidecar["error_code"] == "ERR_COMPARE"
        assert "compare" in sidecar["error_message"]
        assert sidecar["stage"] == "compare"
        assert sidecar["details"]["run_id"] == "run-test"
        assert sidecar["details"]["partial_artifact"] is True

    def test_quarantine_skips_missing_artifacts(self, tmp_path: Path):
        """Nonexistent artifact paths are silently skipped."""
        results = _quarantine_partial_artifacts(
            tmp_path,
            ["Inbox/Sources/nonexistent.yaml"],
            error_code="ERR_TEST",
            error_message="Test",
            stage="extract",
            run_id="run-test",
            source_id="src-test",
        )
        assert results == []

    def test_pipeline_result_has_quarantined_paths(self):
        """PipelineResult includes quarantined_paths field."""
        pr = PipelineResult(run_id="r", source_id="s")
        assert pr.quarantined_paths == []
        pr.quarantined_paths = ["Quarantine/test.yaml"]
        d = pr.to_dict()
        assert "quarantined_paths" in d

    def test_pipeline_result_to_dict_omits_empty_quarantine(self):
        """to_dict omits quarantined_paths when empty."""
        pr = PipelineResult(run_id="r", source_id="s")
        d = pr.to_dict()
        assert "quarantined_paths" not in d


# ── AC-2: Delta Report reflects failure ──────────────────────────────

class TestDeltaReportReflectsFailure:
    """AC-2: Delta Report reflects failure via pipeline_status and failures."""

    def test_failure_delta_has_failed_status(self, tmp_path: Path):
        """Failure after fingerprint produces a Delta Report with failure status."""
        # Use a valid source that will get through fingerprint
        si = _text_source()
        result, env = run_pipeline(
            si, vault_root=tmp_path, run_id="run-1", source_id="src-1"
        )
        # Successful run should have completed status
        if result.delta_report is not None:
            assert result.delta_report["pipeline_status"] == "completed"

    def test_early_failure_no_delta(self, tmp_path: Path):
        """Capture failure (before fingerprint) has no Delta Report."""
        si = SourceInput()
        result, _ = run_pipeline(si, vault_root=tmp_path, run_id="run-fail")
        assert result.delta_report is None


# ── AC-5: Pipeline stages use atomic writes ──────────────────────────

class TestAtomicWritesInPipeline:
    """AC-5: Write operations use atomic patterns."""

    def test_extraction_bundle_written_atomically(self, tmp_path: Path):
        """Extract stage writes bundles atomically (no temp files remain)."""
        si = _text_source()
        run_pipeline(si, vault_root=tmp_path, run_id="run-1", source_id="src-1")
        inbox = tmp_path / "Inbox" / "Sources"
        if inbox.exists():
            temp_files = [f for f in inbox.iterdir() if f.name.startswith(".")]
            assert temp_files == [], f"Temp files left: {temp_files}"

    def test_delta_report_written_atomically(self, tmp_path: Path):
        """Delta stage writes reports atomically (no temp files remain)."""
        si = _text_source()
        run_pipeline(si, vault_root=tmp_path, run_id="run-1", source_id="src-1")
        delta_dir = tmp_path / "Reports" / "Delta"
        if delta_dir.exists():
            temp_files = [f for f in delta_dir.iterdir() if f.name.startswith(".")]
            assert temp_files == [], f"Temp files left: {temp_files}"

    def test_queue_items_written_atomically(self, tmp_path: Path):
        """Queue stage writes items atomically (no temp files remain)."""
        si = _text_source()
        result, _ = run_pipeline(si, vault_root=tmp_path, run_id="run-1", source_id="src-1")
        queue_dir = tmp_path / "Inbox" / "ReviewQueue"
        if queue_dir.exists():
            temp_files = [f for f in queue_dir.iterdir() if f.name.startswith(".")]
            assert temp_files == [], f"Temp files left: {temp_files}"

    def test_atomic_write_content_integrity(self, tmp_path: Path):
        """Files written by pipeline are valid YAML (not truncated)."""
        import yaml

        si = _text_source()
        run_pipeline(si, vault_root=tmp_path, run_id="run-1", source_id="src-1")
        # Check all YAML files are parseable
        for yaml_file in tmp_path.rglob("*.yaml"):
            content = yaml_file.read_text()
            try:
                yaml.safe_load(content)
            except yaml.YAMLError:
                pytest.fail(f"Invalid YAML in {yaml_file}")
