---
created: 2026-04-09
description: Root map of content for the Mycelium knowledge vault
type: moc
status: canon
---

# Vault Map of Content

## Sources

Captured knowledge from external URLs, PDFs, and text bundles.

- **Forecasting / Prediction** — event forecasting, calibration, temporal reasoning
  - [[frozen context snapshots solve temporal contamination in LLM forecasting evaluation by enabling rapid backtesting]]
  - [[RAG-based forecasting systems approach human-level calibration by retrieving and synthesizing evidence before predicting]]
  - [[superforecasters achieve 0.08 Brier scores through reference class reasoning and calibrated probability updates]]
  - [[process reward models that verify each reasoning step outperform outcome-only supervision for mathematical problem solving]]
- **Agent Self-Improvement** — reflection, memory, self-evaluation
  - [[agents that store linguistic feedback in episodic memory improve through verbal reinforcement without weight updates]]
  - [[Self-RAG teaches models to generate inline reflection tokens that decide when to retrieve and whether retrieved content is relevant]]
  - [[modality-specific experts outperform treating time series as text tokens for financial forecasting with interleaved data]]
  - [[historical news context consistently improves financial market impact prediction but compressed summaries outperform raw long contexts]]
  - [[LLMs show strong strategic reasoning about ongoing conflicts but are more reliable on economic constraints than political ambiguity]]
  - [[continual pretraining with data replay matches retraining from scratch at 2.6x less compute on web-scale temporal data]]
- **Sports Analytics / Event Prediction** — soccer, sequence modeling, temporal point processes
  - [[treating soccer match events as a language enables transformer-based next-event prediction and novel metric creation]]
- **Deep Learning / Time Series** — forecasting, neural architectures, foundation models
  - [[pure deep learning outperforms statistical methods for time series forecasting]]
  - [[pretrained time series foundation models extend from univariate to multivariate and covariate-informed forecasting via group attention]]
  - [[decoder-only transformers with lag covariates achieve foundation model zero-shot generalization for probabilistic time series forecasting]]
  - [[periodicity-aware tokenization enables a 1.3M parameter model to outperform 700M parameter time series foundation models]]
  - [[dynamic copula models with nonparametric marginals provide general-purpose probabilistic forecasting for heterogeneous multivariate time series]]
  - [[combining local convolutional and global recurrent encoders captures both short-range and long-range patterns in temporal point processes]]
- **Transformer Efficiency** — attention optimization, GPU memory hierarchy, systems
  - [[IO-aware tiling makes exact attention faster than approximate methods by avoiding HBM bottlenecks]]
- **Generative Models** — diffusion, score matching, image synthesis
  - [[diffusion models generate high quality images by learning to reverse a gradual noising process]]
  - [[running diffusion in a learned latent space makes high-resolution image synthesis accessible on consumer hardware]]
  - [[consistency models enable single-step image generation by learning to map any point on a diffusion trajectory to its origin]]
  - [[non-Markovian diffusion processes enable deterministic sampling that is 10x to 50x faster than DDPMs]]
  - [[2D diffusion models can serve as 3D priors by optimizing a NeRF to produce low-loss renderings from random angles]]
- **Reinforcement Learning** — deep RL, Q-learning, policy learning, game AI
  - [[deep Q-networks learn control policies directly from raw pixels by combining CNNs with experience replay]]
  - [[learning a model that predicts planning-relevant quantities eliminates the need for known environment dynamics]]
  - [[asynchronous parallel actors stabilize deep RL training better than experience replay while running on a single CPU]]
  - [[reinforcement learning can be reduced to sequence modeling by conditioning a transformer on desired returns]]
