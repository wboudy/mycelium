---
created: 2026-04-11
description: Koval, Andrews, and Yan show that historical context significantly improves LLM-based financial news impact prediction, and that compressing context via a small LM into prefix summary embeddings outperforms simply concatenating full articles into long contexts
source: financial_impact.pdf
status: canon
type: source
tags: [financial-forecasting, context-compression, news-analysis, LLM, market-impact, NAndrews]
---

## Key Takeaways

Financial news articles are not self-contained — interpreting their market impact requires understanding the historical context of prior coverage. An earnings report is bullish or bearish depending on whether it exceeds or misses expectations set by previous articles. A merger announcement has different impact depending on prior rumors and regulatory signals. This paper shows that providing this historical context consistently and significantly improves market impact prediction across methods and time horizons.

The practical challenge is how to provide context efficiently. Simply concatenating all historical articles into a long context is computationally expensive (near-quadratic complexity) and empirically underperforms — LLMs exhibit positional biases and ignore content "lost in the middle." The solution is Prefix Summary Context (PSC): a small LM compresses historical articles into concise summary embeddings, which are then aligned with the large LM's representation space via Cross-Model Alignment and prepended as prefix tokens. This gives the large LM access to historical background without the computational cost of processing full articles.

This connects to [[modality-specific experts outperform treating time series as text tokens for financial forecasting with interleaved data]] — the same research line, where the first paper tackles multimodal integration and this one tackles temporal context. Both show that naive approaches (string conversion, full concatenation) fail and that architecturally informed solutions are needed.

The improvements translate to substantial gains in simulated investment performance, grounding the work in practical value beyond benchmark metrics.

## Claims

- **[empirical]** Historical news context provides consistent and significant improvement in financial market impact prediction across methods and time horizons (supports)
- **[empirical]** Compressed context summaries outperform raw long-context concatenation because LLMs suffer from positional biases and content dilution in long sequences (supports)
- **[causal]** Financial news interpretation requires understanding novelty relative to historical coverage — the same event can be bullish or bearish depending on prior expectations set by earlier articles (supports)
- **[procedural]** Prefix Summary Context uses a small LM to compress historical articles into summary embeddings, aligns them with the large LM's representation space, and prepends them as prefix tokens (neutral)
- **[empirical]** Improvements in prediction accuracy translate to substantial gains in simulated investment performance (supports)
- **[causal]** Near-quadratic computational complexity of self-attention makes full-context concatenation impractical for incorporating many historical articles (supports)

## External Resources

- [GitHub: rosskoval/calm_fin_news](https://github.com/rosskoval/calm_fin_news) — code
- [arXiv:2509.12519](https://arxiv.org/abs/2509.12519) — original paper

## Original Content

> [!quote]- Source Material
> Context-Aware Language Models for Forecasting Market Impact from Sequences of Financial News
>
> Ross Koval, Nicholas Andrews, Xifeng Yan
> UC Santa Barbara, Johns Hopkins University, AJO Vista, 2025
>
> Abstract: Financial news plays a critical role in the information diffusion process in financial markets. However, each article often requires broader historical context for accurate interpretation. We find that historical context provides consistent and significant improvement in performance. We propose an efficient contextualization method using a small LM to encode historical context into summary embeddings aligned with the large model's representation space. We demonstrate that the value of historical context translates to substantial improvements in simulated investment performance.
>
> [Source PDF](financial_impact.pdf)
