"""Tests for wikilink resolution and strict mode checking (LNK-001).

Verifies acceptance criteria:
  AC-LNK-001-1: Link-check helper reports unresolved links;
                 Strict Mode fails if unresolved count > 0.
  AC-LNK-001-2: Non-Strict Mode reports unresolved links as warnings.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from mycelium.wikilink import (
    check_wikilinks,
    extract_wikilinks,
    resolve_wikilink,
    validate_wikilinks_strict,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_note(vault: Path, rel_path: str, content: str) -> Path:
    """Create a note at the given vault-relative path."""
    full = vault / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")
    return full


# ─── extract_wikilinks ───────────────────────────────────────────────────

class TestExtractWikilinks:

    def test_no_links(self):
        assert extract_wikilinks("No links here.") == []

    def test_single_link(self):
        assert extract_wikilinks("See [[Sources/s-001]].") == ["Sources/s-001"]

    def test_multiple_links(self):
        content = "See [[Sources/a]] and [[Claims/b]]."
        result = extract_wikilinks(content)
        assert result == ["Sources/a", "Claims/b"]

    def test_link_with_alias(self):
        content = "See [[Sources/s-001|my source]]."
        result = extract_wikilinks(content)
        assert result == ["Sources/s-001"]

    def test_link_with_spaces(self):
        content = "See [[Sources/my note]]."
        result = extract_wikilinks(content)
        assert result == ["Sources/my note"]

    def test_bare_note_id(self):
        content = "See [[s-001]]."
        result = extract_wikilinks(content)
        assert result == ["s-001"]

    def test_multiline(self):
        content = "Line 1 [[a]].\nLine 2 [[b]].\n"
        result = extract_wikilinks(content)
        assert result == ["a", "b"]

    def test_nested_brackets_ignored(self):
        # Only valid wikilinks are captured
        content = "Not a link: [regular](url). A link: [[real]]."
        result = extract_wikilinks(content)
        assert result == ["real"]

    def test_empty_string(self):
        assert extract_wikilinks("") == []

    def test_adjacent_links(self):
        content = "[[a]][[b]]"
        result = extract_wikilinks(content)
        assert result == ["a", "b"]


# ─── resolve_wikilink ───────────────────────────────────────────────────

class TestResolveWikilink:

    def test_direct_path(self, tmp_path: Path):
        _write_note(tmp_path, "Sources/s-001.md", "content")
        result = resolve_wikilink("Sources/s-001", tmp_path)
        assert result is not None
        assert result.name == "s-001.md"

    def test_unresolved(self, tmp_path: Path):
        result = resolve_wikilink("Sources/nonexistent", tmp_path)
        assert result is None

    def test_basename_search_in_canonical(self, tmp_path: Path):
        _write_note(tmp_path, "Sources/s-001.md", "content")
        # Search by bare basename (no directory prefix)
        result = resolve_wikilink("s-001", tmp_path)
        assert result is not None
        assert result.name == "s-001.md"

    def test_basename_search_claims(self, tmp_path: Path):
        _write_note(tmp_path, "Claims/c-001.md", "content")
        result = resolve_wikilink("c-001", tmp_path)
        assert result is not None
        assert result.name == "c-001.md"

    def test_basename_search_concepts(self, tmp_path: Path):
        _write_note(tmp_path, "Concepts/con-001.md", "content")
        result = resolve_wikilink("con-001", tmp_path)
        assert result is not None

    def test_with_extension(self, tmp_path: Path):
        _write_note(tmp_path, "Sources/s-001.md", "content")
        result = resolve_wikilink("Sources/s-001.md", tmp_path)
        assert result is not None

    def test_directory_not_resolved(self, tmp_path: Path):
        (tmp_path / "Sources").mkdir(parents=True)
        result = resolve_wikilink("Sources", tmp_path)
        assert result is None


# ─── check_wikilinks ─────────────────────────────────────────────────────

class TestCheckWikilinks:

    def test_no_notes(self, tmp_path: Path):
        result = check_wikilinks(tmp_path)
        assert result == []

    def test_all_resolved(self, tmp_path: Path):
        _write_note(tmp_path, "Sources/s-001.md", "See [[Sources/s-002]].")
        _write_note(tmp_path, "Sources/s-002.md", "Content.")
        result = check_wikilinks(tmp_path)
        assert result == []

    def test_unresolved_reported(self, tmp_path: Path):
        _write_note(tmp_path, "Sources/s-001.md", "See [[Sources/missing]].")
        result = check_wikilinks(tmp_path)
        assert len(result) == 1
        assert result[0]["target"] == "Sources/missing"
        assert result[0]["source_file"] == "Sources/s-001.md"

    def test_multiple_unresolved(self, tmp_path: Path):
        _write_note(
            tmp_path, "Claims/c-001.md",
            "See [[missing-a]] and [[missing-b]].",
        )
        result = check_wikilinks(tmp_path)
        assert len(result) == 2

    def test_mixed_resolved_and_unresolved(self, tmp_path: Path):
        _write_note(tmp_path, "Sources/s-001.md", "Content.")
        _write_note(
            tmp_path, "Sources/s-002.md",
            "See [[Sources/s-001]] and [[Sources/nope]].",
        )
        result = check_wikilinks(tmp_path)
        assert len(result) == 1
        assert result[0]["target"] == "Sources/nope"

    def test_cross_scope_resolution(self, tmp_path: Path):
        """Wikilinks in Sources/ can resolve to Claims/."""
        _write_note(tmp_path, "Claims/c-001.md", "A claim.")
        _write_note(tmp_path, "Sources/s-001.md", "See [[Claims/c-001]].")
        result = check_wikilinks(tmp_path)
        assert result == []

    def test_basename_resolution_in_check(self, tmp_path: Path):
        """Bare note IDs resolve via basename search."""
        _write_note(tmp_path, "Sources/s-001.md", "Content.")
        _write_note(tmp_path, "Claims/c-001.md", "See [[s-001]].")
        result = check_wikilinks(tmp_path)
        assert result == []

    def test_only_canonical_scope_scanned(self, tmp_path: Path):
        """Draft scope files are not scanned for broken links."""
        _write_note(
            tmp_path, "Inbox/Sources/draft.md",
            "See [[totally-missing]].",
        )
        result = check_wikilinks(tmp_path)
        assert result == []

    def test_multiple_files_multiple_links(self, tmp_path: Path):
        _write_note(tmp_path, "Sources/s-001.md", "See [[nope-a]].")
        _write_note(tmp_path, "Claims/c-001.md", "See [[nope-b]].")
        result = check_wikilinks(tmp_path)
        assert len(result) == 2
        targets = {r["target"] for r in result}
        assert targets == {"nope-a", "nope-b"}


# ─── AC-LNK-001-1 / AC-LNK-001-2: validate_wikilinks_strict ────────────

class TestValidateWikilinksStrict:

    def test_no_unresolved(self, tmp_path: Path):
        _write_note(tmp_path, "Sources/s-001.md", "No links.")
        unresolved, warnings = validate_wikilinks_strict(tmp_path)
        assert unresolved == []
        assert warnings == []

    def test_unresolved_produces_warnings(self, tmp_path: Path):
        """AC-LNK-001-2: Unresolved links are reported as warnings."""
        _write_note(tmp_path, "Sources/s-001.md", "See [[missing]].")
        unresolved, warnings = validate_wikilinks_strict(tmp_path)
        assert len(unresolved) == 1
        assert len(warnings) == 1
        assert warnings[0]["code"] == "WARN_UNRESOLVED_WIKILINK"
        assert "missing" in warnings[0]["message"]

    def test_strict_mode_fails_on_unresolved(self, tmp_path: Path):
        """AC-LNK-001-1: Strict Mode fails if unresolved count > 0."""
        _write_note(tmp_path, "Sources/s-001.md", "See [[missing]].")
        unresolved, _ = validate_wikilinks_strict(tmp_path)
        # In strict mode, caller checks: len(unresolved) > 0 → fail
        assert len(unresolved) > 0

    def test_warning_format_for_delta_report(self, tmp_path: Path):
        """Warnings are suitable for Delta Report warnings array."""
        _write_note(tmp_path, "Sources/s-001.md", "See [[bad-link]].")
        _, warnings = validate_wikilinks_strict(tmp_path)
        w = warnings[0]
        assert "code" in w
        assert "message" in w
        assert isinstance(w["code"], str)
        assert isinstance(w["message"], str)

    def test_multiple_unresolved_links(self, tmp_path: Path):
        _write_note(
            tmp_path, "Sources/s-001.md",
            "See [[a]] and [[b]] and [[c]].",
        )
        unresolved, warnings = validate_wikilinks_strict(tmp_path)
        assert len(unresolved) == 3
        assert len(warnings) == 3

    def test_empty_vault(self, tmp_path: Path):
        unresolved, warnings = validate_wikilinks_strict(tmp_path)
        assert unresolved == []
        assert warnings == []

    def test_resolved_links_no_warnings(self, tmp_path: Path):
        _write_note(tmp_path, "Sources/s-001.md", "Content.")
        _write_note(tmp_path, "Sources/s-002.md", "See [[Sources/s-001]].")
        unresolved, warnings = validate_wikilinks_strict(tmp_path)
        assert unresolved == []
        assert warnings == []