- **AI Coding Agents** — AGENTS.md, coding workflows, agent efficiency
  - [[AGENTS.md files reduce AI coding agent runtime by 29 percent and output tokens by 17 percent without hurting task completion]]
  - [[coding agents need structured issue trackers not markdown plans because they lose context across sessions and cannot manage nested work]]
  - [[orchestrating 20 to 30 parallel coding agents requires Kubernetes-like infrastructure not just a better IDE]]
  - [[agentic reasoning reframes LLMs from passive sequence generators to autonomous agents that plan act and learn through interaction]]
  - [[agents can learn to consolidate memory as part of reasoning achieving constant memory usage across arbitrarily long horizons]]
  - [[multi-agent coordination degrades performance on sequential tasks by 39 to 70 percent despite helping on parallelizable ones]]
  - [[replacing token-level chain-of-thought with discrete state machine actions improves retrieval while cutting tokens by 74 percent]]
  - [[coding agents will shift from single super-workers to colony workers optimized for orchestration and coordination]]
- **Harness Engineering / Operational Practice** — specs, memory, skills, role separation
  - [[harness engineering is the discipline of building operational infrastructure that keeps long-running agent sessions alive and productive]]
  - [[reusable prompt skill libraries standardize agent workflows across sessions and prevent re-invention of solved patterns]]
  - [[role-separated agent pipelines with human gates at each handoff produce more reliable output than monolithic autonomous agents]]
- **Generalist Agents** — multi-task, multi-modal, unified architectures
  - [[a single transformer with one set of weights can play games caption images chat and control robots by treating all modalities as tokens]]
- **Multimodal / Vision-Language** — VLMs, few-shot learning, cross-modal bridging
  - [[bridging frozen vision and language models enables few-shot learning on multimodal tasks without fine-tuning]]
- **Self-Supervised Learning / World Models** — JEPA, video prediction, physical understanding
  - [[self-supervised video prediction in latent space yields world models that transfer to zero-shot robot planning]]
  - [[isotropic Gaussian embeddings provably minimize downstream risk making JEPA training heuristic-free]]
  - [[learning a world model and planning in imagination masters diverse domains with a single fixed configuration]]
  - [[world models learn compressed representations of environment dynamics enabling planning and prediction without direct interaction]]
- **Model Efficiency / Compression** — distillation, lightweight models, attention alternatives
  - [[knowledge distillation compresses large model capabilities into smaller ones by training on soft probability distributions]]
  - [[DeltaNet uses delta rule updates to create linear attention with fast associative memory that improves with sequence length]]
- **LLM Reasoning** — chain-of-thought, emergent reasoning, RL for language models
  - [[pure reinforcement learning without human demonstrations produces superior reasoning in LLMs]]
  - [[hierarchical recurrence at two timescales achieves deep reasoning that flat transformers and chain-of-thought cannot]]
  - [[teaching LLMs to internalize search processes as linearized reasoning traces enables System 2 thinking without external search]]
  - [[LLMs consistently resist incorporating external feedback even when it is near-perfect and they claim to understand it]]
- **Philosophy of Science / Complex Systems** — emergence, reductionism, ontology
  - [[emergence should be classified by the structure of maps between micro and macro theories not by subjective novelty]]
- **Deep Learning Theory** — kernels, random features, interpretability, representation alignment
  - [[deep networks converge to deterministic kernels independent of initialization because weight covariances not individual weights are the learned quantities]]
- **Speech / Audio** — deepfake detection, speech synthesis, anti-spoofing
  - [[few-shot prototypical networks adapt deepfake speech detectors to new synthesis methods with as few as 10 samples]]
- **Robustness / Generalization** — OOD, causal invariance, distribution shift
  - [[progressive multi-step causal inference outperforms single-step methods for out-of-distribution generalization on graphs]]
- **Training Strategies / Optimization** — curriculum learning, pre-training, continuation methods
  - [[curriculum learning improves generalization by acting as a continuation method on non-convex objectives]]

## Claims

Atomic, falsifiable assertions extracted from sources.

## Concepts

Definitions, terms, and entities.

## Questions

Unresolved questions and uncertainties.

## Projects

Project-specific knowledge collections.
