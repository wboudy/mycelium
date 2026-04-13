---
created: 2026-04-11
description: Tri Dao et al. show that accounting for GPU memory hierarchy (SRAM vs HBM) matters more than reducing FLOPs, achieving up to 7.6x speedup on exact attention through tiling and kernel fusion
source: fast attention.pdf
status: canon
type: source
tags: [transformers, attention, GPU-optimization, memory-hierarchy, systems]
---

## Key Takeaways

FlashAttention's central thesis is that FLOP count is the wrong optimization target for attention. On modern GPUs, compute speed has outpaced memory bandwidth so dramatically that most transformer operations are memory-bound, not compute-bound. The standard attention implementation materializes the full N x N attention matrix to GPU high bandwidth memory (HBM), which is the real bottleneck — not the O(N^2) arithmetic.

The solution uses two classical techniques applied to the GPU memory hierarchy. First, tiling: split Q, K, V into blocks that fit in on-chip SRAM (19 TB/s, ~20MB per streaming multiprocessor on A100) and compute attention block-by-block without ever materializing the full attention matrix in HBM (1.5 TB/s, 40-80GB). Second, recomputation: instead of storing the attention matrix for the backward pass, store only the softmax normalization statistics and recompute attention on-chip during backprop. This trades extra FLOPs for drastically fewer HBM accesses — and the trade is overwhelmingly worth it because SRAM is ~13x faster than HBM.

The IO complexity analysis is the paper's theoretical contribution: FlashAttention requires O(N^2 d^2 M^-1) HBM accesses versus standard attention's O(Nd + N^2), and this is provably optimal — no exact attention algorithm can do better asymptotically across all SRAM sizes. This is a rare case of a practical systems paper with tight lower bounds.

The practical impact was enormous. FlashAttention enabled longer contexts (16K-64K sequences) which directly improved model quality — 0.7 better perplexity on GPT-2, first-ever better-than-chance on Path-X (16K) and Path-256 (64K). This connects to [[curriculum learning improves generalization by acting as a continuation method on non-convex objectives]] in spirit: both show that training procedure innovations (not just architecture) unlock capabilities that were previously inaccessible.

## Claims

- **[causal]** Approximate attention methods fail to achieve wall-clock speedup despite reducing FLOPs because they ignore memory access overhead — the real bottleneck on modern GPUs is HBM bandwidth, not compute (supports)
- **[empirical]** FlashAttention achieves up to 7.6x speedup on GPT-2 attention computation and 3x end-to-end training speedup while computing exact attention, not an approximation (supports)
- **[empirical]** FlashAttention uses linear memory in sequence length rather than quadratic, because the N x N attention matrix is never materialized in HBM (supports)
- **[causal]** Tiling the attention computation into SRAM-sized blocks and recomputing attention in the backward pass trades extra FLOPs for fewer HBM accesses, which is net positive because SRAM bandwidth is ~13x higher than HBM bandwidth (supports)
- **[empirical]** FlashAttention's IO complexity of O(N^2 d^2 M^-1) HBM accesses is provably optimal — no exact attention algorithm can asymptotically improve on this across all SRAM sizes (supports)
- **[empirical]** Longer context enabled by FlashAttention directly improves model quality: 0.7 better perplexity on GPT-2, 6.4 point lift on long-document classification, and first better-than-chance performance on Path-X (16K) and Path-256 (64K) (supports)
- **[empirical]** Block-sparse FlashAttention scales to 64K sequence length and is 2-4x faster than dense FlashAttention, with IO complexity improved by a factor proportional to the sparsity ratio (supports)

## External Resources

- [GitHub: HazyResearch/flash-attention](https://github.com/HazyResearch/flash-attention) — official implementation
- [arXiv:2205.14135](https://arxiv.org/abs/2205.14135) — original paper

## Original Content

> [!quote]- Source Material
> FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness
>
> Tri Dao, Daniel Y. Fu, Stefano Ermon, Atri Rudra, Christopher Re
> Stanford University, University at Buffalo, 2022
>
> Abstract: Transformers are slow and memory-hungry on long sequences, since the time and memory complexity of self-attention are quadratic in sequence length. Approximate attention methods have attempted to address this problem by trading off model quality to reduce the compute complexity, but often do not achieve wall-clock speedup. We argue that a missing principle is making attention algorithms IO-aware — accounting for reads and writes between levels of GPU memory. We propose FlashAttention, an IO-aware exact attention algorithm that uses tiling to reduce the number of memory reads/writes between GPU high bandwidth memory (HBM) and GPU on-chip SRAM. We analyze the IO complexity of FlashAttention, showing that it requires fewer HBM accesses than standard attention, and is optimal for a range of SRAM sizes.
>
> [Source PDF](fast attention.pdf)
