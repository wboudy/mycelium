"""
Tests for Mycelium MCP Server.

Covers all 7 tools with happy path, edge cases, and error handling.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from mycelium.mcp.server import (
    COMMAND_ALLOWLIST,
    PathNotAllowedError,
    _get_current_agent as get_current_agent,
    _list_files as list_files,
    _read_file as read_file,
    _read_progress as read_progress,
    _requires_approval as requires_approval,
    _run_command as run_command,
    _safe_resolve,
    _search_codebase as search_codebase,
    _update_progress as update_progress,
    _write_file as write_file,
)
import mycelium.mcp.server as _server


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing and set it as sandbox root."""
    with tempfile.TemporaryDirectory() as tmpdir:
        original_sandbox = _server.SANDBOX_ROOT
        _server.SANDBOX_ROOT = Path(tmpdir).resolve()
        try:
            yield Path(tmpdir)
        finally:
            _server.SANDBOX_ROOT = original_sandbox


@pytest.fixture
def sample_progress_yaml(temp_dir):
    """Create a sample progress.yaml file."""
    progress = {
        "current_agent": "implementer",
        "mission_context": {
            "phase": "Testing",
            "objective": "Test the MCP tools",
        },
        "scientist_plan": {
            "definition_of_done": [
                {"description": "Tool works", "status": "pending"},
            ],
        },
        "implementer_log": [],
        "verifier_report": [],
    }
    
    progress_file = temp_dir / "progress.yaml"
    with open(progress_file, "w") as f:
        yaml.safe_dump(progress, f)
    
    return progress_file


@pytest.fixture
def sample_files(temp_dir):
    """Create sample files for testing."""
    # Create directories
    (temp_dir / "subdir").mkdir()
    
    # Create files
    (temp_dir / "test.py").write_text("def hello():\n    return 'world'\n")
    (temp_dir / "readme.md").write_text("# Test\n\nSome content here.\n")
    (temp_dir / "subdir" / "nested.txt").write_text("Nested content\n")
    (temp_dir / ".hidden").write_text("Hidden file\n")
    
    return temp_dir


# =============================================================================
# Tests: read_progress
# =============================================================================

class TestReadProgress:
    """Tests for read_progress tool."""
    
    def test_read_valid_mission(self, sample_progress_yaml):
        """read_progress returns dict for valid mission."""
        result = read_progress(str(sample_progress_yaml.parent))
        
        assert isinstance(result, dict)
        assert result["current_agent"] == "implementer"
        assert result["mission_context"]["phase"] == "Testing"
    
    def test_read_progress_yaml_file(self, sample_progress_yaml):
        """read_progress works with direct .yaml file path."""
        result = read_progress(str(sample_progress_yaml))
        
        assert isinstance(result, dict)
        assert result["current_agent"] == "implementer"
    
    def test_read_nonexistent_mission(self, temp_dir):
        """read_progress raises error for non-existent mission."""
        nonexistent = temp_dir / "does_not_exist"
        
        with pytest.raises(FileNotFoundError):
            read_progress(str(nonexistent))
    
    def test_read_malformed_yaml(self, temp_dir):
        """read_progress handles malformed YAML gracefully."""
        bad_yaml = temp_dir / "progress.yaml"
        bad_yaml.write_text("current_agent: [invalid\n  broken yaml")
        
        with pytest.raises(ValueError, match="Failed to parse YAML"):
            read_progress(str(temp_dir))
    
    def test_read_empty_yaml(self, temp_dir):
        """read_progress handles empty YAML file."""
        empty_yaml = temp_dir / "progress.yaml"
        empty_yaml.write_text("")
        
        result = read_progress(str(temp_dir))
        assert result == {}

    def test_read_non_mapping_root_raises_value_error(self, temp_dir):
        """read_progress rejects non-mapping YAML roots for contract stability."""
        progress_file = temp_dir / "progress.yaml"
        progress_file.write_text("- not-a-mapping\n")

        with pytest.raises(ValueError, match="Expected YAML dict, got"):
            read_progress(str(temp_dir))


# =============================================================================
# Tests: update_progress
# =============================================================================

