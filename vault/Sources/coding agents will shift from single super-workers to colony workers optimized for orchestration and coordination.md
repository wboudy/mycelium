---
created: 2026-04-11
description: Yegge predicts that the future of coding agents is not bigger individual agents but colonies — coordinated swarms that outperform single super-workers — requiring agents to expose orchestrator APIs and shift from pair-programmer to factory-worker paradigm
source: future of coding agents yegge.pdf
status: canon
type: source
tags: [coding-agents, orchestration, predictions, vibe-coding, colonies, industry-trends]
---

## Key Takeaways

This post, written three days after Gas Town's launch, makes four key predictions about the future of coding agents. The central thesis is Brendan Hopper's ant colony metaphor: current coding agents are "the world's biggest fuckin' ant" — individual super-workers. But nature prefers colonies for getting work done. The industry will shift from making individual agents better to making agents coordinate as colony workers.

Four free upgrades will make Gas Town better without any engineering effort: (1) models getting smarter — Opus 4.5 already made Python Gas Town dramatically smoother overnight; (2) Gas Town and Beads entering the training corpus so agents use them natively by summer; (3) agent vendors waking up and competing on orchestrator API support rather than individual agent power; (4) community contributions (50+ PRs in the first weekend).

The "Desire Paths" approach to agent UX is a practical design philosophy: tell the agent what you want, watch what it tries to do, then implement the thing it tried. Make the interface match the agent's natural behavior rather than forcing agents into human-designed workflows. This is why Beads works with zero training — agents naturally understand issue-tracker patterns.

The prediction about big companies being "really screwed" connects to [[orchestrating 20 to 30 parallel coding agents requires Kubernetes-like infrastructure not just a better IDE]] — if tiny teams with agent colonies can outperform large engineering organizations, the competitive dynamics of software development fundamentally change. The lunch story about ex-Amazon engineers spending $60K/year on agent compute while doing startup work illustrates the economics of this shift.

## Claims

- **[normative]** Coding agents will shift from being optimized as individual pair programmers to being optimized as colony workers with orchestrator API surfaces (supports)
- **[causal]** Nature prefers colonies for getting work done — coordinated swarms of agents will outperform single super-workers regardless of how powerful individual agents become (supports)
- **[empirical]** Gas Town grew 10x faster than Beads in its first weekend, with 50+ PRs, indicating strong demand for orchestration infrastructure (supports)
- **[procedural]** The "Desire Paths" approach to agent UX — watch what agents try, then implement it — produces interfaces agents use naturally without training (neutral)
- **[normative]** Small teams with agent colonies will dramatically outperform large companies in 2026, creating a period of churn where company size becomes a liability (supports)
- **[empirical]** Model upgrades passively improve orchestrator quality — Opus 4.5 made Python Gas Town dramatically smoother overnight without any code changes (supports)
- **[causal]** Agent vendors that embrace the colony-worker paradigm and expose orchestrator APIs will win over those optimizing only for individual agent capability (supports)

## External Resources

- [Medium: The Future of Coding Agents](https://steve-yegge.medium.com/the-future-of-coding-agents-e9451a84207c) — original blog post

## Original Content

> [!quote]- Source Material
> The Future of Coding Agents
>
> Steve Yegge, Medium, January 2026
>
> Summary: Three days after Gas Town's launch, Yegge argues that the future is colonies not super-workers. Four forces will make Gas Town better passively: smarter models, training corpus inclusion, vendor API support, and community. Predicts big companies will be disrupted by tiny teams wielding agent colonies. Introduces "Desire Paths" as an agent UX design philosophy.
>
> [Source](https://steve-yegge.medium.com/the-future-of-coding-agents-e9451a84207c)
