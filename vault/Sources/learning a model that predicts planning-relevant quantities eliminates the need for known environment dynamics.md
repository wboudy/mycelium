---
created: 2026-04-11
description: MuZero achieves superhuman performance across board games and Atari by learning a latent dynamics model that predicts only rewards, policies, and values — without reconstructing observations or knowing game rules
source: mastering agents.pdf
status: canon
type: source
tags: [reinforcement-learning, model-based-RL, planning, MCTS, learned-models, game-AI]
---

## Key Takeaways

MuZero resolves a long-standing tension in RL: model-based methods excel at planning-heavy domains (chess, Go) but require known dynamics, while model-free methods handle unknown environments (Atari) but can't do sophisticated lookahead. MuZero bridges this by learning a model — but critically, not a model of the environment. Instead, it learns a model of the quantities that matter for planning: rewards, policies, and values.

The architecture has three components: a representation function h that encodes observations into a hidden state, a dynamics function g that takes a hidden state and action to produce the next hidden state and predicted reward, and a prediction function f that outputs policy and value from any hidden state. The hidden state has no requirement to reconstruct observations or match true environment states — it's free to represent whatever is useful for planning. This is the key insight: you don't need to model pixels or physics, you just need value equivalence.

MCTS runs over this learned model at each timestep, producing improved policy and value estimates that then serve as training targets. This creates a virtuous cycle: search improves the targets, better targets improve the model, a better model improves search. The same algorithm — with zero knowledge of game rules — matches AlphaZero's superhuman performance on Go, chess, and shogi while simultaneously achieving state-of-the-art on all 57 Atari games, where previous model-based methods had failed.

This connects to the broader pattern seen in [[deep Q-networks learn control policies directly from raw pixels by combining CNNs with experience replay]] and [[pure reinforcement learning without human demonstrations produces superior reasoning in LLMs]]: letting the learning system discover its own internal representations, rather than imposing human-designed structure, consistently produces superior results. MuZero's hidden states might encode concepts that have no human-interpretable analogue, but they're exactly what's needed for effective planning.

## Claims

- **[empirical]** MuZero matches AlphaZero's superhuman performance in Go, chess, and shogi without any knowledge of game rules, while simultaneously achieving state-of-the-art on all 57 Atari games (supports)
- **[causal]** Learning to predict only planning-relevant quantities (reward, policy, value) rather than full observation reconstruction drastically reduces the information the model must maintain, enabling effective planning in visually complex domains (supports)
- **[definition]** MuZero's model consists of three functions: representation h (observations to hidden state), dynamics g (hidden state + action to next hidden state + reward), and prediction f (hidden state to policy + value), trained end-to-end to support MCTS planning (neutral)
- **[causal]** The hidden state has no semantic requirement to match true environment state or reconstruct observations — it is free to represent whatever supports accurate reward, policy, and value prediction (supports)
- **[empirical]** Previous model-based RL methods that tried to model pixel-level observations or reconstruct environment state failed to match model-free methods in visually complex domains like Atari (supports)
- **[causal]** MCTS over the learned model creates a self-improving loop: search produces better policy and value targets, which train a better model, which enables better search (supports)
- **[empirical]** MuZero uses only 50 MCTS simulations per step in Atari (vs 800 in board games), demonstrating the model learns efficient planning even in domains requiring fast decisions (supports)

## External Resources

- [arXiv:1911.08265](https://arxiv.org/abs/1911.08265) — original paper
- [Nature publication](https://www.nature.com/articles/s41586-020-03051-4) — peer-reviewed version

## Original Content

> [!quote]- Source Material
> Mastering Atari, Go, Chess and Shogi by Planning with a Learned Model
>
> Julian Schrittwieser, Ioannis Antonoglou, Thomas Hubert, Karen Simonyan, Laurent Sifre, Simon Schmitt, Arthur Guez, Edward Lockhart, Demis Hassabis, Thore Graepel, Timothy Lillicrap, David Silver
> DeepMind, 2020
>
> Abstract: Constructing agents with planning capabilities has long been one of the main challenges in the pursuit of artificial intelligence. Tree-based planning methods have enjoyed huge success in challenging domains, such as chess and Go, where a perfect simulator is available. However, in real-world problems the dynamics governing the environment are often complex and unknown. In this work we present the MuZero algorithm which, by combining a tree-based search with a learned model, achieves superhuman performance in a range of challenging and visually complex domains, without any knowledge of their underlying dynamics. MuZero learns a model that, when applied iteratively, predicts the quantities most directly relevant to planning: the reward, the action-selection policy, and the value function.
>
> [Source PDF](mastering agents.pdf)