class TestUpdateProgress:
    """Tests for update_progress tool."""
    
    def test_update_modifies_correctly(self, sample_progress_yaml):
        """update_progress modifies progress.yaml correctly."""
        result = update_progress(
            str(sample_progress_yaml.parent),
            "current_agent",
            {"value": "verifier"},
        )
        
        assert result["current_agent"] == "verifier"
        
        # Verify the file was actually updated
        with open(sample_progress_yaml) as f:
            saved = yaml.safe_load(f)
        assert saved["current_agent"] == "verifier"
    
    def test_update_preserves_unmodified(self, sample_progress_yaml):
        """update_progress preserves unmodified sections."""
        original = read_progress(str(sample_progress_yaml.parent))
        
        update_progress(
            str(sample_progress_yaml.parent),
            "current_agent",
            {"value": "verifier"},
        )
        
        with open(sample_progress_yaml) as f:
            updated = yaml.safe_load(f)
        
        assert updated["mission_context"] == original["mission_context"]
        assert updated["scientist_plan"] == original["scientist_plan"]
    
    def test_update_invalid_section(self, sample_progress_yaml):
        """update_progress raises error for invalid section."""
        with pytest.raises(ValueError, match="Invalid section"):
            update_progress(
                str(sample_progress_yaml.parent),
                "not_a_valid_section",
                {"data": "value"},
            )
    
    def test_update_merge_dict_section(self, sample_progress_yaml):
        """update_progress merges dict sections correctly."""
        result = update_progress(
            str(sample_progress_yaml.parent),
            "mission_context",
            {"new_field": "new_value"},
        )
        
        assert result["mission_context"]["phase"] == "Testing"
        assert result["mission_context"]["new_field"] == "new_value"

    def test_update_rejects_non_mapping_yaml_root(self, temp_dir):
        """update_progress rejects progress.yaml roots that are not mappings."""
        progress_file = temp_dir / "progress.yaml"
        progress_file.write_text("- bad-root\n")

        with pytest.raises(ValueError, match="expected YAML mapping/object root"):
            update_progress(
                str(temp_dir),
                "mission_context",
                {"phase": "x"},
            )

    def test_update_list_section_rejects_non_append_dict_payload(self, sample_progress_yaml):
        """List sections should not be overwritten by malformed dict payloads."""
        with pytest.raises(ValueError, match="must include 'append' or list 'replace'"):
            update_progress(
                str(sample_progress_yaml.parent),
                "implementer_log",
                {"entry": "not-valid"},
            )

        with open(sample_progress_yaml) as f:
            saved = yaml.safe_load(f)
        assert saved["implementer_log"] == []

    def test_update_dict_section_requires_mapping_payload(self, sample_progress_yaml):
        """Dict sections require mapping payloads for merge semantics."""
        with pytest.raises(ValueError, match="requires mapping payload"):
            update_progress(
                str(sample_progress_yaml.parent),
                "mission_context",
                "not-a-dict",
            )

    def test_update_list_section_allows_list_replace(self, sample_progress_yaml):
        """List sections can be explicitly replaced with list payloads."""
        result = update_progress(
            str(sample_progress_yaml.parent),
            "implementer_log",
            [{"step": "replace"}],
        )

        assert result["implementer_log"] == [{"step": "replace"}]


# =============================================================================
# Tests: list_files
# =============================================================================

class TestListFiles:
    """Tests for list_files tool."""
    
    def test_list_valid_directory(self, sample_files):
        """list_files returns file list for valid directory."""
        result = list_files(str(sample_files))
        
        assert isinstance(result, list)
        assert len(result) >= 3  # subdir, test.py, readme.md
        
        names = [f["name"] for f in result]
        assert "test.py" in names
        assert "readme.md" in names
        assert "subdir" in names
    
    def test_list_excludes_hidden(self, sample_files):
        """list_files excludes hidden files by default."""
        result = list_files(str(sample_files), include_hidden=False)
        
        names = [f["name"] for f in result]
        assert ".hidden" not in names
    
    def test_list_includes_hidden(self, sample_files):
        """list_files includes hidden files when requested."""
        result = list_files(str(sample_files), include_hidden=True)
        
        names = [f["name"] for f in result]
        assert ".hidden" in names
    
    def test_list_nonexistent_directory(self, temp_dir):
        """list_files raises error for non-existent directory."""
        with pytest.raises(FileNotFoundError):
            list_files(str(temp_dir / "does_not_exist"))
    
    def test_list_empty_directory(self, temp_dir):
        """list_files handles empty directories."""
        empty = temp_dir / "empty"
        empty.mkdir()
        
        result = list_files(str(empty))
        assert result == []
    
    def test_list_file_metadata(self, sample_files):
        """list_files returns proper metadata for files."""
        result = list_files(str(sample_files))
        
        # Find test.py
        test_file = next(f for f in result if f["name"] == "test.py")
        assert test_file["type"] == "file"
        assert "size" in test_file
        assert test_file["size"] > 0
        
        # Find subdir
        subdir = next(f for f in result if f["name"] == "subdir")
        assert subdir["type"] == "directory"


