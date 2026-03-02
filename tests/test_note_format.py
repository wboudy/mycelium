"""Tests for canonical note format enforcement (MIG-001).

Validates acceptance criteria from §11.1:
  AC-MIG-001-1: Canonical Notes contain only YAML frontmatter + Markdown
                body; no binary blobs.
  AC-MIG-001-2: Schema changes that add fields do not require rewriting
                unchanged canonical notes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mycelium.note_format import (
    NoteFormatError,
    is_binary_file,
    parse_note,
    validate_canonical_note_format,
)


# ─── parse_note ──────────────────────────────────────────────────────────

class TestParseNote:

    def test_valid_note(self):
        content = "---\ntype: source\nid: src-001\n---\n# My Note\nBody text.\n"
        fm, body = parse_note(content)
        assert fm["type"] == "source"
        assert fm["id"] == "src-001"
        assert "My Note" in body

    def test_empty_body(self):
        content = "---\ntype: source\nid: src-001\n---\n"
        fm, body = parse_note(content)
        assert fm["type"] == "source"
        assert body == ""

    def test_multiline_body(self):
        content = "---\ntype: claim\n---\nLine 1\nLine 2\nLine 3\n"
        fm, body = parse_note(content)
        assert "Line 1" in body
        assert "Line 3" in body

    def test_no_opening_delimiter_raises(self):
        with pytest.raises(NoteFormatError, match="must start with '---'"):
            parse_note("type: source\nid: src-001\n")

    def test_no_closing_delimiter_raises(self):
        with pytest.raises(NoteFormatError, match="No closing '---'"):
            parse_note("---\ntype: source\nid: src-001\n")

    def test_empty_frontmatter_raises(self):
        with pytest.raises(NoteFormatError, match="Empty YAML"):
            parse_note("---\n---\nBody\n")

    def test_invalid_yaml_raises(self):
        with pytest.raises(NoteFormatError, match="Invalid YAML"):
            parse_note("---\n: invalid: yaml: [unclosed\n---\nBody\n")

    def test_non_dict_frontmatter_raises(self):
        with pytest.raises(NoteFormatError, match="must be a YAML mapping"):
            parse_note("---\n- list\n- item\n---\nBody\n")

    def test_complex_frontmatter(self):
        content = (
            "---\n"
            "type: source\n"
            "id: src-001\n"
            "status: draft\n"
            "created: 2025-01-01T00:00:00Z\n"
            "updated: 2025-01-01T00:00:00Z\n"
            "tags:\n"
            "  - ai\n"
            "  - research\n"
            "confidence: 0.8\n"
            "---\n"
            "# Title\n\nBody paragraph.\n"
        )
        fm, body = parse_note(content)
        assert fm["tags"] == ["ai", "research"]
        assert fm["confidence"] == 0.8
        assert "Title" in body


# ─── AC-MIG-001-1: no binary blobs ──────────────────────────────────────

class TestBinaryDetection:
    """AC-MIG-001-1: Canonical Notes contain only YAML frontmatter +
    Markdown body; no binary blobs."""

    def test_text_file_not_binary(self, tmp_path: Path):
        f = tmp_path / "note.md"
        f.write_text("---\ntype: source\n---\nBody\n")
        assert is_binary_file(f) is False

    def test_binary_extension_detected(self, tmp_path: Path):
        for ext in [".png", ".jpg", ".pdf", ".exe", ".db"]:
            f = tmp_path / f"file{ext}"
            f.write_bytes(b"\x00data")
            assert is_binary_file(f) is True

    def test_null_bytes_detected(self, tmp_path: Path):
        f = tmp_path / "suspicious.md"
        f.write_bytes(b"---\ntype: source\n---\n\x00binary\x00data\n")
        assert is_binary_file(f) is True

    def test_clean_text_not_binary(self, tmp_path: Path):
        f = tmp_path / "clean.md"
        f.write_text("---\ntype: source\n---\nClean text content\n")
        assert is_binary_file(f) is False


class TestValidateCanonicalFormat:
    """Full validation of canonical note format."""

    def test_valid_note_passes(self, tmp_path: Path):
        f = tmp_path / "note.md"
        f.write_text("---\ntype: source\nid: src-001\n---\n# Title\nBody.\n")
        errors = validate_canonical_note_format(f)
        assert errors == []

    def test_binary_file_rejected(self, tmp_path: Path):
        f = tmp_path / "note.png"
        f.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00")
        errors = validate_canonical_note_format(f)
        assert any("Binary file" in e or "binary" in e.lower() for e in errors)

    def test_null_byte_file_rejected(self, tmp_path: Path):
        f = tmp_path / "note.md"
        f.write_bytes(b"---\ntype: source\n---\n\x00binary\n")
        errors = validate_canonical_note_format(f)
        assert any("binary" in e.lower() or "Binary" in e for e in errors)

    def test_non_utf8_rejected(self, tmp_path: Path):
        f = tmp_path / "note.md"
        f.write_bytes(b"---\ntype: source\n---\n\xff\xfe invalid utf8\n")
        errors = validate_canonical_note_format(f)
        assert len(errors) > 0

    def test_no_frontmatter_rejected(self, tmp_path: Path):
        f = tmp_path / "note.md"
        f.write_text("Just plain markdown\nNo frontmatter.\n")
        errors = validate_canonical_note_format(f)
        assert any("---" in e for e in errors)

    def test_nonexistent_file_error(self, tmp_path: Path):
        errors = validate_canonical_note_format(tmp_path / "nope.md")
        assert any("not found" in e.lower() for e in errors)

    def test_directory_error(self, tmp_path: Path):
        errors = validate_canonical_note_format(tmp_path)
        assert any("Not a file" in e for e in errors)

    def test_vault_relative_in_error_message(self, tmp_path: Path):
        f = tmp_path / "note.md"
        f.write_text("no frontmatter")
        errors = validate_canonical_note_format(
            f, vault_relative="Sources/note.md"
        )
        assert any("Sources/note.md" in e for e in errors)


# ─── AC-MIG-001-2: forward compatibility ────────────────────────────────

class TestForwardCompatibility:
    """AC-MIG-001-2: Schema changes that add fields do not require
    rewriting unchanged canonical notes."""

    def test_unknown_fields_pass_validation(self, tmp_path: Path):
        """Notes with extra unknown fields still validate successfully."""
        f = tmp_path / "note.md"
        f.write_text(
            "---\n"
            "type: source\n"
            "id: src-001\n"
            "status: draft\n"
            "created: 2025-01-01T00:00:00Z\n"
            "updated: 2025-01-01T00:00:00Z\n"
            "future_field: some_value\n"
            "another_new_field: 42\n"
            "---\n"
            "# My Note\n"
        )
        errors = validate_canonical_note_format(f)
        assert errors == []

    def test_old_notes_still_parse(self):
        """A note with only the original shared keys still parses fine."""
        content = (
            "---\n"
            "type: source\n"
            "id: src-001\n"
            "status: draft\n"
            "created: 2025-01-01T00:00:00Z\n"
            "updated: 2025-01-01T00:00:00Z\n"
            "---\n"
            "Body\n"
        )
        fm, body = parse_note(content)
        assert fm["type"] == "source"
        assert "Body" in body

    def test_new_fields_dont_break_old_notes(self):
        """Adding new fields to frontmatter doesn't affect parsing of
        notes that lack those fields."""
        old_content = (
            "---\n"
            "type: claim\n"
            "id: clm-001\n"
            "status: reviewed\n"
            "created: 2025-01-01T00:00:00Z\n"
            "updated: 2025-06-01T00:00:00Z\n"
            "---\n"
            "Old claim body.\n"
        )
        new_content = (
            "---\n"
            "type: claim\n"
            "id: clm-002\n"
            "status: draft\n"
            "created: 2025-07-01T00:00:00Z\n"
            "updated: 2025-07-01T00:00:00Z\n"
            "provenance_chain: [src-001]\n"
            "review_history: []\n"
            "---\n"
            "New claim with extra fields.\n"
        )
        old_fm, old_body = parse_note(old_content)
        new_fm, new_body = parse_note(new_content)
        # Both parse successfully
        assert old_fm["id"] == "clm-001"
        assert new_fm["id"] == "clm-002"
        # Old note doesn't have new fields — that's fine
        assert "provenance_chain" not in old_fm
        assert "provenance_chain" in new_fm

    def test_schema_validation_ignores_unknown_keys(self):
        """validate_shared_frontmatter ignores unknown keys (§4.2.1)."""
        from mycelium.schema import validate_shared_frontmatter

        fm = {
            "type": "source",
            "id": "src-001",
            "status": "draft",
            "created": "2025-01-01T00:00:00Z",
            "updated": "2025-01-01T00:00:00Z",
            "future_field_v2": "value",
            "nested_future": {"key": "val"},
        }
        errors = validate_shared_frontmatter(fm)
        assert errors == []
