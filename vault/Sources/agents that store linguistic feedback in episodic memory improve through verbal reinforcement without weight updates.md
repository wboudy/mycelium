---
created: 2026-04-11
description: Reflexion enables language agents to learn from trial-and-error by storing verbal self-reflections in episodic memory, improving performance on coding, reasoning, and decision-making tasks without gradient updates
source: https://arxiv.org/abs/2303.11366
status: canon
type: source
tags: [agents, self-reflection, episodic-memory, verbal-reinforcement, in-context-learning]
---

## Key Takeaways

Reflexion introduces a simple but powerful mechanism for agent self-improvement: after failing at a task, the agent generates a verbal self-reflection ("I failed because I didn't check the edge case..."), stores it in an episodic memory buffer, and uses it as context on the next attempt. This is "verbal reinforcement learning" — instead of updating weights, the agent learns by accumulating linguistic lessons that modify its behavior through in-context conditioning.

The approach works across coding (HumanEval), reasoning (HotPotQA), and decision-making (AlfWorld) tasks. It's particularly effective because the reflections are semantically rich — they encode not just what went wrong but why and how to fix it, providing much denser learning signal than scalar rewards.

This connects to [[LLMs consistently resist incorporating external feedback even when it is near-perfect and they claim to understand it]] — Feedback Friction shows that externally provided feedback hits resistance, but Reflexion's self-generated reflections may sidestep this because the model is more receptive to its own analysis. It also connects to [[agents can learn to consolidate memory as part of reasoning achieving constant memory usage across arbitrarily long horizons]] — MEM1 internalizes memory into hidden states, while Reflexion keeps it as explicit text in an episodic buffer.

## Claims

- **[empirical]** Reflexion improves agent performance on coding, reasoning, and decision-making tasks through verbal self-reflection stored in episodic memory, without any weight updates (supports)
- **[causal]** Verbal self-reflections provide richer learning signal than scalar rewards because they encode what went wrong, why, and how to fix it (supports)
- **[causal]** Self-generated reflections may be more effective than externally provided feedback because the model is generating analysis in its own representational space (supports)
- **[definition]** Reflexion stores linguistic self-reflections from failed attempts in an episodic memory buffer that conditions subsequent attempts through in-context learning (neutral)

## External Resources

- [arXiv:2303.11366](https://arxiv.org/abs/2303.11366) — original paper

## Original Content

> [!quote]- Source Material
> Reflexion: Language Agents with Verbal Reinforcement Learning
>
> Noah Shinn, Federico Cassano, et al., 2023
>
> Summary: Agents learn from trial-and-error by generating verbal self-reflections, storing them in episodic memory, and using them as context on subsequent attempts. Improves coding, reasoning, and decision-making without gradient updates.
>
> [arXiv:2303.11366](https://arxiv.org/abs/2303.11366)