# =============================================================================
# Tests: read_file
# =============================================================================

class TestReadFile:
    """Tests for read_file tool."""
    
    def test_read_valid_file(self, sample_files):
        """read_file returns content for valid file."""
        result = read_file(str(sample_files / "test.py"))
        
        assert "def hello():" in result
        assert "return 'world'" in result
    
    def test_read_nonexistent_file(self, temp_dir):
        """read_file raises error for non-existent file."""
        with pytest.raises(FileNotFoundError):
            read_file(str(temp_dir / "does_not_exist.txt"))
    
    def test_read_directory_error(self, sample_files):
        """read_file raises error when path is directory."""
        with pytest.raises(IsADirectoryError):
            read_file(str(sample_files))
    
    def test_read_binary_encoding_error(self, temp_dir):
        """read_file handles binary/encoding errors gracefully."""
        binary_file = temp_dir / "binary.bin"
        binary_file.write_bytes(b"\x00\x01\x02\xff\xfe\xfd")
        
        with pytest.raises(ValueError, match="Failed to decode"):
            read_file(str(binary_file), encoding="utf-8")


# =============================================================================
# Tests: write_file
# =============================================================================

class TestWriteFile:
    """Tests for write_file tool."""

    def test_write_blocked_without_mission_path(self, temp_dir):
        """write_file is blocked when no mission_path is set (fail-closed)."""
        target = temp_dir / "new_file.txt"

        result = write_file(str(target), "Hello, World!")

        assert result["success"] is False
        assert result["approval_required"] is True
        assert not target.exists()

    def test_write_allowed_for_scientist(self, temp_dir):
        """write_file succeeds when current_agent is scientist (bypass agent)."""
        (temp_dir / "progress.yaml").write_text("current_agent: scientist\n")
        target = temp_dir / "new_file.txt"

        result = write_file(str(target), "Hello, World!", mission_path=str(temp_dir))

        assert result["success"] is True
        assert result["bytes_written"] == 13
        assert target.read_text() == "Hello, World!"

    def test_write_requires_approval_when_implementer(self, sample_progress_yaml, temp_dir):
        """write_file requires approval when current_agent=implementer."""
        target = temp_dir / "new_file.txt"

        result = write_file(
            str(target),
            "Hello, World!",
            mission_path=str(sample_progress_yaml.parent),
        )

        assert result["success"] is False
        assert result["approval_required"] is True
        assert "HITL approval required" in result["message"]
        assert not target.exists()

    def test_write_creates_parent_directories(self, temp_dir):
        """write_file creates parent directories if needed."""
        (temp_dir / "progress.yaml").write_text("current_agent: scientist\n")
        target = temp_dir / "nested" / "deep" / "file.txt"

        result = write_file(
            str(target), "Nested content",
            mission_path=str(temp_dir), create_dirs=True,
        )

        assert result["success"] is True
        assert target.exists()
        assert target.read_text() == "Nested content"

    def test_write_with_env_auto_approve(self, temp_dir, sample_progress_yaml):
        """write_file respects MYCELIUM_HITL_AUTO_APPROVE env var."""
        target = temp_dir / "new_file.txt"
        from mycelium.mcp import server

        original_value = server.HITL_AUTO_APPROVE
        server.HITL_AUTO_APPROVE = True

        try:
            result = write_file(
                str(target),
                "Auto approved content",
                mission_path=str(sample_progress_yaml.parent),
            )

            assert result["success"] is True
        finally:
            server.HITL_AUTO_APPROVE = original_value


# =============================================================================
# Tests: HITL gate (fail-closed + normalization)
# =============================================================================

