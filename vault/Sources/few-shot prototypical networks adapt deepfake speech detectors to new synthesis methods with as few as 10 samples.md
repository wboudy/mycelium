---
created: 2026-04-11
description: Garg, Andrews et al. propose self-attentive prototypical networks for synthetic speech detection that adapt to distribution shifts from unseen synthesis methods, languages, and speakers using only 10 in-distribution samples, achieving up to 32% relative EER reduction
source: deepfake detection.pdf
status: canon
type: source
tags: [speech-synthesis, deepfake-detection, few-shot-learning, distribution-shift, anti-spoofing, JHU-HLTCOE]
---

## Key Takeaways

The core problem is that supervised speech deepfake detectors trained on one set of synthesis methods fail when encountering new methods, speakers, languages, or audio conditions at test time. Since new synthesis methods appear constantly and you can't anticipate all distribution shifts, the detector must adapt rapidly with minimal data.

The solution uses self-attentive prototypical networks — a few-shot learning approach where the model learns to map speech samples to embeddings, then classifies new samples by distance to class prototypes (centroids of the few in-distribution examples). The self-attention mechanism over the support set allows the model to weight different examples based on their relevance, producing more robust prototypes than simple averaging. Using self-supervised speech representations (SSL features) as the backbone provides strong initial features that can be fine-tuned efficiently with small samples.

With as few as 10 in-distribution samples, the approach achieves up to 32% relative EER reduction on Japanese deepfakes and 20% on ASVspoof 2021 — a significant improvement over zero-shot detectors that have no access to in-distribution samples. The study systematically controls distribution shifts across synthesis methods (12 vocoders), languages, and datasets.

This connects to [[bridging frozen vision and language models enables few-shot learning on multimodal tasks without fine-tuning]] in methodology — both leverage strong pretrained representations and few-shot adaptation to generalize beyond training distributions, avoiding the need for large labeled datasets in each new domain.

## Claims

- **[empirical]** Self-attentive prototypical networks achieve up to 32% relative EER reduction on Japanese deepfakes and 20% on ASVspoof 2021 using only 10 in-distribution samples (supports)
- **[causal]** Distribution shifts from unseen synthesis methods, speakers, languages, and audio conditions degrade supervised deepfake detectors, making few-shot adaptation essential for real-world deployment (supports)
- **[causal]** Self-supervised speech representations (SSL features) are more readily fine-tuned with small samples than features trained from scratch, because SSL pretraining captures general speech properties under diverse conditions (supports)
- **[empirical]** Self-attentive prototype aggregation outperforms simple mean-based prototypes by allowing the model to weight support examples based on relevance to the query (supports)
- **[empirical]** Supervised fine-tuning of SSL-based detectors shows strong performance in "medium-shot" settings with larger adaptation sets, complementing the prototypical network approach for few-shot settings (supports)

## External Resources

- [arXiv:2508.13320](https://arxiv.org/abs/2508.13320) — original paper (IEEE ASRU 2025)

## Original Content

> [!quote]- Source Material
> Rapidly Adapting to New Voice Spoofing: Few-Shot Detection of Synthesized Speech Under Distribution Shifts
>
> Ashi Garg, Zexin Cai, Henry Li Xinyuan, Leibny Paola Garcia-Perera, Kevin Duh, Sanjeev Khudanpur, Matthew Wiesner, Nicholas Andrews
> JHU HLTCOE, IEEE ASRU 2025
>
> Abstract: We address the challenge of detecting synthesized speech under distribution shifts. Few-shot learning methods are a promising way to tackle distribution shifts by rapidly adapting on the basis of a few in-distribution samples. We propose a self-attentive prototypical network to enable more robust few-shot adaptation. Our proposed technique can quickly adapt using as few as 10 in-distribution samples — achieving up to 32% relative EER reduction.
>
> [Source PDF](deepfake detection.pdf)
