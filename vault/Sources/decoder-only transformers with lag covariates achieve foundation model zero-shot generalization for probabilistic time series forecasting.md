---
created: 2026-04-11
description: Lag-Llama is a decoder-only transformer foundation model for univariate probabilistic time series forecasting that uses lags as covariates and demonstrates strong zero-shot generalization across domains, achieving state-of-the-art with minimal fine-tuning
source: lagllama.pdf
status: canon
type: source
tags: [time-series, foundation-models, probabilistic-forecasting, zero-shot, transformers, NAndrews]
---

## Key Takeaways

Lag-Llama brings the foundation model paradigm to probabilistic time series forecasting. The architecture is a decoder-only transformer (Llama-style) that uses time series lags as covariates — past values at specific offsets serve as features, which is a natural analog to how autoregressive language models attend to prior tokens. This design choice makes the model inherently probabilistic: it generates full predictive distributions, not just point forecasts, giving decision-makers uncertainty quantification for downstream planning.

The model is pretrained on a large corpus of diverse time series data from multiple domains, then evaluated on completely unseen datasets. Zero-shot performance is competitive with domain-specific models, and with even small amounts of fine-tuning data, Lag-Llama achieves state-of-the-art — emerging as the best general-purpose model on average across tested datasets.

This directly complements [[pretrained time series foundation models extend from univariate to multivariate and covariate-informed forecasting via group attention]] (Chronos-2) — Lag-Llama focuses on univariate probabilistic forecasting with lag-based covariates, while Chronos-2 extends to multivariate and external covariates. Together they represent the evolution of time series foundation models from single-domain to universal.

## Claims

- **[empirical]** Lag-Llama demonstrates strong zero-shot generalization on downstream datasets across domains, competitive with dataset-specific models (supports)
- **[empirical]** Fine-tuning on small fractions of unseen datasets yields state-of-the-art performance, outperforming prior deep learning approaches on average (supports)
- **[causal]** Using lags as covariates in a decoder-only transformer naturally captures autoregressive temporal dependencies and enables probabilistic output distributions (supports)
- **[causal]** Pretraining on diverse time series data from multiple domains enables cross-domain transfer, unlike dataset-specific models that must be retrained per use case (supports)
- **[definition]** Lag-Llama is a general-purpose foundation model for univariate probabilistic time series forecasting based on a decoder-only transformer pretrained on diverse multi-domain time series data (neutral)

## External Resources

- [arXiv:2310.08278](https://arxiv.org/abs/2310.08278) — original paper

## Original Content

> [!quote]- Source Material
> Lag-Llama: Towards Foundation Models for Probabilistic Time Series Forecasting
>
> Kashif Rasul, Arjun Ashok, et al.
> Morgan Stanley, ServiceNow Research, Mila, 2024
>
> Abstract: We present Lag-Llama, a general-purpose foundation model for univariate probabilistic time series forecasting based on a decoder-only transformer using lags as covariates. Pretrained on diverse time series data, it demonstrates strong zero-shot generalization and achieves state-of-the-art with minimal fine-tuning.
>
> [Source PDF](lagllama.pdf)