class TestHITLGate:
    """Tests for fail-closed HITL gate and current_agent normalization."""

    def test_fail_closed_missing_progress(self, temp_dir):
        """HITL gate requires approval when progress.yaml is missing."""
        requires, reason = requires_approval(str(temp_dir))
        assert requires is True
        assert "could not be determined" in reason

    def test_fail_closed_empty_agent(self, temp_dir):
        """HITL gate requires approval when current_agent is empty."""
        (temp_dir / "progress.yaml").write_text("current_agent: ''\n")
        requires, reason = requires_approval(str(temp_dir))
        assert requires is True
        assert "could not be determined" in reason

    def test_fail_closed_malformed_yaml(self, temp_dir):
        """HITL gate requires approval when YAML is malformed."""
        (temp_dir / "progress.yaml").write_text("current_agent: [broken\n")
        requires, reason = requires_approval(str(temp_dir))
        assert requires is True
        assert "could not be determined" in reason

    def test_normalize_implementer_case(self, temp_dir):
        """HITL gate blocks 'Implementer' (case-insensitive)."""
        (temp_dir / "progress.yaml").write_text("current_agent: Implementer\n")
        requires, reason = requires_approval(str(temp_dir))
        assert requires is True
        assert "implementer" in reason

    def test_normalize_implementer_uppercase(self, temp_dir):
        """HITL gate blocks 'IMPLEMENTER' (case-insensitive)."""
        (temp_dir / "progress.yaml").write_text("current_agent: IMPLEMENTER\n")
        requires, reason = requires_approval(str(temp_dir))
        assert requires is True

    def test_scientist_bypasses_gate(self, temp_dir):
        """Scientist agent bypasses HITL gate."""
        (temp_dir / "progress.yaml").write_text("current_agent: scientist\n")
        requires, _ = requires_approval(str(temp_dir))
        assert requires is False

    def test_verifier_bypasses_gate(self, temp_dir):
        """Verifier agent bypasses HITL gate."""
        (temp_dir / "progress.yaml").write_text("current_agent: verifier\n")
        requires, _ = requires_approval(str(temp_dir))
        assert requires is False

    def test_maintainer_bypasses_gate(self, temp_dir):
        """Maintainer agent bypasses HITL gate."""
        (temp_dir / "progress.yaml").write_text("current_agent: Maintainer\n")
        requires, _ = requires_approval(str(temp_dir))
        assert requires is False

    def test_unknown_agent_requires_approval(self, temp_dir):
        """Unknown agent role requires approval (fail-closed)."""
        (temp_dir / "progress.yaml").write_text("current_agent: rogue_agent\n")
        requires, reason = requires_approval(str(temp_dir))
        assert requires is True
        assert "rogue_agent" in reason

    def test_env_auto_approve_overrides(self, temp_dir):
        """HITL_AUTO_APPROVE env var bypasses gate regardless of agent."""
        (temp_dir / "progress.yaml").write_text("current_agent: implementer\n")
        from mycelium.mcp import server

        original = server.HITL_AUTO_APPROVE
        server.HITL_AUTO_APPROVE = True
        try:
            requires, _ = requires_approval(str(temp_dir))
            assert requires is False
        finally:
            server.HITL_AUTO_APPROVE = original

    def test_no_mission_path_requires_approval(self):
        """No mission_path triggers fail-closed (approval required)."""
        requires, reason = requires_approval(None)
        assert requires is True
        assert "fail-closed" in reason

    def test_empty_mission_path_requires_approval(self):
        """Empty mission_path triggers fail-closed."""
        requires, reason = requires_approval("")
        assert requires is True
        assert "fail-closed" in reason

    def test_get_current_agent_normalizes(self, temp_dir):
        """_get_current_agent returns lowercased, stripped value."""
        (temp_dir / "progress.yaml").write_text("current_agent: '  Scientist  '\n")
        assert get_current_agent(str(temp_dir)) == "scientist"

    def test_get_current_agent_returns_none_on_missing(self, temp_dir):
        """_get_current_agent returns None when file is missing."""
        assert get_current_agent(str(temp_dir / "nonexistent")) is None

    def test_get_current_agent_normalizes_non_string(self, temp_dir):
        """_get_current_agent normalizes non-string current_agent via _normalize_agent_value."""
        (temp_dir / "progress.yaml").write_text("current_agent:\n  nested: value\n")
        # _normalize_agent_value stringifies dicts without recognized keys
        result = get_current_agent(str(temp_dir))
        assert isinstance(result, str)

    def test_write_requires_approval_with_malformed_nested_implementer(self, sample_progress_yaml, temp_dir):
        """Malformed nested current_agent payloads should still enforce HITL approval."""
        with open(sample_progress_yaml) as f:
            progress = yaml.safe_load(f)
        progress["current_agent"] = {"current_agent": {"value": "implementer"}}
        with open(sample_progress_yaml, "w") as f:
            yaml.dump(progress, f)

        target = temp_dir / "malformed-guard.txt"
        result = write_file(
            str(target),
            "blocked",
            mission_path=str(sample_progress_yaml.parent),
        )

        assert result["success"] is False
        assert result["approval_required"] is True
        assert not target.exists()

    def test_write_requires_approval_when_current_agent_unreadable(self, temp_dir):
        """Unreadable progress state should fail closed and require approval."""
        mission_dir = temp_dir / "mission"
        mission_dir.mkdir()
        (mission_dir / "progress.yaml").write_text("current_agent: [broken\n")

        target = temp_dir / "unreadable-guard.txt"
        result = write_file(
            str(target),
            "blocked",
            mission_path=str(mission_dir),
        )

        assert result["success"] is False
        assert result["approval_required"] is True
        assert "fail-closed" in result["reason"]
        assert not target.exists()


