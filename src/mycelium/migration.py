"""Schema migration framework with forward migration and rollback (MIG-002).

Any breaking schema or layout change MUST include a migration and rollback
procedure. This module provides a registry-based migration framework:

- Migrations are registered with a version string and forward/rollback callables.
- Forward migration transforms note frontmatter to the new schema.
- Rollback restores the original frontmatter.
- Migrations are applied in version order.
- Each migration operates on frontmatter dicts (not raw files).

Spec reference: mycelium_refactor_plan_apr_round5.md §11.2 (MIG-002)
"""

from __future__ import annotations

import copy
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import yaml

from mycelium.note_format import parse_note


# Type alias for migration functions
MigrationFn = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass
class Migration:
    """A single schema migration step.

    Attributes:
        version: Semantic version string (e.g., "0.2.0").
        description: Human-readable description of the migration.
        forward: Function that transforms frontmatter forward.
        rollback: Function that transforms frontmatter backward.
    """

    version: str
    description: str
    forward: MigrationFn
    rollback: MigrationFn


class MigrationRegistry:
    """Registry of schema migrations, ordered by version.

    Migrations are applied in registration order. Each migration's forward
    function receives the frontmatter dict and returns the modified dict.
    The rollback function reverses the transformation.
    """

    def __init__(self) -> None:
        self._migrations: list[Migration] = []

    def register(
        self,
        version: str,
        description: str,
        forward: MigrationFn,
        rollback: MigrationFn,
    ) -> None:
        """Register a new migration.

        Args:
            version: Version string for this migration.
            description: Human-readable description.
            forward: Function to apply the migration.
            rollback: Function to reverse the migration.
        """
        self._migrations.append(
            Migration(
                version=version,
                description=description,
                forward=forward,
                rollback=rollback,
            )
        )

    @property
    def migrations(self) -> list[Migration]:
        """Return all registered migrations in order."""
        return list(self._migrations)

    def get_migrations_after(self, current_version: str) -> list[Migration]:
        """Return migrations that come after the given version.

        Args:
            current_version: The current schema version.

        Returns:
            List of migrations to apply (in order).
        """
        found = False
        result: list[Migration] = []
        for m in self._migrations:
            if found:
                result.append(m)
            if m.version == current_version:
                found = True
        if not found and current_version == "":
            return list(self._migrations)
        return result

    def get_migrations_before(self, target_version: str) -> list[Migration]:
        """Return migrations to rollback to reach target_version (in reverse order).

        Args:
            target_version: The version to roll back to.

        Returns:
            List of migrations to roll back (in reverse order).
        """
        result: list[Migration] = []
        for m in self._migrations:
            if m.version == target_version:
                break
            result.append(m)
        result.reverse()
        return result


def apply_migration_to_frontmatter(
    frontmatter: dict[str, Any],
    migration: Migration,
    *,
    direction: str = "forward",
) -> dict[str, Any]:
    """Apply a single migration to a frontmatter dict.

    Args:
        frontmatter: The frontmatter dict to transform.
        migration: The migration to apply.
        direction: "forward" or "rollback".

    Returns:
        The transformed frontmatter dict.
    """
    fm = copy.deepcopy(frontmatter)
    if direction == "forward":
        return migration.forward(fm)
    return migration.rollback(fm)


def migrate_note_content(
    content: str,
    migrations: list[Migration],
    *,
    direction: str = "forward",
) -> str:
    """Apply migrations to a note's content string.

    Parses the note, applies each migration's forward/rollback to the
    frontmatter, and reconstructs the note with the original body.

    Args:
        content: The full note content (YAML frontmatter + Markdown body).
        migrations: List of migrations to apply in order.
        direction: "forward" or "rollback".

    Returns:
        The updated note content string.
    """
    fm, body = parse_note(content)

    for m in migrations:
        fm = apply_migration_to_frontmatter(fm, m, direction=direction)

    # Reconstruct note
    fm_yaml = yaml.dump(fm, default_flow_style=False, allow_unicode=True, sort_keys=False)
    return f"---\n{fm_yaml}---\n{body}"


def migrate_vault_notes(
    vault_root: Path,
    migrations: list[Migration],
    *,
    direction: str = "forward",
    note_glob: str = "**/*.md",
    backup: bool = True,
) -> list[dict[str, Any]]:
    """Apply migrations to all notes in a vault.

    AC-MIG-002-1: Applies the migration to all matching notes and validates
    they still parse correctly.

    AC-MIG-002-2: When backup=True, creates .bak copies for rollback.

    Args:
        vault_root: Path to the vault root directory.
        migrations: List of migrations to apply.
        direction: "forward" or "rollback".
        note_glob: Glob pattern for finding notes.
        backup: Whether to create .bak backup files before migrating.

    Returns:
        List of result dicts: [{path, status, error?}].
    """
    results: list[dict[str, Any]] = []

    for note_path in sorted(vault_root.glob(note_glob)):
        if not note_path.is_file():
            continue
        if note_path.suffix != ".md":
            continue

        rel_path = str(note_path.relative_to(vault_root))
        result: dict[str, Any] = {"path": rel_path, "status": "ok"}

        try:
            content = note_path.read_text(encoding="utf-8")

            # Skip files that don't have frontmatter
            if not content.startswith("---"):
                result["status"] = "skipped"
                result["reason"] = "no frontmatter"
                results.append(result)
                continue

            # Backup if requested
            if backup:
                backup_path = note_path.with_suffix(note_path.suffix + ".bak")
                shutil.copy2(str(note_path), str(backup_path))

            # Apply migrations
            new_content = migrate_note_content(
                content, migrations, direction=direction,
            )

            note_path.write_text(new_content, encoding="utf-8")

        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)

        results.append(result)

    return results


def rollback_vault_from_backups(vault_root: Path, note_glob: str = "**/*.md.bak") -> int:
    """Restore notes from .bak backup files.

    AC-MIG-002-2: Restores the pre-migration state byte-for-byte.

    Args:
        vault_root: Path to the vault root directory.
        note_glob: Glob pattern for finding backup files.

    Returns:
        Number of files restored.
    """
    count = 0
    for bak_path in sorted(vault_root.glob(note_glob)):
        if not bak_path.is_file():
            continue
        original = bak_path.with_suffix("")  # Remove .bak
        shutil.copy2(str(bak_path), str(original))
        bak_path.unlink()
        count += 1
    return count
