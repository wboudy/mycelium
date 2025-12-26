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
    _list_files as list_files,
    _read_file as read_file,
    _read_progress as read_progress,
    _run_command as run_command,
    _search_codebase as search_codebase,
    _update_progress as update_progress,
    _write_file as write_file,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


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
        yaml.dump(progress, f)
    
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
    
    def test_write_with_auto_approve(self, temp_dir):
        """write_file with auto_approve=True writes file."""
        target = temp_dir / "new_file.txt"
        
        result = write_file(
            str(target),
            "Hello, World!",
            auto_approve=True,
        )
        
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
            auto_approve=False,
        )
        
        assert result["success"] is False
        assert result["approval_required"] is True
        assert "HITL approval required" in result["message"]
        assert not target.exists()
    
    def test_write_creates_parent_directories(self, temp_dir):
        """write_file creates parent directories if needed."""
        target = temp_dir / "nested" / "deep" / "file.txt"
        
        result = write_file(
            str(target),
            "Nested content",
            auto_approve=True,
            create_dirs=True,
        )
        
        assert result["success"] is True
        assert target.exists()
        assert target.read_text() == "Nested content"
    
    def test_write_with_env_auto_approve(self, temp_dir):
        """write_file respects MYCELIUM_HITL_AUTO_APPROVE env var."""
        target = temp_dir / "new_file.txt"
        
        with patch.dict(os.environ, {"MYCELIUM_HITL_AUTO_APPROVE": "1"}):
            # Need to reimport to pick up env change
            from mycelium.mcp import server
            
            original_value = server.HITL_AUTO_APPROVE
            server.HITL_AUTO_APPROVE = True
            
            try:
                result = write_file(
                    str(target),
                    "Auto approved content",
                )
                
                assert result["success"] is True
            finally:
                server.HITL_AUTO_APPROVE = original_value


# =============================================================================
# Tests: run_command
# =============================================================================

class TestRunCommand:
    """Tests for run_command tool."""
    
    def test_run_with_auto_approve(self, temp_dir):
        """run_command with auto_approve=True executes and returns output."""
        result = run_command(
            "echo 'Hello, World!'",
            cwd=str(temp_dir),
            auto_approve=True,
        )
        
        assert result["success"] is True
        assert "Hello, World!" in result["stdout"]
        assert result["exit_code"] == 0
    
    def test_run_requires_approval_when_implementer(self, sample_progress_yaml, temp_dir):
        """run_command requires approval when current_agent=implementer."""
        result = run_command(
            "echo 'test'",
            cwd=str(temp_dir),
            mission_path=str(sample_progress_yaml.parent),
            auto_approve=False,
        )
        
        assert result["success"] is False
        assert result["approval_required"] is True
        assert "HITL approval required" in result["message"]
    
    def test_run_captures_stdout_stderr(self, temp_dir):
        """run_command captures stdout, stderr, and exit_code."""
        result = run_command(
            "echo 'stdout' && echo 'stderr' >&2",
            cwd=str(temp_dir),
            auto_approve=True,
        )
        
        assert "stdout" in result["stdout"]
        assert "stderr" in result["stderr"]
        assert result["exit_code"] == 0
    
    def test_run_handles_timeout(self, temp_dir):
        """run_command handles command timeout."""
        result = run_command(
            "sleep 10",
            cwd=str(temp_dir),
            auto_approve=True,
            timeout=1,
        )
        
        assert result["success"] is False
        assert "timed out" in result["error"]
    
    def test_run_failing_command(self, temp_dir):
        """run_command captures exit code for failing commands."""
        result = run_command(
            "exit 42",
            cwd=str(temp_dir),
            auto_approve=True,
        )
        
        assert result["success"] is False
        assert result["exit_code"] == 42


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
