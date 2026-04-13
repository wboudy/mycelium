---
created: 2026-04-11
description: Steve Yegge argues that AI coding agents fail at long-horizon work because markdown plans decay into confusion across sessions, and introduces Beads — a lightweight issue tracker designed as persistent memory that gives agents structured work discovery and stack management
source: beads.pdf
status: canon
type: source
tags: [AI-agents, coding-agents, issue-tracking, agent-memory, orchestration, vibe-coding]
---

## Key Takeaways

Yegge identifies the core failure mode of AI coding agents in long-horizon tasks: the "dementia problem." Agents have no memory between sessions (~10 minutes before compaction). They boot up, find whatever is on disk, and focus on it — but real engineering workflows span many sessions, involve nested subtasks, and require tracking where you are in a multi-phase plan. Markdown plans, the default approach, decay catastrophically: agents create plans, then sub-plans, then sub-sub-plans, until you have 605 inscrutable markdown files in a plans/ folder and the agent is "meandering intelligently but blindly."

The solution is Beads — an issue tracker specifically designed for AI agents, not humans. It gives agents structured work discovery (what should I work on next?), dependency tracking (what blocks what?), and stack management (I was working on X, got interrupted by Y, need to return to X). The key design choice is that Beads is integrated into AGENTS.md with a single line, so agents automatically gain cognitive capabilities for long-horizon planning.

This connects directly to [[AGENTS.md files reduce AI coding agent runtime by 29 percent and output tokens by 17 percent without hurting task completion]] — Beads extends the AGENTS.md pattern from static context into dynamic work state management. And the failure of markdown plans parallels the failure of [[reinforcement learning can be reduced to sequence modeling by conditioning a transformer on desired returns]] in long contexts — sequence models need structured state, not free-form text, to maintain coherence over extended horizons.

Yegge's two architectural mistakes (Temporal too heavyweight, markdown plans too unstructured) offer practical wisdom: the right tool for agent orchestration is lighter than enterprise workflow engines but more structured than flat files. The lesson from 350K lines of burned code is that agent memory infrastructure is the foundation everything else depends on.

## Claims

- **[causal]** AI coding agents fail at long-horizon work because they have no memory between sessions and markdown plans decay into hundreds of inscrutable files as agents create nested sub-plans without global context (supports)
- **[empirical]** After six weeks and 350K lines of code, the vibecoder project had to be completely rewritten because two foundational mistakes (Temporal too heavyweight, markdown plans too unstructured) had permeated the entire system (supports)
- **[causal]** Structured issue tracking (not markdown plans) gives agents the persistent state needed for work discovery, dependency management, and stack-based task switching across compaction boundaries (supports)
- **[procedural]** Beads integrates into AGENTS.md with a single line, providing agents with an immediate cognitive upgrade for long-horizon planning without requiring architectural changes (supports)
- **[causal]** The "dementia problem" — agents knowing only what's on disk when they boot — means that the format of persistent artifacts directly determines agent capability, making structured state management more important than raw model intelligence (supports)
- **[empirical]** 95-99% of interactions with coding agents are mundane babysitting ("fix the tests", "yes continue", "no don't drop that table"), motivating automation of the agentic workflow itself (supports)

## External Resources

- [Medium: Introducing Beads](https://steve-yegge.medium.com/introducing-beads-a-coding-agent-memory-system-637d7d92514a) — original blog post
- [GitHub: Beads](https://github.com/) — referenced in post

## Original Content

> [!quote]- Source Material
> Introducing Beads: A coding agent memory system
>
> Steve Yegge, Medium, October 2025
>
> Summary: After building a 350K-line orchestration engine that had to be completely rewritten, Yegge identifies the fundamental problem as agent memory across sessions. Markdown plans decay into chaos at scale. Beads is a lightweight issue tracker designed as cognitive infrastructure for AI coding agents — install it, point AGENTS.md at it, and agents gain structured work discovery and long-horizon planning capabilities.
>
> [Source](https://steve-yegge.medium.com/introducing-beads-a-coding-agent-memory-system-637d7d92514a)
