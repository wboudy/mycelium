---
created: 2026-04-11
description: DeltaNet replaces softmax attention with delta rule-based linear attention, enabling O(n) complexity while maintaining key-value associative memory that improves as sequences get longer
source: https://sustcsonglin.github.io/blog/2024/deltanet-1/
status: canon
type: source
tags: [attention, linear-attention, delta-rule, transformers, efficiency]
---

## Key Takeaways

DeltaNet reimagines attention through the lens of the delta rule from associative memory theory. Standard softmax attention computes pairwise similarities between all tokens (O(n^2)), but DeltaNet replaces this with a linear recurrence that maintains a key-value memory matrix updated via the delta rule: new associations strengthen existing ones and overwrite outdated ones.

This creates linear attention (O(n) per step) that actually *improves* with longer sequences — the memory accumulates more associations over time, unlike standard attention which becomes diluted. The delta rule provides a principled update mechanism: when a key-value pair is presented, it updates the memory by moving the stored value for that key toward the target value, with a learning rate that controls how aggressively old associations are overwritten.

This connects to [[IO-aware tiling makes exact attention faster than approximate methods by avoiding HBM bottlenecks]] — both address attention efficiency, but FlashAttention optimizes the hardware implementation of exact attention while DeltaNet changes the mathematical formulation entirely. It also relates to [[agents can learn to consolidate memory as part of reasoning achieving constant memory usage across arbitrarily long horizons]] — both use recurrent state that selectively retains and overwrites information.

## Claims

- **[causal]** Delta rule-based updates provide a principled mechanism for linear attention to selectively retain and overwrite key-value associations, creating associative memory that improves with sequence length (supports)
- **[empirical]** DeltaNet achieves O(n) complexity per step while maintaining competitive performance with softmax attention on language modeling tasks (supports)
- **[causal]** Standard linear attention methods degrade with sequence length because they accumulate noise, while the delta rule's selective overwriting prevents this degradation (supports)
- **[definition]** DeltaNet maintains a memory matrix updated via the delta rule: for each new key-value pair, the stored value for that key is moved toward the target value, with old associations being selectively overwritten (neutral)

## External Resources

- [DeltaNet explainer](https://sustcsonglin.github.io/blog/2024/deltanet-1/) — Songlin Yang's technical blog post

## Original Content

> [!quote]- Source Material
> What is DeltaNet? — Songlin Yang's blog
>
> Technical explainer on DeltaNet, a linear attention mechanism based on the delta rule from associative memory theory. Replaces softmax attention with a recurrent key-value memory updated via selective overwriting.
>
> [Blog post](https://sustcsonglin.github.io/blog/2024/deltanet-1/)
