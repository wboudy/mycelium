---
created: 2026-04-11
description: Chronos-2 extends pretrained time series models from univariate to universal forecasting through group attention that enables in-context learning across related series, variates, and covariates without task-specific training
source: chronos2.pdf
status: canon
type: source
tags: [time-series, foundation-models, forecasting, multivariate, in-context-learning, NAndrews]
---

## Key Takeaways

Chronos-2 addresses the critical limitation of pretrained time series models: they only handle univariate forecasting. Real-world forecasting requires multivariate data (co-evolving metrics like CPU/memory/storage) and covariates (external factors like promotions driving retail demand). Chronos-2 handles all three in zero-shot mode through a single pretrained model.

The key architectural innovation is group attention — a mechanism that enables in-context learning by efficiently sharing information across multiple time series within a group. A "group" can represent related series, variates of a multivariate series, or targets and covariates. This allows the model to learn cross-series relationships from context rather than requiring explicit multivariate training data. Training uses synthetic datasets that impose diverse multivariate structures on univariate series, teaching the model to discover relationships without real multivariate datasets.

State-of-the-art across three benchmarks (fev-bench, GIFT-Eval, Chronos Benchmark II), with particularly large margins on covariate-informed tasks. This connects to [[modality-specific experts outperform treating time series as text tokens for financial forecasting with interleaved data]] — both recognize that time series requires dedicated modeling, but Chronos-2 achieves it through a foundation model approach rather than task-specific architecture.

## Claims

- **[empirical]** Chronos-2 achieves state-of-the-art zero-shot performance across univariate, multivariate, and covariate-informed forecasting on three comprehensive benchmarks (supports)
- **[causal]** Group attention enables in-context learning across related time series by efficiently sharing information within a group, allowing the model to discover cross-series relationships from context (supports)
- **[empirical]** Training on synthetic datasets with imposed multivariate structures enables general-purpose multivariate capabilities without requiring real multivariate training data (supports)
- **[empirical]** On covariate-informed tasks, Chronos-2 consistently outperforms baselines by wide margins, demonstrating practical utility in energy and retail domains (supports)
- **[causal]** Pretrained time series models shift the paradigm from training per-dataset/per-series to inference-only forecasting that eliminates task-specific training (supports)

## External Resources

- [GitHub: amazon-science/chronos-forecasting](https://github.com/amazon-science/chronos-forecasting) — code
- [arXiv:2510.15821](https://arxiv.org/abs/2510.15821) — original paper

## Original Content

> [!quote]- Source Material
> Chronos-2: From Univariate to Universal Forecasting
>
> Abdul Fatir Ansari, Oleksandr Shchur, Jaris Kuken, et al.
> Amazon Web Services, 2025
>
> Abstract: We present Chronos-2, a pretrained model capable of handling univariate, multivariate, and covariate-informed forecasting in zero-shot. It employs group attention for in-context learning through information sharing across multiple time series within a group. State-of-the-art across three comprehensive benchmarks with substantial improvements on covariate-informed tasks.
>
> [Source PDF](chronos2.pdf)
