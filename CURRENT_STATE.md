# CURRENT_STATE

## 1. System Overview
Mycelium is currently a Python orchestration layer for a human-gated multi-agent development workflow, plus an MCP tool server and Claude skill definitions for Beads-driven task flow.

What it does today:
- Orchestrates a mission state machine stored in `progress.yaml` with roles `scientist -> implementer -> verifier -> maintainer`.
- Builds prompts from `.mycelium/CONTRACT.md` and `.mycelium/agents/mission/<role>.md` and executes through LiteLLM.
- Exposes mission/filesystem operations as LiteLLM function schemas (`src/mycelium/tools.py`) and as MCP tools (`src/mycelium/mcp/server.py`).
- Appends token/cost usage per agent run into mission state (`llm_usage`).

Runtime model:
- Foreground CLI (`mycelium-py`) with `run`, `status`, and `auto`.
- MCP server process (`python -m mycelium.mcp`) exposing 7 tools.
- No distributed runtime, queue workers, or built-in scheduler.

## 2. Tech Stack
Languages:
- Python (`requires-python = ">=3.10"`).

Frameworks/libraries:
- `litellm` for provider abstraction, completion calls, and tool-calling payloads.
- `fastmcp` for MCP server/tool registration.
- `pyyaml` for mission state serialization.
- `pytest` and `ruff` for test/lint workflows.

Storage:
- Mission state in local YAML files (`progress.yaml`).
- Work tracking state in `.beads/` (JSONL plus local Beads DB artifacts).
- No application-owned persistent DB in `src/mycelium`.

Infrastructure assumptions:
- Local shell process execution is available (`subprocess.run(..., shell=True)` in command tool).
- At least one supported model API key is available when running LLM calls.
- Mission/template files are available in the local repository filesystem.

## 3. High-Level Architecture
Top-level directory map:
- `.beads/`: issue-tracking data/config for `bd`.
- `.claude/`: Claude skill definitions for workflow roles and Beads commands.
- `sandbox/`: toy-run documentation and example script.
- `src/`: Python package source (`mycelium`).
- `tests/`: pytest coverage for orchestrator, LLM wrapper, MCP tools, and tool schemas.

Major components and responsibilities:
- `src/mycelium/cli.py`: command parsing, mission status display, and auto-loop control.
- `src/mycelium/orchestrator.py`: mission I/O, repo-root detection, prompt construction, HITL gate, LLM/tool loop, usage write-back.
- `src/mycelium/llm.py`: retry/backoff completion wrapper, provider key checks, usage extraction, approximate cost calculation.
- `src/mycelium/tools.py`: OpenAI-style function schemas and name->implementation dispatch.
- `src/mycelium/mcp/server.py`: concrete tool implementations and FastMCP-decorated exports.
- `src/mycelium/mcp/__main__.py`: MCP server entrypoint.

Notable structural fact:
- Runtime orchestration requires a `.mycelium/` directory, but this repo snapshot does not contain `.mycelium`; tests create temporary `.mycelium` fixtures.

## 4. Data & Interfaces
Public interfaces:
- CLI: `mycelium-py run <mission_path> [--model] [--approve] [--dry-run]`.
- CLI: `mycelium-py status <mission_path> [-v]`.
- CLI: `mycelium-py auto <mission_path> [--model] [--max-iterations] [--max-cost] [--max-failures] [--approve] [--no-tools] [-v]`.
- MCP tools: `read_progress`, `update_progress`, `list_files`, `read_file`, `write_file`, `run_command`, `search_codebase`.
- Python export: `mycelium.complete` (re-export of `llm.complete`).

Key internal interfaces:
- `llm.complete(...) -> CompletionResponse`: returns content, usage, success/error, and optional tool calls.
- `orchestrator.run_agent(...) -> CompletionResponse`: executes one current-agent pass and persists usage.
- `tools.execute_tool(name, arguments)`: dispatches tool calls to MCP server helper functions.

