---
created: 2026-04-11
description: Steve Yegge's Gas Town is a fourth-generation agent orchestrator that manages 20-30 concurrent Claude Code instances via tmux, Beads-backed work queues, and a merge queue, arguing that the next paradigm shift is from single-agent CLI to industrialized multi-agent factories
source: gastown.pdf
status: canon
type: source
tags: [agent-orchestration, multi-agent, coding-agents, Gas-Town, vibe-coding, infrastructure]
---

## Key Takeaways

Gas Town is Yegge's fourth attempt at an agent orchestrator (after three failures in 2025), and it represents a vision for what coding looks like at "Stage 8" of developer evolution: you're a Product Manager running an "Idea Compiler," designing features and slinging tasks to 20-30 parallel Claude Code instances that churn through implementation. Your job is decomposition and quality control, not writing code.

The architecture resembles Kubernetes mated with Temporal: work discovery from [[coding agents need structured issue trackers not markdown plans because they lose context across sessions and cannot manage nested work]], a merge queue for reconciling parallel changes, quality gates for validation, and hierarchical supervision where some agents supervise others. Beads is the universal git-backed data plane and control plane — there's no alternative backend.

The 8-stage evolution of AI-assisted developers is a useful framework: from near-zero AI (Stage 1) through single CLI agent (Stage 5) to multi-agent hand-management (Stage 7) to building your own orchestrator (Stage 8). Gas Town targets Stage 7-8 developers and is explicitly not for anyone earlier — the "superintelligent chimpanzees" metaphor captures the reality that powerful agents operating in parallel will wreck things if you're not an experienced handler.

Key operational characteristics: chaotic by design (some work gets done multiple times, some gets lost), throughput-focused (creation and correction at the speed of thought), expensive (requires multiple Claude Code accounts), and built on tmux as the primary UI. The MAKER problem (20-disc Tower of Hanoi) is solved trivially with million-step wisps, demonstrating that long-horizon planning works when properly orchestrated.

This connects to [[AGENTS.md files reduce AI coding agent runtime by 29 percent and output tokens by 17 percent without hurting task completion]] — Gas Town is where AGENTS.md and Beads culminate: not just agent efficiency on individual tasks, but industrialized parallel execution of entire development workflows.

## Claims

- **[empirical]** Gas Town is Yegge's fourth complete functioning orchestrator of 2025, after three that failed at different points, indicating the problem space is genuinely hard and requires iterative discovery (supports)
- **[causal]** Managing 20-30 parallel coding agents requires Kubernetes-like infrastructure (work queues, merge queues, quality gates, hierarchical supervision) because hand-management breaks down past 5-7 concurrent instances (supports)
- **[normative]** The developer role shifts from code author to Product Manager at scale — you design features and decompose work, agents implement, and the orchestrator coordinates (supports)
- **[empirical]** Gas Town solves the MAKER problem (20-disc Tower of Hanoi requiring ~1M steps) trivially with formulaic wisps, while LLMs alone fail after a few hundred steps (supports)
- **[causal]** Multi-agent orchestration is inherently chaotic — some work gets duplicated, some gets lost — but throughput at the speed of thought compensates for imperfect efficiency (supports)
- **[procedural]** Gas Town's 8-stage developer evolution framework positions single-agent CLI (Stage 5) as a transitional form, with multi-agent orchestration (Stages 7-8) as the emerging paradigm (neutral)
- **[empirical]** Gas Town is expensive — requires multiple Claude Code accounts for sustained operation of 20-30 agents (supports)

## External Resources

- [Medium: Welcome to Gas Town](https://steve-yegge.medium.com/welcome-to-gas-town-4f25ee16dd04) — original blog post

## Original Content

> [!quote]- Source Material
> Welcome to Gas Town
>
> Steve Yegge, Medium, January 2026
>
> Summary: Gas Town is a multi-agent orchestrator that manages 20-30 concurrent Claude Code instances. Built on Beads (git-backed issue tracking), it operates like "Kubernetes for agents" with work queues, merge queues, quality gates, and hierarchical supervision. It represents Stage 8 of developer evolution — where you become a Product Manager running an Idea Compiler, and agents handle all implementation.
>
> [Source](https://steve-yegge.medium.com/welcome-to-gas-town-4f25ee16dd04)
