---
created: 2026-04-11
description: Bengio et al. show that training neural networks with progressively harder examples improves generalization and convergence, formalizing curriculum learning as a continuation method for non-convex optimization
source: 2009_curriculum_icml.pdf
status: canon
type: source
tags: [machine-learning, training-strategy, optimization, deep-learning]
---

## Key Takeaways

Curriculum learning formalizes the intuition that presenting training examples in a meaningful order — easy to hard — yields better generalization than random presentation. The paper connects this to continuation methods from global optimization, where you first optimize a smoothed version of the objective and gradually transition to the true (non-convex) criterion. This dual framing is powerful: curriculum learning both speeds convergence and acts as a regularizer, finding better local minima in the loss landscape.

The key theoretical contribution is defining a curriculum as a sequence of training distributions with monotonically increasing entropy and example weights, eventually converging to the full training distribution. This means a curriculum progressively expands the diversity of examples while never discarding previously introduced ones.

Experimentally, even a two-step curriculum (easy subset then full set) produced statistically significant improvements on vision and language tasks, including shape recognition and language modeling. The results parallel the benefits of unsupervised pre-training — both guide optimization toward better basins of attraction in parameter space.

## Claims

- **[empirical]** Training with a curriculum strategy (easy-to-hard example ordering) produces significantly better generalization than random ordering on non-convex objectives (supports)
- **[causal]** Curriculum learning acts as a continuation method, guiding optimization through progressively less-smoothed versions of the loss landscape toward better local minima (supports)
- **[empirical]** A simple two-step curriculum (clean subset then full training set) is sufficient to achieve measurable generalization improvements (supports)
- **[empirical]** Curriculum learning functions as a regularizer — benefits are most pronounced on test error rather than training error (supports)
- **[causal]** Starting with cleaner/easier examples helps convergence because noisy examples near the decision boundary slow down gradient-based optimization (supports)
- **[definition]** A curriculum is a sequence of training distributions with monotonically increasing entropy, where example weights increase monotonically and converge to uniform weighting over the full dataset (neutral)
- **[empirical]** Curriculum learning on language modeling with Wikipedia data improved perplexity by training first on shorter/simpler sentences sorted by vocabulary frequency (supports)

## External Resources

- [Continuation Methods in Optimization](https://en.wikipedia.org/wiki/Continuation_method) — the global optimization framework that curriculum learning maps onto
- [Deep Learning Pre-training (Hinton et al., 2006)](https://www.cs.toronto.edu/~hinton/absps/fastnc.pdf) — greedy layer-wise pre-training, which curriculum learning parallels

## Original Content

> [!quote]- Source Material
> Curriculum Learning
>
> Yoshua Bengio, Jerome Louradour, Ronan Collobert, Jason Weston
> ICML 2009
>
> Abstract: Humans and animals learn much better when the examples are not randomly presented but organized in a meaningful order which illustrates gradually more concepts, and gradually more complex ones. Here, we formalize such training strategies in the context of machine learning, and call them "curriculum learning". In the context of recent research studying the difficulty of training in the presence of non-convex training criteria (for deep deterministic and stochastic neural networks), we explore curriculum learning in various set-ups. The experiments show that significant improvements in generalization can be achieved. We hypothesize that curriculum learning has both an effect on the speed of convergence of the training process to a minimum and, in the case of non-convex criteria, on the quality of the local minima obtained: curriculum learning can be seen as a particular form of continuation method (a general strategy for global optimization of non-convex functions).
>
> [Source PDF](2009_curriculum_icml.pdf)
