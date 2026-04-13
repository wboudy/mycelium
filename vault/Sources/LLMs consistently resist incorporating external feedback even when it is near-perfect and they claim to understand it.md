---
created: 2026-04-11
description: Jiang, Zhang, Wang, Andrews, and Khashabi show that LLMs plateau below target accuracy even with near-ideal feedback from a model with ground-truth access — feedback resistance, not feedback quality, is the dominant failure mode across all tasks
source: feedback friction.pdf
status: canon
type: source
tags: [LLM, self-improvement, feedback, reasoning, limitations, JHU-HLTCOE]
---

## Key Takeaways

Feedback Friction reveals a fundamental limitation in LLM self-improvement: even when given near-perfect, targeted feedback from a model with complete ground-truth access, LLMs consistently fail to fully incorporate corrections. They plateau well below the theoretically achievable accuracy across math reasoning (AIME, MATH-500), knowledge reasoning (TriviaQA, PopQA), scientific reasoning (GPQA), and multi-domain evaluation (MMLU Pro).

The experimental design is carefully controlled to isolate the problem. Three levels of feedback quality are tested — binary correctness, self-generated reflection, and strong-model reflection — and while better feedback helps, *no level of feedback quality is sufficient* to close the gap. Error analysis on the strongest model tested (Claude 3.7 with Extended Thinking) shows that feedback resistance (the model ignoring clear, correct feedback) is the dominant failure mode, accounting for the majority of persistent errors. Feedback quality issues are secondary.

The most striking finding: models consistently claim to understand the feedback and express willingness to update (>95% of the time), yet fail to actually change their behavior. This disconnect between stated intentions and actual behavior is deeply relevant to [[pure reinforcement learning without human demonstrations produces superior reasoning in LLMs]] — if models can't reliably incorporate explicit corrections, the path to self-improvement may require RL-based approaches that optimize behavior directly rather than relying on verbal reflection.

Semantic entropy (a confidence measure) predicts feedback resistance: high-confidence predictions are more resistant to correction. This suggests that once a model has "committed" to an answer with high certainty, its internal representations resist perturbation from external feedback.

## Claims

- **[empirical]** LLMs consistently plateau below target accuracy even with near-perfect feedback from a model with ground-truth access, across math, knowledge, scientific, and multi-domain reasoning tasks (supports)
- **[empirical]** Feedback resistance — models failing to incorporate clear and accurate feedback — is the dominant failure mode, responsible for the majority of persistent errors (supports)
- **[empirical]** Models claim to understand feedback and express willingness to update their beliefs more than 95% of the time, yet fail to actually incorporate corrections — revealing a disconnect between stated intentions and actual behavior (supports)
- **[causal]** High-confidence predictions (measured by semantic entropy) are more resistant to external correction, suggesting that committed internal representations resist perturbation from feedback (supports)
- **[empirical]** Progressive temperature increases and explicit rejection of previously incorrect answers improve performance but still fail to help models reach target accuracy (supports)
- **[causal]** Feedback quality is not the bottleneck — even the strongest feedback mechanism (GPT-4.1 mini with full ground-truth access) cannot overcome feedback resistance (supports)

## External Resources

- [GitHub: JHU-CLSP/Feedback-Friction](https://github.com/JHU-CLSP/Feedback-Friction) — code
- [arXiv:2506.11930](https://arxiv.org/abs/2506.11930) — original paper (NeurIPS 2025)

## Original Content

> [!quote]- Source Material
> Feedback Friction: LLMs Struggle to Fully Incorporate External Feedback
>
> Dongwei Jiang, Alvin Zhang, Andrew Wang, Nicholas Andrews, Daniel Khashabi
> Johns Hopkins University, NeurIPS 2025
>
> Abstract: Recent studies have shown LLMs possess some ability to improve responses when given external feedback. However, it remains unclear how effectively models can incorporate feedback. We systematically investigate this by providing near-perfect feedback from a model with ground-truth access. Surprisingly, even under these near-ideal conditions, solver models consistently show resistance to feedback — a limitation we term Feedback Friction. We find that models' confidence predicts feedback resistance: high-confidence predictions remain resistant to external correction.
>
> [Source PDF](feedback friction.pdf)
