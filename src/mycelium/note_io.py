"""Note I/O for Obsidian-compatible Markdown+YAML frontmatter files (INV-001).

Implements the canonical storage substrate invariant: all canonical content is
stored as Obsidian-compatible Markdown Notes in the vault filesystem. No
canonical knowledge exists only in a non-Markdown store.

Spec reference: §3 INV-001, §4.2.1
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

# ── YAML frontmatter delimiters ─────────────────────────────────────────────

_FM_DELIMITER = "---"


def parse_note(content: str) -> tuple[dict[str, Any], str]:
    """Parse a Markdown note with YAML frontmatter.

    Args:
        content: The full text content of the note file.

    Returns:
        A tuple of (frontmatter_dict, body_markdown).

    Raises:
        ValueError: If the content does not start with a valid YAML
            frontmatter block delimited by ``---``.
    """
    if not content.startswith(_FM_DELIMITER):
        raise ValueError(
            "Note does not start with YAML frontmatter delimiter '---'"
        )

    # Find the closing delimiter
    end_idx = content.find("\n" + _FM_DELIMITER + "\n", len(_FM_DELIMITER))
    if end_idx < 0:
        raise ValueError("No closing YAML frontmatter delimiter '---' found")

    fm_text = content[len(_FM_DELIMITER) + 1 : end_idx]
    body = content[end_idx + len(_FM_DELIMITER) + 2 :]

    frontmatter = yaml.safe_load(fm_text)
    if frontmatter is None:
        frontmatter = {}
    if not isinstance(frontmatter, dict):
        raise ValueError(
            f"YAML frontmatter must be a mapping, got {type(frontmatter).__name__}"
        )

    return frontmatter, body


def render_note(frontmatter: dict[str, Any], body: str) -> str:
    """Render a Markdown note with YAML frontmatter.

    Produces an Obsidian-compatible Markdown file with YAML frontmatter
    delimited by ``---``. This is the canonical on-disk format per INV-001.

    Args:
        frontmatter: The YAML frontmatter dictionary.
        body: The Markdown body content.

    Returns:
        The full note text ready for writing to disk.
    """
    fm_text = yaml.safe_dump(
        frontmatter,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )
    # Ensure body starts on its own line after the closing delimiter
    if body and not body.startswith("\n"):
        separator = "\n"
    else:
        separator = ""

    return f"{_FM_DELIMITER}\n{fm_text}{_FM_DELIMITER}\n{separator}{body}"


def read_note(path: Path) -> tuple[dict[str, Any], str]:
    """Read and parse a Markdown note file from disk.

    Args:
        path: Path to the ``.md`` note file.

    Returns:
        A tuple of (frontmatter_dict, body_markdown).

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file is not valid YAML+Markdown format.
    """
    content = path.read_text(encoding="utf-8")
    return parse_note(content)


def write_note(
    path: Path,
    frontmatter: dict[str, Any],
    body: str,
    *,
    mkdir: bool = True,
) -> None:
    """Write a Markdown note with YAML frontmatter to disk.

    This writes the canonical Obsidian-compatible format per INV-001.

    Args:
        path: Target file path.
        frontmatter: The YAML frontmatter dictionary.
        body: The Markdown body content.
        mkdir: If True, create parent directories as needed.
    """
    content = render_note(frontmatter, body)

    from mycelium.atomic_write import atomic_write_text

    atomic_write_text(path, content, mkdir=mkdir)


def list_notes(vault_dir: Path, scope_dir: str) -> list[Path]:
    """List all ``.md`` note files under a vault scope directory.

    Args:
        vault_dir: The vault root directory.
        scope_dir: A vault-relative directory path (e.g. ``"Sources"``).

    Returns:
        Sorted list of ``.md`` file paths found under the scope directory.
    """
    target = vault_dir / scope_dir
    if not target.is_dir():
        return []
    return sorted(target.rglob("*.md"))
