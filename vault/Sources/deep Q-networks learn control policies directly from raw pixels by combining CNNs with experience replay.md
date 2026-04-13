---
created: 2026-04-11
description: Mnih et al. at DeepMind demonstrate that a convolutional neural network trained with Q-learning and experience replay can learn successful control policies directly from high-dimensional pixel input on Atari 2600 games
source: deep RL atari.pdf
status: canon
type: source
tags: [reinforcement-learning, deep-learning, Q-learning, experience-replay, game-AI]
---

## Key Takeaways

This paper is the landmark that connected deep learning to reinforcement learning in a way that actually worked at scale. The core insight is that two key innovations — experience replay and a CNN function approximator — together solve the problems that had plagued deep RL for years: correlated training data and non-stationary distributions.

Experience replay is the critical mechanism. By storing transitions in a replay buffer and sampling uniformly at random during training, the approach breaks temporal correlations between consecutive samples and smooths over changes in the data distribution as the agent's policy evolves. This is what makes SGD-based training of the Q-network stable, whereas previous attempts at combining neural networks with Q-learning had diverged.

The architecture is surprisingly simple: a CNN takes 4 stacked preprocessed frames (84x84 grayscale) as input and outputs Q-values for each possible action. No game-specific features, no hand-engineering, no access to internal emulator state — the same architecture and hyperparameters work across all 7 Atari games tested. This generality was the real shock: a single architecture surpassing all prior RL approaches on 6 of 7 games and beating human experts on 3.

The paper also revives the question left dormant after TD-Gammon: whether deep function approximation in RL was a special case (helped by backgammon's dice stochasticity) or a general principle. DQN answers decisively that it generalizes, connecting to the broader narrative that [[curriculum learning improves generalization by acting as a continuation method on non-convex objectives]] — both papers show that careful training procedure design matters as much as architecture.

## Claims

- **[empirical]** A single CNN architecture trained with Q-learning and experience replay outperforms all prior RL approaches on 6 of 7 Atari 2600 games and surpasses human expert performance on 3 (supports)
- **[causal]** Experience replay stabilizes deep Q-learning by breaking temporal correlations in training data and smoothing over non-stationary distribution shifts as the policy changes (supports)
- **[empirical]** The same network architecture and hyperparameters work across all tested games without game-specific tuning, demonstrating generality of the approach (supports)
- **[empirical]** Deep Q-learning achieves data efficiency gains from experience replay because each stored transition can be used in many weight updates rather than being discarded after one use (supports)
- **[causal]** Earlier failures to combine non-linear function approximators with Q-learning were due to correlated data and non-stationary distributions, not fundamental incompatibility between deep learning and RL (supports)
- **[definition]** A Deep Q-Network (DQN) is a convolutional neural network that approximates the optimal action-value function Q*(s,a) from raw pixel input, trained by minimizing the squared Bellman error with experience replay (neutral)
- **[empirical]** The agent learns from only raw pixel observations, scalar rewards, and the set of possible actions — no access to internal game state or hand-designed features (supports)

## External Resources

- [Arcade Learning Environment (ALE)](https://github.com/mgbellemare/Arcade-Learning-Environment) — the Atari 2600 RL benchmark platform used for evaluation
- [arXiv:1312.5602](https://arxiv.org/abs/1312.5602) — original paper on arXiv

## Original Content

> [!quote]- Source Material
> Playing Atari with Deep Reinforcement Learning
>
> Volodymyr Mnih, Koray Kavukcuoglu, David Silver, Alex Graves, Ioannis Antonoglou, Daan Wierstra, Martin Riedmiller
> DeepMind Technologies, 2013
>
> Abstract: We present the first deep learning model to successfully learn control policies directly from high-dimensional sensory input using reinforcement learning. The model is a convolutional neural network, trained with a variant of Q-learning, whose input is raw pixels and whose output is a value function estimating future rewards. We apply our method to seven Atari 2600 games from the Arcade Learning Environment, with no adjustment of the architecture or learning algorithm. We find that it outperforms all previous approaches on six of the games and surpasses a human expert on three of them.
>
> [Source PDF](deep RL atari.pdf)
