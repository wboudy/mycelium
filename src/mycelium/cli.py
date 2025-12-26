#!/usr/bin/env python3
"""
Mycelium CLI - Python-based orchestration commands.

This module provides:
- mycelium run <mission-path>: Run the current agent via LiteLLM
- mycelium status <mission-path>: Show mission status with LLM usage
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def cmd_run(args: argparse.Namespace) -> int:
    """Execute the run command."""
    from mycelium.orchestrator import run_agent
    
    mission_path = Path(args.mission_path)
    
    if not mission_path.exists():
        print(f"❌ Error: Path does not exist: {mission_path}", file=sys.stderr)
        return 1
    
    print(f"🚀 Running agent for mission: {mission_path}")
    print()
    
    response = run_agent(
        mission_path=mission_path,
        model=args.model,
        auto_approve=args.approve,
        dry_run=args.dry_run,
    )
    
    if not response.success:
        print(f"❌ Error: {response.error}", file=sys.stderr)
        return 1
    
    print("=" * 60)
    print("AGENT OUTPUT")
    print("=" * 60)
    print(response.content)
    print("=" * 60)
    print()
    
    if response.usage.total_tokens > 0:
        print(f"📊 Tokens: {response.usage.total_tokens:,} "
              f"(prompt: {response.usage.prompt_tokens:,}, "
              f"completion: {response.usage.completion_tokens:,})")
        print(f"💰 Cost: ${response.usage.cost_usd:.6f}")
    
    print()
    print("✅ Agent run complete")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Execute the status command with LLM usage."""
    from mycelium.orchestrator import get_usage_summary, load_progress
    
    mission_path = Path(args.mission_path)
    
    if not mission_path.exists():
        print(f"❌ Error: Path does not exist: {mission_path}", file=sys.stderr)
        return 1
    
    try:
        progress = load_progress(mission_path)
    except FileNotFoundError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"❌ Error parsing progress.yaml: {e}", file=sys.stderr)
        return 1
    
    # Mission info
    mission_name = mission_path.name if mission_path.is_dir() else mission_path.parent.name
    current_agent = progress.get("current_agent", "")
    objective = progress.get("mission_context", {}).get("objective", "")
    
    print()
    print(f"📋 Mission: {mission_name}")
    print("─" * 50)
    
    if not current_agent:
        print("Agent:      ✅ (complete)")
    else:
        print(f"Agent:      🔵 {current_agent}")
    
    if objective:
        print()
        print("Objective:")
        # Wrap long objectives
        if len(objective) > 70:
            words = objective.split()
            line = "  "
            for word in words:
                if len(line) + len(word) + 1 > 70:
                    print(line)
                    line = "  " + word
                else:
                    line += " " + word if line != "  " else word
            if line.strip():
                print(line)
        else:
            print(f"  {objective}")
    
    # LLM usage summary
    usage = get_usage_summary(mission_path)
    
    if usage["runs"] > 0:
        print()
        print("📊 LLM Usage:")
        print(f"  Runs:        {usage['runs']}")
        print(f"  Total tokens: {usage['total_tokens']:,}")
        print(f"  Total cost:   ${usage['total_cost_usd']:.6f}")
        
        if args.verbose and usage.get("runs_detail"):
            print()
            print("  Run Details:")
            for i, run in enumerate(usage["runs_detail"], 1):
                print(f"    {i}. {run.get('agent_role', 'unknown')} - "
                      f"{run.get('total_tokens', 0):,} tokens - "
                      f"${run.get('cost_usd', 0):.6f}")
    else:
        print()
        print("📊 LLM Usage: (no runs yet)")
    
    print()
    return 0


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="mycelium-py",
        description="Mycelium CLI - AI agent orchestration via LiteLLM",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output",
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # run command
    run_parser = subparsers.add_parser(
        "run",
        help="Run the current agent for a mission via LiteLLM",
    )
    run_parser.add_argument(
        "mission_path",
        help="Path to mission directory or progress.yaml",
    )
    run_parser.add_argument(
        "--model", "-m",
        help="Model to use (default: anthropic/claude-sonnet-4-20250514)",
    )
    run_parser.add_argument(
        "--approve", "-y",
        action="store_true",
        help="Auto-approve HITL gate for Implementer",
    )
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build prompt but don't call LLM",
    )
    run_parser.set_defaults(func=cmd_run)
    
    # status command  
    status_parser = subparsers.add_parser(
        "status",
        help="Show mission status with LLM usage",
    )
    status_parser.add_argument(
        "mission_path",
        help="Path to mission directory or progress.yaml",
    )
    status_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show detailed usage breakdown",
    )
    status_parser.set_defaults(func=cmd_status)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Set logging level
    if getattr(args, "verbose", False):
        logging.getLogger().setLevel(logging.DEBUG)
    
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
