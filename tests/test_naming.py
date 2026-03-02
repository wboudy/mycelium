"""
Tests for Note ID naming rules and filename alignment (NAM-001).

Verifies all three acceptance criteria from §4.3.1:
  AC-NAM-001-1: Validator rejects Notes where filename and id differ.
  AC-NAM-001-2: Validator rejects id strings outside allowed patterns.
  AC-NAM-001-3: Machine-generated notes default to hybrid <slug>--h-<12hex>.
"""

from __future__ import annotations

import pytest

from mycelium.naming import (
    generate_hash_id,
    generate_hash_suffix,
    generate_hybrid_id,
    is_valid_note_id,
    slug_from_text,
    validate_filename_id_match,
    validate_note_id,
)


# ─── AC-NAM-001-2: id pattern validation ────────────────────────────────

class TestValidNoteId:
    """AC-NAM-001-2: Rejects id strings outside allowed patterns."""

    # Slug-only valid
    @pytest.mark.parametrize("note_id", [
        "aspirin",
        "aspirin-reduces-inflammation",
        "source-001",
        "a",
        "a-b-c-d-e",
        "abc123",
        "my-3-notes",
    ])
    def test_slug_only_valid(self, note_id: str):
        assert is_valid_note_id(note_id) is True
        assert validate_note_id(note_id) == []

    # Hash-only valid
    @pytest.mark.parametrize("note_id", [
        "h-" + "a" * 12,
        "h-" + "0" * 64,
        "h-abcdef012345",
        "h-" + "f" * 32,
    ])
    def test_hash_only_valid(self, note_id: str):
        assert is_valid_note_id(note_id) is True
        assert validate_note_id(note_id) == []

    # Hybrid valid
    @pytest.mark.parametrize("note_id", [
        "aspirin-study--h-abcdef012345",
        "my-note--h-000000000000",
        "a--h-123456789abc",
    ])
    def test_hybrid_valid(self, note_id: str):
        assert is_valid_note_id(note_id) is True
        assert validate_note_id(note_id) == []

    # Invalid ids
    @pytest.mark.parametrize("note_id", [
        "",                          # empty
        "Aspirin",                   # uppercase
        "aspirin_study",             # underscore
        "aspirin study",             # space
        "aspirin--study",            # double dash without h- prefix
        # "h-abc" is valid as slug-only (segments: "h", "abc")
        "h-ABCDEF012345",            # uppercase hex
        "h-",                        # no hex digits
        "aspirin--h-abc",            # hybrid hash too short
        "aspirin--h-" + "a" * 13,   # hybrid hash too long
        "Aspirin--h-abcdef012345",   # hybrid slug has uppercase
        "--h-abcdef012345",          # hybrid missing slug
        "aspirin--h-",               # hybrid missing hash
        ".hidden",                   # starts with dot
        "note/path",                 # contains slash
    ])
    def test_invalid_ids(self, note_id: str):
        assert is_valid_note_id(note_id) is False
        errors = validate_note_id(note_id)
        assert len(errors) >= 1

    def test_non_string_id(self):
        errors = validate_note_id(42)  # type: ignore[arg-type]
        assert len(errors) >= 1

    def test_none_id(self):
        errors = validate_note_id(None)  # type: ignore[arg-type]
        assert len(errors) >= 1


# ─── AC-NAM-001-1: filename/id alignment ────────────────────────────────

class TestFilenameIdMatch:
    """AC-NAM-001-1: Rejects Notes where filename and id differ."""

    def test_matching_filename(self):
        errors = validate_filename_id_match("aspirin-study.md", "aspirin-study")
        assert errors == []

    def test_matching_with_path(self):
        errors = validate_filename_id_match(
            "Sources/aspirin-study.md", "aspirin-study"
        )
        assert errors == []

    def test_mismatched_filename(self):
        errors = validate_filename_id_match("wrong-name.md", "aspirin-study")
        assert len(errors) >= 1
        assert "aspirin-study.md" in errors[0]

    def test_missing_md_extension(self):
        errors = validate_filename_id_match("aspirin-study.yaml", "aspirin-study")
        assert len(errors) >= 1

    def test_hybrid_id_filename(self):
        note_id = "aspirin-study--h-abcdef012345"
        errors = validate_filename_id_match(f"{note_id}.md", note_id)
        assert errors == []

    def test_hash_id_filename(self):
        note_id = "h-abcdef012345"
        errors = validate_filename_id_match(f"{note_id}.md", note_id)
        assert errors == []


# ─── AC-NAM-001-3: machine-generated hybrid IDs ─────────────────────────

class TestHybridIdGeneration:
    """AC-NAM-001-3: Machine-generated notes default to hybrid form."""

    def test_generate_hybrid_id(self):
        note_id = generate_hybrid_id("Aspirin reduces inflammation", "https://example.com")
        assert is_valid_note_id(note_id)
        assert "--h-" in note_id

    def test_hybrid_id_is_deterministic(self):
        id1 = generate_hybrid_id("My Note Title", "content-hash-source")
        id2 = generate_hybrid_id("My Note Title", "content-hash-source")
        assert id1 == id2

    def test_different_content_different_hash(self):
        id1 = generate_hybrid_id("Same Title", "content-a")
        id2 = generate_hybrid_id("Same Title", "content-b")
        assert id1 != id2

    def test_different_title_different_slug(self):
        id1 = generate_hybrid_id("Title A", "same-content")
        id2 = generate_hybrid_id("Title B", "same-content")
        # Slugs differ, but hashes are the same
        assert id1.split("--h-")[0] != id2.split("--h-")[0]
        assert id1.split("--h-")[1] == id2.split("--h-")[1]

    def test_hybrid_id_matches_pattern(self):
        note_id = generate_hybrid_id("Complex: Title! With #Symbols", "data")
        assert is_valid_note_id(note_id)

    def test_hybrid_slug_max_words(self):
        long_title = " ".join(f"word{i}" for i in range(20))
        note_id = generate_hybrid_id(long_title, "x", max_words=3)
        slug_part = note_id.split("--h-")[0]
        assert len(slug_part.split("-")) <= 3


# ─── Slug generation ────────────────────────────────────────────────────

class TestSlugFromText:

    def test_simple_text(self):
        assert slug_from_text("Hello World") == "hello-world"

    def test_unicode_normalized(self):
        assert slug_from_text("café résumé") == "cafe-resume"

    def test_special_chars_stripped(self):
        slug = slug_from_text("What's the impact?")
        assert slug == "whats-the-impact"

    def test_max_words(self):
        slug = slug_from_text("one two three four five six seven", max_words=3)
        assert slug == "one-two-three"

    def test_empty_gives_untitled(self):
        assert slug_from_text("") == "untitled"

    def test_symbols_only_gives_untitled(self):
        assert slug_from_text("!@#$%") == "untitled"


# ─── Hash generation ────────────────────────────────────────────────────

class TestHashGeneration:

    def test_hash_suffix_length(self):
        suffix = generate_hash_suffix("test", length=12)
        assert len(suffix) == 12

    def test_hash_suffix_deterministic(self):
        s1 = generate_hash_suffix("same-input")
        s2 = generate_hash_suffix("same-input")
        assert s1 == s2

    def test_hash_id_valid(self):
        note_id = generate_hash_id("content")
        assert is_valid_note_id(note_id)
        assert note_id.startswith("h-")

    def test_hash_id_deterministic(self):
        id1 = generate_hash_id("content")
        id2 = generate_hash_id("content")
        assert id1 == id2