# =============================================================================
# Tests: run_command
# =============================================================================

class TestRunCommand:
    """Tests for run_command tool."""

    @pytest.fixture(autouse=True)
    def _scientist_mission(self, temp_dir):
        """Create a scientist mission so HITL gate is bypassed for command tests."""
        (temp_dir / "progress.yaml").write_text("current_agent: scientist\n")
        self._mission = str(temp_dir)

    def _run(self, command, **kwargs):
        """Helper: run command with scientist mission_path."""
        kwargs.setdefault("mission_path", self._mission)
        return run_command(command, **kwargs)

    def test_run_blocked_without_mission_path(self, temp_dir):
        """run_command is blocked when no mission_path is set (fail-closed)."""
        result = run_command("echo Hello", cwd=str(temp_dir))

        assert result["success"] is False
        assert result["approval_required"] is True

    def test_run_allowed_for_scientist(self, temp_dir):
        """run_command executes for bypass agents."""
        result = self._run("echo Hello, World!", cwd=str(temp_dir))

        assert result["success"] is True
        assert "Hello, World!" in result["stdout"]
        assert result["exit_code"] == 0

    def test_run_requires_approval_when_implementer(self, sample_progress_yaml, temp_dir):
        """run_command requires approval when current_agent=implementer."""
        result = run_command(
            "echo test",
            cwd=str(temp_dir),
            mission_path=str(sample_progress_yaml.parent),
        )

        assert result["success"] is False
        assert result["approval_required"] is True
        assert "HITL approval required" in result["message"]

    def test_run_handles_timeout(self, temp_dir):
        """run_command handles command timeout."""
        # Use 'tail -f /dev/null' which blocks indefinitely using an allowed command
        result = self._run(
            "tail -f /dev/null",
            cwd=str(temp_dir),
            timeout=1,
        )

        assert result["success"] is False
        assert "timed out" in result["error"]

    def test_run_failing_command(self, temp_dir):
        """run_command captures exit code for failing commands."""
        # Use 'grep' with a pattern that won't match to get exit code 1
        result = self._run(
            "grep __NOMATCH__ /dev/null",
            cwd=str(temp_dir),
        )

        assert result["success"] is False
        assert result["exit_code"] == 1

    def test_run_blocks_disallowed_command(self, temp_dir):
        """run_command rejects commands not in the allowlist."""
        result = self._run("rm -rf /", cwd=str(temp_dir))

        assert result["success"] is False
        assert "not in the allowed command list" in result["error"]

    def test_run_blocks_shell_injection(self, temp_dir):
        """run_command prevents shell metacharacter injection."""
        result = self._run("echo safe; rm -rf /", cwd=str(temp_dir))

        # shlex.split treats ";" as a literal arg to echo, not a command separator
        assert result["success"] is True
        assert "safe; rm -rf /" in result["stdout"]

    def test_run_blocks_absolute_path_to_disallowed(self, temp_dir):
        """run_command checks base name, blocking /bin/sh etc."""
        result = self._run("/bin/sh -c 'echo pwned'", cwd=str(temp_dir))

        assert result["success"] is False
        assert "not in the allowed command list" in result["error"]

    def test_run_empty_command(self, temp_dir):
        """run_command rejects empty command string."""
        result = self._run("", cwd=str(temp_dir))

        assert result["success"] is False

    def test_allowlist_contains_expected_commands(self):
        """COMMAND_ALLOWLIST includes essential safe commands."""
        for cmd in ("echo", "git", "pytest", "ls", "grep", "br"):
            assert cmd in COMMAND_ALLOWLIST

    def test_allowlist_excludes_dangerous_commands(self):
        """COMMAND_ALLOWLIST excludes shell and destructive commands."""
        for cmd in ("sh", "bash", "zsh", "rm", "curl", "wget", "nc", "ncat", "python", "python3"):
            assert cmd not in COMMAND_ALLOWLIST

    def test_run_requires_approval_with_malformed_list_implementer(self, sample_progress_yaml, temp_dir):
        """Malformed list-shaped current_agent payloads should still enforce HITL approval."""
        with open(sample_progress_yaml) as f:
            progress = yaml.safe_load(f)
        progress["current_agent"] = [{"unexpected": "shape"}, {"value": "implementer"}]
        with open(sample_progress_yaml, "w") as f:
            yaml.dump(progress, f)

        result = run_command(
            "echo 'should not run'",
            cwd=str(temp_dir),
            mission_path=str(sample_progress_yaml.parent),
        )

        assert result["success"] is False
        assert result["approval_required"] is True

    def test_run_requires_approval_when_current_agent_unreadable(self, temp_dir):
        """Unreadable progress state should fail closed and require approval."""
        mission_dir = temp_dir / "mission"
        mission_dir.mkdir()
        (mission_dir / "progress.yaml").write_text("current_agent: [broken\n")

        result = run_command(
            "echo 'should not run'",
            cwd=str(temp_dir),
            mission_path=str(mission_dir),
        )

        assert result["success"] is False
        assert result["approval_required"] is True
        assert "fail-closed" in result["reason"]


