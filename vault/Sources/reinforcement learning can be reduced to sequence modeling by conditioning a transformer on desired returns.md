---
created: 2026-04-11
description: Decision Transformer recasts offline RL as conditional sequence modeling — an autoregressive GPT trained on (return, state, action) sequences generates optimal actions when conditioned on high desired returns, matching or exceeding model-free offline RL baselines
source: offline RL sequence.pdf
status: canon
type: source
tags: [reinforcement-learning, offline-RL, transformers, sequence-modeling, decision-transformer]
---

## Key Takeaways

Decision Transformer proposes a paradigm shift: instead of learning value functions or computing policy gradients, treat RL as sequence modeling. An autoregressive transformer is trained on trajectories of (return-to-go, state, action) tokens, and at test time, you generate optimal behavior by conditioning on the *desired* return. Specify a high return-to-go as the prompt, and the model generates the actions needed to achieve it. This is essentially reward-conditioned generation — the same idea as conditional text generation, applied to control.

The elegance is in what this avoids. No temporal difference learning (and thus no "deadly triad" instability). No bootstrapping for long-term credit assignment — the transformer handles it directly via self-attention over the full context. No discounting of future rewards, which eliminates the short-sightedness that discounting induces. No need for value pessimism or behavior regularization, techniques that prior offline RL methods required to prevent overestimation of unseen actions.

The illustrative example is beautiful: train on random walks on a graph, condition on optimal return at test time, and the model generates shortest paths — policy improvement without dynamic programming. This works because the transformer models the full distribution of behaviors in the training data and can compose subsequences to achieve returns not seen in any single training trajectory.

This connects to [[a single transformer with one set of weights can play games caption images chat and control robots by treating all modalities as tokens]] — both show that reducing diverse problems to token sequences lets you leverage the transformer's proven scaling properties. And it foreshadows [[pure reinforcement learning without human demonstrations produces superior reasoning in LLMs]], where LLMs are trained with RL — Decision Transformer goes the other direction, using LM-style training for RL.

## Claims

- **[empirical]** Decision Transformer matches or exceeds state-of-the-art model-free offline RL baselines (CQL, BEAR, BCQ) on Atari, OpenAI Gym, and Key-to-Door tasks (supports)
- **[causal]** Conditioning an autoregressive model on desired return-to-go enables policy improvement at test time without dynamic programming — specifying higher returns generates better actions (supports)
- **[causal]** Self-attention performs credit assignment directly across the full sequence context, bypassing the slow reward propagation of Bellman backups and handling sparse/distracting rewards more effectively (supports)
- **[causal]** Reducing RL to sequence modeling avoids the deadly triad (function approximation + bootstrapping + off-policy learning) that destabilizes conventional offline RL (supports)
- **[empirical]** Trained only on random walk data with no expert demonstrations, Decision Transformer generates optimal shortest paths by conditioning on maximum possible returns (supports)
- **[causal]** Longer context lengths improve performance because the transformer can consider more of the trajectory history when making decisions, unlike Markovian approaches (supports)
- **[definition]** Decision Transformer feeds (return-to-go, state, action) triplets as tokens into a causally masked GPT, training to predict actions autoregressively conditioned on desired returns and past trajectory (neutral)

## External Resources

- [Project page](https://sites.google.com/berkeley.edu/decision-transformer) — code and results
- [arXiv:2106.01345](https://arxiv.org/abs/2106.01345) — original paper

## Original Content

> [!quote]- Source Material
> Decision Transformer: Reinforcement Learning via Sequence Modeling
>
> Lili Chen, Kevin Lu, Aravind Rajeswaran, Kimin Lee, Aditya Grover, Michael Laskin, Pieter Abbeel, Aravind Srinivas, Igor Mordatch
> UC Berkeley, Facebook AI Research, Google Brain, 2021
>
> Abstract: We introduce a framework that abstracts Reinforcement Learning as a sequence modeling problem. We present Decision Transformer, an architecture that casts RL as conditional sequence modeling. Unlike prior approaches that fit value functions or compute policy gradients, Decision Transformer simply outputs optimal actions by leveraging a causally masked Transformer. By conditioning on the desired return, past states, and actions, our model can generate future actions that achieve the desired return. Despite its simplicity, Decision Transformer matches or exceeds state-of-the-art model-free offline RL baselines.
>
> [Source PDF](offline RL sequence.pdf)
