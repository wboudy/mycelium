"""
Mycelium MCP Server.

Implements 7 tools for MCP-compatible clients:
- read_progress: Read mission progress.yaml
- update_progress: Update progress.yaml sections
- list_files: List directory contents
- read_file: Read file contents
- write_file: Write files with HITL gate
- run_command: Execute commands with HITL gate
- search_codebase: Grep-like search
"""

from __future__ import annotations

import fcntl
import os
import re
import shlex
import subprocess
from pathlib import Path
from typing import Any

import yaml
from fastmcp import FastMCP

# Create the MCP server instance
mcp = FastMCP("Mycelium MCP Server")

# Environment variable to control auto-approval (for testing/automation)
HITL_AUTO_APPROVE = os.environ.get("MYCELIUM_HITL_AUTO_APPROVE", "").lower() in ("1", "true", "yes")

# Allowed command executables. Only these base names may be invoked via run_command.
# This prevents arbitrary binary execution through the MCP interface.
COMMAND_ALLOWLIST = frozenset({
    "br", "bd",                                          # beads CLI
    "cat", "head", "tail", "wc", "grep", "find", "ls",  # filesystem inspection
    "echo", "printf", "date", "pwd",                     # basic utilities
    "git",                                               # version control
    # python/pip intentionally excluded — allows arbitrary code execution
    "pytest",                                            # test runner
    "mkdir", "cp", "mv", "touch",                        # safe filesystem ops
})

# Sandbox root: all file I/O tools are confined to this directory.
# Set MYCELIUM_MCP_SANDBOX_ROOT to override. Defaults to cwd.
SANDBOX_ROOT = Path(os.environ.get("MYCELIUM_MCP_SANDBOX_ROOT", ".")).resolve()


class PathNotAllowedError(ValueError):
    """Raised when a path escapes the MCP sandbox root."""


def _safe_resolve(user_path: str) -> Path:
    """Resolve a user-provided path and verify it's within the sandbox.

    Args:
        user_path: Path string from the MCP client.

    Returns:
        Resolved absolute Path.

    Raises:
        PathNotAllowedError: If the resolved path escapes SANDBOX_ROOT.
    """
    resolved = Path(user_path).resolve()
    sandbox = SANDBOX_ROOT
    if resolved == sandbox or str(resolved).startswith(str(sandbox) + os.sep):
        return resolved
    raise PathNotAllowedError(
        f"Path '{user_path}' resolves outside the sandbox root ({sandbox})"
    )


def _normalize_agent_value(raw_agent: Any) -> str:
    """Normalize current_agent values that may be malformed by LLM writes."""
    def _normalize(value: Any, allow_fallback_stringify: bool) -> str:
        if value is None:
            return ""

        if isinstance(value, dict):
            saw_agent_key = False
            for key in ("current_agent", "value", "agent"):
                if key in value:
                    saw_agent_key = True
                    normalized = _normalize(value[key], allow_fallback_stringify=False)
                    if normalized:
                        return normalized
            if saw_agent_key:
                return ""
            if allow_fallback_stringify:
                return str(value).strip().lower()
            return ""

        if isinstance(value, (list, tuple)):
            for item in value:
                normalized = _normalize(item, allow_fallback_stringify=False)
                if normalized:
                    return normalized
            return ""

        if isinstance(value, set):
            for item in sorted(value, key=str):
                normalized = _normalize(item, allow_fallback_stringify=False)
                if normalized:
                    return normalized
            return ""

        return str(value).strip().lower()

    return _normalize(raw_agent, allow_fallback_stringify=True)


def _get_current_agent(mission_path: str) -> str | None:
    """Get normalized current_agent from progress.yaml, or None if unreadable."""
    progress_file = Path(mission_path)
    if progress_file.is_dir():
        progress_file = progress_file / "progress.yaml"

    if not progress_file.exists():
        return None

    try:
        with open(progress_file) as f:
            progress = yaml.safe_load(f) or {}
        if not isinstance(progress, dict):
            return None
        return _normalize_agent_value(progress.get("current_agent", ""))
    except Exception:
        return None


# Agents that are explicitly allowed to bypass HITL approval.
_HITL_BYPASS_AGENTS = frozenset({"scientist", "verifier", "maintainer"})


