---
created: 2026-04-11
description: Empirical study on 10 repos and 124 PRs shows AGENTS.md files reduce median runtime by 28.64% and output token consumption by 16.58% for AI coding agents while maintaining comparable task completion
source: agents md impact.pdf
status: canon
type: source
tags: [AI-agents, software-engineering, AGENTS-md, coding-agents, efficiency, developer-tools]
---

## Key Takeaways

This is the first empirical study isolating the impact of AGENTS.md files on AI coding agent efficiency. The experimental design is clean: same tasks, same repos, same agent (OpenAI Codex with gpt-5.2-codex), run with and without an AGENTS.md file. The results are clear — AGENTS.md reduces median runtime by 28.64% and output token consumption by 16.58% while maintaining comparable task completion behavior.

The broader significance is that AGENTS.md represents a new class of software artifact — not code, not documentation for humans, but version-controlled configuration files that shape agent behavior. Over 60,000 repos have adopted the format, shifting agent guidance from ephemeral prompts to persistent, inspectable, collaboratively maintained artifacts. This is "context engineering" for agents.

The efficiency gains likely come from AGENTS.md providing architectural context, build commands, coding conventions, and operational constraints upfront, which reduces the agent's exploration and trial-and-error during repository navigation. Instead of spending tokens discovering project structure, the agent gets it immediately.

This directly validates the approach used in the Mycelium project's own AGENTS.md, and connects to the broader pattern that [[reinforcement learning can be reduced to sequence modeling by conditioning a transformer on desired returns]] — conditioning on the right context (whether desired returns or project-specific instructions) dramatically improves agent behavior without requiring any model changes.

## Claims

- **[empirical]** AGENTS.md files reduce median AI coding agent runtime by 28.64% and output token consumption by 16.58% across 10 repositories and 124 pull requests (supports)
- **[empirical]** Task completion behavior is comparable with and without AGENTS.md, meaning efficiency gains come without sacrificing effectiveness (supports)
- **[empirical]** Over 60,000 repositories have adopted the AGENTS.md format as of early 2026, establishing it as a widespread practice (supports)
- **[causal]** Repository-level instruction files reduce agent exploration costs by providing architectural context, build commands, and conventions upfront rather than requiring the agent to discover them (supports)
- **[definition]** AGENTS.md files are persistent, version-controlled, developer-curated instruction artifacts that serve as "READMEs for agents," specifying project-specific knowledge for autonomous coding agents (neutral)
- **[normative]** Agent context files should be studied as a new class of software artifact with implications for cost, scalability, and workflow integration of AI coding agents (supports)

## External Resources

- [arXiv:2601.20404](https://arxiv.org/abs/2601.20404) — original paper
- [Online appendix](https://github.com/) — replication package (referenced in paper)

## Original Content

> [!quote]- Source Material
> On the Impact of AGENTS.md Files on the Efficiency of AI Coding Agents
>
> Jai Lal Lulla, Seyedmoein Mohsenimofidi, Matthias Galster, Jie M. Zhang, Sebastian Baltes, Christoph Treude
> Singapore Management University, Heidelberg University, King's College London, University of Bamberg, ICSE JAWs 2026
>
> Abstract: We study the impact of AGENTS.md files on the runtime and token consumption of AI coding agents operating on GitHub pull requests. We analyze 10 repositories and 124 pull requests, executing agents under two conditions: with and without an AGENTS.md file. Our results show that the presence of AGENTS.md is associated with a lower median runtime (28.64%) and reduced output token consumption (16.58%), while maintaining comparable task completion behavior.
>
> [Source PDF](agents md impact.pdf)
