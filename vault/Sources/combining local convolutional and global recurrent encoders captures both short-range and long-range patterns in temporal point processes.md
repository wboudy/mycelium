---
created: 2026-04-11
description: A novel temporal point process model combines continuous-time convolutional neural networks for local event context with RNNs for global context, improving probabilistic sequential modeling and event prediction accuracy
source: tpp.pdf
status: canon
type: source
tags: [temporal-point-processes, event-prediction, convolution, continuous-time, NAndrews]
---

## Key Takeaways

Temporal point processes (TPPs) model discrete events along a continuous timeline — predicting both when the next event will occur and what type it will be. Existing neural TPP models encode event history using RNNs or self-attention for global context, but ignore local context — the patterns in nearby events that influence what happens next. This paper introduces the first convolutional approach to TPP modeling, combining a continuous-time convolutional encoder for local patterns with an RNN for global context.

The challenge is that standard CNNs operate in discrete time (fixed grid), while TPP events are irregularly spaced on a continuous timeline. The solution adapts convolution to continuous time, enabling local pattern extraction from non-uniformly distributed events. The framework is flexible and scalable, handling large datasets with long sequences and complex latent patterns.

This is relevant to the pizza_at_the_pentagon forecasting project, which models event sequences across multiple domains. The distinction between local context (recent event clusters) and global context (long-range dependencies) maps directly to [[historical news context consistently improves financial market impact prediction but compressed summaries outperform raw long contexts]] — both papers show that different temporal scales require different architectural treatment.

## Claims

- **[empirical]** Combining local convolutional and global recurrent event encoders improves both probabilistic sequential modeling and event prediction accuracy over models using only global context (supports)
- **[causal]** Local event contexts — patterns in nearby events — play an important role in event occurrence but have been largely ignored by existing TPP models that focus only on global history encoding (supports)
- **[causal]** Standard CNNs cannot be applied to TPP modeling because they assume discrete, uniformly-spaced time steps, while TPP events are irregularly distributed on a continuous timeline (supports)
- **[definition]** Temporal point processes describe discrete event occurrences along a continuous timeline, where each event has a mark (type) and arrival timestamp, and intervals between events are non-uniform (neutral)

## External Resources

- [arXiv:2306.14072](https://arxiv.org/abs/2306.14072) — original paper

## Original Content

> [!quote]- Source Material
> Intensity-free Convolutional Temporal Point Process: Incorporating Local and Global Event Contexts
>
> Wang-Tao Zhou, Zhao Kang, Ling Tian, Yi Su
> University of Electronic Science and Technology of China, 2023
>
> Abstract: We propose a novel TPP modelling approach that combines local and global contexts by integrating a continuous-time convolutional event encoder with an RNN. The framework is flexible and scalable, and experimental results show improved probabilistic sequential modeling and event prediction accuracy.
>
> [Source PDF](tpp.pdf)
