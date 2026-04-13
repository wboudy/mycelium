---
created: 2026-04-11
description: LightGTS achieves state-of-the-art time series forecasting with only 1.3M parameters by exploiting periodic inductive biases through Periodical Tokenization and Periodical Parallel Decoding, outperforming models 200-500x larger
source: lightGTS.pdf
status: canon
type: source
tags: [time-series, foundation-models, lightweight, periodicity, efficiency, NAndrews]
---

## Key Takeaways

LightGTS challenges the assumption that time series foundation models need to be massive. While models like Chronos (700M params), MOIRAI (311M), and Time-MoE (453M) achieve good generalization through scale, LightGTS achieves state-of-the-art with only 1.3M parameters — 200-500x smaller — by exploiting an inductive bias that scale-based approaches ignore: periodicity.

The two key techniques are Periodical Tokenization, which extracts consistent periodic patterns across datasets with different scales, and Periodical Parallel Decoding, which leverages historical tokens at the same phase position to improve forecasting. These techniques make the model inherently suited for time series, rather than relying on generic transformer capacity to learn periodicity from data.

State-of-the-art on 9 benchmarks in both zero-shot and full-shot settings with dramatically better efficiency. This is the [[IO-aware tiling makes exact attention faster than approximate methods by avoiding HBM bottlenecks]] of time series: working in the right space (periodic decomposition vs. raw values) matters more than brute-force scaling.

## Claims

- **[empirical]** LightGTS with 1.3M parameters achieves state-of-the-art forecasting on 9 benchmarks, outperforming models with 67M-700M parameters (supports)
- **[causal]** Periodical Tokenization extracts consistent periodic patterns across datasets with varying scales, providing a domain-appropriate inductive bias that generic transformers must learn from data (supports)
- **[causal]** Periodical Parallel Decoding leverages historical tokens at the same phase position, exploiting the repetitive structure inherent in time series for more accurate predictions (supports)
- **[empirical]** LightGTS achieves comparable or better performance in both zero-shot and full-shot settings with much better computational efficiency (supports)

## External Resources

- [arXiv:2506.06005](https://arxiv.org/abs/2506.06005) — original paper

## Original Content

> [!quote]- Source Material
> LightGTS: A Lightweight General Time Series Forecasting Model
>
> Yihang Wang, Yuying Qiu, Peng Chen, Yang Shu, Zhongwen Rao, Lujia Pan, Bin Yang, Chenjuan Guo, 2025
>
> Abstract: We introduce LightGTS, a lightweight general time series forecasting model using Periodical Tokenization and Periodical Parallel Decoding. With only 1.3M parameters, it achieves state-of-the-art on 9 benchmarks in both zero-shot and full-shot settings with much better efficiency than existing foundation models.
>
> [Source PDF](lightGTS.pdf)
