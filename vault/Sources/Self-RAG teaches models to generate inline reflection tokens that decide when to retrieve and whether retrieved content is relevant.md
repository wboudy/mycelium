---
created: 2026-04-11
description: Self-RAG trains LLMs to generate special reflection tokens inline during generation that control when to retrieve, whether retrieved passages are relevant, and whether the generated output is supported — achieving ICLR 2024 Oral (top 1%)
source: https://arxiv.org/abs/2310.08560
status: canon
type: source
tags: [RAG, retrieval, self-evaluation, reflection-tokens, ICLR-2024]
---

## Key Takeaways

Standard RAG retrieves indiscriminately — it always retrieves, regardless of whether retrieval is needed, and uses whatever comes back without evaluating relevance. Self-RAG fixes both problems by training the model to generate special reflection tokens during generation: [Retrieve] decides whether to trigger retrieval, [IsRel] evaluates whether retrieved passages are relevant, [IsSup] checks whether the generation is supported by the passages, and [IsUse] scores overall utility.

These tokens are generated inline as part of the normal generation process — no separate verifier or reranker needed. The model learns to self-evaluate its own retrieval needs and output quality. This is the [[replacing token-level chain-of-thought with discrete state machine actions improves retrieval while cutting tokens by 74 percent]] approach applied to retrieval: structured actions (retrieve/don't, relevant/not) replace unstructured generation.

Directly relevant to the pizza_at_the_pentagon forecasting project, which must decide when to retrieve evidence and how to evaluate its relevance to the forecasting question. The project's retriever and auditor agents perform these functions, but Self-RAG shows they can be unified into a single model.

## Claims

- **[empirical]** Self-RAG achieves ICLR 2024 Oral acceptance (top 1%), demonstrating significant improvement over standard RAG on knowledge-intensive tasks (supports)
- **[causal]** Training models to generate inline reflection tokens that control retrieval and evaluate relevance eliminates the need for separate retriever, reranker, and verifier components (supports)
- **[causal]** Indiscriminate retrieval hurts performance because irrelevant passages dilute attention and introduce noise — selective retrieval via learned tokens avoids this (supports)
- **[definition]** Self-RAG generates special tokens inline: [Retrieve] for retrieval decisions, [IsRel] for relevance evaluation, [IsSup] for support checking, and [IsUse] for utility scoring (neutral)

## External Resources

- [arXiv:2310.08560](https://arxiv.org/abs/2310.08560) — original paper (ICLR 2024 Oral)

## Original Content

> [!quote]- Source Material
> Self-RAG: Learning to Retrieve, Generate, and Critique Through Self-Reflection
>
> Akari Asai, Zeqiu Wu, et al.
> ICLR 2024 Oral (Top 1%)
>
> Summary: Self-RAG trains LLMs to generate inline reflection tokens that decide when to retrieve, evaluate relevance of retrieved content, and check whether generation is supported. Unifies retrieval, generation, and evaluation in a single model.
>
> [arXiv:2310.08560](https://arxiv.org/abs/2310.08560)
