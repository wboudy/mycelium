---
created: 2026-04-11
description: Lightman et al. show that training reward models on step-level correctness labels (process supervision) outperforms outcome-only supervision for mathematical reasoning, with PRM800K providing 800K step-level annotations
source: https://arxiv.org/abs/2305.20050
status: canon
type: source
tags: [process-reward-models, reasoning, verification, mathematical-reasoning, RLHF]
---

## Key Takeaways

Process Reward Models (PRMs) represent a fundamental shift in how we verify reasoning: instead of only checking whether the final answer is correct (outcome supervision), PRMs evaluate each intermediate step. Lightman et al. at OpenAI created PRM800K — 800K step-level human labels on mathematical reasoning traces — and showed that process supervision produces better-aligned reward models than outcome supervision.

The key insight is that outcome-based reward models can be fooled by reasoning that arrives at the right answer for wrong reasons. A model might make errors that cancel out, or use a correct shortcut that doesn't generalize. Process supervision catches these failure modes by requiring each step to be independently valid.

This is directly relevant to the pizza_at_the_pentagon project's judge model, which must evaluate forecasting reasoning trajectories step by step. The literature appendix in that project extensively discusses PRMs, Process Advantage Verifiers (PAVs), and ThinkPRM — all descendants of this foundational work. It also connects to [[pure reinforcement learning without human demonstrations produces superior reasoning in LLMs]] — DeepSeek-R1 uses outcome-only rewards (accuracy), while process supervision offers a complementary path that may catch reasoning failures that outcome supervision misses.

## Claims

- **[empirical]** Process reward models trained on step-level labels outperform outcome-supervised reward models for mathematical reasoning, achieving 78% accuracy on MATH problems (supports)
- **[causal]** Outcome-based supervision can be fooled by reasoning that reaches correct answers through incorrect steps, while process supervision catches each intermediate error (supports)
- **[empirical]** PRM800K provides 800K human step-level correctness labels for mathematical reasoning traces, enabling training of fine-grained reward models (supports)
- **[causal]** Step-level verification is more informative than outcome-level verification because it provides denser training signal and prevents reward hacking through compensating errors (supports)
- **[definition]** A Process Reward Model evaluates the correctness of each intermediate step in a reasoning chain, in contrast to Outcome Reward Models that only evaluate the final answer (neutral)

## External Resources

- [arXiv:2305.20050](https://arxiv.org/abs/2305.20050) — original paper

## Original Content

> [!quote]- Source Material
> Let's Verify Step by Step
>
> Hunter Lightman, Vineet Kosaraju, Yura Burda, et al.
> OpenAI, 2023
>
> Summary: Process supervision — training reward models on step-level correctness labels rather than outcome-only supervision — produces better mathematical reasoning verification. PRM800K provides 800K step-level human annotations for training process reward models.
>
> [arXiv:2305.20050](https://arxiv.org/abs/2305.20050)