# =============================================================================
# Tests: search_codebase
# =============================================================================

class TestSearchCodebase:
    """Tests for search_codebase tool."""
    
    def test_search_finds_matches(self, sample_files):
        """search_codebase finds matches for known pattern."""
        result = search_codebase(
            "hello",
            directory=str(sample_files),
        )
        
        assert len(result) >= 1
        match = result[0]
        assert "test.py" in match["file"]
        assert match["line_number"] == 1
        assert "hello" in match["content"].lower()
    
    def test_search_no_matches(self, sample_files):
        """search_codebase returns empty list for no matches."""
        result = search_codebase(
            "this_pattern_does_not_exist_anywhere",
            directory=str(sample_files),
        )
        
        assert result == []
    
    def test_search_regex_patterns(self, sample_files):
        """search_codebase handles regex patterns."""
        result = search_codebase(
            r"def \w+\(\):",
            directory=str(sample_files),
            is_regex=True,
        )
        
        assert len(result) >= 1
        assert any("def hello():" in m["content"] for m in result)
    
    def test_search_respects_directory_scope(self, sample_files):
        """search_codebase respects directory scope."""
        # Search only in subdir
        result = search_codebase(
            "content",
            directory=str(sample_files / "subdir"),
        )
        
        # Should find nested.txt but not readme.md
        assert len(result) >= 1
        assert all("subdir" in m["file"] for m in result)
    
    def test_search_file_pattern(self, sample_files):
        """search_codebase filters by file pattern."""
        result = search_codebase(
            "content",
            directory=str(sample_files),
            file_pattern="*.md",
        )
        
        # Should only find in .md files
        assert all(m["file"].endswith(".md") for m in result)
    
    def test_search_case_insensitive(self, sample_files):
        """search_codebase handles case insensitivity."""
        result = search_codebase(
            "HELLO",
            directory=str(sample_files),
            case_insensitive=True,
        )
        
        assert len(result) >= 1
        
        result_sensitive = search_codebase(
            "HELLO",
            directory=str(sample_files),
            case_insensitive=False,
        )
        
        # Should find fewer or no matches with case sensitive
        assert len(result_sensitive) <= len(result)
    
    def test_search_max_results(self, temp_dir):
        """search_codebase respects max_results limit."""
        # Create many files with matches
        for i in range(20):
            (temp_dir / f"file_{i}.txt").write_text("match this pattern\n")
        
        result = search_codebase(
            "match",
            directory=str(temp_dir),
            max_results=5,
        )
        
        assert len(result) == 5

    def test_search_zero_max_results_returns_empty(self, temp_dir):
        """max_results <= 0 should return no matches."""
        (temp_dir / "file.txt").write_text("match this pattern\n")

        result = search_codebase(
            "match",
            directory=str(temp_dir),
            max_results=0,
        )

        assert result == []

    def test_search_invalid_max_results_raises_value_error(self, temp_dir):
        """Non-integer max_results values should raise a clear validation error."""
        (temp_dir / "file.txt").write_text("match this pattern\n")

        with pytest.raises(ValueError, match="max_results must be an integer"):
            search_codebase(
                "match",
                directory=str(temp_dir),
                max_results="bad",  # type: ignore[arg-type]
            )


