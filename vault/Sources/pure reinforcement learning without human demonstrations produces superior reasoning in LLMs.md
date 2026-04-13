---
created: 2026-04-11
description: DeepSeek-AI demonstrates that applying RL with only correctness-based rewards to a base LLM — skipping supervised fine-tuning on human reasoning traces — produces emergent chain-of-thought reasoning that surpasses models trained on human demonstrations
source: deepseek.pdf
status: canon
type: source
tags: [LLM, reinforcement-learning, reasoning, chain-of-thought, GRPO, emergence]
---

## Key Takeaways

The central insight is provocative: human-annotated reasoning traces are not just unnecessary for teaching LLMs to reason — they may actually be counterproductive. DeepSeek-R1-Zero skips supervised fine-tuning entirely, applying GRPO (Group Relative Policy Optimization) directly to a base model with only two reward signals: accuracy (is the answer correct?) and format (did you use the think/answer tags?). No process rewards, no neural reward models, no human demonstrations.

What emerges is remarkable. The model spontaneously develops sophisticated reasoning behaviors — self-reflection, verification, backtracking, and exploration of alternative approaches — that were never explicitly taught. Response length grows steadily during training as the model learns to "think longer" on harder problems. The paper documents an "aha moment" where the model suddenly starts using "wait" during its reasoning, marking a phase transition in its problem-solving strategy. This connects deeply to [[deep Q-networks learn control policies directly from raw pixels by combining CNNs with experience replay]] — both show that providing the right learning signal and letting the model self-organize beats hand-engineering the solution strategy.

GRPO itself is elegant: instead of PPO's expensive critic network, it samples a group of outputs for each question, computes advantages relative to the group mean, and optimizes with a clipped objective plus KL penalty against a reference policy. This makes large-scale RL on LLMs practical.

The multi-stage pipeline for the full DeepSeek-R1 is also important: cold-start SFT on a small set of long CoT examples, then RL on reasoning tasks with rule-based + language consistency rewards, then rejection sampling to generate training data for a second SFT stage mixing reasoning and non-reasoning data, and finally RL on diverse prompts with both rule-based and preference rewards. The distilled smaller models (1.5B-70B) retain strong reasoning, suggesting that the reasoning patterns discovered by RL can be transferred through knowledge distillation.

The deliberate avoidance of neural reward models is a key design choice — they found neural rewards are susceptible to reward hacking at scale, and retraining them is expensive. Rule-based rewards on verifiable tasks sidestep this entirely.

## Claims

- **[empirical]** DeepSeek-R1-Zero, trained with pure RL and no supervised fine-tuning on reasoning data, achieves 77.9% pass@1 on AIME 2024 (86.7% with self-consistency), surpassing the average human competitor score (supports)
- **[causal]** Skipping SFT before RL allows the model to discover non-human reasoning pathways that are superior to those constrained by human demonstrations, which introduce cognitive biases and cap performance (supports)
- **[empirical]** Advanced reasoning behaviors — self-reflection, verification, backtracking, dynamic strategy adaptation — emerge spontaneously from RL without being explicitly taught (supports)
- **[empirical]** Response length increases steadily during RL training, indicating the model autonomously learns to allocate more "thinking time" to problems (supports)
- **[causal]** Neural reward models are avoided because they are susceptible to reward hacking during large-scale RL, and retraining them adds substantial complexity — rule-based rewards on verifiable tasks provide cleaner signal (supports)
- **[empirical]** Reasoning patterns discovered by large-scale RL can be transferred to smaller models (1.5B-70B) through distillation, with distilled models outperforming their instruction-tuned counterparts (supports)
- **[definition]** GRPO (Group Relative Policy Optimization) computes advantages by sampling a group of outputs per question and normalizing rewards within the group, eliminating the need for a separate critic network used in PPO (neutral)
- **[empirical]** The "aha moment" — a phase transition in reasoning behavior marked by increased use of reflective language like "wait" — demonstrates discontinuous capability emergence during RL training (supports)

## External Resources

- [HuggingFace: deepseek-ai](https://huggingface.co/deepseek-ai) — released model weights
- [arXiv:2501.12948](https://arxiv.org/abs/2501.12948) — original paper

## Original Content

> [!quote]- Source Material
> DeepSeek-R1: Incentivizing Reasoning Capability in LLMs via Reinforcement Learning
>
> DeepSeek-AI, 2025
>
> Abstract: General reasoning represents a long-standing and formidable challenge in artificial intelligence. Recent breakthroughs, exemplified by large language models and chain-of-thought prompting, have achieved considerable success on foundational reasoning tasks. However, this success is heavily contingent upon extensive human-annotated demonstrations, and models' capabilities are still insufficient for more complex problems. Here we show that the reasoning abilities of LLMs can be incentivized through pure reinforcement learning, obviating the need for human-labeled reasoning trajectories. The proposed RL framework facilitates the emergent development of advanced reasoning patterns, such as self-reflection, verification, and dynamic strategy adaptation. Consequently, the trained model achieves superior performance on verifiable tasks such as mathematics, coding competitions, and STEM fields, surpassing its counterparts trained via conventional supervised learning on human demonstrations.
>
> [Source PDF](deepseek.pdf)
