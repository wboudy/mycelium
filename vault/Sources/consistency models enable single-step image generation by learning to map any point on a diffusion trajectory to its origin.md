---
created: 2026-04-11
description: Song et al. propose consistency models that learn a self-consistency property — all points on the same probability flow ODE trajectory map to the same data point — enabling high-quality one-step generation while retaining the option of iterative refinement
source: consistency models.pdf
status: canon
type: source
tags: [generative-models, diffusion, consistency-models, fast-sampling, ODE]
---

## Key Takeaways

Consistency models attack the fundamental speed problem of [[diffusion models generate high quality images by learning to reverse a gradual noising process]]: iterative sampling requires 10-2000 network evaluations per image. The insight is geometric: every noisy data point at any noise level lies on a specific probability flow ODE trajectory that starts at a clean data point. If you can learn a function that maps *any* point on a trajectory directly to its origin, you get single-step generation — feed in noise, get out data in one evaluation.

The self-consistency property is the training signal: for any two points on the same ODE trajectory, the model must produce the same output. This can be enforced in two ways. Consistency distillation uses a pre-trained diffusion model and an ODE solver to find pairs of adjacent points on trajectories, then trains the consistency model to produce matching outputs for these pairs. Consistency training eliminates the pre-trained model entirely, using the score function estimated from the training data directly.

The key advantage over other distillation approaches (like progressive distillation) is that consistency models aren't just fast — they're a genuine new family of generative models. They support single-step generation by design, but you can optionally chain multiple evaluations for better quality (trading compute for quality, like diffusion). They also inherit zero-shot editing capabilities: inpainting, colorization, and super-resolution work without explicit training because you can fix known regions and let the consistency model map the noisy unknown regions to data.

Results: state-of-the-art one-step generation (FID 3.55 on CIFAR-10, 6.20 on ImageNet 64x64), outperforming both existing distillation methods and standalone one-step generators. This connects to [[running diffusion in a learned latent space makes high-resolution image synthesis accessible on consumer hardware]] — both papers democratize generation by reducing compute, but through orthogonal mechanisms (latent space vs. fewer steps).

## Claims

- **[empirical]** Consistency models achieve state-of-the-art one-step generation with FID 3.55 on CIFAR-10 and 6.20 on ImageNet 64x64, outperforming all prior distillation techniques (supports)
- **[causal]** The self-consistency property — all points on the same ODE trajectory must map to the same origin — provides a training signal that enables single-step generation without adversarial training (supports)
- **[empirical]** Consistency models can be trained either by distilling pre-trained diffusion models (consistency distillation) or as standalone generative models from scratch (consistency training) (supports)
- **[causal]** Multi-step sampling with consistency models improves quality by iteratively adding noise and denoising, trading compute for quality similar to diffusion but starting from much fewer steps (supports)
- **[empirical]** Zero-shot data editing (inpainting, colorization, super-resolution) works without task-specific training, inherited from the diffusion model framework (supports)
- **[definition]** A consistency model is a function that maps any point (x_t, t) on a probability flow ODE trajectory to the trajectory's origin x_0, trained to satisfy f(x_t, t) = f(x_t', t') for all t, t' on the same trajectory (neutral)

## External Resources

- [arXiv:2303.01469](https://arxiv.org/abs/2303.01469) — original paper

## Original Content

> [!quote]- Source Material
> Consistency Models
>
> Yang Song, Prafulla Dhariwal, Mark Chen, Ilya Sutskever
> OpenAI, ICML 2023
>
> Abstract: Diffusion models have significantly advanced the fields of image, audio, and video generation, but they depend on an iterative sampling process that causes slow generation. To overcome this limitation, we propose consistency models, a new family of models that generate high quality samples by directly mapping noise to data. They support fast one-step generation by design, while still allowing multistep sampling to trade compute for sample quality. They also support zero-shot data editing, such as image inpainting, colorization, and super-resolution, without requiring explicit training on these tasks.
>
> [Source PDF](consistency models.pdf)
