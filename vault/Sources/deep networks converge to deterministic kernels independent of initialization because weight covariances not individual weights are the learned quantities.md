---
created: 2026-04-11
description: Guth, Menard, Rochette, and Mallat prove that deep networks define deterministic hierarchical kernels in the infinite-width limit via the rainbow model, showing that weight covariance matrices (not individual weights) are the true learned quantities
source: deep network black boxes.pdf
status: canon
type: source
tags: [deep-learning-theory, kernels, random-features, representation-learning, interpretability]
---

## Key Takeaways

This paper addresses one of the deepest questions in deep learning: what exactly do neural networks learn, and does the answer depend on random initialization? The empirical observation is that kernels defined by hidden activations (the inner products of representations) are remarkably similar across different training runs of the same architecture — even though the individual weights are completely different.

The rainbow model explains this by extending the random feature framework from shallow to deep networks. At each layer, the network weights are modeled as random samples from a learned distribution. In the infinite-width limit, the kernel at each layer concentrates to a deterministic value by the law of large numbers — regardless of which specific weights were sampled. The key insight for deep networks is that activations at each layer are the same up to a random rotation, and the weights at the next layer rotate correspondingly. This co-rotation is what allows the concentration argument to propagate through depth.

The practical implication is that weight covariance matrices, not individual neuron weights, are the true learned quantities. These covariances are observed to be low-rank — meaning feature learning amounts to discovering a low-dimensional subspace at each layer. Each layer can be decomposed into a linear dimensionality reduction (from the "colored" part of the covariance) followed by a nonlinear high-dimensional embedding (from "white" random features). This is the "rainbow" — the spectrum of the covariance at each layer determines what the network has learned.

This theoretical framework connects to the broader question of why [[curriculum learning improves generalization by acting as a continuation method on non-convex objectives]] works: if the learned kernels are deterministic regardless of initialization, then curriculum strategies are effective because they change the covariance structure of the learned features, not because they find specific weight configurations.

## Claims

- **[causal]** Deep networks define deterministic hierarchical kernels in the infinite-width limit because hidden activations concentrate via the law of large numbers over neuron weights sampled from learned distributions (supports)
- **[empirical]** Kernels defined by hidden activations are similar across different initializations and training runs of the same architecture, as verified numerically on deep CNNs trained on image classification (supports)
- **[causal]** Weight covariance matrices, not individual neuron weights, are the true invariant learned quantities — different training runs learn the same covariances but sample different weights from them (supports)
- **[empirical]** Learned weight covariances at each layer are low-rank, meaning feature learning discovers a low-dimensional subspace for the meaningful variation at each depth (supports)
- **[empirical]** Rainbow networks sampled from the random feature model with learned covariances achieve similar performance to the actually trained networks, validating the model (supports)
- **[definition]** A rainbow network decomposes each layer into a linear dimensionality reduction (colored covariance eigenvectors) followed by a nonlinear high-dimensional embedding (white random features), with deterministic kernels emerging in the wide limit (neutral)

## External Resources

- [arXiv:2305.18512](https://arxiv.org/abs/2305.18512) — original paper
- [JMLR publication](http://jmlr.org/papers/v25/23-1573.html) — peer-reviewed version

## Original Content

> [!quote]- Source Material
> A Rainbow in Deep Network Black Boxes
>
> Florentin Guth, Brice Menard, Gaspar Rochette, Stephane Mallat
> NYU, Johns Hopkins, ENS, College de France, Flatiron Institute, JMLR 2024
>
> Abstract: A central question in deep learning is to understand the functions learned by deep networks. What is their approximation class? Do the learned weights and representations depend on initialization? Here, we provide a deep extension of random feature models, which we call the rainbow model. We prove that rainbow networks define deterministic (hierarchical) kernels in the infinite-width limit. The resulting functions belong to a data-dependent RKHS which does not depend on the weight randomness. Our results highlight the central role played by the covariances of network weights at each layer, which are observed to be low-rank as a result of feature learning.
>
> [Source PDF](deep network black boxes.pdf)
