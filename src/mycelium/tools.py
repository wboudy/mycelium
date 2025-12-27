"""
LiteLLM Tool Schemas for Mycelium.

Provides OpenAI-compatible function schemas for all 7 MCP tools,
enabling LLM function-calling during agent execution.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# Tool Schemas (OpenAI-compatible format)
# =============================================================================

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "read_progress",
            "description": "Read and parse a mission's progress.yaml file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "mission_path": {
                        "type": "string",
                        "description": "Path to mission directory or progress.yaml file.",
                    },
                },
                "required": ["mission_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_progress",
            "description": "Update a specific section of a mission's progress.yaml file. Valid sections: current_agent, mission_context, scientist_plan, implementer_log, verifier_report, maintainer_notes, maintainer_summary, llm_usage, commit_message.",
            "parameters": {
                "type": "object",
                "properties": {
                    "mission_path": {
                        "type": "string",
                        "description": "Path to mission directory or progress.yaml file.",
                    },
                    "section": {
                        "type": "string",
                        "description": "Name of the section to update (e.g., 'scientist_plan', 'implementer_log').",
                        "enum": [
                            "current_agent",
                            "mission_context",
                            "scientist_plan",
                            "implementer_log",
                            "verifier_report",
                            "maintainer_notes",
                            "maintainer_summary",
                            "llm_usage",
                            "commit_message",
                        ],
                    },
                    "data": {
                        "type": "object",
                        "description": "Dictionary containing the data to merge into the section.",
                    },
                },
                "required": ["mission_path", "section", "data"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List contents of a directory. Returns file/directory info with name, type, and size.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Path to directory to list.",
                    },
                    "include_hidden": {
                        "type": "boolean",
                        "description": "Whether to include hidden files (starting with .). Default: false.",
                        "default": False,
                    },
                },
                "required": ["directory"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read contents of a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to file to read.",
                    },
                    "encoding": {
                        "type": "string",
                        "description": "Character encoding to use. Default: utf-8.",
                        "default": "utf-8",
                    },
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file. May require HITL approval when current_agent is implementer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to file to write.",
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write to the file.",
                    },
                    "mission_path": {
                        "type": "string",
                        "description": "Optional path to mission for HITL check.",
                        "default": "",
                    },
                    "auto_approve": {
                        "type": "boolean",
                        "description": "If True, bypass HITL approval. Default: false.",
                        "default": False,
                    },
                    "create_dirs": {
                        "type": "boolean",
                        "description": "If True, create parent directories if they don't exist. Default: true.",
                        "default": True,
                    },
                },
                "required": ["file_path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Execute a shell command. May require HITL approval when current_agent is implementer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell command to execute.",
                    },
                    "cwd": {
                        "type": "string",
                        "description": "Working directory for command. Defaults to current directory.",
                        "default": "",
                    },
                    "mission_path": {
                        "type": "string",
                        "description": "Optional path to mission for HITL check.",
                        "default": "",
                    },
                    "auto_approve": {
                        "type": "boolean",
                        "description": "If True, bypass HITL approval. Default: false.",
                        "default": False,
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Command timeout in seconds. Default: 60.",
                        "default": 60,
                    },
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_codebase",
            "description": "Search for a pattern in files (grep-like functionality).",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Search pattern (string or regex).",
                    },
                    "directory": {
                        "type": "string",
                        "description": "Directory to search in. Default: current directory.",
                        "default": ".",
                    },
                    "file_pattern": {
                        "type": "string",
                        "description": "Optional glob pattern to filter files (e.g., '*.py').",
                        "default": "",
                    },
                    "is_regex": {
                        "type": "boolean",
                        "description": "If True, treat pattern as regex; otherwise literal string. Default: false.",
                        "default": False,
                    },
                    "case_insensitive": {
                        "type": "boolean",
                        "description": "If True, ignore case when matching. Default: true.",
                        "default": True,
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return. Default: 50.",
                        "default": 50,
                    },
                },
                "required": ["pattern"],
            },
        },
    },
]


# =============================================================================
# Helper Functions
# =============================================================================

def get_tool_by_name(name: str) -> dict[str, Any] | None:
    """
    Get a tool schema by name.
    
    Args:
        name: Tool name (e.g., 'read_progress').
        
    Returns:
        Tool schema dict, or None if not found.
    """
    for tool in TOOL_SCHEMAS:
        if tool.get("function", {}).get("name") == name:
            return tool
    return None


def get_tool_names() -> list[str]:
    """Get list of all available tool names."""
    return [tool["function"]["name"] for tool in TOOL_SCHEMAS]


def execute_tool(name: str, arguments: dict[str, Any]) -> Any:
    """
    Execute a tool by name with given arguments.
    
    Args:
        name: Tool name to execute.
        arguments: Dictionary of arguments to pass to the tool.
        
    Returns:
        Tool execution result.
        
    Raises:
        ValueError: If tool name is unknown.
    """
    # Import tool implementations from mcp.server
    from mycelium.mcp.server import (
        _list_files,
        _read_file,
        _read_progress,
        _run_command,
        _search_codebase,
        _update_progress,
        _write_file,
    )
    
    # Map tool names to their implementations
    tool_map = {
        "read_progress": _read_progress,
        "update_progress": _update_progress,
        "list_files": _list_files,
        "read_file": _read_file,
        "write_file": _write_file,
        "run_command": _run_command,
        "search_codebase": _search_codebase,
    }
    
    if name not in tool_map:
        raise ValueError(f"Unknown tool: {name}. Available tools: {list(tool_map.keys())}")
    
    logger.info(f"Executing tool: {name} with args: {list(arguments.keys())}")
    
    try:
        result = tool_map[name](**arguments)
        logger.debug(f"Tool {name} completed successfully")
        return result
    except Exception as e:
        logger.error(f"Tool {name} failed: {e}")
        raise


def format_tool_result(tool_name: str, result: Any) -> str:
    """
    Format a tool result for inclusion in LLM messages.
    
    Args:
        tool_name: Name of the tool that produced the result.
        result: Raw result from tool execution.
        
    Returns:
        JSON string representation of the result.
    """
    if isinstance(result, str):
        # For string results (like file contents), truncate if too long
        if len(result) > 10000:
            return json.dumps({
                "content": result[:10000],
                "truncated": True,
                "total_length": len(result),
            })
        return json.dumps({"content": result})
    elif isinstance(result, (dict, list)):
        return json.dumps(result, default=str)
    else:
        return json.dumps({"result": str(result)})
