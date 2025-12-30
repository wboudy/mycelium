# Mycelium Roadmap

There's a lot to be done. The mycelium wants to grow. More nodes, more tools, more automation:

- **Improved Context Management**: Adding a "Historian" agent to track decisions across missions and improved state maintenance.
- **Variable Model Routing**: Dynamically routing tasks—cheap models for verification, reasoning models for planning, and code models for implementation.
- **LangGraph**: Porting the workflow to LangGraph to enable true graph-based state management and cyclic agent flows.
    - **MCP**: Exposing Mycelium as an MCP server so agents can access repo externally. Make agents stronger via tool use.
- **Prompt Engineering**: Implementing thinking protocols and few-shot tool use examples.

More details [here](https://github.com/wboudy/mycelium).

---

## 🟢 Phase 1: Hardening

**Focus:** Transition from text-heavy prompts to machine-verifiable artifacts.

### 1.1 YAML-Based Artifacts ✅ (Partial)

Replace markdown progress files with structured YAML.

| Markdown | YAML |
|----------|------|
| Freeform text | Schema-enforced fields |
| Human-readable | Machine-parseable |
| Easy to miss fields | Validation catches gaps |

**Why YAML?**
- **Schema validation** — Require `definition_of_done`, `dependencies`, `estimated_impact`
- **Fewer hallucinations** — LLMs produce more consistent output with nested YAML than freeform markdown
- **Diffable** — Cleaner git diffs for mission state changes

**Sub-tasks:**
- [x] Define YAML schema for `progress.yaml` — *Completed in progress-yaml-migration mission*
- [x] Create `PROGRESS_TEMPLATE.yaml` with self-documenting comments
- [x] Update all agent files to reference `.yaml` format
- [x] Migration guide from current markdown templates — *Added to WORKFLOW.md*
- [ ] Define YAML schema for `agent_call.yaml` (optional — current `.md` works)
- [ ] Create JSON Schema for automated validation (`progress.schema.json`)

---

### 1.2 `mycelium validate` CLI

A gatekeeper that rejects malformed missions before work begins.

**Validation rules:**
- Scientist must fill `definition_of_done` before Implementer starts
- Implementer must log `commands_run` before Verifier starts
- Verifier must include `pass_fail_status` before Maintainer starts

**Example:**
```bash
$ mycelium validate .mycelium/missions/my-mission/progress.yaml
❌ Missing required field: definition_of_done
   → Mission rejected. Scientist must complete DoD.
```

**Sub-tasks:**
- [ ] Implement `mycelium validate` CLI
- [ ] Add pre-handoff validation hook
- [ ] CI integration (block PR if validation fails)

---

### 1.3 Context Metrics & Auto-Compression ⏸️ (Deferred)

> **Status:** Shelved — requires API-level integration for accurate metrics.

**Problem Discovered:**
A CLI-based `mycelium metrics` command was implemented that measured progress.yaml file size as a proxy for token usage. However, this approach has fundamental limitations:

| Limitation | Why It Matters |
|------------|----------------|
| Only measures progress.yaml | Actual context includes all files read, conversation history, system prompts |
| Can't query conversation context | Model providers don't expose per-conversation token usage externally |
| Hardcoded model references | Would need configuration per-user since different models have different context windows |

**When This Becomes Feasible:**
Comprehensive metrics requires Mycelium to sit in the request path:
- **Phase 2: MCP Server** — Still on the tool side, won't have API visibility
- **Future: API Proxy Layer** — A local proxy between client and model API could:
  - Intercept and log all requests/responses
  - Count actual tokens from API payloads
  - Track per-conversation and per-mission usage
  - Warn when approaching context limits

**Archived Mission:** `.mycelium/missions/redacted-context-metrics/`

**Sub-tasks (for API stage):**
- [ ] Build local proxy server (intercepts model API calls)
- [ ] Token counting from actual API request/response payloads
- [ ] Per-model context window configuration
- [ ] Auto-compression trigger when approaching limits

---

### 1.4 Prompt Engineering 🧠

**Focus:** Implementing thinking protocols and few-shot tool use examples.

**Goal:** Improve agent reliability and complex reasoning by enforcing structured thought processes before action.

**Sub-tasks:**
- [ ] Implement `<thinking>` blocks for reasoning steps
- [ ] Create few-shot examples for complex tool usage
- [ ] Integrate "chain of thought" prompting into base agent templates

---

## 🟡 Phase 2: Orchestration

**Focus:** Move from linear manual chains to dynamic, tool-aware systems.

### 2.1 Mycelium MCP Server 🚀 (The Monetization Engine)

**Action:** Transition Mycelium from a "folder in a repo" to a global MCP Host.

**Mycelium as MCP Host:**
| Tool | Description |
|------|-------------|
| `start_mission` | Initialize a new mission from natural language |
| `verify_logic` | Run the Verifier on current mission state |
| `run_command` | Execute shell commands, return output |
| `grid_exec` | Submit jobs to compute clusters (SLURM, etc.) |
| `arxiv_search` | Pull latest papers by topic |
| `slack_notify` | Send mission updates to Slack |

**Mycelium as MCP Resource:**
- External tools can read mission state
- Tool-aware LLMs can participate in workflow
- Enables multi-agent coordination across systems

**Monetization Strategy:**
| Model | Description |
|-------|-------------|
| **Marketplace Listing** | Publish on Apify Store or Smithery — earn pay-per-event revenue (~$0.01/run) |
| **Outcome-Based Billing** | Charge for "Successful Verifications" or "Completed Missions" not raw API calls |
| **SaaS Gateway** | Local server free; Cloud Historian + Multi-Device Sync = $19/mo subscription |

**Sub-tasks:**
- [ ] Implement standard MCP JSON-RPC interface (TypeScript or Python)
- [ ] Expose `start_mission` and `verify_logic` as MCP Tools
- [ ] Add tool registry for custom tools
- [ ] Authentication for external access
- [ ] Integrate Stripe/Apify for usage-based billing

---

### 2.2 LangGraph Integration

Model agent flow as a graph with cycles and shared state.

**Benefits over linear chains:**
- **Reflection loops** — Verifier ↔ Implementer can cycle N times autonomously before escalating
- **Conditional branching** — Skip Verifier for docs-only changes
- **Checkpoints** — "Time-travel" to previous mission state if agent goes off-track

**Sub-tasks:**
- [ ] Define agent nodes and edges
- [ ] Implement checkpoint save/restore
- [ ] Add max-iteration limits to prevent infinite loops
- [ ] Visualization of mission flow

---

### 2.3 `mycelium next` CLI

Replace manual copy-paste with automated handoffs.

**Modes:**
- `mycelium next` — Invoke next agent based on current state
- `mycelium next --auto` — Auto-approve for low-risk missions
- `mycelium watch` — Daemon that monitors `progress.yaml` and auto-invokes

**Human-in-the-Loop:**
Uses MCP Elicitation primitive to pause for high-risk approvals:
> *"Is it okay to spend $5.00 on this deep-reasoning call?"*

**Sub-tasks:**
- [ ] Implement `mycelium next` CLI
- [ ] File watcher daemon
- [ ] MCP Elicitation for cost/risk approvals
- [ ] Notification hooks (Slack, email) for human-gated steps

---

## 🔴 Phase 3: Intelligence

**Focus:** Multi-model efficiency and long-term recursive learning.

### 3.1 Role-Specific Model Routing

Route agents to appropriate models based on task complexity.

| Agent | Model Type | Rationale |
|-------|------------|-----------|
| Scientist | High-reasoning (Claude Opus, o1) | Complex architectural planning |
| Implementer | Balanced (Claude Sonnet, GPT-4o) | Code generation + context |
| Verifier | Fast/cheap (Gemini Flash, GPT-4o mini) | Parse logs, find "FAIL" |
| Maintainer | Balanced | Refactoring requires judgment |

**Sub-tasks:**
- [ ] Define complexity heuristics
- [ ] Model selection config per agent
- [ ] Cost/latency tracking

---

### 3.2 The Historian Agent

A background crawler that converts completed missions into a **local RAG knowledge base**.

**Responsibilities:**
- Crawl completed `.mycelium/missions/` folders
- Extract patterns, failures, and lessons learned
- Advise Scientist: *"In Mission #42, we tried library X — it had memory leaks on the grid"*
- Automatically warn about previously attempted (and failed) approaches

**Memory bank contents:**
- Successful patterns → reuse
- Failed approaches → avoid
- Dependency conflicts → warn early

**Sub-tasks:**
- [ ] Define memory bank schema
- [ ] Implement mission crawler
- [ ] Build local RAG index (embeddings + retrieval)
- [ ] Integrate with Scientist planning phase

---

### 3.3 Headless Execution

Run long missions autonomously — "set it and forget it."

**Use case:**
> "Test every hyperparameter combination on the JHU CLSP Grid overnight."

**How it works:**
1. Define mission with `headless: true`
2. Agents handle queueing, monitoring, error-recovery
3. On completion, write `mission_complete.yaml` with results
4. Notify user via Slack/email

**Sub-tasks:**
- [ ] Headless mode flag in mission config
- [ ] Robust error recovery (retry logic, dead-letter queue)
- [ ] Automated Slack/Email completion notifications
- [ ] Result visualization (graphs, tables)

---

## Recent Updates

### 2024-12-22: YAML Progress Migration Complete ✅

**Mission:** `progress-yaml-migration`

Migrated progress artifacts from Markdown (`.md`) to YAML (`.yaml`) format:
- Created `PROGRESS_TEMPLATE.yaml` with all original fields preserved
- Updated `mission_organizer` to create `progress.yaml` for new missions
- All agent files now reference YAML format
- Added migration guidance in `WORKFLOW.md`
- Existing missions using `.md` remain backward compatible

This is a prerequisite for Phase 2 automation (schema validation, CLI tooling).

---

## Contributing

To propose roadmap changes, open an issue or submit a PR.
