---
created: 2026-04-11
description: A forward-only backtesting framework for LLM forecasting that captures frozen web search snapshots paired with prediction market questions, eliminating temporal contamination and staleness confounds while enabling rapid strategy comparison
source: 14662_Forecasting_with_LLMs_A_.pdf
status: canon
type: source
tags: [forecasting, LLM-evaluation, temporal-contamination, backtesting, prediction-markets, NAndrews]
---

## Key Takeaways

This paper attacks three methodological problems that plague LLM forecasting evaluation. Temporal contamination: models tested on events before their training cutoff may be echoing memorized outcomes rather than reasoning about the future. Staleness confound: models trained on more recent data appear superior simply because their training includes fresher information, not better forecasting ability. Evaluation delay: forward-looking benchmarks that track unresolved questions require waiting for real-world outcomes to resolve before measuring accuracy.

The solution is elegant: continuously scrape unresolved questions from prediction markets, freeze the web search context available at scraping time into structured snapshots, and store these paired (question, context) bundles. Once questions resolve, you can rapidly backtest any forecasting strategy against the frozen context — the model sees only what was knowable at the time, not future information. This eliminates temporal contamination by construction and controls for staleness by making all models reason from identical context snapshots.

This is directly relevant to the pizza_at_the_pentagon forecasting project, which faces exactly these evaluation challenges. The frozen snapshot approach connects to the "time-versioned Wikipedia corpus" described in that project's architecture — both are attempting to create temporally honest evaluation environments for forecasting systems.

## Claims

- **[causal]** Standard forecasting benchmarks are vulnerable to temporal contamination because models may have seen outcomes in training data, making it unclear whether they are reasoning or recalling (supports)
- **[causal]** Frozen context snapshots eliminate temporal contamination by construction — models reason from fixed information available at the time of scraping, not from future knowledge (supports)
- **[causal]** The staleness confound makes model comparisons unfair because newer models have fresher training data, which the snapshot approach controls for by providing identical context to all models (supports)
- **[procedural]** The pipeline continuously scrapes unresolved prediction market questions, captures contemporaneous web search results at multiple timepoints, and stores frozen snapshots for future backtesting (neutral)
- **[empirical]** The framework enables rapid identification of effective forecasting strategies through backtesting on resolved questions, substantially accelerating research cycles compared to waiting for real-world resolution (supports)

## External Resources

- [ICLR 2026 submission](https://openreview.net/forum?id=Q5o249Z3Je) — under review

## Original Content

> [!quote]- Source Material
> Forecasting with LLMs: A Dataset for Rapid Backtesting Without Temporal Contamination
>
> Anonymous authors (ICLR 2026 submission, double-blind)
>
> Abstract: The rise of LLMs has made scalable forecasting increasingly feasible, yet evaluating their forecasting ability presents three methodological challenges: temporal contamination, staleness confounds, and evaluation delays. We address these with a forward-only, backtestable evaluation framework built on frozen context snapshots: contemporaneous web search summaries paired with forecasting questions. Our pipeline continuously scrapes unresolved questions from prediction markets and captures supporting context, eliminating temporal contamination and enabling rapid backtesting.
>
> [Source PDF](14662_Forecasting_with_LLMs_A_.pdf)