# =============================================================================
# Integration: MCP Server
# =============================================================================

class TestMCPServerIntegration:
    """Integration tests for the MCP server."""
    
    def test_mcp_server_exports_tools(self):
        """MCP server exports all 7 tools."""
        from mycelium.mcp.server import mcp
        
        # The fastmcp server should have all our tools registered
        # This is a basic sanity check that the server is properly configured
        assert mcp is not None
        assert mcp.name == "Mycelium MCP Server"
    
    def test_server_module_import(self):
        """Server module can be imported without errors."""
        from mycelium.mcp import mcp as server_instance
        
        assert server_instance is not None
    
    def test_main_module_exists(self):
        """__main__.py module exists and is importable."""
        # This should not raise
        import mycelium.mcp.__main__
        assert hasattr(mycelium.mcp.__main__, "mcp")


# =============================================================================
# Tests: Path sandbox (bd-1fn)
# =============================================================================

class TestPathSandbox:
    """Verify file I/O tools are confined to the sandbox root."""

    def test_safe_resolve_allows_child(self, temp_dir):
        """_safe_resolve allows paths within the sandbox."""
        target = temp_dir / "subdir" / "file.txt"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("ok")
        result = _safe_resolve(str(target))
        assert result == target.resolve()

    def test_safe_resolve_blocks_traversal(self, temp_dir):
        """_safe_resolve blocks paths that escape the sandbox."""
        with pytest.raises(PathNotAllowedError):
            _safe_resolve(str(temp_dir / ".." / ".." / "etc" / "passwd"))

    def test_safe_resolve_blocks_absolute_outside(self, temp_dir):
        """_safe_resolve blocks absolute paths outside sandbox."""
        with pytest.raises(PathNotAllowedError):
            _safe_resolve("/etc/passwd")

    def test_read_file_sandbox(self, temp_dir):
        """read_file blocks reads outside sandbox."""
        with pytest.raises(PathNotAllowedError):
            read_file("/etc/passwd")

    def test_list_files_sandbox(self, temp_dir):
        """list_files blocks listing outside sandbox."""
        with pytest.raises(PathNotAllowedError):
            list_files("/etc")

    def test_write_file_sandbox(self, temp_dir):
        """write_file blocks writes outside sandbox."""
        (temp_dir / "progress.yaml").write_text("current_agent: scientist\n")
        result = write_file("/tmp/evil.txt", "pwned", mission_path=str(temp_dir))
        assert result["success"] is False
        assert "outside the sandbox" in result["error"]

    def test_search_codebase_sandbox(self, temp_dir):
        """search_codebase blocks search outside sandbox."""
        with pytest.raises(PathNotAllowedError):
            search_codebase("password", directory="/etc")

    def test_run_command_cwd_sandbox(self, temp_dir):
        """run_command blocks cwd outside sandbox."""
        (temp_dir / "progress.yaml").write_text("current_agent: scientist\n")
        result = run_command("echo test", cwd="/etc", mission_path=str(temp_dir))
        assert result["success"] is False
        assert "outside the sandbox" in result["error"]

    def test_symlink_escape_blocked(self, temp_dir):
        """Symlinks that resolve outside sandbox are blocked."""
        link = temp_dir / "sneaky_link"
        link.symlink_to("/etc")
        with pytest.raises(PathNotAllowedError):
            _safe_resolve(str(link / "passwd"))
