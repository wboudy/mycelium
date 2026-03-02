"""Tests for vault directory layout and scope boundaries (VLT-001).

Verifies acceptance criteria from §4.1:
  AC-VLT-001-1: Without Promotion, the system writes only under Draft Scope
                 directories: Inbox/, Reports/, Logs/, Indexes/, Quarantine/.
  AC-VLT-001-2: Promotion applies approved changes by creating or modifying
                 Notes only within Canonical Scope and updates status to canon.
"""

from __future__ import annotations

import pytest

from mycelium.vault_layout import (
    CANONICAL_DIRS,
    DRAFT_DIRS,
    ScopeClassification,
    all_vault_dirs,
    classify_scope,
    is_canonical_scope,
    is_draft_scope,
)


# ─── AC-VLT-001-1: Draft Scope classification ──────────────────────────────

class TestDraftScope:
    """AC-VLT-001-1: Without Promotion, the system writes only under Draft
    Scope directories: Inbox/, Reports/, Logs/, Indexes/, Quarantine/."""

    @pytest.mark.parametrize("path", [
        "Inbox/Sources/draft-note.md",
        "Inbox/ReviewQueue/item-001.md",
        "Inbox/ReviewDigest/digest-2026-03.md",
        "Reports/Delta/run-abc123.yaml",
        "Logs/Audit/2026-03-01.yaml",
        "Indexes/dedupe-cache.json",
        "Quarantine/invalid-note.md",
    ])
    def test_draft_scope_paths(self, path: str):
        assert is_draft_scope(path) is True
        assert is_canonical_scope(path) is False
        assert classify_scope(path) is ScopeClassification.DRAFT

    @pytest.mark.parametrize("path", [
        "Inbox",
        "Inbox/Sources",
        "Reports",
        "Reports/Delta",
        "Logs",
        "Logs/Audit",
        "Indexes",
        "Quarantine",
    ])
    def test_draft_scope_directory_roots(self, path: str):
        """Bare directory paths are also classified correctly."""
        assert is_draft_scope(path) is True

    def test_nested_draft_path(self):
        assert is_draft_scope("Inbox/Sources/subdir/deep/note.md") is True

    def test_all_draft_top_level_prefixes(self):
        """Verify the 5 top-level draft directories from AC-VLT-001-1."""
        draft_tops = {"Inbox", "Reports", "Logs", "Indexes", "Quarantine"}
        for top in draft_tops:
            assert is_draft_scope(f"{top}/file.txt") is True


# ─── AC-VLT-001-2: Canonical Scope classification ──────────────────────────

class TestCanonicalScope:
    """AC-VLT-001-2: Promotion writes only within Canonical Scope."""

    @pytest.mark.parametrize("path", [
        "Sources/source-note.md",
        "Claims/claim-note.md",
        "Concepts/concept-note.md",
        "Questions/question-note.md",
        "Projects/project-note.md",
        "MOCs/moc-note.md",
    ])
    def test_canonical_scope_paths(self, path: str):
        assert is_canonical_scope(path) is True
        assert is_draft_scope(path) is False
        assert classify_scope(path) is ScopeClassification.CANONICAL

    @pytest.mark.parametrize("path", CANONICAL_DIRS)
    def test_canonical_directory_roots(self, path: str):
        assert is_canonical_scope(path) is True

    def test_nested_canonical_path(self):
        assert is_canonical_scope("Sources/subdir/note.md") is True


# ─── Mutual exclusion ──────────────────────────────────────────────────────

class TestScopeMutualExclusion:
    """No path can be both canonical and draft."""

    @pytest.mark.parametrize("path", [
        "Sources/a.md", "Claims/b.md", "Concepts/c.md",
        "Inbox/Sources/d.md", "Reports/Delta/e.yaml",
        "Quarantine/f.md", "Indexes/g.json",
    ])
    def test_scopes_are_mutually_exclusive(self, path: str):
        canonical = is_canonical_scope(path)
        draft = is_draft_scope(path)
        assert not (canonical and draft), f"{path} classified as both scopes"

    def test_unknown_path_is_neither(self):
        assert is_canonical_scope("random/file.txt") is False
        assert is_draft_scope("random/file.txt") is False
        assert classify_scope("random/file.txt") is None

    def test_empty_path(self):
        assert classify_scope("") is None
        assert is_canonical_scope("") is False
        assert is_draft_scope("") is False


# ─── Directory constants ──────────────────────────────────────────────────

class TestDirectoryConstants:
    """Verify the directory constants match the §4.1 spec table."""

    def test_canonical_dirs_count(self):
        assert len(CANONICAL_DIRS) == 6

    def test_canonical_dirs_contents(self):
        expected = {"Sources", "Claims", "Concepts", "Questions", "Projects", "MOCs"}
        assert set(CANONICAL_DIRS) == expected

    def test_draft_dirs_count(self):
        assert len(DRAFT_DIRS) == 7

    def test_draft_dirs_contents(self):
        expected = {
            "Inbox/Sources", "Inbox/ReviewQueue", "Inbox/ReviewDigest",
            "Reports/Delta", "Logs/Audit", "Indexes", "Quarantine",
        }
        assert set(DRAFT_DIRS) == expected

    def test_all_vault_dirs(self):
        all_dirs = all_vault_dirs()
        assert len(all_dirs) == 13
        # Canonical first, then draft
        assert all_dirs[:6] == list(CANONICAL_DIRS)
        assert all_dirs[6:] == list(DRAFT_DIRS)
