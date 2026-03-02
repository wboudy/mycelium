"""Canonical note format enforcement (MIG-001).

All Canonical Notes MUST remain human-readable and git-diff friendly:
- YAML frontmatter + Markdown body; no binary blobs.
- Schema changes that add fields do not require rewriting unchanged notes.

A canonical note has the format:
    ---
    <YAML frontmatter>
    ---
    <Markdown body>

Spec reference: mycelium_refactor_plan_apr_round5.md §11.1 (MIG-001)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


# ── Binary detection ─────────────────────────────────────────────────────

# File extensions that are never valid canonical notes
BINARY_EXTENSIONS: frozenset[str] = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".pptx",
    ".zip", ".tar", ".gz", ".bz2", ".7z", ".rar",
    ".exe", ".dll", ".so", ".dylib", ".bin",
    ".mp3", ".mp4", ".wav", ".avi", ".mkv",
    ".pyc", ".pyo", ".class", ".o", ".obj",
    ".db", ".sqlite", ".sqlite3",
})


def is_binary_file(path: Path) -> bool:
    """Check if a file appears to be binary.

    Uses a combination of extension check and null-byte detection.

    Args:
        path: Path to the file to check.

    Returns:
        True if the file appears to be binary.
    """
    if path.suffix.lower() in BINARY_EXTENSIONS:
        return True

    # Read first 8KB and check for null bytes
    try:
        chunk = path.read_bytes()[:8192]
        return b"\x00" in chunk
    except (OSError, PermissionError):
        return False


# ── Note parsing ────────────────────────────────────────────────────────

class NoteFormatError(Exception):
    """Raised when a file does not conform to canonical note format."""

    def __init__(self, path: str, reason: str) -> None:
        self.path = path
        self.reason = reason
        super().__init__(f"{path}: {reason}")


def parse_note(content: str) -> tuple[dict[str, Any], str]:
    """Parse a canonical note into frontmatter dict and Markdown body.

    The note format is:
        ---
        <YAML frontmatter>
        ---
        <Markdown body>

    Args:
        content: The full text content of the note.

    Returns:
        Tuple of (frontmatter_dict, markdown_body).

    Raises:
        NoteFormatError: If the content is not valid YAML frontmatter + Markdown.
    """
    if not content.startswith("---"):
        raise NoteFormatError("(inline)", "Note must start with '---' (YAML frontmatter delimiter)")

    # Find the closing delimiter — must be on its own line (line-anchored)
    # to avoid matching '---' inside YAML values
    second_delim = content.find("\n---", 3)
    if second_delim == -1:
        raise NoteFormatError("(inline)", "No closing '---' delimiter for YAML frontmatter")
    second_delim += 1  # skip the leading newline to point at '---'

    # Extract frontmatter YAML
    fm_text = content[3:second_delim].strip()
    if not fm_text:
        raise NoteFormatError("(inline)", "Empty YAML frontmatter")

    try:
        frontmatter = yaml.safe_load(fm_text)
    except yaml.YAMLError as e:
        raise NoteFormatError("(inline)", f"Invalid YAML in frontmatter: {e}")

    if not isinstance(frontmatter, dict):
        raise NoteFormatError("(inline)", "Frontmatter must be a YAML mapping")

    # Extract body (everything after closing ---)
    body = content[second_delim + 3:]
    if body.startswith("\n"):
        body = body[1:]

    return frontmatter, body


def validate_canonical_note_format(
    path: Path,
    *,
    vault_relative: str | None = None,
) -> list[str]:
    """Validate that a file conforms to canonical note format (MIG-001).

    Checks:
    - AC-MIG-001-1: File contains only YAML frontmatter + Markdown body;
      no binary blobs.
    - The file is valid UTF-8 text.
    - The file starts with YAML frontmatter delimiters (---).
    - The frontmatter parses as valid YAML.

    Args:
        path: Absolute path to the file.
        vault_relative: Optional vault-relative path for error messages.

    Returns:
        List of validation error strings (empty means valid).
    """
    display = vault_relative or str(path)
    errors: list[str] = []

    if not path.exists():
        errors.append(f"File not found: {display}")
        return errors

    if not path.is_file():
        errors.append(f"Not a file: {display}")
        return errors

    # Check for binary content
    if is_binary_file(path):
        errors.append(f"Binary file detected: {display} (canonical notes must be text)")
        return errors

    # Read as text
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        errors.append(f"File is not valid UTF-8: {display}")
        return errors

    # Parse frontmatter
    try:
        parse_note(content)
    except NoteFormatError as e:
        errors.append(f"{display}: {e.reason}")

    return errors
