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
import os
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

_AUTO_APPROVE_TRUE_VALUES = {"1", "true", "yes"}


def _normalize_objective(progress: dict) -> str:
    """Extract a printable objective string from possibly malformed progress payloads."""
    mission_context = progress.get("mission_context")
    if not isinstance(mission_context, dict):
        return ""

    objective = mission_context.get("objective", "")
    if objective is None:
        return ""
    if isinstance(objective, str):
        return objective.strip()
    return str(objective).strip()


def _parse_env_int(name: str, default: int, minimum: int) -> int:
    """Parse and validate integer environment values."""
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        parsed = int(raw)
    except ValueError:
        logger.warning(f"Ignoring invalid {name}={raw!r}; using default {default}")
        return default
    if parsed < minimum:
        logger.warning(f"Ignoring {name}={parsed}; expected >= {minimum}, using default {default}")
        return default
    return parsed


def _parse_env_float(name: str, default: float, minimum: float) -> float:
    """Parse and validate float environment values."""
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        parsed = float(raw)
    except ValueError:
        logger.warning(f"Ignoring invalid {name}={raw!r}; using default {default}")
        return default
    if parsed < minimum:
        logger.warning(f"Ignoring {name}={parsed}; expected >= {minimum}, using default {default}")
        return default
    return parsed


def _resolve_auto_config(args: argparse.Namespace) -> tuple[int, float, int, bool]:
    """Resolve and sanitize auto-loop runtime configuration."""
    max_iterations = (
        args.max_iterations
        if args.max_iterations is not None
        else _parse_env_int("MYCELIUM_MAX_ITERATIONS", default=10, minimum=1)
    )
    max_cost = (
        args.max_cost
        if args.max_cost is not None
        else _parse_env_float("MYCELIUM_MAX_COST", default=1.0, minimum=0.0)
    )
    max_failures = (
        args.max_failures
        if args.max_failures is not None
        else _parse_env_int("MYCELIUM_MAX_FAILURES", default=3, minimum=1)
    )

    if max_iterations < 1:
        logger.warning(f"max_iterations={max_iterations} is invalid; clamping to 1")
        max_iterations = 1
    if max_cost < 0:
        logger.warning(f"max_cost={max_cost} is invalid; clamping to 0.0")
        max_cost = 0.0
    if max_failures < 1:
        logger.warning(f"max_failures={max_failures} is invalid; clamping to 1")
        max_failures = 1

    env_auto_approve = os.environ.get("MYCELIUM_AUTO_APPROVE", "").strip().lower()
    auto_approve = bool(args.approve) or env_auto_approve in _AUTO_APPROVE_TRUE_VALUES
    return max_iterations, max_cost, max_failures, auto_approve


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
    from mycelium.orchestrator import get_usage_summary, load_progress, normalize_current_agent
    
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
    current_agent = normalize_current_agent(progress.get("current_agent", ""))
    objective = _normalize_objective(progress)
    
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
    from mycelium.orchestrator import (
        get_usage_summary,
        load_progress,
        normalize_current_agent,
        run_agent,
    )
    
    mission_path = Path(args.mission_path)
    
    if not mission_path.exists():
        print(f"❌ Error: Path does not exist: {mission_path}", file=sys.stderr)
        return 1
    
    # Configuration from args/env
    max_iterations, max_cost, max_failures, auto_approve = _resolve_auto_config(args)
    
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
    exit_reason = "complete"

    while True:
        # Load current progress
        try:
            progress = load_progress(mission_path)
        except Exception as e:
            print(f"❌ Error loading progress: {e}", file=sys.stderr)
            return 1
        
        current_agent = normalize_current_agent(progress.get("current_agent", ""))
        
        # Check completion
        if not current_agent:
            print()
            print("✅ Mission complete!")
            break
        
        # Circuit breakers
        if iteration >= max_iterations:
            print()
            print(f"⚠️  Max iterations ({max_iterations}) reached")
            exit_reason = "max_iterations"
            break

        if cumulative_cost >= max_cost:
            print()
            print(f"⚠️  Max cost (${max_cost:.2f}) exceeded - current: ${cumulative_cost:.4f}")
            exit_reason = "max_cost"
            break

        if consecutive_failures >= max_failures:
            print()
            print(f"⚠️  Max consecutive failures ({max_failures}) reached")
            exit_reason = "max_failures"
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

    return 0 if exit_reason == "complete" else 2


# ─── Knowledge Vault command handlers ─────────────────────────────────────


def _print_envelope(envelope) -> int:
    """Print an OutputEnvelope as JSON and return exit code."""
    import json
    from dataclasses import asdict
    print(json.dumps(asdict(envelope), indent=2, default=str))
    return 0 if envelope.ok else 1


