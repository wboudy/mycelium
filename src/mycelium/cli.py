#!/usr/bin/env python3
"""
Mycelium CLI - Python-based orchestration commands.

This module provides:
- mycelium-py run <mission-path>: Run the current agent via LiteLLM
- mycelium-py status <mission-path>: Show mission status with LLM usage
- mycelium-py auto <mission-path>: Run agents in a loop until mission complete
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


def cmd_auto(args: argparse.Namespace) -> int:
    """Execute auto-loop command - runs agents until mission complete or circuit breaker trips."""
    import os
    
    from mycelium.orchestrator import get_usage_summary, load_progress, run_agent
    
    mission_path = Path(args.mission_path)
    
    if not mission_path.exists():
        print(f"❌ Error: Path does not exist: {mission_path}", file=sys.stderr)
        return 1
    
    # Configuration from args/env
    max_iterations = args.max_iterations or int(os.environ.get("MYCELIUM_MAX_ITERATIONS", "10"))
    max_cost = args.max_cost or float(os.environ.get("MYCELIUM_MAX_COST", "1.0"))
    max_failures = args.max_failures or int(os.environ.get("MYCELIUM_MAX_FAILURES", "3"))
    auto_approve = args.approve or os.environ.get("MYCELIUM_AUTO_APPROVE", "").lower() in ("1", "true", "yes")
    
    print(f"🔄 Auto mode for mission: {mission_path}")
    print(f"   Max iterations: {max_iterations}")
    print(f"   Max cost: ${max_cost:.2f}")
    print(f"   Max failures: {max_failures}")
    print(f"   Auto-approve: {auto_approve}")
    print()
    
    # Loop state
    iteration = 0
    consecutive_failures = 0
    cumulative_cost = 0.0
    
    while True:
        # Load current progress
        try:
            progress = load_progress(mission_path)
        except Exception as e:
            print(f"❌ Error loading progress: {e}", file=sys.stderr)
            return 1
        
        raw_agent = progress.get("current_agent", "")
        if isinstance(raw_agent, dict):
            # Handle case where LLM wrote a nested dict or object
            # Attempt to find the value or just convert to string
            # Common failure: current_agent: { current_agent: "implementer" }
            if "current_agent" in raw_agent:
                current_agent = str(raw_agent["current_agent"]).strip()
            else:
                # Just take the first value or stringify
                current_agent = str(raw_agent).strip()
        else:
            current_agent = str(raw_agent).strip()
        
        # Check completion
        if not current_agent:
            print()
            print("✅ Mission complete!")
            break
        
        # Circuit breakers
        if iteration >= max_iterations:
            print()
            print(f"⚠️  Max iterations ({max_iterations}) reached")
            break
        
        if cumulative_cost >= max_cost:
            print()
            print(f"⚠️  Max cost (${max_cost:.2f}) exceeded - current: ${cumulative_cost:.4f}")
            break
        
        if consecutive_failures >= max_failures:
            print()
            print(f"⚠️  Max consecutive failures ({max_failures}) reached")
            break
        
        # HITL gate (if not auto-approved)
        if not auto_approve:
            print(f"\n🔵 Next agent: {current_agent} (iteration {iteration + 1}/{max_iterations})")
            try:
                response = input("Run this agent? [y/n/q]: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\nAborted by user")
                break
            
            if response == 'q':
                print("Aborted by user")
                break
            if response != 'y':
                print(f"Skipping {current_agent}")
                consecutive_failures += 1
                continue
        
        # Run agent
        print("\n" + "=" * 50)
        print(f"🔄 SWITCHING AGENT: {current_agent.upper()}")
        print("=" * 50)
        print(f"🚀 Running {current_agent} agent (iteration {iteration + 1}/{max_iterations})")
        
        response = run_agent(
            mission_path=mission_path,
            model=args.model,
            auto_approve=True,  # HITL already checked above
            enable_tools=not args.no_tools,
        )
        
        # Track metrics
        iteration += 1
        
        if response.success:
            consecutive_failures = 0
            cumulative_cost += response.usage.cost_usd
            
            print(f"   ✓ Tokens: {response.usage.total_tokens:,}")
            print(f"   ✓ Cost: ${response.usage.cost_usd:.6f} (cumulative: ${cumulative_cost:.4f})")
            
            if args.verbose:
                print(f"\n--- Output ---")
                print(response.content[:500] + "..." if len(response.content) > 500 else response.content)
                print(f"--- End ---\n")
        else:
            consecutive_failures += 1
            print(f"   ✗ Failed: {response.error}")
    
    # Summary
    print()
    print("=" * 50)
    print(f"📊 Auto mode complete after {iteration} iteration(s)")
    
    usage = get_usage_summary(mission_path)
    if usage["runs"] > 0:
        print(f"   Total tokens: {usage['total_tokens']:,}")
        print(f"   Total cost: ${usage['total_cost_usd']:.6f}")
    
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
    
    # auto command
    auto_parser = subparsers.add_parser(
        "auto",
        help="Run agents in a loop until mission complete or circuit breaker trips",
    )
    auto_parser.add_argument(
        "mission_path",
        help="Path to mission directory or progress.yaml",
    )
    auto_parser.add_argument(
        "--model", "-m",
        help="Model to use (default: anthropic/claude-sonnet-4-20250514)",
    )
    auto_parser.add_argument(
        "--max-iterations", "-n",
        type=int,
        help="Maximum number of agent iterations (default: 10)",
    )
    auto_parser.add_argument(
        "--max-cost", "-c",
        type=float,
        help="Maximum cumulative cost in USD (default: 1.0)",
    )
    auto_parser.add_argument(
        "--max-failures", "-f",
        type=int,
        help="Maximum consecutive failures before stopping (default: 3)",
    )
    auto_parser.add_argument(
        "--approve", "-y",
        action="store_true",
        help="Auto-approve HITL gate for all agents",
    )
    auto_parser.add_argument(
        "--no-tools",
        action="store_true",
        help="Disable tool calling (agents cannot read/write files)",
    )
    auto_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show agent output after each iteration",
    )
    auto_parser.set_defaults(func=cmd_auto)
    
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

