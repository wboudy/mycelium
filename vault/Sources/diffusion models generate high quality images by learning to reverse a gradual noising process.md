---
created: 2026-04-11
description: Ho, Jain, and Abbeel show that diffusion probabilistic models trained to reverse a fixed Gaussian noising process achieve state-of-the-art image synthesis quality, revealing an equivalence between diffusion training and denoising score matching
source: diffusion.pdf
status: canon
type: source
tags: [generative-models, diffusion, image-synthesis, variational-inference, score-matching]
---

## Key Takeaways

The core idea is elegant in its simplicity: take a data sample, gradually destroy it by adding Gaussian noise over T timesteps (the forward process), then train a neural network to reverse each step (the reverse process). At generation time, start from pure noise and iteratively denoise. The forward process is fixed — no learnable parameters — which means training reduces to a simple regression problem: predict the noise that was added at each step.

The key theoretical insight is that predicting noise (the epsilon-parameterization) is equivalent to denoising score matching with Langevin dynamics. This connection is what makes the simplified training objective work: instead of optimizing the full variational bound with its many KL divergence terms, you can just train with a reweighted MSE loss on the predicted noise. The simplified objective drops the per-timestep weighting and empirically produces better samples despite being a looser bound on the log-likelihood.

An important subtlety: diffusion models achieve excellent sample quality (FID 3.17 on CIFAR10, matching ProgressiveGAN on LSUN 256x256) but do NOT have competitive log-likelihoods compared to other likelihood-based models. The paper shows this isn't a flaw — most of the model's coding capacity goes to imperceptible image details. The progressive decoding interpretation reframes sampling as a generalization of autoregressive decoding along a bit ordering, where coarse structure emerges first and fine details fill in last.

This paper launched the entire modern diffusion model era, leading directly to work like [[deep Q-networks learn control policies directly from raw pixels by combining CNNs with experience replay]] in RL — both demonstrate that simple, well-chosen training procedures on powerful architectures beat more complex approaches.

## Claims

- **[empirical]** Diffusion models achieve state-of-the-art FID score of 3.17 on unconditional CIFAR10 and sample quality comparable to ProgressiveGAN on 256x256 LSUN (supports)
- **[causal]** The epsilon-parameterization — training the network to predict the noise added at each timestep rather than the denoised image — is equivalent to denoising score matching with Langevin dynamics (supports)
- **[empirical]** A simplified training objective that drops the per-timestep loss weighting produces better sample quality than the full variational bound, despite being a looser bound on log-likelihood (supports)
- **[empirical]** Diffusion models do not achieve competitive log-likelihoods compared to other likelihood-based generative models, but most lossless codelength is consumed describing imperceptible image details (supports)
- **[definition]** A diffusion probabilistic model is a parameterized Markov chain trained via variational inference where the forward process gradually adds Gaussian noise to data and the reverse process learns to denoise step by step (neutral)
- **[causal]** The progressive sampling procedure acts as a form of lossy decompression that generalizes autoregressive decoding — coarse image structure is decoded first, fine details last (supports)
- **[empirical]** Both fixed variance schedules (beta_t and beta_tilde_t) for the reverse process produce similar results, corresponding to upper and lower bounds on reverse process entropy (neutral)

## External Resources

- [GitHub: hojonathanho/diffusion](https://github.com/hojonathanho/diffusion) — official implementation
- [arXiv:2006.11239](https://arxiv.org/abs/2006.11239) — original paper

## Original Content

> [!quote]- Source Material
> Denoising Diffusion Probabilistic Models
>
> Jonathan Ho, Ajay Jain, Pieter Abbeel
> UC Berkeley, NeurIPS 2020
>
> Abstract: We present high quality image synthesis results using diffusion probabilistic models, a class of latent variable models inspired by considerations from nonequilibrium thermodynamics. Our best results are obtained by training on a weighted variational bound designed according to a novel connection between diffusion probabilistic models and denoising score matching with Langevin dynamics, and our models naturally admit a progressive lossy decompression scheme that can be interpreted as a generalization of autoregressive decoding. On the unconditional CIFAR10 dataset, we obtain an Inception score of 9.46 and a state-of-the-art FID score of 3.17. On 256x256 LSUN, we obtain sample quality similar to ProgressiveGAN.
>
> [Source PDF](diffusion.pdf)
