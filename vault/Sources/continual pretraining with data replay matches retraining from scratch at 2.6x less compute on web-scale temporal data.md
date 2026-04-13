---
created: 2026-04-11
description: Apple Research introduces TiC-LM, a web-scale benchmark from 114 Common Crawl dumps showing that autoregressive learning rate schedules with fixed-ratio replay of older data match from-scratch retraining at 2.6x less compute for continual LLM pretraining
source: TiC-LM.pdf
status: canon
type: source
tags: [continual-learning, LLM-pretraining, temporal-data, knowledge-cutoff, data-replay, NAndrews]
---

## Key Takeaways

LLMs trained on historical web data become outdated as the world changes, but retraining from scratch on every new data dump is prohibitively expensive. TiC-LM studies this problem at actual web scale using 114 Common Crawl dumps — orders of magnitude larger than previous continual learning benchmarks that focused on single domains like Wikipedia or Twitter.

The key finding is that combining autoregressive (AR) learning rate meta-schedules with a fixed-ratio replay of older data nearly matches the performance of an "Oracle" series that retrains from scratch every two years — at 2.6x less compute. This is the practical answer to knowledge cutoff: you don't need to retrain, you need to replay strategically while training on new data.

The nuance is that the optimal replay balance is domain-dependent. Replay is crucial for general web data (where forgetting degrades perplexity across many implicit domains), but less important for specific domains like Wikipedia or StackExchange. Methods that only modify the optimizer or loss function (without replay) insufficiently prevent forgetting and plateau.

This is directly relevant to the pizza_at_the_pentagon forecasting project, which uses temporally stratified data and needs to evaluate how models handle temporal distribution shifts. TiC-LM's time-stratified evaluations across general CC data and specific domains provide exactly the benchmarking infrastructure needed for studying [[frozen context snapshots solve temporal contamination in LLM forecasting evaluation by enabling rapid backtesting]] at the pretraining level.

## Claims

- **[empirical]** Autoregressive learning rate schedules with fixed-ratio data replay match from-scratch retraining performance at 2.6x less compute on web-scale continual pretraining (supports)
- **[empirical]** Methods that only modify the optimizer or loss function without data replay insufficiently prevent catastrophic forgetting on general web data (supports)
- **[empirical]** The optimal balance between new data incorporation and old data replay differs across domains — replay is crucial for general web data but less important for specific domains like Wikipedia (supports)
- **[causal]** LLMs trained on historical web data inevitably deteriorate on newer data due to knowledge cutoffs, creating a practical need for continual updating at scale (supports)
- **[empirical]** TiC-LM provides 114 Common Crawl dumps spanning 2013-2024, orders of magnitude larger than previous continual language modeling benchmarks (supports)
- **[procedural]** Time-stratified evaluation across general CC data and specific domains (Wikipedia, StackExchange, code documentation) enables measuring both adaptation to new data and retention of old knowledge (neutral)

## External Resources

- [GitHub: apple/ml-tic-lm](https://github.com/apple/ml-tic-lm) — code
- [arXiv:2504.02107](https://arxiv.org/abs/2504.02107) — original paper

## Original Content

> [!quote]- Source Material
> TiC-LM: A Web-Scale Benchmark for Time-Continual LLM Pretraining
>
> Jeffrey Li, Mohammadreza Armandpour, Sachin Mehta, Vaishaal Shankar, Raviteja Vemulapalli, Samy Bengio, Iman Mirzadeh, Hadi Pouransari, Fartash Faghri
> University of Washington, Apple, 2025
>
> Abstract: We introduce a web-scale dataset for time-continual pretraining derived from 114 Common Crawl dumps. We find that autoregressive meta-schedules combined with fixed-ratio replay can achieve comparable loss to retraining from scratch while requiring 2.6x less computation. However, the optimal replay balance differs across domains.
>
> [Source PDF](TiC-LM.pdf)