def cmd_ingest(args: argparse.Namespace) -> int:
    """Handle the ingest command."""
    from mycelium.commands.ingest import execute_ingest

    raw_input: dict = {}
    if args.url:
        raw_input["url"] = args.url
    if args.pdf_path:
        raw_input["pdf_path"] = args.pdf_path
    if args.text_bundle:
        raw_input["text_bundle"] = {"text": args.text_bundle, "ref": "cli-input"}
    if args.why_saved:
        raw_input["why_saved"] = args.why_saved
    if args.tags:
        raw_input["tags"] = args.tags
    raw_input["strict"] = args.strict
    raw_input["dry_run"] = args.dry_run

    return _print_envelope(execute_ingest(raw_input))


def cmd_review(args: argparse.Namespace) -> int:
    """Handle the review command."""
    from mycelium.commands.review import execute_review

    raw_input: dict = {}
    if args.queue_id:
        raw_input["queue_id"] = args.queue_id
    if args.decision:
        raw_input["decision"] = args.decision
    if args.reason:
        raw_input["reason"] = args.reason

    return _print_envelope(execute_review(raw_input))


def cmd_digest(args: argparse.Namespace) -> int:
    """Handle the digest command."""
    from mycelium.commands.review_digest import execute_review_digest
    return _print_envelope(execute_review_digest({}))


def cmd_delta(args: argparse.Namespace) -> int:
    """Handle the delta command."""
    from mycelium.commands.delta import execute_delta

    raw_input: dict = {}
    if args.source_id:
        raw_input["source_id"] = args.source_id
    if args.delta_report_path:
        raw_input["delta_report_path"] = args.delta_report_path

    return _print_envelope(execute_delta(raw_input))


def cmd_frontier(args: argparse.Namespace) -> int:
    """Handle the frontier command."""
    from mycelium.commands.frontier import execute_frontier

    raw_input: dict = {}
    if args.project:
        raw_input["project"] = args.project
    if args.tags:
        raw_input["tags"] = args.tags
    if args.limit:
        raw_input["limit"] = args.limit

    return _print_envelope(execute_frontier(raw_input))


def cmd_context(args: argparse.Namespace) -> int:
    """Handle the context command."""
    from mycelium.commands.context import execute_context

    raw_input: dict = {}
    if args.goal:
        raw_input["goal"] = args.goal
    if args.project:
        raw_input["project"] = args.project
    if args.tags:
        raw_input["tags"] = args.tags
    if args.limit:
        raw_input["limit"] = args.limit
    raw_input["strict"] = args.strict

    return _print_envelope(execute_context(raw_input))


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

    # ── Knowledge Vault commands ──────────────────────────────────────────

    # ingest
    ingest_parser = subparsers.add_parser(
        "ingest",
        help="Ingest a URL, PDF, or text bundle into the knowledge vault",
    )
    ingest_parser.add_argument("--url", help="URL to ingest")
    ingest_parser.add_argument("--pdf", dest="pdf_path", help="Path to PDF file")
    ingest_parser.add_argument("--text", dest="text_bundle", help="Inline text to ingest")
    ingest_parser.add_argument("--why", dest="why_saved", help="Why this source is being saved")
    ingest_parser.add_argument("--tags", nargs="*", default=[], help="Tags for the source")
    ingest_parser.add_argument("--strict", action="store_true", help="Enable strict mode")
    ingest_parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    ingest_parser.set_defaults(func=cmd_ingest)

    # review
    review_parser = subparsers.add_parser(
        "review",
        help="Review and decide on pending queue items",
    )
    review_parser.add_argument("--queue-id", help="Specific queue item ID to review")
    review_parser.add_argument("--decision", choices=["approve", "reject", "hold"], help="Decision")
    review_parser.add_argument("--reason", help="Reason for decision")
    review_parser.set_defaults(func=cmd_review)

    # digest
    digest_parser = subparsers.add_parser(
        "digest",
        help="Generate review digest of pending queue items",
    )
    digest_parser.set_defaults(func=cmd_digest)

    # delta
    delta_parser = subparsers.add_parser(
        "delta",
        help="Show delta report for a source",
    )
    delta_parser.add_argument("--source-id", help="Source ID to show delta for")
    delta_parser.add_argument("--path", dest="delta_report_path", help="Path to delta report")
    delta_parser.set_defaults(func=cmd_delta)

    # frontier
    frontier_parser = subparsers.add_parser(
        "frontier",
        help="Show knowledge frontier — topics with gaps or conflicts",
    )
    frontier_parser.add_argument("--project", help="Filter by project")
    frontier_parser.add_argument("--tags", nargs="*", help="Filter by tags")
    frontier_parser.add_argument("--limit", type=int, help="Max results")
    frontier_parser.set_defaults(func=cmd_frontier)

    # context
    context_parser = subparsers.add_parser(
        "context",
        help="Build a context pack for a goal",
    )
    context_parser.add_argument("goal", nargs="?", help="Goal or question for context pack")
    context_parser.add_argument("--project", help="Filter by project")
    context_parser.add_argument("--tags", nargs="*", default=[], help="Filter by tags")
    context_parser.add_argument("--limit", type=int, help="Token budget limit")
    context_parser.add_argument("--strict", action="store_true", help="Enable strict mode")
    context_parser.set_defaults(func=cmd_context)

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
