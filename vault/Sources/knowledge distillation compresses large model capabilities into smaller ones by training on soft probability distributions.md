---
created: 2026-04-11
description: Quanta Magazine explainer on how distillation transfers knowledge from large teacher models to small student models by training on soft probability distributions rather than hard labels, making AI cheaper and more deployable
source: https://www.quantamagazine.org/how-distillation-makes-ai-models-smaller-and-cheaper-20250718/
status: canon
type: source
tags: [distillation, model-compression, training, efficiency, accessible-explainer]
---

## Key Takeaways

Knowledge distillation is one of the most important practical techniques in modern AI: train a large expensive model (teacher), then train a small cheap model (student) to mimic the teacher's behavior. The key insight is that the student trains on the teacher's soft probability distributions (which encode dark knowledge about inter-class relationships) rather than hard one-hot labels.

When a teacher model assigns 70% to "cat" and 20% to "lynx" and 10% to "dog," those soft probabilities carry information that hard labels don't — the teacher is telling the student that cats and lynxes are more similar to each other than to dogs. This "dark knowledge" in the probability distribution provides much richer training signal per example.

This directly connects to [[pure reinforcement learning without human demonstrations produces superior reasoning in LLMs]] — DeepSeek-R1 uses distillation to transfer reasoning capabilities from its large RL-trained model to smaller 1.5B-70B models that retain strong reasoning despite being orders of magnitude smaller. It's also the mechanism behind [[running diffusion in a learned latent space makes high-resolution image synthesis accessible on consumer hardware]] — making expensive capabilities accessible through compression.

## Claims

- **[causal]** Training on soft probability distributions from a teacher model provides richer learning signal than hard labels because the distribution encodes inter-class relationships and model uncertainty (supports)
- **[empirical]** Distilled student models can achieve performance close to much larger teacher models at a fraction of the compute cost (supports)
- **[causal]** "Dark knowledge" in the teacher's probability distribution — the relative probabilities assigned to non-target classes — carries information about similarity structure that hard labels discard (supports)
- **[procedural]** The temperature parameter in distillation controls how soft the probability distribution is: higher temperature spreads probability more evenly, revealing more dark knowledge at the cost of signal strength (neutral)

## External Resources

- [Quanta Magazine article](https://www.quantamagazine.org/how-distillation-makes-ai-models-smaller-and-cheaper-20250718/) — accessible explainer

## Original Content

> [!quote]- Source Material
> How Distillation Makes AI Models Smaller and Cheaper — Quanta Magazine
>
> Explainer article on knowledge distillation: transferring capabilities from large teacher models to small student models by training on soft probability distributions that encode "dark knowledge" about inter-class relationships.
>
> [Quanta Magazine](https://www.quantamagazine.org/how-distillation-makes-ai-models-smaller-and-cheaper-20250718/)
