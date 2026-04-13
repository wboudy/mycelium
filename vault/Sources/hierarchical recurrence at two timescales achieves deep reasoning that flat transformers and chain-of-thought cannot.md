---
created: 2026-04-11
description: HRM uses two coupled recurrent modules operating at different timescales — slow abstract planning and fast detailed computation — to achieve effective computational depth that surpasses CoT-based LLMs on ARC, Sudoku, and maze tasks with only 27M parameters and 1000 training examples
source: hierarchical_reasoning.pdf
status: canon
type: source
tags: [reasoning, recurrent-networks, hierarchical-processing, ARC, computational-depth]
---

## Key Takeaways

HRM starts from a fundamental computational theory argument: standard transformers have fixed depth, placing them in complexity classes (AC0/TC0) that cannot solve problems requiring polynomial time. No amount of width scaling helps — you need depth for complex reasoning. But naively stacking layers causes vanishing gradients, and standard recurrent networks suffer from early convergence where later computational steps become inert.

The biological inspiration is the brain's hierarchical multi-timescale processing: slow cortical areas do abstract planning while fast lower-level circuits execute detailed computation, connected by recurrent feedback loops. HRM instantiates this with two coupled recurrent modules: a high-level (H) module for slow, abstract reasoning that operates at a lower frequency, and a low-level (L) module for rapid, detailed computation. The H module guides the L module while the L module feeds refined representations back — creating effective computational depth far beyond what either module could achieve alone.

The results are striking: with only 27M parameters and ~1000 training examples, HRM achieves near-perfect performance on Sudoku-Extreme and optimal path-finding in 30x30 mazes — tasks where DeepSeek-R1, Claude 3.7, and o3-mini-high all score near zero using Chain-of-Thought. On ARC-AGI benchmarks, HRM outperforms these much larger models despite having orders of magnitude fewer parameters. Critically, HRM does this in a single forward pass without CoT, without pretraining, and without explicit supervision of intermediate reasoning steps.

This challenges the dominant paradigm where reasoning = more tokens. [[Pure reinforcement learning without human demonstrations produces superior reasoning in LLMs]] showed that RL can discover reasoning behaviors, but still operates through token-level CoT. HRM suggests the future may be latent reasoning in continuous hidden states, not linguistic externalization.

## Claims

- **[empirical]** HRM with 27M parameters and ~1000 training examples achieves near-perfect accuracy on Sudoku-Extreme and 30x30 maze path-finding, where state-of-the-art CoT models (DeepSeek-R1, Claude 3.7, o3-mini-high) score near zero (supports)
- **[causal]** Fixed-depth transformers are computationally limited to AC0/TC0 complexity classes and cannot solve problems requiring polynomial-time reasoning regardless of width scaling (supports)
- **[causal]** Two coupled recurrent modules operating at different timescales — slow abstract planning and fast detailed computation — achieve effective computational depth that overcomes the saturation problem of standard deep or recurrent architectures (supports)
- **[empirical]** HRM outperforms much larger CoT-based models on ARC-AGI benchmarks despite having orders of magnitude fewer parameters and no pretraining (supports)
- **[causal]** Chain-of-Thought reasoning is brittle because it externalizes computation into token-level language, where a single misstep can derail the entire reasoning chain — latent reasoning in hidden state space avoids this (supports)
- **[empirical]** HRM solves tasks in a single forward pass without generating intermediate reasoning tokens, making it dramatically faster than CoT approaches that generate thousands of tokens (supports)
- **[definition]** HRM consists of a high-level recurrent module for slow abstract planning that guides a low-level recurrent module for fast detailed computation, with bidirectional information flow between them (neutral)

## External Resources

- [GitHub: sapientinc/HRM](https://github.com/sapientinc/HRM) — official implementation
- [arXiv:2506.21734](https://arxiv.org/abs/2506.21734) — original paper

## Original Content

> [!quote]- Source Material
> Hierarchical Reasoning Model
>
> Guan Wang, Jin Li, Yuhao Sun, Xing Chen, Changling Liu, Yue Wu, Meng Lu, Sen Song, Yasin Abbasi Yadkori
> Sapient Intelligence, Tsinghua University, 2025
>
> Abstract: Reasoning remains a critical challenge in AI. Current LLMs primarily employ Chain-of-Thought techniques, which suffer from brittle task decomposition, extensive data requirements, and high latency. Inspired by hierarchical and multi-timescale processing in the human brain, we propose the Hierarchical Reasoning Model (HRM), a novel recurrent architecture that attains significant computational depth while maintaining training stability and efficiency. With only 27 million parameters, HRM achieves exceptional performance on complex reasoning tasks using only 1000 training samples, without pre-training or CoT data, yet achieves nearly perfect performance on challenging tasks including complex Sudoku puzzles and optimal path finding in large mazes.
>
> [Source PDF](hierarchical_reasoning.pdf)
