---
created: 2026-04-11
description: Skill libraries — versioned, reusable prompt templates that load into agent sessions automatically — standardize workflows, encode operational knowledge, and prevent the re-invention of patterns that have already been validated
source: portfolio-derived
status: canon
type: source
tags: [prompt-engineering, skill-libraries, agent-workflows, operational-knowledge, original-concept]
---

## Key Takeaways

Prompt skill libraries solve a practical problem: when you discover a good workflow for an agent task (e.g., how to do code review, how to ingest a URL, how to verify a Definition of Done), that knowledge lives in your head or in a chat history that will be lost. Skill libraries persist these workflows as versioned, reusable prompt templates that load into agent sessions automatically.

The Mycelium project maintains 15 skills across two categories: Beads issue tracking (bd-create, bd-show, bd-ready, bd-close, bd-update, bd-sync) and Mycelium workflow (scientist, implementer, verifier, maintainer, next, onboard, review, ingest, bug-interrupt). Each skill is a SKILL.md file that encodes the complete workflow — inputs, steps, validation checks, and output format — so any agent session can invoke it consistently.

The key insight is that skills are not just prompts — they're encoded operational knowledge that accumulates over time. Each time you refine a skill (fix an edge case, add a validation step, improve the output format), that improvement persists for all future sessions. This is the agent equivalent of writing reusable functions: you invest in the abstraction once and benefit forever.

The Fly Orchestration Kit demonstrated this at scale with 28+ shared prompts across Claude, Codex, and Gemini — showing that skill libraries can be cross-agent, not locked to one provider. [[AGENTS.md files reduce AI coding agent runtime by 29 percent and output tokens by 17 percent without hurting task completion]] validates that providing structured context to agents improves efficiency; skill libraries extend this from static context to dynamic workflow guidance.

## Claims

- **[causal]** Skill libraries prevent re-invention of validated workflows across agent sessions by encoding operational knowledge in versioned, reusable prompt templates (supports)
- **[procedural]** Each skill is a SKILL.md file encoding the complete workflow: inputs, steps, validation checks, and output format, loadable by any agent session (neutral)
- **[causal]** Skills accumulate improvements over time — each refinement persists for all future sessions, creating compounding operational value (supports)
- **[empirical]** The Fly Orchestration Kit demonstrated cross-agent skill libraries with 28+ shared prompts across Claude, Codex, and Gemini (supports)
- **[causal]** Skill libraries extend the AGENTS.md pattern from static context to dynamic workflow guidance, providing structured behavioral templates rather than just project information (supports)

## External Resources

- [Mycelium skills](portfolio-derived) — 15 skills in .claude/skills/
- [Fly Orchestration Kit](portfolio-derived) — 28+ shared prompts across agents

## Original Content

> [!quote]- Source Material
> Prompt Skill Libraries — domain knowledge from practice
>
> Developed through Mycelium (15 skills for knowledge management workflow) and Fly Orchestration Kit (28+ cross-agent prompts). Skills encode validated workflows as versioned prompt templates that load automatically into agent sessions.
>
> [Portfolio-derived knowledge]
