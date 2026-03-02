"""Tests for note I/O and canonical storage substrate (INV-001).

Verifies acceptance criteria:
  AC-INV-001-1: Obsidian opens the Vault and renders YAML frontmatter and
                Markdown body for Notes in Canonical Scope, without requiring
                any non-Markdown store.
  AC-INV-001-2: No canonical knowledge required for operation exists only in a
                non-Markdown store. If indexes exist, deleting/rebuilding them
                does not delete Canonical Notes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mycelium.note_io import (
    list_notes,
    parse_note,
    read_note,
    render_note,
    write_note,
)


# ─── parse_note / render_note round-trip ────────────────────────────────────

class TestParseNote:

    def test_basic_parse(self):
        content = "---\ntype: source\nid: s-001\nstatus: draft\n---\n# Body\nHello"
        fm, body = parse_note(content)
        assert fm["type"] == "source"
        assert fm["id"] == "s-001"
        assert fm["status"] == "draft"
        assert "# Body" in body
        assert "Hello" in body

    def test_empty_body(self):
        content = "---\ntype: claim\nid: c-001\nstatus: draft\n---\n"
        fm, body = parse_note(content)
        assert fm["type"] == "claim"
        assert body == ""

    def test_multiline_body(self):
        content = "---\nid: x\n---\nLine 1\nLine 2\nLine 3\n"
        fm, body = parse_note(content)
        assert fm["id"] == "x"
        assert "Line 1" in body
        assert "Line 3" in body

    def test_no_frontmatter_delimiter_raises(self):
        with pytest.raises(ValueError, match="frontmatter delimiter"):
            parse_note("No frontmatter here")

    def test_no_closing_delimiter_raises(self):
        with pytest.raises(ValueError):
            parse_note("---\nid: x\nno closing")

    def test_non_dict_frontmatter_raises(self):
        with pytest.raises(ValueError, match="mapping"):
            parse_note("---\n- list\n- item\n---\nbody")

    def test_empty_frontmatter(self):
        content = "---\n---\nbody text"
        fm, body = parse_note(content)
        assert fm == {}
        assert "body text" in body


class TestRenderNote:

    def test_basic_render(self):
        fm = {"type": "source", "id": "s-001", "status": "draft"}
        body = "# My Source\nContent here."
        result = render_note(fm, body)
        assert result.startswith("---\n")
        assert "type: source" in result
        assert result.count("---") == 2
        assert "# My Source" in result
        assert "Content here." in result

    def test_render_empty_body(self):
        fm = {"id": "x"}
        result = render_note(fm, "")
        assert result.startswith("---\n")
        assert result.endswith("---\n")


class TestRoundTrip:
    """AC-INV-001-1: Notes are self-contained Markdown+YAML."""

    def test_round_trip_preserves_data(self):
        original_fm = {
            "type": "concept",
            "id": "con-001",
            "status": "draft",
            "created": "2026-03-01T00:00:00Z",
            "updated": "2026-03-01T12:00:00Z",
            "tags": ["test", "demo"],
            "confidence": 0.85,
        }
        original_body = "# Concept\n\nThis is a test concept.\n\n## Details\nMore content."

        rendered = render_note(original_fm, original_body)
        parsed_fm, parsed_body = parse_note(rendered)

        assert parsed_fm["type"] == "concept"
        assert parsed_fm["id"] == "con-001"
        assert parsed_fm["status"] == "draft"
        assert parsed_fm["tags"] == ["test", "demo"]
        assert parsed_fm["confidence"] == 0.85
        assert "# Concept" in parsed_body
        assert "More content." in parsed_body

    def test_round_trip_with_unicode(self):
        fm = {"id": "uni-001", "title": "Über die Quantenmechanik"}
        body = "Schrödinger's 猫 equation: ψ"
        rendered = render_note(fm, body)
        parsed_fm, parsed_body = parse_note(rendered)
        assert parsed_fm["title"] == "Über die Quantenmechanik"
        assert "猫" in parsed_body


# ─── File I/O ──────────────────────────────────────────────────────────────

class TestReadWriteNote:
    """AC-INV-001-1: Notes are readable from disk as Markdown+YAML."""

    def test_write_and_read(self, tmp_path: Path):
        note_path = tmp_path / "Sources" / "test-note.md"
        fm = {"type": "source", "id": "s-001", "status": "canon"}
        body = "# Test Note\nCanonical content."

        write_note(note_path, fm, body)

        assert note_path.exists()
        read_fm, read_body = read_note(note_path)
        assert read_fm["type"] == "source"
        assert read_fm["status"] == "canon"
        assert "Canonical content." in read_body

    def test_write_creates_directories(self, tmp_path: Path):
        note_path = tmp_path / "deep" / "nested" / "note.md"
        write_note(note_path, {"id": "x"}, "body")
        assert note_path.exists()

    def test_write_no_mkdir(self, tmp_path: Path):
        note_path = tmp_path / "nonexistent" / "note.md"
        with pytest.raises(FileNotFoundError):
            write_note(note_path, {"id": "x"}, "body", mkdir=False)

    def test_read_nonexistent_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            read_note(tmp_path / "nope.md")

    def test_file_is_valid_utf8(self, tmp_path: Path):
        note_path = tmp_path / "note.md"
        write_note(note_path, {"id": "u"}, "Héllo wörld")
        raw = note_path.read_bytes()
        raw.decode("utf-8")  # should not raise


# ─── AC-INV-001-2: Canonical notes survive index deletion ──────────────────

class TestCanonicalSurvivesIndexDeletion:
    """AC-INV-001-2: Deleting/rebuilding Indexes/ does not delete
    Canonical Notes."""

    def test_canonical_notes_unaffected_by_index_deletion(self, tmp_path: Path):
        vault = tmp_path
        # Create canonical notes
        write_note(
            vault / "Sources" / "s1.md",
            {"type": "source", "id": "s1", "status": "canon"},
            "Source content",
        )
        write_note(
            vault / "Claims" / "c1.md",
            {"type": "claim", "id": "c1", "status": "canon"},
            "Claim content",
        )

        # Create an index file
        idx_dir = vault / "Indexes"
        idx_dir.mkdir()
        (idx_dir / "cache.json").write_text('{"cached": true}')

        # Verify everything exists
        assert (vault / "Sources" / "s1.md").exists()
        assert (vault / "Claims" / "c1.md").exists()
        assert (vault / "Indexes" / "cache.json").exists()

        # Delete Indexes/
        import shutil
        shutil.rmtree(idx_dir)

        # Canonical notes must still exist and be readable
        assert (vault / "Sources" / "s1.md").exists()
        assert (vault / "Claims" / "c1.md").exists()
        fm, body = read_note(vault / "Sources" / "s1.md")
        assert fm["id"] == "s1"
        assert "Source content" in body


# ─── list_notes ────────────────────────────────────────────────────────────

class TestListNotes:

    def test_list_canonical_notes(self, tmp_path: Path):
        vault = tmp_path
        write_note(vault / "Sources" / "a.md", {"id": "a"}, "A")
        write_note(vault / "Sources" / "b.md", {"id": "b"}, "B")
        (vault / "Sources" / "not-a-note.txt").write_text("ignore")

        notes = list_notes(vault, "Sources")
        assert len(notes) == 2
        names = [n.name for n in notes]
        assert "a.md" in names
        assert "b.md" in names

    def test_list_empty_dir(self, tmp_path: Path):
        (tmp_path / "Sources").mkdir()
        assert list_notes(tmp_path, "Sources") == []

    def test_list_nonexistent_dir(self, tmp_path: Path):
        assert list_notes(tmp_path, "NoSuchDir") == []

    def test_list_nested_notes(self, tmp_path: Path):
        vault = tmp_path
        write_note(vault / "Sources" / "sub" / "deep.md", {"id": "d"}, "D")
        notes = list_notes(vault, "Sources")
        assert len(notes) == 1
        assert notes[0].name == "deep.md"
