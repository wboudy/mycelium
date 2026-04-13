---
created: 2026-04-11
description: Song, Meng, and Ermon show that generalizing DDPMs to non-Markovian forward processes yields deterministic implicit models (DDIMs) that use the same trained network but sample 10-50x faster with semantically meaningful latent interpolation
source: diffusion implicit.pdf
status: canon
type: source
tags: [generative-models, diffusion, sampling-acceleration, DDIM, implicit-models]
---

## Key Takeaways

DDIMs exploit a beautiful mathematical observation: the training objective of [[diffusion models generate high quality images by learning to reverse a gradual noising process]] doesn't actually require the forward process to be Markovian. There exists a whole family of non-Markovian forward processes that share the same marginals q(x_t|x_0) and therefore the same training objective. Different members of this family lead to different generative processes — and crucially, some of these generative processes are deterministic.

The deterministic variant is the key innovation. When the reverse process has zero stochasticity (sigma=0), the generative process becomes a fixed ODE mapping from noise to data. This has three major consequences: (1) you can skip timesteps freely — sample at 10, 20, or 50 steps instead of 1000, with graceful quality degradation; (2) the mapping is deterministic, so the same initial noise always produces the same image, enabling semantically meaningful interpolation in latent space; (3) you can encode real images back to their latent codes with very low reconstruction error, which DDPMs can't do because their stochastic reverse process is lossy.

The practical acceleration is dramatic: 10-50x faster wall-clock sampling with only minor quality loss. A DDPM that takes 20 hours to generate 50K 32x32 images can be accelerated to under an hour. And the same pre-trained DDPM network is reused with zero retraining — you just change the sampling procedure.

This work directly enables [[consistency models enable single-step image generation by learning to map any point on a diffusion trajectory to its origin]], which builds on the ODE trajectory interpretation that DDIMs formalized. DDIMs showed that trajectories exist; consistency models learned to shortcut them entirely.

## Claims

- **[empirical]** DDIMs generate samples 10x to 50x faster than DDPMs in wall-clock time while maintaining comparable quality, using the same pre-trained model with no retraining (supports)
- **[causal]** Generalizing DDPMs to non-Markovian forward processes that share the same marginals yields a family of generative models with identical training objectives but different sampling behaviors (supports)
- **[causal]** The deterministic (sigma=0) variant creates a fixed mapping from noise to data, enabling consistent sample generation where the same initial noise always produces the same image (supports)
- **[empirical]** DDIMs enable semantically meaningful latent space interpolation — interpolating between two initial noise vectors produces images that smoothly transition in high-level features, unlike DDPMs whose stochastic process interpolates near image space (supports)
- **[empirical]** DDIMs can encode real images back to their latent representations with very low reconstruction error, functioning as an approximate encoder-decoder (supports)
- **[causal]** Accelerated sampling works by using a subsequence of the original timesteps — the model was trained on all T steps but can be evaluated on any subset, with quality degrading gracefully as fewer steps are used (supports)

## External Resources

- [arXiv:2010.02502](https://arxiv.org/abs/2010.02502) — original paper

## Original Content

> [!quote]- Source Material
> Denoising Diffusion Implicit Models
>
> Jiaming Song, Chenlin Meng, Stefano Ermon
> Stanford University, ICLR 2021
>
> Abstract: Denoising diffusion probabilistic models (DDPMs) have achieved high quality image generation without adversarial training, yet they require simulating a Markov chain for many steps in order to produce a sample. To accelerate sampling, we present denoising diffusion implicit models (DDIMs), a more efficient class of iterative implicit probabilistic models with the same training procedure as DDPMs. We generalize DDPMs via a class of non-Markovian diffusion processes that lead to the same training objective. These non-Markovian processes can correspond to generative processes that are deterministic, giving rise to implicit models that produce high quality samples much faster. We empirically demonstrate that DDIMs can produce high quality samples 10x to 50x faster in terms of wall-clock time compared to DDPMs.
>
> [Source PDF](diffusion implicit.pdf)