def _requires_approval(mission_path: str | None = None) -> tuple[bool, str]:
    """
    Check if HITL approval is required.

    Fail-closed: approval is required by default. Only agents in
    _HITL_BYPASS_AGENTS or the HITL_AUTO_APPROVE env var can bypass.

    Returns:
        Tuple of (requires_approval, reason)
    """
    if HITL_AUTO_APPROVE:
        return False, "HITL_AUTO_APPROVE enabled via environment"

    if not mission_path:
        return True, "no mission_path provided (fail-closed)"

    current_agent = _get_current_agent(mission_path)
    if current_agent is None:
        return True, "current_agent could not be determined (fail-closed)"
    if current_agent in _HITL_BYPASS_AGENTS:
        return False, f"current_agent '{current_agent}' is allowed"
    return True, f"current_agent '{current_agent}' requires approval"


# =============================================================================
# Tool Logic (testable functions without decorators)
# =============================================================================

def _read_progress(mission_path: str) -> dict[str, Any]:
    """
    Read and parse a mission's progress.yaml file.

    Args:
        mission_path: Path to mission directory or progress.yaml file.

    Returns:
        Parsed progress.yaml content as a dictionary.

    Raises:
        FileNotFoundError: If progress.yaml doesn't exist.
        ValueError: If YAML parsing fails.
        PathNotAllowedError: If path is outside the sandbox.
    """
    # Validate mission_path is within the sandbox
    safe_path = _safe_resolve(mission_path)
    path = safe_path

    if path.is_dir():
        progress_file = path / "progress.yaml"
    elif path.suffix == ".yaml":
        progress_file = path
    else:
        progress_file = path / "progress.yaml"
    
    if not progress_file.exists():
        raise FileNotFoundError(f"progress.yaml not found at: {progress_file}")
    
    try:
        with open(progress_file) as f:
            content = yaml.safe_load(f)
            if content is None:
                return {}
            if not isinstance(content, dict):
                raise ValueError(f"Expected YAML dict, got {type(content).__name__}")
            return content
    except yaml.YAMLError as e:
        raise ValueError(f"Failed to parse YAML: {e}")


