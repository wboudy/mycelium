---
created: 2026-04-11
description: Temporally grounded analysis of LLM reasoning during the 2026 Middle East conflict reveals models attend to underlying incentives and material constraints rather than surface rhetoric, but perform unevenly across economic vs politically ambiguous domains
source: fog of war.pdf
status: canon
type: source
tags: [geopolitical-forecasting, LLM-reasoning, temporal-analysis, conflict, fog-of-war]
---

## Key Takeaways

This paper creates the first temporally grounded analysis of LLM reasoning during an *ongoing* geopolitical conflict — the 2026 Middle East crisis — using events after model training cutoffs to avoid data leakage. The design is clever: 11 critical temporal nodes, 42 verifiable questions, and 5 exploratory questions, where models must reason only from information publicly available at each moment.

Three key findings emerge. First, LLMs demonstrate surprisingly strong strategic reasoning — they move beyond surface political rhetoric to analyze underlying incentives, deterrence pressures, and material constraints. This suggests models have internalized geopolitical reasoning patterns, not just memorized event sequences. Second, this capability is domain-dependent: models are more reliable when reasoning about economic and logistic constraints (structured, quantifiable) than in politically ambiguous multi-actor environments (where motivations are opaque and alliances shift). Third, model narratives evolve over the temporal nodes — shifting from early expectations of rapid containment to systemic accounts of regional entrenchment and attritional de-escalation.

This connects to [[frozen context snapshots solve temporal contamination in LLM forecasting evaluation by enabling rapid backtesting]] — both papers grapple with the temporal contamination problem, but this one uses post-cutoff events as the natural solution, while the other creates frozen snapshots. The uneven domain performance connects to [[LLMs consistently resist incorporating external feedback even when it is near-perfect and they claim to understand it]] — models have confidence-dependent blind spots that affect reasoning quality.

## Claims

- **[empirical]** LLMs demonstrate strong strategic reasoning about ongoing conflicts, attending to underlying incentives, deterrence pressures, and material constraints rather than surface political rhetoric (supports)
- **[empirical]** LLM reasoning capability is uneven across domains — models are more reliable in economically and logistically structured settings than in politically ambiguous multi-actor environments (supports)
- **[empirical]** Model narratives evolve over temporal nodes, shifting from expectations of rapid containment to systemic accounts of regional entrenchment (supports)
- **[causal]** Using events after model training cutoffs substantially mitigates training-data leakage concerns, creating a setting suited for studying genuine reasoning rather than memorization (supports)
- **[procedural]** The temporally grounded design constrains models to reason from information available at each temporal node, simulating real-time analysis under the fog of war (neutral)
- **[normative]** The work serves as an archival snapshot of model reasoning during an unfolding crisis, enabling future studies without hindsight bias (supports)

## External Resources

- [Project page](https://www.war-forecast-arena.com) — interactive results
- [arXiv:2603.16642](https://arxiv.org/abs/2603.16642) — original paper

## Original Content

> [!quote]- Source Material
> When AI Navigates the Fog of War
>
> Ming Li, Xirui Li, Tianyi Zhou
> MBZUAI, University of Maryland, 2026
>
> Abstract: Can AI reason about and forecast the trajectory of an ongoing war? We address this through a temporally grounded case study of the 2026 Middle East conflict, which unfolded after the training cutoff of current frontier models. We construct 11 critical temporal nodes and 42 verifiable questions. Our analysis reveals that LLMs show strong strategic reasoning, moving beyond surface rhetoric to underlying incentives, but this capability is uneven across domains and evolves over time.
>
> [Source PDF](fog of war.pdf)
