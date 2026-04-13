---
created: 2026-04-11
description: V-JEPA 2 pretrained on 1M hours of internet video learns representations that enable state-of-the-art video understanding, action anticipation, and zero-shot robot manipulation with only 62 hours of unlabeled interaction data
source: vjepa2.pdf
status: canon
type: source
tags: [self-supervised-learning, world-models, video-understanding, robotics, JEPA, planning]
---

## Key Takeaways

V-JEPA 2 represents perhaps the clearest demonstration yet of LeCun's vision for how AI should learn about the physical world: not by generating pixels or collecting reward signals, but by predicting in a learned representation space. The key distinction from generative approaches (like video generation models) is that JEPA predicts *abstract representations* of masked video segments, not pixel values. This means the model learns to capture predictable aspects of a scene (object trajectories, physical dynamics) while ignoring unpredictable details (precise grass blade positions, leaf patterns). This is exactly the kind of abstraction that [[learning a model that predicts planning-relevant quantities eliminates the need for known environment dynamics]] showed MuZero achieves — learn what matters for planning, discard the rest.

The staged training is elegant: first, pretrain on 1M+ hours of internet video with a mask-denoising prediction objective (action-free — the model just watches). This produces a general-purpose video encoder (up to 1B parameters) that captures motion, appearance, and temporal dynamics. Then, post-train a lightweight action-conditioned predictor (300M params) on just 62 hours of unlabeled robot data. The result, V-JEPA 2-AC, can be deployed zero-shot on Franka robot arms in completely new environments to perform pick-and-place tasks using model predictive control — no task-specific training, no reward engineering, no data from the target environment.

The understanding results are equally impressive: state-of-the-art on action anticipation (39.7 R@5 on Epic-Kitchens-100, 44% relative improvement), strong motion understanding (77.3% on Something-Something v2), and when aligned with an LLM, state-of-the-art on multiple video QA benchmarks at the 8B scale. Notably, a video encoder pretrained *without any language supervision* can be aligned with an LLM and outperform models that were trained with language from the start — challenging conventional wisdom about multimodal pretraining.

The connection to [[bridging frozen vision and language models enables few-shot learning on multimodal tasks without fine-tuning]] is direct: both show that powerful pretrained models can be bridged with lightweight adapters. But V-JEPA 2 goes further — the same representations that power video QA also power physical robot planning, suggesting these latent representations genuinely capture world dynamics, not just visual features.

## Claims

- **[empirical]** Self-supervised pretraining on 1M+ hours of internet video produces video representations that achieve state-of-the-art on action anticipation (39.7 R@5 on Epic-Kitchens-100, 44% relative improvement over prior best) and strong motion understanding (77.3% top-1 on SSv2) (supports)
- **[causal]** Predicting in a learned representation space rather than pixel space forces the model to capture predictable physical dynamics while discarding unpredictable visual details, yielding more useful representations for planning (supports)
- **[empirical]** Only 62 hours of unlabeled robot interaction data is needed to post-train the action-conditioned world model V-JEPA 2-AC, which then performs zero-shot pick-and-place in new environments without task-specific training or reward (supports)
- **[empirical]** A video encoder pretrained without language supervision can be aligned with an LLM to achieve state-of-the-art video QA at the 8B scale (84.0 on PerceptionTest, 76.9 on TempCompass), contradicting the assumption that language supervision is needed during visual pretraining (supports)
- **[causal]** The same learned representations enable both visual understanding tasks (classification, QA) and physical planning tasks (robot manipulation), suggesting they capture genuine world dynamics rather than surface-level visual features (supports)
- **[definition]** V-JEPA 2 uses a joint-embedding-predictive architecture where a context encoder processes visible video patches and a predictor network predicts the representations of masked patches, trained with an L1 loss against an EMA target encoder (neutral)
- **[empirical]** Scaling self-supervised video pretraining (more data, larger models) consistently improves representation quality across understanding, prediction, and planning tasks (supports)

## External Resources

- [GitHub: facebookresearch/vjepa2](https://github.com/facebookresearch/vjepa2) — official code
- [arXiv:2506.09985](https://arxiv.org/abs/2506.09985) — original paper
- [Meta AI Blog](https://ai.meta.com/blog/v-jepa-2-world-model-benchmarks) — blog post

## Original Content

> [!quote]- Source Material
> V-JEPA 2: Self-Supervised Video Models Enable Understanding, Prediction and Planning
>
> Mahmoud Assran, Adrien Bardes, David Fan, Quentin Garrido, Russell Howes, Mojtaba Komeili, Matthew Muckley, Ammar Rizvi, Claire Roberts, Koustuv Sinha, Artem Zholus, et al.
> FAIR at Meta, Mila, 2025
>
> Abstract: A major challenge for modern AI is to learn to understand the world and learn to act largely by observation. This paper explores a self-supervised approach that combines internet-scale video data with a small amount of interaction data (robot trajectories), to develop models capable of understanding, predicting, and planning in the physical world. We first pre-train an action-free joint-embedding-predictive architecture, V-JEPA 2, on a video and image dataset comprising over 1 million hours of internet video. V-JEPA 2 achieves strong performance on motion understanding and state-of-the-art performance on human action anticipation surpassing previous task-specific models. Finally, we show how self-supervised learning can be applied to robotic planning tasks by post-training a latent action-conditioned world model, V-JEPA 2-AC, using less than 62 hours of unlabeled robot videos.
>
> [Source PDF](vjepa2.pdf)
