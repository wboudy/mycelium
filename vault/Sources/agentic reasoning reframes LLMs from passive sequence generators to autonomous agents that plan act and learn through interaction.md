---
created: 2026-04-11
description: Comprehensive survey organizing agentic reasoning into three layers — foundational capabilities (planning, tool use, search), self-evolving adaptation (feedback, memory), and collective multi-agent coordination — with in-context and post-training optimization as cross-cutting dimensions
source: agentic reasoning LLMs survey.pdf
status: canon
type: source
tags: [agentic-AI, LLM-agents, reasoning, planning, multi-agent, survey]
---

## Key Takeaways

This survey provides a unified taxonomy for the rapidly expanding field of agentic reasoning. The key conceptual shift is reframing reasoning as the organizing principle for perception, planning, decision, and verification — not just Chain-of-Thought text generation but actual interaction with environments, tools, and other agents.

The three-layer structure maps cleanly to increasing environmental complexity. Foundational agentic reasoning covers single-agent capabilities in stable environments: planning (task decomposition, goal pursuit), tool use (API calling, code execution), and search (exploration strategies). Self-evolving reasoning adds adaptation in dynamic environments: feedback integration (Reflexion-style critique loops), memory persistence (storing reasoning traces for reuse), and policy updates. Collective reasoning extends to multi-agent scenarios: role coordination, knowledge sharing, and collaborative goal pursuit.

The cross-cutting optimization dimension is crucial: in-context reasoning scales test-time interaction through structured orchestration and workflow design (no weight updates), while post-training reasoning optimizes behaviors through RL and SFT (permanent capability changes). This maps to the distinction between [[pure reinforcement learning without human demonstrations produces superior reasoning in LLMs]] (post-training) and [[reinforcement learning can be reduced to sequence modeling by conditioning a transformer on desired returns]] (in-context conditioning).

The open challenges identified — personalization, long-horizon interaction, world modeling, scalable multi-agent training, and governance — align well with the practical problems faced in [[orchestrating 20 to 30 parallel coding agents requires Kubernetes-like infrastructure not just a better IDE]] and [[coding agents need structured issue trackers not markdown plans because they lose context across sessions and cannot manage nested work]].

## Claims

- **[definition]** Agentic reasoning positions reasoning as the central mechanism of intelligent agents, spanning foundational capabilities, self-evolving adaptation, and collective coordination, realizable through in-context orchestration or post-training optimization (neutral)
- **[causal]** The shift from static one-shot inference to sequential decision-making under uncertainty requires agents to plan over long horizons, navigate partial observability, and actively improve through feedback (supports)
- **[empirical]** Foundational agentic reasoning capabilities — planning, tool use, and search — form the bedrock upon which self-evolution and multi-agent coordination are built (supports)
- **[causal]** Self-evolving agents that persist memory and integrate feedback across interactions develop capabilities that fixed-reasoning agents cannot, because cumulative experience enables policy improvement (supports)
- **[causal]** In-context reasoning and post-training reasoning are complementary — the former scales at test time without weight changes while the latter permanently embeds capabilities (supports)
- **[normative]** Open challenges include personalization, long-horizon interaction, world modeling, scalable multi-agent training, and governance frameworks for real-world deployment (supports)

## External Resources

- [GitHub: weitianxin/Awesome-Agentic-Reasoning](https://github.com/weitianxin/Awesome-Agentic-Reasoning) — curated resource list
- [arXiv:2601.12538](https://arxiv.org/abs/2601.12538) — original paper

## Original Content

> [!quote]- Source Material
> Agentic Reasoning for Large Language Models: Foundations, Evolution, Collaboration
>
> Tianxin Wei, Ting-Wei Li, Zhining Liu, et al.
> UIUC, Meta, Amazon, Google DeepMind, Yale, UCSD, 2026
>
> Abstract: While LLMs demonstrate strong reasoning in closed-world settings, they struggle in open-ended and dynamic environments. The emergence of agentic reasoning marks a paradigm shift, bridging thought and action by reframing LLMs as autonomous agents that plan, act, and learn through continual interaction. This survey organizes agentic reasoning along three dimensions: foundational capabilities, self-evolving adaptation, and collective multi-agent reasoning, with in-context and post-training optimization as cross-cutting dimensions.
>
> [Source PDF](agentic reasoning LLMs survey.pdf)