def _update_progress(mission_path: str, section: str, data: Any) -> dict[str, Any]:
    """
    Update a specific section of a mission's progress.yaml file.

    Args:
        mission_path: Path to mission directory or progress.yaml file.
        section: Name of the section to update (e.g., 'scientist_plan', 'implementer_log').
        data: Dictionary containing the data to merge into the section.

    Returns:
        Updated progress.yaml content.

    Raises:
        FileNotFoundError: If progress.yaml doesn't exist.
        ValueError: If section is invalid or YAML operations fail.
        PathNotAllowedError: If path is outside the sandbox.
    """
    # Validate mission_path is within the sandbox
    safe_path = _safe_resolve(mission_path)
    path = safe_path

    if path.is_dir():
        progress_file = path / "progress.yaml"
    elif path.suffix == ".yaml":
        progress_file = path
    else:
        progress_file = path / "progress.yaml"
    
    if not progress_file.exists():
        raise FileNotFoundError(f"progress.yaml not found at: {progress_file}")
    
    # Valid sections that can be updated
    valid_sections = {
        "current_agent",
        "mission_context",
        "scientist_plan",
        "implementer_log",
        "verifier_report",
        "maintainer_notes",
        "maintainer_summary",
        "llm_usage",
        "commit_message",
    }
    
    if section not in valid_sections:
        raise ValueError(f"Invalid section: '{section}'. Valid sections: {valid_sections}")
    
    # Use advisory file locking to prevent TOCTOU races from concurrent
    # update_progress calls in a multi-agent system.
    lock_path = progress_file.with_suffix(".yaml.lock")
    lock_fd = open(lock_path, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)

        try:
            with open(progress_file) as f:
                progress = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"Failed to parse existing YAML: {e}")

        if not isinstance(progress, dict):
            raise ValueError("Invalid progress.yaml format: expected YAML mapping/object root")

        # Update the section
        if section == "current_agent":
            # Special case: current_agent is a string, not a dict
            # Validation: Enforce string and handle LLM mistakes (nested dicts)
            val = data.get("value", data) if isinstance(data, dict) else data

            if isinstance(val, dict):
                if "current_agent" in val:
                    val = val["current_agent"]
                elif "value" in val:
                    val = val["value"]
                if isinstance(val, dict):
                    val = str(val)

            progress["current_agent"] = str(val).strip()

        elif isinstance(progress.get(section), list):
            # List sections support append operations or explicit list replacement.
            if isinstance(data, dict):
                if "append" in data:
                    progress[section].append(data["append"])
                elif "replace" in data and isinstance(data["replace"], list):
                    progress[section] = data["replace"]
                else:
                    raise ValueError(
                        f"List section '{section}' update must include 'append' or list 'replace'"
                    )
            elif isinstance(data, list):
                progress[section] = data
            else:
                raise ValueError(
                    f"List section '{section}' update requires dict/list payload, got {type(data).__name__}"
                )

        elif isinstance(progress.get(section), dict):
            # Merge dict sections
            if isinstance(data, dict) and section in data and isinstance(data[section], dict):
                data = data[section]

            if not isinstance(data, dict):
                raise ValueError(
                    f"Dict section '{section}' update requires mapping payload, got {type(data).__name__}"
                )

            progress[section].update(data)

        else:
            # Replace section
            progress[section] = data

        # Write back
        try:
            with open(progress_file, "w") as f:
                yaml.safe_dump(progress, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        except Exception as e:
            raise ValueError(f"Failed to write YAML: {e}")

        return progress
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()


def _list_files(directory: str, include_hidden: bool = False) -> list[dict[str, Any]]:
    """
    List contents of a directory.

    Args:
        directory: Path to directory to list.
        include_hidden: Whether to include hidden files (starting with .).

    Returns:
        List of file/directory info dicts with 'name', 'type', 'size' keys.

    Raises:
        FileNotFoundError: If directory doesn't exist.
        NotADirectoryError: If path is not a directory.
        PathNotAllowedError: If path escapes the sandbox.
    """
    path = _safe_resolve(directory)

    if not path.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")

    if not path.is_dir():
        raise NotADirectoryError(f"Not a directory: {directory}")
    
    results = []
    
    try:
        for item in path.iterdir():
            if not include_hidden and item.name.startswith("."):
                continue
            
            entry = {
                "name": item.name,
                "type": "directory" if item.is_dir() else "file",
            }
            
            if item.is_file():
                try:
                    entry["size"] = item.stat().st_size
                except OSError:
                    entry["size"] = None
            
            results.append(entry)
    except PermissionError as e:
        raise PermissionError(f"Permission denied: {directory}") from e
    
    # Sort: directories first, then files, alphabetically
    results.sort(key=lambda x: (x["type"] != "directory", x["name"].lower()))
    
    return results


def _read_file(file_path: str, encoding: str = "utf-8") -> str:
    """
    Read contents of a file.

    Args:
        file_path: Path to file to read.
        encoding: Character encoding to use (default: utf-8).

    Returns:
        File contents as string.

    Raises:
        FileNotFoundError: If file doesn't exist.
        ValueError: If encoding fails.
        PathNotAllowedError: If path escapes the sandbox.
    """
    path = _safe_resolve(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if path.is_dir():
        raise IsADirectoryError(f"Path is a directory, not a file: {file_path}")
    
    try:
        return path.read_text(encoding=encoding)
    except UnicodeDecodeError as e:
        raise ValueError(f"Failed to decode file with {encoding} encoding: {e}")
    except PermissionError as e:
        raise PermissionError(f"Permission denied: {file_path}") from e


def _write_file(
    file_path: str,
    content: str,
    mission_path: str = "",
    create_dirs: bool = True,
) -> dict[str, Any]:
    """
    Write content to a file. Requires HITL approval when current_agent is implementer.

    Args:
        file_path: Path to file to write.
        content: Content to write to the file.
        mission_path: Optional path to mission for HITL check.
        create_dirs: If True, create parent directories if they don't exist.

    Returns:
        Dict with 'success', 'path', 'bytes_written', and optional 'approval_required'.

    Raises:
        PermissionError: If HITL approval is required but not granted.
    """
    requires, reason = _requires_approval(mission_path)

    if requires:
        return {
            "success": False,
            "approval_required": True,
            "reason": reason,
            "message": f"HITL approval required to write file: {file_path}. Set MYCELIUM_HITL_AUTO_APPROVE=1 to bypass.",
        }
    
    try:
        path = _safe_resolve(file_path)
    except PathNotAllowedError as e:
        return {"success": False, "error": str(e)}

    if create_dirs and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)

    try:
        path.write_text(content)
        return {
            "success": True,
            "path": str(path),
            "bytes_written": len(content.encode("utf-8")),
        }
    except PermissionError as e:
        raise PermissionError(f"Permission denied: {file_path}") from e
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


def _run_command(
    command: str,
    cwd: str = "",
    mission_path: str = "",
    timeout: int = 60,
) -> dict[str, Any]:
    """
    Execute a command. Requires HITL approval when current_agent is implementer.

    The command string is parsed via shlex.split (no shell interpretation).
    Only executables in COMMAND_ALLOWLIST may be invoked.

    Args:
        command: Command string (parsed with shlex, not passed to a shell).
        cwd: Working directory for command (defaults to current directory).
        mission_path: Optional path to mission for HITL check.
        timeout: Command timeout in seconds (default: 60).

    Returns:
        Dict with 'stdout', 'stderr', 'exit_code', and optional 'approval_required'.

    Raises:
        PermissionError: If HITL approval is required but not granted.
    """
    requires, reason = _requires_approval(mission_path)

    if requires:
        return {
            "success": False,
            "approval_required": True,
            "reason": reason,
            "message": f"HITL approval required to run command: {command}. Set MYCELIUM_HITL_AUTO_APPROVE=1 to bypass.",
        }

    try:
        argv = shlex.split(command)
    except ValueError as e:
        return {
            "success": False,
            "error": f"Failed to parse command: {e}",
            "exit_code": -1,
        }

    if not argv:
        return {
            "success": False,
            "error": "Empty command",
            "exit_code": -1,
        }

    # Allowlist check: only the base name of the executable is compared.
    executable = Path(argv[0]).name
    if executable not in COMMAND_ALLOWLIST:
        return {
            "success": False,
            "error": (
                f"Command '{executable}' is not in the allowed command list. "
                f"Allowed: {sorted(COMMAND_ALLOWLIST)}"
            ),
            "exit_code": -1,
        }

    if cwd:
        try:
            working_dir: str | None = str(_safe_resolve(cwd))
        except PathNotAllowedError as e:
            return {"success": False, "error": str(e), "exit_code": -1}
    else:
        working_dir = None

    try:
        result = subprocess.run(
            argv,
            shell=False,
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": f"Command timed out after {timeout} seconds",
            "exit_code": -1,
        }
    except FileNotFoundError:
        return {
            "success": False,
            "error": f"Command not found: {argv[0]}",
            "exit_code": -1,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "exit_code": -1,
        }


def _search_codebase(
    pattern: str,
    directory: str = ".",
    file_pattern: str = "",
    is_regex: bool = False,
    case_insensitive: bool = True,
    max_results: int = 50,
) -> list[dict[str, Any]]:
    """
    Search for a pattern in files (grep-like functionality).
    
    Args:
        pattern: Search pattern (string or regex).
        directory: Directory to search in (default: current directory).
        file_pattern: Optional glob pattern to filter files (e.g., '*.py').
        is_regex: If True, treat pattern as regex; otherwise literal string.
        case_insensitive: If True, ignore case when matching.
        max_results: Maximum number of results to return.
        
    Returns:
        List of match dicts with 'file', 'line_number', 'content' keys.
    """
    try:
        result_limit = int(max_results)
    except (TypeError, ValueError):
        raise ValueError("max_results must be an integer")

    if result_limit <= 0:
        return []

    path = _safe_resolve(directory)

    if not path.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")

    if is_regex:
        flags = re.IGNORECASE if case_insensitive else 0
        try:
            regex = re.compile(pattern, flags)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {e}")
    else:
        if case_insensitive:
            pattern_lower = pattern.lower()
    
    results = []
    
    # Get files to search
    if file_pattern:
        files = list(path.rglob(file_pattern))
    else:
        files = [f for f in path.rglob("*") if f.is_file()]
    
    # Skip common non-text files and directories
    skip_dirs = {".git", ".venv", "__pycache__", "node_modules", ".mycelium/bin"}
    skip_extensions = {".pyc", ".pyo", ".so", ".dylib", ".dll", ".exe", ".bin", ".jpg", ".png", ".gif", ".ico"}
    
    for file in files:
        # Skip excluded directories
        if any(skip_dir in file.parts for skip_dir in skip_dirs):
            continue
        
        # Skip binary files
        if file.suffix.lower() in skip_extensions:
            continue
        
        try:
            content = file.read_text(encoding="utf-8", errors="ignore")
        except (PermissionError, IsADirectoryError):
            continue
        
        for line_num, line in enumerate(content.splitlines(), start=1):
            matched = False
            
            if is_regex:
                matched = bool(regex.search(line))
            else:
                if case_insensitive:
                    matched = pattern_lower in line.lower()
                else:
                    matched = pattern in line
            
            if matched:
                results.append({
                    "file": str(file),
                    "line_number": line_num,
                    "content": line.strip(),
                })
                
                if len(results) >= result_limit:
                    return results
    
    return results


# =============================================================================
# MCP Tools (decorated wrappers that call the underlying functions)
# =============================================================================

@mcp.tool
def read_progress(mission_path: str) -> dict[str, Any]:
    """
    Read and parse a mission's progress.yaml file.
    
    Args:
        mission_path: Path to mission directory or progress.yaml file.
        
    Returns:
        Parsed progress.yaml content as a dictionary.
    """
    return _read_progress(mission_path)


@mcp.tool
def update_progress(mission_path: str, section: str, data: dict[str, Any]) -> dict[str, Any]:
    """
    Update a specific section of a mission's progress.yaml file.
    
    Args:
        mission_path: Path to mission directory or progress.yaml file.
        section: Name of the section to update (e.g., 'scientist_plan', 'implementer_log').
        data: Dictionary containing the data to merge into the section.
        
    Returns:
        Updated progress.yaml content.
    """
    return _update_progress(mission_path, section, data)


@mcp.tool
def list_files(directory: str, include_hidden: bool = False) -> list[dict[str, Any]]:
    """
    List contents of a directory.
    
    Args:
        directory: Path to directory to list.
        include_hidden: Whether to include hidden files (starting with .).
        
    Returns:
        List of file/directory info dicts with 'name', 'type', 'size' keys.
    """
    return _list_files(directory, include_hidden)


@mcp.tool
def read_file(file_path: str, encoding: str = "utf-8") -> str:
    """
    Read contents of a file.
    
    Args:
        file_path: Path to file to read.
        encoding: Character encoding to use (default: utf-8).
        
    Returns:
        File contents as string.
    """
    return _read_file(file_path, encoding)


@mcp.tool
def write_file(
    file_path: str,
    content: str,
    mission_path: str = "",
    create_dirs: bool = True,
) -> dict[str, Any]:
    """
    Write content to a file. Requires HITL approval when current_agent is implementer.

    Args:
        file_path: Path to file to write.
        content: Content to write to the file.
        mission_path: Optional path to mission for HITL check.
        create_dirs: If True, create parent directories if they don't exist.

    Returns:
        Dict with 'success', 'path', 'bytes_written', and optional 'approval_required'.
    """
    return _write_file(file_path, content, mission_path, create_dirs)


@mcp.tool
def run_command(
    command: str,
    cwd: str = "",
    mission_path: str = "",
    timeout: int = 60,
) -> dict[str, Any]:
    """
    Execute a command (no shell interpretation). Requires HITL approval
    when current_agent is implementer.

    Args:
        command: Command string (parsed with shlex, not passed to a shell).
        cwd: Working directory for command (defaults to current directory).
        mission_path: Optional path to mission for HITL check.
        timeout: Command timeout in seconds (default: 60).

    Returns:
        Dict with 'stdout', 'stderr', 'exit_code', and optional 'approval_required'.
    """
    return _run_command(command, cwd, mission_path, timeout)


@mcp.tool
def search_codebase(
    pattern: str,
    directory: str = ".",
    file_pattern: str = "",
    is_regex: bool = False,
    case_insensitive: bool = True,
    max_results: int = 50,
) -> list[dict[str, Any]]:
    """
    Search for a pattern in files (grep-like functionality).
    
    Args:
        pattern: Search pattern (string or regex).
        directory: Directory to search in (default: current directory).
        file_pattern: Optional glob pattern to filter files (e.g., '*.py').
        is_regex: If True, treat pattern as regex; otherwise literal string.
        case_insensitive: If True, ignore case when matching.
        max_results: Maximum number of results to return.
        
    Returns:
        List of match dicts with 'file', 'line_number', 'content' keys.
    """
    return _search_codebase(pattern, directory, file_pattern, is_regex, case_insensitive, max_results)
