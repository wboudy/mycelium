"""Vault directory layout and scope boundary classification (VLT-001).

Implements the default vault layout from §4.1 of the refactor spec. The vault
uses vault-relative paths. Every directory falls into one of two scopes:

- **Canonical Scope**: Human-curated knowledge (Sources/, Claims/, Concepts/,
  Questions/, Projects/, MOCs/). Only writable via Promotion.
- **Draft Scope**: Agent-writable directories (Inbox/, Reports/, Logs/,
  Indexes/, Quarantine/). The system writes here without Promotion.

Spec reference: mycelium_refactor_plan_apr_round5.md §4.1, VLT-001
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path, PurePosixPath


class ScopeClassification(Enum):
    """Classification of a vault directory per §4.1."""

    CANONICAL = "canonical"
    DRAFT = "draft"


# ── Directory definitions from §4.1 table ────────────────────────────────────

# Canonical Scope directories
CANONICAL_DIRS: tuple[str, ...] = (
    "Sources",
    "Claims",
    "Concepts",
    "Questions",
    "Projects",
    "MOCs",
)

# Draft Scope directories (derived: draft, durable, rebuildable)
DRAFT_DIRS: tuple[str, ...] = (
    "Inbox/Sources",
    "Inbox/ReviewQueue",
    "Inbox/ReviewDigest",
    "Reports/Delta",
    "Logs/Audit",
    "Indexes",
    "Quarantine",
)

# Top-level draft prefixes for efficient path matching
_DRAFT_TOP_LEVEL: frozenset[str] = frozenset({
    "Inbox",
    "Reports",
    "Logs",
    "Indexes",
    "Quarantine",
})

# Top-level canonical prefixes
_CANONICAL_TOP_LEVEL: frozenset[str] = frozenset(CANONICAL_DIRS)


def classify_scope(vault_relative_path: str) -> ScopeClassification | None:
    """Classify a vault-relative path as Canonical or Draft scope.

    Args:
        vault_relative_path: A path relative to the vault root (e.g.
            ``"Sources/my-note.md"`` or ``"Inbox/Sources/draft.md"``).

    Returns:
        ScopeClassification.CANONICAL for canonical scope paths,
        ScopeClassification.DRAFT for draft scope paths,
        or None if the path does not fall under any known scope directory.
    """
    parts = PurePosixPath(vault_relative_path).parts
    if not parts:
        return None

    top = parts[0]

    if top in _DRAFT_TOP_LEVEL:
        return ScopeClassification.DRAFT
    if top in _CANONICAL_TOP_LEVEL:
        return ScopeClassification.CANONICAL

    return None


def is_canonical_scope(vault_relative_path: str) -> bool:
    """Return True if path is within Canonical Scope.

    Canonical Scope directories: Sources/, Claims/, Concepts/, Questions/,
    Projects/, MOCs/. Only writable via Promotion (§8.3).
    """
    return classify_scope(vault_relative_path) is ScopeClassification.CANONICAL


def is_draft_scope(vault_relative_path: str) -> bool:
    """Return True if path is within Draft Scope.

    Draft Scope directories: Inbox/, Reports/, Logs/, Indexes/, Quarantine/.
    The system may write here without Promotion (AC-VLT-001-1).
    """
    return classify_scope(vault_relative_path) is ScopeClassification.DRAFT


def all_vault_dirs() -> list[str]:
    """Return all vault directories from the §4.1 layout table.

    Returns canonical directories first, then draft directories, matching
    the spec table ordering.
    """
    return list(CANONICAL_DIRS) + list(DRAFT_DIRS)
