---
created: 2026-04-11
description: State Machine Reasoning (SMR) reformulates information retrieval reasoning as transitions between structured states using discrete actions (Refine, Rerank, Stop) rather than free-form CoT, improving nDCG@10 by 3.4% while reducing token usage by 74.4%
source: token to action.pdf
status: canon
type: source
tags: [information-retrieval, reasoning, state-machines, CoT, token-efficiency, query-rewriting]
---

## Key Takeaways

This paper identifies a specific failure mode of Chain-of-Thought reasoning in information retrieval: overthinking. CoT produces semantically redundant reasoning traces (revisiting equivalent query reformulations) and can drift from user intent when compressed via RL. The solution is to lift reasoning from the token level to the action level — instead of autoregressive text generation, each reasoning step is a discrete state transition in a state machine.

The state is a (query, document_list) pair, and three actions are available: REFINE (rewrite the query for better recall), RERANK (reorder retrieved documents for better precision), and STOP (halt when the next step would produce no gain). This formulation makes redundancy detectable — the system can recognize when it's revisiting an equivalent state — and makes each step verifiable in terms of retrieval improvement.

The connection to [[hierarchical recurrence at two timescales achieves deep reasoning that flat transformers and chain-of-thought cannot]] is thematic: both papers argue that token-level CoT is the wrong abstraction for structured reasoning. HRM proposes latent reasoning in hidden states; SMR proposes action-level reasoning through explicit state transitions. Both outperform CoT with dramatically fewer tokens.

This also connects to [[agents can learn to consolidate memory as part of reasoning achieving constant memory usage across arbitrarily long horizons]] — SMR's structured states prevent the unbounded context growth that free-form reasoning causes, achieving token efficiency through architectural constraints rather than learned compression.

## Claims

- **[empirical]** SMR improves retrieval performance (nDCG@10) by 3.4% while reducing token usage by 74.4% compared to standard CoT reasoning on BEIR and BRIGHT benchmarks (supports)
- **[causal]** Token-level CoT generation causes redundant reasoning (revisiting semantically equivalent query reformulations) and misguided reasoning (drifting from user intent when compressed), both of which SMR's discrete action framework prevents (supports)
- **[causal]** Structured state transitions make redundancy detectable because equivalent states can be compared, unlike token-level generation which lacks mechanisms to recognize semantic repetition (supports)
- **[empirical]** SMR generalizes across different LLMs and retrievers without task-specific tuning, unlike RL-based CoT compression which requires task-specific reward engineering (supports)
- **[definition]** State Machine Reasoning represents each reasoning step as a transition between (query, document_list) states via three actions: REFINE for query rewriting, RERANK for document reordering, and STOP for early termination when no improvement is possible (neutral)
- **[causal]** Grounding reasoning in IR-relevant operations (refine, rerank) ensures each step yields incremental retrieval improvement, unlike free-form generation which may produce syntactically varied but semantically identical outputs (supports)

## External Resources

- [GitHub: ldilab/SMR](https://github.com/ldilab/SMR) — official code
- [arXiv:2505.23059](https://arxiv.org/abs/2505.23059) — original paper

## Original Content

> [!quote]- Source Material
> From Token to Action: State Machine Reasoning to Mitigate Overthinking in Information Retrieval
>
> Dohyeon Lee, Yeonseok Jeong, Seung-won Hwang
> Seoul National University, 2025
>
> Abstract: Chain-of-Thought prompting enables complex reasoning in LLMs, but often leads to overthinking with excessively long and semantically redundant traces. We identify redundant trajectories and misguided reasoning as key IR challenges. We propose State Machine Reasoning (SMR), a transition-based framework with discrete actions (REFINE, RERANK, STOP). SMR improves nDCG@10 by 3.4% while reducing token usage by 74.4%.
>
> [Source PDF](token to action.pdf)
