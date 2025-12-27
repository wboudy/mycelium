"""
Orchestrator Module for Mycelium.

Manages the execution of agents by:
1. Reading mission progress.yaml
2. Building agent prompts from templates
3. Invoking LLM via the llm module (handling tool calls)
4. Logging usage back to progress.yaml
5. Implementing Human-in-the-Loop approval gate for Implementer
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from mycelium.llm import CompletionResponse, complete

logger = logging.getLogger(__name__)

# Agent roles that can be orchestrated
VALID_AGENTS = {"scientist", "implementer", "verifier", "maintainer"}

# Agents that require HITL approval before execution
REQUIRES_APPROVAL = {"implementer"}


def find_repo_root(start_path: Path | None = None) -> Path | None:
    """Find the repository root by looking for .mycelium directory."""
    current = start_path or Path.cwd()
    
    # Resolve to absolute path
    current = current.resolve()
    
    # Check current and all parent directories
    while True:
        if (current / ".mycelium").is_dir():
            return current
        parent = current.parent
        if parent == current:
            # Reached filesystem root
            break
        current = parent
    
    return None


def load_progress(mission_path: Path) -> dict[str, Any]:
    """
    Load progress.yaml from mission path.
    
    Args:
        mission_path: Path to mission directory or progress.yaml file.
        
    Returns:
        Parsed YAML content as dict.
        
    Raises:
        FileNotFoundError: If progress.yaml doesn't exist.
        yaml.YAMLError: If YAML parsing fails.
    """
    if mission_path.suffix == ".yaml":
        progress_file = mission_path
    else:
        progress_file = mission_path / "progress.yaml"
    
    if not progress_file.exists():
        raise FileNotFoundError(f"progress.yaml not found at: {progress_file}")
    
    with open(progress_file) as f:
        return yaml.safe_load(f)


def save_progress(mission_path: Path, progress: dict[str, Any]) -> None:
    """
    Save progress.yaml to mission path.
    
    Args:
        mission_path: Path to mission directory or progress.yaml file.
        progress: Progress data to save.
    """
    if mission_path.suffix == ".yaml":
        progress_file = mission_path
    else:
        progress_file = mission_path / "progress.yaml"
    
    with open(progress_file, "w") as f:
        yaml.dump(progress, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def get_agent_template(repo_root: Path, agent_role: str) -> str:
    """
    Load agent template markdown file.
    
    Args:
        repo_root: Repository root path.
        agent_role: Agent role name (scientist, implementer, etc.).
        
    Returns:
        Content of agent template file.
    """
    template_path = repo_root / ".mycelium" / "agents" / "mission" / f"{agent_role}.md"
    
    if not template_path.exists():
        raise FileNotFoundError(f"Agent template not found: {template_path}")
    
    return template_path.read_text()


def get_contract(repo_root: Path) -> str:
    """Load CONTRACT.md content."""
    contract_path = repo_root / ".mycelium" / "CONTRACT.md"
    
    if not contract_path.exists():
        raise FileNotFoundError(f"CONTRACT.md not found: {contract_path}")
    
    return contract_path.read_text()


def build_agent_prompt(
    repo_root: Path,
    mission_path: Path,
    progress: dict[str, Any],
    agent_role: str,
) -> list[dict[str, str]]:
    """
    Build the prompt messages for an agent call.
    
    Args:
        repo_root: Repository root path.
        mission_path: Path to mission directory.
        progress: Loaded progress.yaml content.
        agent_role: Current agent role.
        
    Returns:
        List of message dicts for LLM completion.
    """
    contract = get_contract(repo_root)
    agent_template = get_agent_template(repo_root, agent_role)
    
    # Format progress.yaml as YAML for context
    progress_yaml = yaml.dump(progress, default_flow_style=False, allow_unicode=True)
    
    # Build system message with full context
    system_content = f"""You are the {agent_role} agent in the Mycelium multi-agent workflow.

## CONTRACT.md
{contract}

## Agent Instructions ({agent_role}.md)
{agent_template}

## Current Mission Progress (progress.yaml)
```yaml
{progress_yaml}
```

## Mission Path
{mission_path}

Follow your agent instructions exactly. Update the progress.yaml file as specified.
Remember: The progress.yaml is the single source of truth - read it first, update it before completing.
"""

    user_content = f"""Execute your role as the {agent_role} agent for this mission.

Read the progress.yaml, perform your tasks according to your agent instructions, and update the artifact.

