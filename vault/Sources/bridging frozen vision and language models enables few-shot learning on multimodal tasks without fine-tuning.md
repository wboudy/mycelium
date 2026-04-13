---
created: 2026-04-11
description: DeepMind's Flamingo connects pretrained frozen vision encoders to frozen language models via gated cross-attention, achieving state-of-the-art few-shot learning on 16 vision-language benchmarks with just a handful of examples
source: flamingo vision.pdf
status: canon
type: source
tags: [multimodal, vision-language, few-shot-learning, VLM, cross-attention]
---

## Key Takeaways

Flamingo's key architectural insight is that you don't need to train a vision-language model from scratch — you can bridge two powerful pretrained models (a vision encoder and a large language model) while keeping both frozen. The trainable components are lightweight connectors: a Perceiver Resampler that compresses variable-length visual features into a fixed number of tokens, and Gated Cross-Attention Dense layers inserted between frozen LM blocks that allow the language model to attend to visual features. The gating mechanism starts at zero, ensuring the model initially behaves exactly like the pretrained LM, then gradually learns to incorporate visual information.

The ability to handle arbitrarily interleaved sequences of images, video, and text is what enables few-shot learning. Just as LLMs can be prompted with text examples, Flamingo can be prompted with image-text pairs that demonstrate a task, followed by a query image. This is in-context learning applied to the multimodal domain — no gradient updates, no fine-tuning, just prompt engineering with visual examples.

The results are striking: on 16 benchmarks spanning VQA, captioning, classification, and video understanding, Flamingo-80B sets new few-shot state-of-the-art on all 9 tasks with published few-shot results, and surpasses the fine-tuned state-of-the-art on 6 tasks despite using orders of magnitude less task-specific data. Performance scales smoothly with both model size and number of shots.

Training on large-scale multimodal web corpora (interleaved image-text from webpages, image-text pairs, and video-text pairs) is critical — this mirrors how [[pure reinforcement learning without human demonstrations produces superior reasoning in LLMs]] shows that the right training signal matters more than curated demonstrations. Flamingo's training data isn't annotated for any specific ML task; it's just the web, in all its messy interleaved glory.

## Claims

- **[empirical]** Flamingo-80B outperforms fine-tuned state-of-the-art models on 6 of 16 vision-language benchmarks using only few-shot prompting with no fine-tuning (supports)
- **[causal]** Bridging frozen pretrained vision and language models with lightweight trainable connectors (Perceiver Resampler + Gated Cross-Attention) preserves the knowledge in both models while enabling multimodal reasoning (supports)
- **[empirical]** Flamingo sets new few-shot state-of-the-art on all 9 benchmarks with published few-shot results, outperforming prior methods by large margins (supports)
- **[causal]** Training on large-scale multimodal web corpora with naturally interleaved images and text — rather than curated task-specific datasets — is what endows the model with general-purpose few-shot capabilities (supports)
- **[definition]** The Perceiver Resampler compresses variable-length visual features from the vision encoder into a fixed small number of visual tokens, enabling efficient cross-attention regardless of input resolution or video length (neutral)
- **[empirical]** Performance scales smoothly with both model size (3B, 9B, 80B) and number of few-shot examples (0, 4, 8, 16, 32) (supports)
- **[causal]** Gated cross-attention layers initialized at zero ensure the model starts as the pretrained LM and gradually learns to incorporate visual information, stabilizing training (supports)

## External Resources

- [arXiv:2204.14198](https://arxiv.org/abs/2204.14198) — original paper

## Original Content

> [!quote]- Source Material
> Flamingo: a Visual Language Model for Few-Shot Learning
>
> Jean-Baptiste Alayrac, Jeff Donahue, Pauline Luc, Antoine Miech, Iain Barr, Yana Hasson, Karel Lenc, Arthur Mensch, Katie Millican, Malcolm Reynolds, Roman Ring, Eliza Rutherford, et al.
> DeepMind, NeurIPS 2022
>
> Abstract: Building models that can be rapidly adapted to novel tasks using only a handful of annotated examples is an open challenge for multimodal machine learning research. We introduce Flamingo, a family of Visual Language Models (VLM) with this ability. We propose key architectural innovations to: (i) bridge powerful pretrained vision-only and language-only models, (ii) handle sequences of arbitrarily interleaved visual and textual data, and (iii) seamlessly ingest images or videos as inputs. Thanks to their flexibility, Flamingo models can be trained on large-scale multimodal web corpora containing arbitrarily interleaved text and images, which is key to endow them with in-context few-shot learning capabilities.
>
> [Source PDF](flamingo vision.pdf)
