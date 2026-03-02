"""Tests for vault path containment (safe_vault_path, sanitize_path_component).

Validates that path traversal attacks are blocked across all vault operations.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mycelium.vault_layout import (
    PathTraversalError,
    safe_vault_path,
    sanitize_path_component,
)


class TestSafeVaultPath:
    """safe_vault_path prevents traversal outside vault root."""

    def test_normal_path(self, tmp_path: Path):
        (tmp_path / "Sources").mkdir()
        result = safe_vault_path(tmp_path, "Sources/note.md")
        assert result == (tmp_path / "Sources" / "note.md").resolve()

    def test_nested_path(self, tmp_path: Path):
        result = safe_vault_path(tmp_path, "Inbox/Sources/draft.md")
        assert "Inbox" in str(result)

    def test_traversal_blocked(self, tmp_path: Path):
        with pytest.raises(PathTraversalError):
            safe_vault_path(tmp_path, "../../etc/passwd")

    def test_traversal_in_middle(self, tmp_path: Path):
        with pytest.raises(PathTraversalError):
            safe_vault_path(tmp_path, "Sources/../../../etc/shadow")

    def test_vault_root_itself_ok(self, tmp_path: Path):
        result = safe_vault_path(tmp_path, ".")
        assert result == tmp_path.resolve()

    def test_absolute_path_rejected(self, tmp_path: Path):
        with pytest.raises(PathTraversalError):
            safe_vault_path(tmp_path, "/etc/passwd")

    def test_single_dot_dot_blocked(self, tmp_path: Path):
        with pytest.raises(PathTraversalError):
            safe_vault_path(tmp_path, "..")


class TestSanitizePathComponent:
    """sanitize_path_component rejects traversal in IDs."""

    def test_normal_id(self):
        assert sanitize_path_component("run-abc123") == "run-abc123"

    def test_id_with_dots(self):
        assert sanitize_path_component("note.v2") == "note.v2"

    def test_traversal_rejected(self):
        with pytest.raises(PathTraversalError):
            sanitize_path_component("../../evil")

    def test_slash_rejected(self):
        with pytest.raises(PathTraversalError):
            sanitize_path_component("dir/file")

    def test_backslash_rejected(self):
        with pytest.raises(PathTraversalError):
            sanitize_path_component("dir\\file")

    def test_dotdot_in_middle(self):
        with pytest.raises(PathTraversalError):
            sanitize_path_component("foo..bar")

    def test_empty_ok(self):
        assert sanitize_path_component("") == ""


class TestPathContainmentIntegration:
    """Path containment in real code paths."""

    def test_quarantine_rejects_traversal(self, tmp_path: Path):
        from mycelium.quarantine import quarantine_file

        with pytest.raises(FileNotFoundError, match="traversal"):
            quarantine_file(
                tmp_path,
                "../../etc/passwd",
                error_code="ERR_TEST",
                error_message="test",
                stage="test",
            )

    def test_graduate_rejects_traversal_in_path(self, tmp_path: Path):
        from mycelium.graduate import GraduateInput, graduate

        params = GraduateInput(all_approved=True, actor="test")
        items = [{
            "queue_id": "q-evil",
            "path": "../../etc/passwd",
            "decision": "approve",
        }]
        env = graduate(tmp_path, params, items)
        assert env.ok is True  # per-item atomicity: item rejected, envelope ok
        assert len(env.data["rejected"]) == 1
        assert "traversal" in env.data["rejected"][0]["reason"].lower()

    def test_graduate_rejects_traversal_in_note_id(self, tmp_path: Path):
        from mycelium.graduate import GraduateInput, graduate
        from mycelium.note_io import write_note

        fm = {
            "id": "../../evil",
            "type": "source",
            "status": "draft",
            "created": "2026-03-01T00:00:00Z",
            "updated": "2026-03-01T00:00:00Z",
        }
        write_note(tmp_path / "Inbox" / "Sources" / "evil.md", fm, "# Evil\n")
        params = GraduateInput(all_approved=True, actor="test")
        items = [{
            "queue_id": "q-evil",
            "path": "Inbox/Sources/evil.md",
            "decision": "approve",
        }]
        env = graduate(tmp_path, params, items)
        assert env.ok is True
        assert len(env.data["rejected"]) == 1
        assert "traversal" in env.data["rejected"][0]["reason"].lower()

    def test_delta_report_rejects_traversal_in_run_id(self, tmp_path: Path):
        from mycelium.delta_report import build_delta_report, save_delta_report

        report = build_delta_report(
            run_id="../../evil",
            source_id="src-1",
            normalized_locator="http://example.com",
            fingerprint="abc123",
        )
        with pytest.raises(PathTraversalError):
            save_delta_report(tmp_path, report)
