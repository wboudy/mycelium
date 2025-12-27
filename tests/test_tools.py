"""
Tests for Mycelium tools module.

Tests tool schema validation and execute_tool dispatch.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from mycelium.tools import (
    TOOL_SCHEMAS,
    execute_tool,
    format_tool_result,
    get_tool_by_name,
    get_tool_names,
)


# =============================================================================
# Tests: Tool Schemas
# =============================================================================

class TestToolSchemas:
    """Tests for TOOL_SCHEMAS list."""
    
    def test_schemas_not_empty(self):
        """TOOL_SCHEMAS contains tools."""
        assert len(TOOL_SCHEMAS) > 0
    
    def test_seven_tools(self):
        """TOOL_SCHEMAS contains exactly 7 tools."""
        assert len(TOOL_SCHEMAS) == 7
    
    def test_all_tools_have_required_fields(self):
        """All tool schemas have type and function fields."""
        for tool in TOOL_SCHEMAS:
            assert "type" in tool
            assert tool["type"] == "function"
            assert "function" in tool
            assert "name" in tool["function"]
            assert "description" in tool["function"]
            assert "parameters" in tool["function"]
    
    def test_all_parameters_have_properties(self):
        """All tool parameters have type and properties."""
        for tool in TOOL_SCHEMAS:
            params = tool["function"]["parameters"]
            assert params["type"] == "object"
            assert "properties" in params
            assert "required" in params
    
    def test_expected_tool_names(self):
        """TOOL_SCHEMAS contains all expected tools."""
        expected = {
            "read_progress",
            "update_progress",
            "list_files",
            "read_file",
            "write_file",
            "run_command",
            "search_codebase",
        }
        actual = set(get_tool_names())
        assert actual == expected


# =============================================================================
# Tests: get_tool_by_name
# =============================================================================

class TestGetToolByName:
    """Tests for get_tool_by_name helper."""
    
    def test_found(self):
        """get_tool_by_name returns tool schema when found."""
        tool = get_tool_by_name("read_progress")
        assert tool is not None
        assert tool["function"]["name"] == "read_progress"
    
    def test_not_found(self):
        """get_tool_by_name returns None for unknown tool."""
        tool = get_tool_by_name("nonexistent_tool")
        assert tool is None
    
    def test_all_tools_findable(self):
        """All tool names can be found."""
        for name in get_tool_names():
            tool = get_tool_by_name(name)
            assert tool is not None


# =============================================================================
# Tests: execute_tool
# =============================================================================

class TestExecuteTool:
    """Tests for execute_tool dispatch."""
    
    @pytest.fixture
    def temp_mission(self, tmp_path):
        """Create a temp mission with progress.yaml."""
        mission_dir = tmp_path / "test-mission"
        mission_dir.mkdir()
        
        progress_data = {
            "current_agent": "scientist",
            "mission_context": {"objective": "test"},
        }
        
        progress_file = mission_dir / "progress.yaml"
        with open(progress_file, "w") as f:
            yaml.dump(progress_data, f)
        
        return mission_dir
    
    def test_unknown_tool_raises(self):
        """execute_tool raises ValueError for unknown tool."""
        with pytest.raises(ValueError, match="Unknown tool"):
            execute_tool("nonexistent_tool", {})
    
    def test_read_progress(self, temp_mission):
        """execute_tool dispatches read_progress correctly."""
        result = execute_tool("read_progress", {"mission_path": str(temp_mission)})
        assert result["current_agent"] == "scientist"
    
    def test_list_files(self, tmp_path):
        """execute_tool dispatches list_files correctly."""
        # Create test files
        (tmp_path / "file1.txt").write_text("content")
        (tmp_path / "file2.py").write_text("code")
        
        result = execute_tool("list_files", {"directory": str(tmp_path)})
        names = [f["name"] for f in result]
        assert "file1.txt" in names
        assert "file2.py" in names
    
    def test_read_file(self, tmp_path):
        """execute_tool dispatches read_file correctly."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world")
        
        result = execute_tool("read_file", {"file_path": str(test_file)})
        assert result == "hello world"
    
    def test_search_codebase(self, tmp_path):
        """execute_tool dispatches search_codebase correctly."""
        (tmp_path / "file.py").write_text("def hello():\n    pass")
        
        result = execute_tool("search_codebase", {
            "pattern": "hello",
            "directory": str(tmp_path),
        })
        assert len(result) > 0
        assert any("hello" in r["content"] for r in result)


# =============================================================================
# Tests: format_tool_result
# =============================================================================

class TestFormatToolResult:
    """Tests for format_tool_result helper."""
    
    def test_string_result(self):
        """format_tool_result handles string results."""
        result = format_tool_result("read_file", "file content here")
        assert '"content":' in result
        assert "file content here" in result
    
    def test_dict_result(self):
        """format_tool_result handles dict results."""
        result = format_tool_result("list_files", {"name": "test.txt", "type": "file"})
        assert "test.txt" in result
        assert "file" in result
    
    def test_list_result(self):
        """format_tool_result handles list results."""
        result = format_tool_result("search_codebase", [{"file": "a.py", "line_number": 1}])
        assert "a.py" in result
    
    def test_long_string_truncated(self):
        """format_tool_result truncates very long strings."""
        long_content = "x" * 15000
        result = format_tool_result("read_file", long_content)
        assert "truncated" in result
        assert len(result) < 15000
