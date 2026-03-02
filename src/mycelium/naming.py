"""
Note ID naming rules and filename alignment (NAM-001).

Implements §4.3.1: Note `id` must match one of three patterns, and the
Markdown filename must equal `<id>.md`.

Patterns:
  - slug-only:  ^[a-z0-9]+(?:-[a-z0-9]+)*$
  - hash-only:  ^h-[0-9a-f]{12,64}$
  - hybrid:     ^[a-z0-9]+(?:-[a-z0-9]+)*--h-[0-9a-f]{12}$

Spec reference: §4.3.1
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import PurePosixPath


# ── ID Patterns (§4.3.1) ────────────────────────────────────────────────

_SLUG_ONLY_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_HASH_ONLY_RE = re.compile(r"^h-[0-9a-f]{12,64}$")
_HYBRID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*--h-[0-9a-f]{12}$")


def is_valid_note_id(note_id: str) -> bool:
    """Check if a note ID matches one of the three allowed patterns.

    AC-NAM-001-2: Rejects id strings outside the allowed patterns.
    """
    return bool(
        _SLUG_ONLY_RE.match(note_id)
        or _HASH_ONLY_RE.match(note_id)
        or _HYBRID_RE.match(note_id)
    )


def validate_note_id(note_id: str) -> list[str]:
    """Validate a note ID against NAM-001 patterns.

    Returns a list of error strings (empty means valid).
    """
    if not isinstance(note_id, str) or not note_id:
        return ["id must be a non-empty string"]
    if not is_valid_note_id(note_id):
        return [
            f"id {note_id!r} does not match any allowed pattern: "
            f"slug-only, hash-only (h-<12..64hex>), or hybrid (<slug>--h-<12hex>)"
        ]
    return []


def validate_filename_id_match(filename: str, note_id: str) -> list[str]:
    """Validate that filename equals <id>.md.

    AC-NAM-001-1: Rejects Notes where filename and id differ.

    Args:
        filename: The filename (just the name, not the full path).
            Can be a full path — only the final component is checked.
        note_id: The id from frontmatter.
    """
    # Extract just the filename from a path
    name = PurePosixPath(filename).name
    expected = f"{note_id}.md"
    if name != expected:
        return [f"Filename {name!r} does not match id; expected {expected!r}"]
    return []


# ── ID Generation ────────────────────────────────────────────────────────

def slug_from_text(text: str, max_words: int = 6) -> str:
    """Generate a URL-safe slug from arbitrary text.

    Normalizes unicode, lowercases, strips non-alphanumeric characters,
    and joins words with hyphens.
    """
    # Normalize unicode to ASCII-compatible form
    normalized = unicodedata.normalize("NFKD", text)
    # Keep only ASCII alphanumeric and spaces
    ascii_only = "".join(
        c for c in normalized
        if c.isascii() and (c.isalnum() or c.isspace())
    )
    # Split into words, lowercase, limit
    words = ascii_only.lower().split()[:max_words]
    slug = "-".join(w for w in words if w)
    return slug or "untitled"


def generate_hash_suffix(content: str, length: int = 12) -> str:
    """Generate a deterministic hex hash suffix from content.

    Uses SHA-256 truncated to `length` hex characters.
    """
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return digest[:length]


def generate_hybrid_id(text: str, content: str, max_words: int = 6) -> str:
    """Generate a hybrid machine-form note ID: <slug>--h-<12hex>.

    AC-NAM-001-3: Machine-generated notes default to hybrid pattern.

    Args:
        text: Human-readable text to derive the slug from (e.g. title).
        content: Content to hash for the suffix (e.g. source URL or claim text).
        max_words: Maximum words in the slug portion.
    """
    slug = slug_from_text(text, max_words)
    suffix = generate_hash_suffix(content)
    return f"{slug}--h-{suffix}"


def generate_hash_id(content: str, length: int = 12) -> str:
    """Generate a hash-only note ID: h-<hex>.

    Args:
        content: Content to hash.
        length: Number of hex characters (12-64).
    """
    suffix = generate_hash_suffix(content, length)
    return f"h-{suffix}"
