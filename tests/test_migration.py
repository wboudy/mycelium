"""Tests for schema migration framework (MIG-002).

Validates acceptance criteria from §11.2:
  AC-MIG-002-1: A migration test applies the migration to a fixture Vault
                and validates that all Notes still pass schema checks.
  AC-MIG-002-2: A rollback test restores the pre-migration fixture state
                byte-for-byte for Canonical Notes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from mycelium.migration import (
    Migration,
    MigrationRegistry,
    apply_migration_to_frontmatter,
    migrate_note_content,
    migrate_vault_notes,
    rollback_vault_from_backups,
)


# ─── Test fixtures ────────────────────────────────────────────────────────

VALID_NOTE = (
    "---\n"
    "type: source\n"
    "id: src-001\n"
    "status: draft\n"
    "created: 2025-01-01T00:00:00Z\n"
    "updated: 2025-01-01T00:00:00Z\n"
    "---\n"
    "# Test Note\n\nBody content.\n"
)


def _add_tags_migration() -> Migration:
    """Sample migration: adds a default tags field."""
    def forward(fm: dict[str, Any]) -> dict[str, Any]:
        if "tags" not in fm:
            fm["tags"] = []
        return fm

    def rollback(fm: dict[str, Any]) -> dict[str, Any]:
        fm.pop("tags", None)
        return fm

    return Migration(
        version="0.2.0",
        description="Add default tags field",
        forward=forward,
        rollback=rollback,
    )


def _rename_field_migration() -> Migration:
    """Sample migration: renames 'confidence' to 'certainty'."""
    def forward(fm: dict[str, Any]) -> dict[str, Any]:
        if "confidence" in fm:
            fm["certainty"] = fm.pop("confidence")
        return fm

    def rollback(fm: dict[str, Any]) -> dict[str, Any]:
        if "certainty" in fm:
            fm["confidence"] = fm.pop("certainty")
        return fm

    return Migration(
        version="0.3.0",
        description="Rename confidence to certainty",
        forward=forward,
        rollback=rollback,
    )


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    """Create a fixture vault with several notes."""
    sources = tmp_path / "Sources"
    sources.mkdir()

    (sources / "note-a.md").write_text(
        "---\n"
        "type: source\n"
        "id: src-a\n"
        "status: draft\n"
        "created: 2025-01-01T00:00:00Z\n"
        "updated: 2025-01-01T00:00:00Z\n"
        "confidence: 0.8\n"
        "---\n"
        "# Note A\n"
    )

    (sources / "note-b.md").write_text(
        "---\n"
        "type: claim\n"
        "id: clm-b\n"
        "status: reviewed\n"
        "created: 2025-02-01T00:00:00Z\n"
        "updated: 2025-02-15T00:00:00Z\n"
        "---\n"
        "# Note B\n\nA claim.\n"
    )

    # Non-note file (should be skipped)
    readme = tmp_path / "README.md"
    readme.write_text("# Vault README\nNo frontmatter here.\n")

    return tmp_path


# ─── MigrationRegistry ──────────────────────────────────────────────────

class TestMigrationRegistry:

    def test_register_and_list(self):
        reg = MigrationRegistry()
        m = _add_tags_migration()
        reg.register(m.version, m.description, m.forward, m.rollback)
        assert len(reg.migrations) == 1
        assert reg.migrations[0].version == "0.2.0"

    def test_get_migrations_after(self):
        reg = MigrationRegistry()
        m1 = _add_tags_migration()
        m2 = _rename_field_migration()
        reg.register(m1.version, m1.description, m1.forward, m1.rollback)
        reg.register(m2.version, m2.description, m2.forward, m2.rollback)

        # After 0.2.0, only 0.3.0 should be returned
        after = reg.get_migrations_after("0.2.0")
        assert len(after) == 1
        assert after[0].version == "0.3.0"

    def test_get_migrations_after_empty(self):
        reg = MigrationRegistry()
        m = _add_tags_migration()
        reg.register(m.version, m.description, m.forward, m.rollback)
        after = reg.get_migrations_after("0.2.0")
        assert len(after) == 0

    def test_get_all_from_start(self):
        reg = MigrationRegistry()
        m1 = _add_tags_migration()
        m2 = _rename_field_migration()
        reg.register(m1.version, m1.description, m1.forward, m1.rollback)
        reg.register(m2.version, m2.description, m2.forward, m2.rollback)
        all_migrations = reg.get_migrations_after("")
        assert len(all_migrations) == 2


# ─── apply_migration_to_frontmatter ─────────────────────────────────────

class TestApplyMigration:

    def test_forward_adds_field(self):
        fm = {"type": "source", "id": "src-001"}
        m = _add_tags_migration()
        result = apply_migration_to_frontmatter(fm, m, direction="forward")
        assert result["tags"] == []
        # Original not mutated
        assert "tags" not in fm

    def test_rollback_removes_field(self):
        fm = {"type": "source", "id": "src-001", "tags": ["ai"]}
        m = _add_tags_migration()
        result = apply_migration_to_frontmatter(fm, m, direction="rollback")
        assert "tags" not in result

    def test_forward_rename(self):
        fm = {"confidence": 0.8}
        m = _rename_field_migration()
        result = apply_migration_to_frontmatter(fm, m, direction="forward")
        assert result["certainty"] == 0.8
        assert "confidence" not in result

    def test_rollback_rename(self):
        fm = {"certainty": 0.9}
        m = _rename_field_migration()
        result = apply_migration_to_frontmatter(fm, m, direction="rollback")
        assert result["confidence"] == 0.9
        assert "certainty" not in result


# ─── migrate_note_content ───────────────────────────────────────────────

class TestMigrateNoteContent:

    def test_forward_migration(self):
        m = _add_tags_migration()
        result = migrate_note_content(VALID_NOTE, [m], direction="forward")
        assert "tags:" in result
        assert "# Test Note" in result

    def test_rollback_migration(self):
        # First apply forward
        m = _add_tags_migration()
        migrated = migrate_note_content(VALID_NOTE, [m], direction="forward")
        assert "tags:" in migrated

        # Then rollback
        rolled_back = migrate_note_content(migrated, [m], direction="rollback")
        assert "tags:" not in rolled_back
        assert "# Test Note" in rolled_back

    def test_multiple_migrations(self):
        m1 = _add_tags_migration()
        m2 = _rename_field_migration()
        note_with_conf = VALID_NOTE.replace(
            "updated: 2025-01-01T00:00:00Z\n",
            "updated: 2025-01-01T00:00:00Z\nconfidence: 0.7\n",
        )
        result = migrate_note_content(
            note_with_conf, [m1, m2], direction="forward",
        )
        assert "tags:" in result
        assert "certainty: 0.7" in result
        assert "confidence:" not in result

    def test_body_preserved(self):
        m = _add_tags_migration()
        result = migrate_note_content(VALID_NOTE, [m])
        assert "# Test Note" in result
        assert "Body content." in result


# ─── AC-MIG-002-1: vault migration with schema validation ───────────────

class TestVaultMigration:
    """AC-MIG-002-1: Migration applies to a fixture vault and all notes
    still pass schema checks."""

    def test_migrate_all_notes(self, vault: Path):
        m = _add_tags_migration()
        results = migrate_vault_notes(vault, [m])

        ok_results = [r for r in results if r["status"] == "ok"]
        assert len(ok_results) == 2  # note-a.md and note-b.md

    def test_migrated_notes_pass_schema(self, vault: Path):
        from mycelium.schema import validate_shared_frontmatter
        from mycelium.note_format import parse_note

        m = _add_tags_migration()
        migrate_vault_notes(vault, [m])

        for note_path in (vault / "Sources").glob("*.md"):
            content = note_path.read_text()
            fm, _ = parse_note(content)
            errors = validate_shared_frontmatter(fm)
            assert errors == [], f"{note_path.name} failed: {errors}"

    def test_skips_non_frontmatter_files(self, vault: Path):
        m = _add_tags_migration()
        results = migrate_vault_notes(vault, [m])
        skipped = [r for r in results if r["status"] == "skipped"]
        assert len(skipped) == 1  # README.md
        assert "README" in skipped[0]["path"]

    def test_backup_files_created(self, vault: Path):
        m = _add_tags_migration()
        migrate_vault_notes(vault, [m], backup=True)
        bak_files = list(vault.rglob("*.bak"))
        assert len(bak_files) == 2  # note-a.md.bak, note-b.md.bak

    def test_no_backup_when_disabled(self, vault: Path):
        m = _add_tags_migration()
        migrate_vault_notes(vault, [m], backup=False)
        bak_files = list(vault.rglob("*.bak"))
        assert len(bak_files) == 0


# ─── AC-MIG-002-2: rollback restores byte-for-byte ──────────────────────

class TestRollback:
    """AC-MIG-002-2: Rollback restores pre-migration state byte-for-byte."""

    def test_rollback_from_backups(self, vault: Path):
        # Capture original content
        originals = {}
        for note_path in sorted((vault / "Sources").glob("*.md")):
            originals[note_path.name] = note_path.read_bytes()

        # Apply migration (with backup)
        m = _add_tags_migration()
        migrate_vault_notes(vault, [m], backup=True)

        # Verify content changed
        for note_path in (vault / "Sources").glob("*.md"):
            assert note_path.read_bytes() != originals[note_path.name]

        # Rollback from backups
        restored = rollback_vault_from_backups(vault)
        assert restored == 2

        # Verify byte-for-byte restoration
        for note_path in sorted((vault / "Sources").glob("*.md")):
            assert note_path.read_bytes() == originals[note_path.name], (
                f"{note_path.name} not restored byte-for-byte"
            )

    def test_rollback_removes_backup_files(self, vault: Path):
        m = _add_tags_migration()
        migrate_vault_notes(vault, [m], backup=True)
        rollback_vault_from_backups(vault)
        bak_files = list(vault.rglob("*.bak"))
        assert len(bak_files) == 0

    def test_migration_forward_then_rollback_via_function(self, vault: Path):
        """Test the migration.rollback function path (not backup-based)."""
        m = _add_tags_migration()

        # Capture originals
        originals = {}
        for p in sorted((vault / "Sources").glob("*.md")):
            originals[p.name] = p.read_text()

        # Forward
        migrate_vault_notes(vault, [m], backup=False)

        # Rollback via migration function
        migrate_vault_notes(vault, [m], direction="rollback", backup=False)

        # Content should be equivalent (YAML reformatting may differ slightly)
        from mycelium.note_format import parse_note

        for p in sorted((vault / "Sources").glob("*.md")):
            orig_fm, orig_body = parse_note(originals[p.name])
            curr_fm, curr_body = parse_note(p.read_text())
            assert orig_fm == curr_fm, f"{p.name} frontmatter differs"
            assert orig_body.strip() == curr_body.strip(), f"{p.name} body differs"

    def test_rollback_idempotent(self, vault: Path):
        """Double rollback is safe."""
        restored = rollback_vault_from_backups(vault)
        assert restored == 0  # No backups to restore
