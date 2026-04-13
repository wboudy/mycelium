---
created: 2026-04-11
description: Koval, Andrews, and Yan show that dedicated modality-specific experts for text and time series within a unified LLM architecture achieve state-of-the-art financial forecasting, demonstrating that converting numerical data to string tokens fails to capture temporal structure
source: financial forecasting.pdf
status: canon
type: source
tags: [financial-forecasting, multimodal, time-series, LLM, modality-experts, NAndrews]
---

## Key Takeaways

This paper addresses a fundamental challenge in multimodal LLMs: text and time series have radically different structures (discrete/compositional vs. continuous/stochastic), and naively converting time series to digit strings loses critical temporal patterns. The solution is modality-specific experts (MSE-ITT) — dedicated components within the LLM that respect each modality's structure while enabling cross-modal reasoning through selective attention.

The financial forecasting setting is ideal for this problem because text (news articles) and time series (stock prices) provide genuinely complementary signals. News describes events (earnings, mergers, product launches) while prices reveal *market reactions* to those events. The interleaved structure — news arriving at irregular intervals between daily price observations — creates a cause-and-effect dynamic that a unified model can learn: how did markets respond to similar news historically?

The cross-modal alignment framework with salient token weighting is the key technical innovation: it learns to align representations across modalities while focusing on the most informative tokens, rather than treating all cross-modal attention equally. The improvements translate to meaningful economic gains in investment simulations, not just metric improvements.

This connects to [[a single transformer with one set of weights can play games caption images chat and control robots by treating all modalities as tokens]] — Gato treats everything as tokens, but this paper shows that approach fails for time series. Modality-specific structure matters when the input types are genuinely different.

## Claims

- **[empirical]** Modality-specific experts achieve state-of-the-art performance on large-scale financial forecasting across a wide variety of unimodal and multimodal baselines (supports)
- **[causal]** Converting time series to string tokens fails because language is discrete and compositional while time series are continuous and governed by temporal dependencies — modality-specific components are needed (supports)
- **[empirical]** Cross-modal alignment with salient token weighting improves multimodal understanding by focusing on the most informative tokens across modalities (supports)
- **[empirical]** Forecasting improvements translate to meaningful economic gains in investment simulations, validating practical utility beyond benchmark metrics (supports)
- **[causal]** Interleaved text and time series provide complementary signals: news provides narrative context and forward-looking indicators while stock prices reveal market reactions as implicit supervision (supports)
- **[empirical]** Interpretability analysis reveals that time series context adds value and reinforces the design of the cross-modal alignment objective (supports)

## External Resources

- [GitHub: rosskoval/mlm_text_ts](https://github.com/rosskoval/mlm_text_ts) — code
- [arXiv:2509.19628](https://arxiv.org/abs/2509.19628) — original paper

## Original Content

> [!quote]- Source Material
> Multimodal Language Models with Modality-Specific Experts for Financial Forecasting from Interleaved Sequences of Text and Time Series
>
> Ross Koval, Nicholas Andrews, Xifeng Yan
> UC Santa Barbara, Johns Hopkins University, AJO Vista, 2025
>
> Abstract: Text and time series data offer complementary views of financial markets. We propose a unified neural architecture that models interleaved sequences using modality-specific experts, allowing the model to learn unique time series patterns while enabling joint reasoning across modalities. We achieve state-of-the-art performance across strong unimodal and multimodal baselines, with improvements translating to meaningful economic gains in investment simulations.
>
> [Source PDF](financial forecasting.pdf)
