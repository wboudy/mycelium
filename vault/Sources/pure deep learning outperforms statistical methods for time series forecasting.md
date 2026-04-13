---
created: 2026-04-09
description: N-BEATS demonstrates that a pure deep learning architecture with no time-series-specific components beats established statistical forecasting methods on M3, M4, and TOURISM datasets
source: https://arxiv.org/pdf/1905.10437
status: canon
type: source
tags: [deep-learning, time-series, forecasting, N-BEATS, interpretability]
---

## Key Takeaways

N-BEATS challenges the prevailing belief that deep learning cannot beat classical statistical methods for time series forecasting. The architecture uses nothing but fully-connected layers with residual connections — no recurrence, no convolutions, no attention, no time-series-specific feature engineering. Despite this simplicity, it achieves state-of-the-art on M3, M4, and TOURISM competition datasets, improving forecast accuracy by 11% over the statistical benchmark and 3% over the M4 competition winner (which was a hand-crafted hybrid of neural networks and Holt-Winters).

The doubly residual stacking principle is the key architectural insight. Each block predicts both a "backcast" (its best reconstruction of the input) and a "forecast" (its contribution to the output). The residual from the backcast passes to the next block, so each subsequent block works on what prior blocks couldn't explain. This is analogous to boosting but within a single differentiable architecture.

The interpretable configuration constrains basis functions to trend and seasonality components, producing decompositions similar to classical STL decomposition but learned end-to-end. This achieves the interpretability of traditional methods without sacrificing much accuracy — a rare combination in deep learning.

The paper's strongest rhetorical move is using the forecasting community's own competition benchmarks to make the case. By beating methods on M3, M4, and TOURISM — datasets the statistical community curated specifically to test forecasting — they remove the objection that deep learning only works on cherry-picked problems.

## Claims

- **[empirical]** Pure deep learning with no time-series-specific components outperforms established statistical methods on M3, M4, and TOURISM competition datasets (supports)
- **[empirical]** N-BEATS improves forecast accuracy by 11% over the statistical benchmark and 3% over the M4 competition winner on the M4 dataset (supports)
- **[empirical]** The six pure ML methods submitted to M4 competition ranked 23rd, 37th, 38th, 48th, 54th, and 57th out of 60 entries — prior to N-BEATS (supports)
- **[causal]** Doubly residual stacking enables very deep architectures by allowing each block to focus on the unexplained residual from prior blocks (supports)
- **[empirical]** The interpretable N-BEATS configuration using trend and seasonality basis functions achieves accuracy close to the generic configuration while producing human-readable decompositions (supports)
- **[definition]** N-BEATS stands for Neural Basis Expansion Analysis for Interpretable Time Series Forecasting (neutral)
- **[empirical]** The M4 competition winner relied heavily on a Holt-Winters statistical component, making it a hybrid rather than pure deep learning approach (supports)
- **[causal]** Constraining basis functions to polynomial (trend) and harmonic (seasonality) forces the network to decompose forecasts into interpretable components without explicit supervision (supports)
- **[procedural]** N-BEATS uses an ensemble of models with different lookback window lengths and loss functions to achieve robust performance across diverse time series types (supports)

## External Resources

- [N-BEATS code repository](https://github.com/ServiceNow/N-BEATS) — Official implementation
- [M4 Competition](https://www.m4.unic.ac.cy/) — The forecasting competition benchmark used for evaluation
- [arXiv paper](https://arxiv.org/abs/1905.10437) — Full paper (published at ICLR 2020)

## Original Content

> [!quote]- Source Material
> Published as a conference paper at ICLR 2020
>
> N-BEATS: Neural Basis Expansion Analysis for Interpretable Time Series Forecasting
>
> Boris N. Oreshkin, Dmitri Carpov, Nicolas Chapados, Yoshua Bengio
> Element AI / Mila
>
> We focus on solving the univariate times series point forecasting problem using deep learning. We propose a deep neural architecture based on backward and forward residual links and a very deep stack of fully-connected layers. The architecture has a number of desirable properties, being interpretable, applicable without modification to a wide array of target domains, and fast to train. We test the proposed architecture on several well-known datasets, including M3, M4 and TOURISM competition datasets containing time series from diverse domains. We demonstrate state-of-the-art performance for two configurations of N-BEATS for all the datasets, improving forecast accuracy by 11% over a statistical benchmark and by 3% over last year's winner of the M4 competition, a domain-adjusted hand-crafted hybrid between neural network and statistical time series models. The first configuration of our model does not employ any time-series-specific components and its performance on heterogeneous datasets strongly suggests that, contrarily to received wisdom, deep learning primitives such as residual blocks are by themselves sufficient to solve a wide range of forecasting problems. Finally, we demonstrate how the proposed architecture can be augmented to provide outputs that are interpretable without considerable loss in accuracy.
>
> [Original paper](https://arxiv.org/pdf/1905.10437)
