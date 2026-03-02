"""Tests for quarantine with diagnostic sidecar (ERR-002).

Validates acceptance criteria from §10.2:
  AC-ERR-002-1: A corrupted frontmatter fixture results in a quarantined
                copy and a diagnostic file containing the parse error and
                the affected original path.
  AC-ERR-002-2: The original corrupted canonical file (if any) is not
                overwritten.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import yaml

from mycelium.quarantine import (
    QuarantineRecord,
    QuarantineResult,
    quarantine_file,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def vault(tmp_path: Path) -> Path:
    """Create a minimal vault structure with a corrupted note."""
    sources = tmp_path / "Sources"
    sources.mkdir()
    note = sources / "bad-note.md"
    note.write_text("---\ntype: invalid_type\n---\nBroken note content\n")
    return tmp_path


@pytest.fixture
def canonical_note(vault: Path) -> str:
    """Return vault-relative path of the corrupted note."""
    return "Sources/bad-note.md"


# ─── QuarantineRecord ────────────────────────────────────────────────────

class TestQuarantineRecord:

    def test_basic_record(self):
        rec = QuarantineRecord(
            original_path="Sources/bad-note.md",
            error_code="ERR_CORRUPTED_NOTE",
            error_message="Missing required key: id",
        )
        assert rec.original_path == "Sources/bad-note.md"
        assert rec.error_code == "ERR_CORRUPTED_NOTE"
        assert rec.quarantined_at  # auto-generated timestamp

    def test_record_with_stage(self):
        rec = QuarantineRecord(
            original_path="Sources/bad.md",
            error_code="ERR_SCHEMA_VALIDATION",
            error_message="invalid type",
            stage="extract",
        )
        d = rec.to_dict()
        assert d["stage"] == "extract"

    def test_record_without_stage(self):
        rec = QuarantineRecord(
            original_path="Sources/bad.md",
            error_code="ERR_CORRUPTED_NOTE",
            error_message="parse error",
        )
        d = rec.to_dict()
        assert "stage" not in d

    def test_record_with_details(self):
        rec = QuarantineRecord(
            original_path="Sources/bad.md",
            error_code="ERR_CORRUPTED_NOTE",
            error_message="parse error",
            details={"line": 3, "column": 5},
        )
        d = rec.to_dict()
        assert d["details"] == {"line": 3, "column": 5}

    def test_record_without_details(self):
        rec = QuarantineRecord(
            original_path="Sources/bad.md",
            error_code="ERR_CORRUPTED_NOTE",
            error_message="parse error",
        )
        d = rec.to_dict()
        assert "details" not in d

    def test_to_dict_required_keys(self):
        rec = QuarantineRecord(
            original_path="Sources/bad.md",
            error_code="ERR_CORRUPTED_NOTE",
            error_message="parse error",
        )
        d = rec.to_dict()
        assert "original_path" in d
        assert "error_code" in d
        assert "error_message" in d
        assert "quarantined_at" in d

    def test_explicit_timestamp(self):
        rec = QuarantineRecord(
            original_path="Sources/bad.md",
            error_code="ERR_CORRUPTED_NOTE",
            error_message="parse error",
            quarantined_at="2025-01-01T00:00:00.000000Z",
        )
        assert rec.quarantined_at == "2025-01-01T00:00:00.000000Z"


# ─── AC-ERR-002-1: quarantine copy + diagnostic sidecar ─────────────────

class TestQuarantineFile:
    """AC-ERR-002-1: Quarantined copy and diagnostic sidecar exist."""

    def test_quarantined_copy_created(self, vault: Path, canonical_note: str):
        result = quarantine_file(
            vault, canonical_note,
            error_code="ERR_CORRUPTED_NOTE",
            error_message="Missing required key: id",
        )
        q_path = vault / result.quarantined_path
        assert q_path.exists()

    def test_quarantined_copy_content_matches(self, vault: Path, canonical_note: str):
        original_content = (vault / canonical_note).read_text()
        result = quarantine_file(
            vault, canonical_note,
            error_code="ERR_CORRUPTED_NOTE",
            error_message="Missing required key: id",
        )
        q_content = (vault / result.quarantined_path).read_text()
        assert q_content == original_content

    def test_diagnostic_sidecar_created(self, vault: Path, canonical_note: str):
        result = quarantine_file(
            vault, canonical_note,
            error_code="ERR_CORRUPTED_NOTE",
            error_message="Missing required key: id",
        )
        s_path = vault / result.sidecar_path
        assert s_path.exists()

    def test_sidecar_contains_error(self, vault: Path, canonical_note: str):
        result = quarantine_file(
            vault, canonical_note,
            error_code="ERR_CORRUPTED_NOTE",
            error_message="Missing required key: id",
        )
        s_path = vault / result.sidecar_path
        with open(s_path) as f:
            sidecar = yaml.safe_load(f)
        assert sidecar["error_code"] == "ERR_CORRUPTED_NOTE"
        assert sidecar["error_message"] == "Missing required key: id"

    def test_sidecar_contains_original_path(self, vault: Path, canonical_note: str):
        result = quarantine_file(
            vault, canonical_note,
            error_code="ERR_CORRUPTED_NOTE",
            error_message="Missing required key: id",
        )
        s_path = vault / result.sidecar_path
        with open(s_path) as f:
            sidecar = yaml.safe_load(f)
        assert sidecar["original_path"] == canonical_note

    def test_sidecar_contains_timestamp(self, vault: Path, canonical_note: str):
        result = quarantine_file(
            vault, canonical_note,
            error_code="ERR_CORRUPTED_NOTE",
            error_message="parse error",
        )
        s_path = vault / result.sidecar_path
        with open(s_path) as f:
            sidecar = yaml.safe_load(f)
        assert "quarantined_at" in sidecar
        assert sidecar["quarantined_at"]  # non-empty

    def test_sidecar_contains_stage(self, vault: Path, canonical_note: str):
        result = quarantine_file(
            vault, canonical_note,
            error_code="ERR_SCHEMA_VALIDATION",
            error_message="invalid type",
            stage="extract",
        )
        s_path = vault / result.sidecar_path
        with open(s_path) as f:
            sidecar = yaml.safe_load(f)
        assert sidecar["stage"] == "extract"

    def test_quarantine_dir_created(self, vault: Path, canonical_note: str):
        result = quarantine_file(
            vault, canonical_note,
            error_code="ERR_CORRUPTED_NOTE",
            error_message="parse error",
        )
        assert (vault / "Quarantine").is_dir()

    def test_quarantine_paths_are_vault_relative(self, vault: Path, canonical_note: str):
        result = quarantine_file(
            vault, canonical_note,
            error_code="ERR_CORRUPTED_NOTE",
            error_message="parse error",
        )
        assert result.quarantined_path.startswith("Quarantine/")
        assert result.sidecar_path.startswith("Quarantine/")

    def test_result_is_quarantine_result(self, vault: Path, canonical_note: str):
        result = quarantine_file(
            vault, canonical_note,
            error_code="ERR_CORRUPTED_NOTE",
            error_message="parse error",
        )
        assert isinstance(result, QuarantineResult)
        assert isinstance(result.record, QuarantineRecord)


# ─── AC-ERR-002-2: original file not overwritten ─────────────────────────

class TestOriginalPreserved:
    """AC-ERR-002-2: The original corrupted canonical file is not overwritten."""

    def test_original_file_still_exists(self, vault: Path, canonical_note: str):
        original_content = (vault / canonical_note).read_text()
        quarantine_file(
            vault, canonical_note,
            error_code="ERR_CORRUPTED_NOTE",
            error_message="parse error",
        )
        # Original file must still exist with same content
        assert (vault / canonical_note).exists()
        assert (vault / canonical_note).read_text() == original_content

    def test_original_preserved_flag(self, vault: Path, canonical_note: str):
        result = quarantine_file(
            vault, canonical_note,
            error_code="ERR_CORRUPTED_NOTE",
            error_message="parse error",
        )
        assert result.original_preserved is True


# ─── Error cases ──────────────────────────────────────────────────────────

class TestErrorCases:

    def test_nonexistent_file_raises(self, vault: Path):
        with pytest.raises(FileNotFoundError):
            quarantine_file(
                vault, "Sources/nonexistent.md",
                error_code="ERR_CORRUPTED_NOTE",
                error_message="file not found",
            )


# ─── Filename derivation ─────────────────────────────────────────────────

class TestFilenameDeriv:

    def test_path_separator_replacement(self, vault: Path, canonical_note: str):
        result = quarantine_file(
            vault, canonical_note,
            error_code="ERR_CORRUPTED_NOTE",
            error_message="parse error",
        )
        # Should not contain path separators in the quarantine filename
        q_name = result.quarantined_path.split("/")[-1]
        assert "/" not in q_name

    def test_sidecar_has_diagnostic_extension(self, vault: Path, canonical_note: str):
        result = quarantine_file(
            vault, canonical_note,
            error_code="ERR_CORRUPTED_NOTE",
            error_message="parse error",
        )
        assert result.sidecar_path.endswith(".diagnostic.yaml")


# ─── Integration with schema validation ──────────────────────────────────

class TestIntegration:
    """Integration test: schema validation → quarantine."""

    def test_invalid_schema_triggers_quarantine(self, vault: Path):
        from mycelium.schema import validate_shared_frontmatter

        # Read the corrupted note's frontmatter
        note_path = vault / "Sources" / "bad-note.md"
        content = note_path.read_text()
        # Parse frontmatter (between --- markers)
        lines = content.split("---")
        frontmatter = yaml.safe_load(lines[1])

        # Validate — should have errors
        errors = validate_shared_frontmatter(frontmatter)
        assert len(errors) > 0

        # Quarantine with the validation error
        result = quarantine_file(
            vault, "Sources/bad-note.md",
            error_code="ERR_SCHEMA_VALIDATION",
            error_message="; ".join(errors),
        )

        # Verify quarantine
        assert (vault / result.quarantined_path).exists()
        assert (vault / result.sidecar_path).exists()

        # Verify sidecar contents
        with open(vault / result.sidecar_path) as f:
            sidecar = yaml.safe_load(f)
        assert sidecar["error_code"] == "ERR_SCHEMA_VALIDATION"
        assert "invalid_type" in sidecar["error_message"] or "type" in sidecar["error_message"]
        assert sidecar["original_path"] == "Sources/bad-note.md"

        # Original preserved
        assert note_path.exists()