Current agent: {progress.get('current_agent', agent_role)}
"""

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]


def append_llm_usage(
    progress: dict[str, Any],
    agent_role: str,
    response: CompletionResponse,
) -> dict[str, Any]:
    """
    Append LLM usage metadata to progress.yaml's llm_usage section.
    
    Args:
        progress: Progress data to update.
        agent_role: Role of agent that made the call.
        response: LLM completion response with usage data.
        
    Returns:
        Updated progress dict.
    """
    # Initialize llm_usage section if it doesn't exist
    if "llm_usage" not in progress:
        progress["llm_usage"] = {
            "runs": [],
            "total_tokens": 0,
            "total_cost_usd": 0.0,
        }
    
    llm_usage = progress["llm_usage"]
    
    # Create run entry
    run_entry = {
        "agent_role": agent_role,
        "model": response.usage.model,
        "prompt_tokens": response.usage.prompt_tokens,
        "completion_tokens": response.usage.completion_tokens,
        "total_tokens": response.usage.total_tokens,
        "cost_usd": round(response.usage.cost_usd, 6),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "success": response.success,
    }
    
    if response.error:
        run_entry["error"] = response.error
    
    # Append to runs
    llm_usage["runs"].append(run_entry)
    
    # Update totals
    llm_usage["total_tokens"] = sum(r.get("total_tokens", 0) for r in llm_usage["runs"])
    llm_usage["total_cost_usd"] = round(
        sum(r.get("cost_usd", 0) for r in llm_usage["runs"]), 6
    )
    
    return progress


def check_hitl_approval(agent_role: str, auto_approve: bool = False) -> bool:
    """
    Check Human-in-the-Loop approval for agents that require it.
    
    Args:
        agent_role: Agent role to check.
        auto_approve: If True, bypass approval (e.g., --approve flag).
        
    Returns:
        True if approved, False otherwise.
    """
    if agent_role not in REQUIRES_APPROVAL:
        return True
    
    if auto_approve:
        logger.info(f"Auto-approval enabled for {agent_role}")
        return True
    
    # Interactive confirmation
    print(f"\n⚠️  HUMAN-IN-THE-LOOP APPROVAL REQUIRED")
    print(f"Agent '{agent_role}' may modify source code.")
    print("Review the mission context and confirm execution.\n")
    
    try:
        response = input("Approve execution? [y/N]: ").strip().lower()
        return response in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        print("\nApproval cancelled.")
        return False


def run_agent(
    mission_path: str | Path,
    model: str | None = None,
    auto_approve: bool = False,
    dry_run: bool = False,
    enable_tools: bool = True,
) -> CompletionResponse:
    """
    Run the current agent for a mission via LLM.
    
    Args:
        mission_path: Path to mission directory or progress.yaml.
        model: Optional model override (defaults to claude-sonnet-4-20250514).
        auto_approve: Bypass HITL approval for Implementer.
        dry_run: If True, don't actually call LLM, just build prompt.
        enable_tools: If True, provide tools to LLM and execute tool calls.
        
    Returns:
        CompletionResponse with agent output.
    """
    import json
    
    mission_path = Path(mission_path)
    
    # Find repo root
    repo_root = find_repo_root(mission_path if mission_path.is_dir() else mission_path.parent)
    if not repo_root:
        return CompletionResponse(
            success=False,
            error="Not in a mycelium repository (no .mycelium directory found)",
        )
    
    # Load progress
    try:
        progress = load_progress(mission_path)
    except FileNotFoundError as e:
        return CompletionResponse(success=False, error=str(e))
    except yaml.YAMLError as e:
        return CompletionResponse(success=False, error=f"YAML parse error: {e}")
    
    # Get current agent
    raw_agent = progress.get("current_agent", "")
    if isinstance(raw_agent, dict):
        if "current_agent" in raw_agent:
            current_agent = str(raw_agent["current_agent"]).strip()
        else:
            current_agent = str(raw_agent).strip()
    else:
        current_agent = str(raw_agent).strip()
    
    if not current_agent:
        return CompletionResponse(
            success=True,
            content="Mission complete - no agent to run (current_agent is empty).",
        )
    
    if current_agent not in VALID_AGENTS:
        return CompletionResponse(
            success=False,
            error=f"Invalid current_agent: '{current_agent}'. Valid: {VALID_AGENTS}",
        )
    
    # Build prompt
    try:
        messages = build_agent_prompt(repo_root, mission_path, progress, current_agent)
    except FileNotFoundError as e:
        return CompletionResponse(success=False, error=str(e))
    
    # Dry run - just return the prompt (no HITL check needed)
    if dry_run:
        prompt_content = "\n\n---\n\n".join(m["content"] for m in messages)
        return CompletionResponse(
            success=True,
            content=f"DRY RUN - Prompt for {current_agent}:\n\n{prompt_content}",
        )
    
    # Check HITL approval (only for actual execution)
    if not check_hitl_approval(current_agent, auto_approve):
        return CompletionResponse(
            success=False,
            error=f"Execution not approved for {current_agent}. Use --approve flag to bypass.",
        )
    
    # Call LLM with optional tool support
    from mycelium.llm import DEFAULT_MODEL
    
    effective_model = model or os.environ.get("MYCELIUM_MODEL", DEFAULT_MODEL)
    
    # Get tools if enabled
    tools = None
    if enable_tools:
        try:
            from mycelium.tools import TOOL_SCHEMAS, execute_tool, format_tool_result
            tools = TOOL_SCHEMAS
            logger.info(f"Tools enabled: {len(tools)} tools available")
        except ImportError as e:
            logger.warning(f"Could not import tools module: {e}")
    
    logger.info(f"Running {current_agent} agent with model {effective_model}")
    
    # Tool execution loop
    max_tool_iterations = 20
    total_usage = None
    final_content = ""
    
    for iteration in range(max_tool_iterations):
        response = complete(
            messages=messages,
            model=effective_model,
            agent_role=current_agent,
            tools=tools,
        )
        
        # Accumulate usage
        if total_usage is None:
            total_usage = response.usage
        else:
            # Add usage from this iteration
            from mycelium.llm import UsageMetadata
            total_usage = UsageMetadata(
                prompt_tokens=total_usage.prompt_tokens + response.usage.prompt_tokens,
                completion_tokens=total_usage.completion_tokens + response.usage.completion_tokens,
                total_tokens=total_usage.total_tokens + response.usage.total_tokens,
                cost_usd=total_usage.cost_usd + response.usage.cost_usd,
                model=response.usage.model,
            )
        
        if not response.success:
            # Return failure immediately
            response.usage = total_usage
            return response
        
        # If no tool calls, we're done
        if not response.tool_calls:
            final_content = response.content
            logger.info(f"Agent completed after {iteration + 1} iteration(s)")
            break
        
        # Execute tool calls and add results to messages
        logger.info(f"Executing {len(response.tool_calls)} tool call(s) in iteration {iteration + 1}")
        
        # Add assistant message with tool calls
        assistant_message = {"role": "assistant", "content": response.content or ""}
        if response.tool_calls:
            # Format for LLM context
            assistant_message["tool_calls"] = [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": tc["arguments"],
                    },
                }
                for tc in response.tool_calls
            ]
        messages.append(assistant_message)
        
        # Execute each tool and add results
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            try:
                arguments = json.loads(tool_call["arguments"])
            except json.JSONDecodeError as e:
                tool_result = {"error": f"Invalid JSON arguments: {e}"}
                logger.error(f"Failed to parse tool arguments: {e}")
            else:
                try:
                    # Inject auto_approve for write_file and run_command
                    if tool_name in ("write_file", "run_command") and auto_approve:
                        arguments["auto_approve"] = True
                    if tool_name in ("write_file", "run_command") and "mission_path" not in arguments:
                        arguments["mission_path"] = str(mission_path)
                    
                    result = execute_tool(tool_name, arguments)
                    tool_result = format_tool_result(tool_name, result)
                except Exception as e:
                    tool_result = json.dumps({"error": str(e)})
                    logger.error(f"Tool {tool_name} failed: {e}")
            
            # Add tool result message
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "content": tool_result if isinstance(tool_result, str) else json.dumps(tool_result),
            })
        
        # If we've hit the limit, break with warning
        if iteration == max_tool_iterations - 1:
            logger.warning(f"Hit max tool iterations ({max_tool_iterations}), stopping")
            final_content = response.content or "Max tool iterations reached"
    
    # Create final response with accumulated usage
    final_response = CompletionResponse(
        content=final_content,
        usage=total_usage,
        success=True,
    )
    
    # Log usage to progress.yaml
    # RELOAD from disk first to capture changes made by tool execution
    try:
        progress = load_progress(mission_path)
    except Exception as e:
        logger.warning(f"Could not reload progress.yaml to save usage: {e}")
        # Proceed with in-memory progress (better than nothing), though stale
        
    progress = append_llm_usage(progress, current_agent, final_response)
    
    # Save updated progress
    try:
        save_progress(mission_path, progress)
        logger.info(f"Updated progress.yaml with LLM usage")
    except Exception as e:
        logger.error(f"Failed to save progress: {e}")
        # Don't fail the response, but note the error
        if final_response.error:
            final_response.error += f"; Failed to save progress: {e}"
        else:
            final_response = CompletionResponse(
                content=final_response.content,
                usage=final_response.usage,
                success=final_response.success,
                error=f"Warning: Failed to save progress: {e}",
            )
    
    return final_response


def get_usage_summary(mission_path: str | Path) -> dict[str, Any]:
    """
    Get cumulative LLM usage summary for a mission.
    
    Args:
        mission_path: Path to mission directory or progress.yaml.
        
    Returns:
        Dict with usage summary (total_tokens, total_cost_usd, runs count).
    """
    mission_path = Path(mission_path)
    
    try:
        progress = load_progress(mission_path)
    except (FileNotFoundError, yaml.YAMLError):
        return {"total_tokens": 0, "total_cost_usd": 0.0, "runs": 0}
    
    llm_usage = progress.get("llm_usage", {})
    
    return {
        "total_tokens": llm_usage.get("total_tokens", 0),
        "total_cost_usd": llm_usage.get("total_cost_usd", 0.0),
        "runs": len(llm_usage.get("runs", [])),
        "runs_detail": llm_usage.get("runs", []),
    }