Data models (summarized):
- Mission document (`progress.yaml`) uses sections referenced by runtime code: `current_agent`, `mission_context`, `scientist_plan`, `implementer_log`, `verifier_report`, `maintainer_notes`, `maintainer_summary`, `llm_usage`, `commit_message`.
- `llm_usage` structure stores aggregates (`total_tokens`, `total_cost_usd`, `runs`) and per-run fields (`agent_role`, model, token counts, cost, timestamp, success/error).
- `CompletionResponse` contains `content`, `UsageMetadata`, `success`, `error`, and optional `tool_calls`.

## 5. Execution Model
Control flow (`run`):
1. Resolve mission path and locate repo root by searching for `.mycelium` upward from the mission location.
2. Load `progress.yaml` and validate/normalize `current_agent`.
3. Build system/user prompt context from contract, agent template, and serialized mission state.
4. Enforce HITL approval for `implementer` unless auto-approved.
5. Call LiteLLM; when tool calls are returned, execute tools, append tool outputs, and iterate (max 20 tool iterations).
6. Accumulate usage across iterations.
7. Reload mission state from disk, append usage record(s), and save `progress.yaml`.

Control flow (`auto`):
1. Repeatedly inspect `current_agent` and stop when empty.
2. Apply circuit breakers: max iterations, max cumulative cost, max consecutive failures.
3. Prompt for per-iteration approval unless auto-approve mode is enabled.
4. Execute `run_agent` for each approved iteration.

Background jobs/services/schedulers:
- No scheduler, queue, or background worker subsystem in source.
- MCP server is synchronous request/response in a single process.

## 6. Known Constraints & Invariants
Backward compatibility/robustness behavior present in code:
- `current_agent` is defensively normalized when model output accidentally writes nested dicts.
- `update_progress` unwraps section-recursive dict shapes to recover from malformed tool payloads.
- Mission path handling accepts both mission directory and direct `.yaml` file path.

Hard dependencies:
- LLM calls require at least one of `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`, or `GEMINI_API_KEY`.
- Orchestrator runtime expects `.mycelium/CONTRACT.md` and `.mycelium/agents/mission/<role>.md` to exist.
- Command execution tool depends on local shell availability.

Operational invariants:
- Valid agent set is fixed to `scientist`, `implementer`, `verifier`, `maintainer`.
- HITL gate applies to implementer-side write/command operations unless `auto_approve` or `MYCELIUM_HITL_AUTO_APPROVE` is active.
- LLM retry policy is fixed to 3 attempts with exponential backoff.
- Tool-call loop has a hard upper bound of 20 iterations.

Performance assumptions:
- `search_codebase` performs recursive file scanning and line matching in Python with no index/cache.
- Command execution is synchronous and blocking.
- Orchestrator/tool execution is single-threaded.

Current test execution status:
- `PYTHONPATH=src pytest -q` passes (`86 passed`).
- Plain `pytest -q` fails import resolution unless package path/install is configured (`ModuleNotFoundError: mycelium`).

## 7. Pain Points / Structural Issues
Architectural friction:
- Strict runtime dependency on `.mycelium` templates is not satisfied by this repository snapshot itself.
- Workflow state is split between mission YAML and Beads issue labels/notes without a direct bridge in `src/mycelium`.

Complexity hotspots:
- Multiple paths include defensive fixes for malformed model outputs, indicating recurrent shape/typing drift.
- Runtime code constrains section names but does not enforce a full mission schema contract before orchestration.

Coupling issues:
- `tools.execute_tool` depends on underscored internals from `mcp.server`, tightly coupling LiteLLM tooling to MCP implementation details.
- Tool section names and expectations are duplicated across schema declarations and write/update logic.

Risk-oriented implementation details:
- `run_command` uses `shell=True`, which is intentionally high-trust.
- Cost values are estimates (LiteLLM-derived/fallback), not guaranteed provider bill totals.
