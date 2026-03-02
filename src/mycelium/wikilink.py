"""Wikilink resolution and strict mode checking (LNK-001).

Parses Obsidian Wikilinks (``[[Path/NoteId]]``) from Markdown content,
resolves them to vault file paths, and reports unresolved links.

In Strict Mode, unresolved links in Canonical Scope fail the operation.
In non-Strict Mode, unresolved links are reported as warnings.

Spec reference: §4.3.2 LNK-001
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from mycelium.vault_layout import CANONICAL_DIRS, is_canonical_scope

# Regex to match Obsidian wikilinks: [[target]] or [[target|alias]]
_WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")


def extract_wikilinks(content: str) -> list[str]:
    """Extract all wikilink targets from Markdown content.

    Handles the ``[[Path/NoteId]]`` and ``[[Path/NoteId|display text]]``
    formats used by Obsidian.

    Args:
        content: Markdown text to parse.

    Returns:
        List of wikilink target strings (without brackets or alias).
    """
    return _WIKILINK_RE.findall(content)


def resolve_wikilink(target: str, vault_root: Path) -> Path | None:
    """Resolve a wikilink target to an existing file in the vault.

    Resolution strategy:
    1. Try ``{target}.md`` directly from vault root.
    2. Try ``{target}`` as-is (already has extension).
    3. Search Canonical Scope directories for ``{basename}.md``.

    Args:
        target: The wikilink target (e.g., ``"Sources/s-001"``).
        vault_root: Absolute path to the vault root.

    Returns:
        Path to the resolved file, or None if unresolved.
    """
    # Reject targets with path traversal components
    if ".." in target.split("/"):
        return None

    # 1. Direct path with .md extension
    direct = vault_root / f"{target}.md"
    if direct.exists() and direct.resolve().is_relative_to(vault_root.resolve()):
        return direct

    # 2. Direct path as-is (might already include extension)
    as_is = vault_root / target
    if as_is.exists() and as_is.is_file() and as_is.resolve().is_relative_to(vault_root.resolve()):
        return as_is

    # 3. Search canonical directories for basename match
    basename = target.rsplit("/", 1)[-1]
    for scope_dir in CANONICAL_DIRS:
        candidate = vault_root / scope_dir / f"{basename}.md"
        if candidate.exists():
            return candidate

    return None


def check_wikilinks(
    vault_root: Path,
    *,
    scope: str = "canonical",
) -> list[dict[str, Any]]:
    """Check all wikilinks in the specified scope for resolution.

    Scans Markdown files in the specified scope, extracts wikilinks,
    and checks each for resolution.

    Args:
        vault_root: Absolute path to the vault root.
        scope: Which scope to check. ``"canonical"`` checks only
            Canonical Scope directories (default).

    Returns:
        List of unresolved link records, each with:
        - ``source_file``: vault-relative path of the file containing the link.
        - ``target``: the unresolved wikilink target string.
    """
    unresolved: list[dict[str, Any]] = []
    # NOTE: Only canonical scope is implemented; other scopes are a future TODO.
    dirs = CANONICAL_DIRS

    for scope_dir in dirs:
        scope_path = vault_root / scope_dir
        if not scope_path.exists():
            continue
        for md_file in scope_path.rglob("*.md"):
            content = md_file.read_text(encoding="utf-8")
            targets = extract_wikilinks(content)
            rel_path = str(md_file.relative_to(vault_root))
            for target in targets:
                if resolve_wikilink(target, vault_root) is None:
                    unresolved.append({
                        "source_file": rel_path,
                        "target": target,
                    })

    return unresolved


def validate_wikilinks_strict(
    vault_root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Validate wikilinks in Canonical Scope per LNK-001.

    AC-LNK-001-1: Reports unresolved links. In Strict Mode the caller
    should treat any unresolved links as errors.

    AC-LNK-001-2: In non-Strict Mode, the caller should treat
    unresolved links as warnings.

    Returns:
        A tuple of (unresolved, warnings):
        - unresolved: list of unresolved link records.
        - warnings: list of warning dicts suitable for Delta Report
          ``warnings`` array, each with ``code`` and ``message``.
    """
    unresolved = check_wikilinks(vault_root, scope="canonical")

    warnings = [
        {
            "code": "WARN_UNRESOLVED_WIKILINK",
            "message": (
                f"Unresolved wikilink [[{u['target']}]] "
                f"in {u['source_file']}"
            ),
        }
        for u in unresolved
    ]

    return unresolved, warnings
