---
created: 2026-04-11
description: Poole et al. introduce Score Distillation Sampling to transfer pretrained 2D text-to-image diffusion models into 3D object generation by optimizing a NeRF so that its rendered views score well under the diffusion prior, requiring zero 3D training data
source: dream fusion.pdf
status: canon
type: source
tags: [3D-generation, diffusion, NeRF, text-to-3D, score-distillation, cross-modal]
---

## Key Takeaways

DreamFusion's insight is a clever cross-modal transfer trick: 3D training data is scarce, but 2D text-to-image diffusion models trained on billions of image-text pairs encode rich knowledge about how objects look from different angles. The question is how to extract that 3D-implicit knowledge from a 2D model.

The answer is Score Distillation Sampling (SDS). Instead of sampling from the diffusion model, SDS uses it as a critic: render the NeRF from a random camera angle, add noise to the rendering, ask the diffusion model what the noise-free image should look like given the text prompt, and use the difference as a gradient to update the NeRF's parameters. Repeating this from many random angles sculpts the NeRF into a 3D object that looks correct from all viewpoints according to the diffusion model's prior.

Mathematically, SDS minimizes the KL divergence between a family of Gaussian distributions (centered on NeRF renderings plus noise) and the score functions learned by the pretrained diffusion model. The key property is that gradients of this loss can be computed without backpropagating through the diffusion model itself — only the NeRF receives gradients, making it efficient.

The results require no 3D data whatsoever and no modifications to the diffusion model. The generated 3D objects can be viewed from any angle, relit with arbitrary illumination, and composited into 3D environments. This is a striking example of the pattern seen across [[diffusion models generate high quality images by learning to reverse a gradual noising process]] and [[running diffusion in a learned latent space makes high-resolution image synthesis accessible on consumer hardware]]: diffusion models are not just image generators but general-purpose priors that can be repurposed for entirely different modalities.

## Claims

- **[empirical]** DreamFusion generates coherent 3D objects from text prompts using only a pretrained 2D diffusion model, requiring zero 3D training data and no modifications to the diffusion model (supports)
- **[causal]** Score Distillation Sampling uses the diffusion model as a critic rather than a generator — gradients flow only to the NeRF parameters, not through the diffusion model, making optimization efficient (supports)
- **[definition]** SDS minimizes the KL divergence between Gaussian distributions centered on noisy NeRF renderings and the learned score functions of the diffusion model, using the diffusion model's denoising prediction as the gradient signal (neutral)
- **[causal]** Optimizing from many random camera angles forces the NeRF to be 3D-consistent — each view must independently score well under the 2D diffusion prior (supports)
- **[empirical]** Generated 3D objects support view synthesis from any angle, relighting with arbitrary illumination, and compositing into 3D environments (supports)
- **[causal]** The approach works because text-to-image diffusion models trained on billions of diverse images implicitly encode knowledge about 3D structure and multi-view consistency (supports)

## External Resources

- [dreamfusion3d.github.io](https://dreamfusion3d.github.io) — project page with 3D results
- [arXiv:2209.14988](https://arxiv.org/abs/2209.14988) — original paper

## Original Content

> [!quote]- Source Material
> DreamFusion: Text-to-3D Using 2D Diffusion
>
> Ben Poole, Ajay Jain, Jonathan T. Barron, Ben Mildenhall
> Google Research, UC Berkeley, 2022
>
> Abstract: Recent breakthroughs in text-to-image synthesis have been driven by diffusion models trained on billions of image-text pairs. Adapting this approach to 3D synthesis would require large-scale datasets of labeled 3D data and efficient architectures for denoising 3D data, neither of which currently exist. In this work, we circumvent these limitations by using a pretrained 2D text-to-image diffusion model to perform text-to-3D synthesis. We introduce a loss based on probability density distillation that enables the use of a 2D diffusion model as a prior for optimization of a parametric image generator.
>
> [Source PDF](dream fusion.pdf)
