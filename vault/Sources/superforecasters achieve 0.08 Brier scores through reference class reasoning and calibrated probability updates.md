---
created: 2026-04-11
description: Tetlock and Gardner show that a small group of forecasters consistently outperform experts and prediction markets by combining outside-view base rates with inside-view analysis, updating frequently, and maintaining calibrated uncertainty
source: https://en.wikipedia.org/wiki/Superforecasting
status: canon
type: source
tags: [forecasting, calibration, superforecasting, Tetlock, prediction, decision-making]
---

## Key Takeaways

Superforecasting is the foundational text for evidence-based probability estimation. Tetlock's research through the Good Judgment Project identified a group of "superforecasters" who consistently outperformed intelligence analysts with access to classified information, prediction markets, and domain experts. Their Brier scores (~0.08) significantly beat average forecasters (~0.20).

The key techniques are: (1) reference class reasoning (outside view) — start with base rates for similar events before incorporating specific information; (2) granular probability updates — make small, frequent adjustments rather than large jumps; (3) distinguishing signal from noise — focus on the most diagnostic evidence; (4) avoiding cognitive biases — especially anchoring, confirmation bias, and overconfidence; (5) active open-mindedness — actively seeking disconfirming evidence.

This is the intellectual foundation of the pizza_at_the_pentagon forecasting project. The project's "Forecasting Delta" training objective — scoring trajectories by information gain over the base model while penalizing superstitious reasoning — directly operationalizes Tetlock's principles. [[RAG-based forecasting systems approach human-level calibration by retrieving and synthesizing evidence before predicting]] shows the AI version of these techniques beginning to approach human superforecaster performance.

## Claims

- **[empirical]** Superforecasters achieve ~0.08 Brier scores, significantly outperforming average forecasters (~0.20), intelligence analysts with classified access, and prediction markets (supports)
- **[causal]** Reference class reasoning — starting with outside-view base rates before incorporating specific information — is a key technique that prevents anchoring on salient but non-diagnostic details (supports)
- **[causal]** Frequent, granular probability updates produce better calibration than infrequent large adjustments because they force continuous engagement with new evidence (supports)
- **[empirical]** Superforecasting ability is trainable — it's not innate talent but learnable skills including active open-mindedness and bias avoidance (supports)
- **[causal]** Overconfidence is the most common and damaging forecasting bias — superforecasters maintain calibrated uncertainty even on topics where they have strong opinions (supports)

## External Resources

- [Good Judgment Project](https://goodjudgment.com/) — Tetlock's forecasting research organization
- [Superforecasting (book)](https://en.wikipedia.org/wiki/Superforecasting) — Crown Publishing, 2015

## Original Content

> [!quote]- Source Material
> Superforecasting: The Art and Science of Prediction
>
> Philip E. Tetlock, Dan Gardner
> Crown Publishing, 2015
>
> Summary: Based on the Good Judgment Project, this book identifies the techniques that enable "superforecasters" to consistently outperform experts, prediction markets, and intelligence analysts: reference class reasoning, granular probability updates, active open-mindedness, and calibrated uncertainty.
>
> [Wikipedia](https://en.wikipedia.org/wiki/Superforecasting)
