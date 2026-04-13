---
created: 2026-04-11
description: Seq2Event applies transformer and RNN architectures to predict next match events in soccer from prior event sequences, enabling creation of context-aware metrics like possession utility that correlate 0.91 with xG
source: KDD22_paper_CReady_v20220606.pdf
status: canon
type: source
tags: [sports-analytics, soccer, transformers, event-prediction, sequence-modeling, NAndrews]
---

## Key Takeaways

Seq2Event treats soccer match events as a language — each action (pass, shot, tackle, cross) is a token in a sequence, and transformer/RNN architectures predict the next event given the prior context. This is a direct application of the NLP paradigm to sports: if [[reinforcement learning can be reduced to sequence modeling by conditioning a transformer on desired returns]] works for control, the same reframing works for sports event prediction.

The practical contribution is metric creation from a general-purpose context-aware model. The "poss-util" metric summarizes the expected probability of key attacking events (shots, crosses) during each possession, providing a continuous measure of possession quality. This correlates r=0.91 with the popular xG (expected goals) metric over 190 matches, validating that the model captures meaningful game dynamics.

The deeper insight is that soccer's open and dynamic play, with simultaneous multi-scale temporal patterns and high spatial freedom, has traditionally been analyzed by decomposing the game into isolated problems. Seq2Event offers a holistic approach where the model learns these patterns end-to-end from raw event sequences, without pre-determined aggregation or hand-crafted features.

## Claims

- **[empirical]** Transformer-based Seq2Event model outperforms baseline statistical methods for next-event prediction in soccer using sequential match event data (supports)
- **[empirical]** The poss-util metric derived from Seq2Event correlates r=0.91 with xG across 190 matches, validating that the model captures meaningful attacking dynamics (supports)
- **[causal]** Treating match events as a sequential language allows transformer architectures to learn context-dependent patterns that sequence-invariant methods (RF, MLP, CNN) miss (supports)
- **[procedural]** General-purpose context-aware event prediction models can generate novel domain-specific metrics without requiring hand-crafted feature engineering (supports)
- **[normative]** Sports with stronger sequentiality (like rugby union) may benefit even more from this approach than soccer, which has more open play dynamics (supports)

## External Resources

- [DOI: 10.1145/3534678.3539138](https://doi.org/10.1145/3534678.3539138) — KDD 2022 proceedings

## Original Content

> [!quote]- Source Material
> Seq2Event: Learning the Language of Soccer using Transformer-based Match Event Prediction
>
> Ian Simpson, Ryan J. Beal, Duncan Locke, Timothy J. Norman
> University of Southampton, Rugby Football Union, KDD 2022
>
> Abstract: We propose the Seq2Event model, in which the next match event is predicted given prior match events and context using Transformer or RNN components. We demonstrate metric creation using a general purpose context-aware model, developing the poss-util metric that correlates r=0.91 with xG over 190 matches.
>
> [Source PDF](KDD22_paper_CReady_v20220606.pdf)
