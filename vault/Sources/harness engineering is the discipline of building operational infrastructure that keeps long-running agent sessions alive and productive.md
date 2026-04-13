---
created: 2026-04-11
description: Harness engineering — a practice coined by William Boudy — encompasses specs, memory, context management, safety gates, rollback loops, and escalation points that form the skeleton keeping multi-session agent work coherent
source: portfolio-derived
status: canon
type: source
tags: [harness-engineering, agent-infrastructure, operational-discipline, original-concept]
---

## Key Takeaways

Harness engineering is the operational discipline of building and maintaining the infrastructure that keeps AI agent sessions alive, coherent, and productive across long-horizon work. It's not about making agents smarter — it's about giving them the scaffolding they need to apply their intelligence reliably over time.

The core components of a harness are: (1) specs — clear, versioned documents that define what the agent should build and what done looks like; (2) memory — persistent state that survives session boundaries, from CLAUDE.md files to issue trackers like [[coding agents need structured issue trackers not markdown plans because they lose context across sessions and cannot manage nested work]]; (3) context management — what information loads at session start, what gets compressed, what persists across compactions; (4) safety gates — checkpoints where human approval is required before destructive or irreversible actions; (5) rollback loops — the ability to undo agent work that went wrong without losing the good parts; (6) escalation points — defined moments where the agent should stop and ask rather than guessing.

The term emerged from the observation that the bottleneck in agentic software development shifted from *implementation* (agents are great at writing code) to *orchestration* (knowing what's worth automating, decomposing work correctly, maintaining quality over multi-session arcs). [[AGENTS.md files reduce AI coding agent runtime by 29 percent and output tokens by 17 percent without hurting task completion]] provides empirical evidence that even simple harness components (a single context file) measurably improve agent efficiency.

The Mycelium project itself is an instance of harness engineering: the 4-agent workflow (scientist, implementer, verifier, maintainer) with Beads-backed issue tracking, skill libraries, and human-in-the-loop gates is a complete harness for knowledge management work.

## Claims

- **[definition]** Harness engineering is the discipline of building operational infrastructure (specs, memory, context, safety gates, rollback, escalation) that keeps long-running agent sessions coherent and productive (neutral)
- **[causal]** The bottleneck in agentic development shifted from implementation speed to orchestration quality — agents can code fast but need harness infrastructure to code correctly over time (supports)
- **[procedural]** A complete harness includes: versioned specs, persistent memory, context management, safety gates, rollback loops, and escalation points (neutral)
- **[causal]** Without harness infrastructure, agent sessions degrade over time as context accumulates, plans decay, and the agent loses track of the global objective (supports)
- **[empirical]** Even minimal harness components like AGENTS.md files produce measurable efficiency gains (28% runtime reduction), suggesting that more complete harnesses yield compounding benefits (supports)

## External Resources

- [William Boudy's portfolio](portfolio-derived) — concept coined through practice with Fly Orchestration Kit, Mycelium, and agentic forecasting systems

## Original Content

> [!quote]- Source Material
> Harness Engineering — domain knowledge from practice
>
> Concept developed through building Fly Orchestration Kit (deterministic FSM control plane), Mycelium (knowledge vault with 4-agent workflow), and agentic forecasting systems. The term captures the operational discipline of maintaining agent session coherence across long-horizon work.
>
> [Portfolio-derived knowledge]
